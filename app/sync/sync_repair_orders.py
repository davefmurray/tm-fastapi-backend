"""
Repair Order Sync Module

The main sync module that orchestrates:
- RO discovery via job-board endpoint
- Full RO sync with estimate data
- Profit/labor data for GP% calculations
- Jobs with all line items (parts, labor, sublets, fees)
- Customer and vehicle resolution
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta

from app.sync.sync_base import SyncBase
from app.sync.sync_customers import sync_customer_by_id
from app.sync.sync_vehicles import sync_vehicle_by_id


async def sync_repair_orders(
    tm_shop_id: int,
    days_back: int = 3,
    board: str = "POSTED",
    store_raw: bool = False,
    limit: Optional[int] = None
) -> Dict:
    """
    Sync repair orders for a shop.

    Args:
        tm_shop_id: Tekmetric shop ID
        days_back: How many days back to sync
                   - POSTED board: filters by postedDate (historical invoices)
                   - ACTIVE board: filters by updatedDate (WIP)
        board: Which board to sync: ACTIVE, POSTED, or ALL
        store_raw: Store raw API responses for debugging
        limit: Max number of ROs to sync (for testing)

    Returns:
        Dict with sync results
    """
    sync = SyncBase()
    sync.store_raw_payloads = store_raw

    try:
        # Initialize shop
        shop_uuid = await sync.init_shop(tm_shop_id)

        # Start sync log
        await sync.start_sync(
            sync_type="incremental",
            entity_type="repair_orders",
            metadata={
                "tm_shop_id": tm_shop_id,
                "days_back": days_back,
                "board": board,
                "limit": limit
            }
        )

        # Discover ROs from job board
        ros_to_sync = await _discover_ros(sync, tm_shop_id, board, days_back)

        if limit:
            ros_to_sync = ros_to_sync[:limit]

        sync.stats.fetched = len(ros_to_sync)

        # Track totals for child entities
        jobs_created = 0
        jobs_updated = 0
        parts_count = 0
        labor_count = 0
        sublets_count = 0
        fees_count = 0

        # Process each RO
        for ro_summary in ros_to_sync:
            try:
                tm_ro_id = ro_summary.get("id")
                if not tm_ro_id:
                    sync.stats.skipped += 1
                    continue

                # CRITICAL: Fetch FULL RO data - job-board only returns summary without customerId/vehicleId!
                ro_data = await sync.tm.get(f"/api/shop/{tm_shop_id}/repair-order/{tm_ro_id}")
                if not ro_data:
                    sync.stats.add_error("fetch_ro", tm_ro_id, "RO not found")
                    sync.stats.skipped += 1
                    continue

                result = await _sync_single_ro(sync, shop_uuid, tm_shop_id, ro_data)

                if result["status"] == "created":
                    sync.stats.created += 1
                elif result["status"] == "updated":
                    sync.stats.updated += 1
                else:
                    sync.stats.skipped += 1

                # Accumulate child entity counts
                jobs_created += result.get("jobs_created", 0)
                jobs_updated += result.get("jobs_updated", 0)
                parts_count += result.get("parts", 0)
                labor_count += result.get("labor", 0)
                sublets_count += result.get("sublets", 0)
                fees_count += result.get("fees", 0)

            except Exception as e:
                sync.stats.add_error("repair_order", tm_ro_id, str(e))
                sync.stats.skipped += 1

        # Update cursor with latest updatedDate seen
        if ros_to_sync:
            latest_updated = max(
                datetime.fromisoformat(ro.get("updatedDate", "2000-01-01T00:00:00Z").replace("Z", "+00:00"))
                for ro in ros_to_sync
                if ro.get("updatedDate")
            )
            await sync.update_cursor(
                entity_type="repair_orders",
                last_tm_updated=latest_updated,
                cursor_data={"board": board, "days_back": days_back}
            )

        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "entity_type": "repair_orders",
            "board": board,
            "days_back": days_back,
            "fetched": sync.stats.fetched,
            "created": sync.stats.created,
            "updated": sync.stats.updated,
            "skipped": sync.stats.skipped,
            "errors": len(sync.stats.errors),
            "child_entities": {
                "jobs_created": jobs_created,
                "jobs_updated": jobs_updated,
                "parts": parts_count,
                "labor": labor_count,
                "sublets": sublets_count,
                "fees": fees_count
            }
        }

    except Exception as e:
        await sync.fail_sync(str(e))
        return {
            "status": "failed",
            "shop_id": tm_shop_id,
            "entity_type": "repair_orders",
            "error": str(e)
        }


async def _discover_ros(
    sync: SyncBase,
    tm_shop_id: int,
    board: str,
    days_back: int
) -> List[Dict]:
    """
    Discover ROs to sync using job-board endpoint.

    PAGINATION: Iterates through all pages until empty response.

    DATE FILTERING:
    - POSTED board: filters by postedDate (for historical backfills)
    - ACTIVE board: filters by updatedDate (for incremental syncs)
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    all_ros = []
    seen_ro_ids = set()  # Dedupe across boards

    # Three boards in TM:
    # - ACTIVE: ESTIMATE, WORKINPROGRESS, COMPLETE (recent WIP)
    # - POSTED: POSTED, ACCRECV (invoiced)
    # - COMPLETE: historically completed ROs
    if board == "ALL":
        boards_to_fetch = ["ACTIVE", "POSTED", "COMPLETE"]
    else:
        boards_to_fetch = [board]

    for b in boards_to_fetch:
        page = 0
        board_ros = []

        try:
            # PAGINATION LOOP: fetch all pages
            while True:
                ros = await sync.tm.get(
                    f"/api/shop/{tm_shop_id}/job-board-group-by",
                    params={
                        "view": "list",
                        "board": b,
                        "page": page,
                        "groupBy": "NONE"
                    }
                )

                if not isinstance(ros, list):
                    ros = ros.get("content", []) if isinstance(ros, dict) else []

                # Empty page = done with this board
                if not ros:
                    break

                board_ros.extend(ros)
                page += 1

                # Safety limit to prevent infinite loops
                if page > 100:
                    break

            # Choose date field based on board type
            # POSTED board = historical invoices, filter by postedDate
            # COMPLETE board = historically completed, filter by completedDate
            # ACTIVE board = WIP, filter by updatedDate
            if b == "POSTED":
                date_field = "postedDate"
            elif b == "COMPLETE":
                date_field = "completedDate"
            else:
                date_field = "updatedDate"

            # Filter by appropriate date field
            for ro in board_ros:
                ro_id = ro.get("id")

                # Dedupe (same RO could appear on multiple boards)
                if ro_id in seen_ro_ids:
                    continue

                date_str = ro.get(date_field) or ro.get("updatedDate")
                if date_str:
                    try:
                        date_val = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        if date_val >= cutoff_date:
                            all_ros.append(ro)
                            seen_ro_ids.add(ro_id)
                    except:
                        # Include if we can't parse date
                        all_ros.append(ro)
                        seen_ro_ids.add(ro_id)
                else:
                    # Include if no date field
                    all_ros.append(ro)
                    seen_ro_ids.add(ro_id)

            # Store raw if debugging
            await sync.store_payload(
                endpoint=f"/api/shop/{tm_shop_id}/job-board-group-by",
                response={"board": b, "pages_fetched": page, "total_ros": len(board_ros)},
                request_params={"board": b}
            )

        except Exception as e:
            sync.stats.add_error("discover_ros", b, str(e))

    return all_ros


async def _discover_ros_via_report(
    sync: SyncBase,
    tm_shop_id: int,
    start_date: str,
    end_date: str,
    page_size: int = 100
) -> List[Dict]:
    """
    Discover ROs using the profit-details-report endpoint.

    This endpoint returns ALL historical ROs within a date range,
    unlike job-board which only returns ~81 active ROs.

    Uses cursor-based pagination with nextKeys parameter.

    Args:
        sync: SyncBase instance
        tm_shop_id: Tekmetric shop ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        page_size: Number of ROs per page (default 100)

    Returns:
        List of RO summary dicts with repairOrderId for full fetch
    """
    all_ros = []
    next_keys = None
    page_count = 0

    # Format dates with timezone for TM API
    # TM expects: 2025-11-01T00:00:00.000-05:00
    start_formatted = f"{start_date}T00:00:00.000-05:00"
    end_formatted = f"{end_date}T23:59:59.999-05:00"

    try:
        while True:
            params = {
                "timezone": "America/New_York",
                "size": page_size,
                "shopIds": str(tm_shop_id),
                "start": start_formatted,
                "end": end_formatted,
                "sortBy": "POSTED_DATE",
                "sortOrder": "DESC"
            }

            # Add cursor for subsequent pages
            if next_keys:
                params["nextKeys"] = next_keys

            response = await sync.tm.get(
                "/api/reporting/profit-details-report",
                params=params
            )

            if not response:
                break

            content = response.get("content", [])
            if not content:
                break

            # Transform to match expected RO format for _sync_single_ro
            for item in content:
                ro_summary = {
                    "id": item.get("repairOrderId"),
                    "roNumber": item.get("repairOrderNumber"),
                    "customerId": item.get("customerId"),
                    "vehicleId": item.get("vehicleId"),
                    "serviceWriterId": item.get("serviceWriterId"),
                    "postedDate": item.get("postedDate"),
                    # Include profit data from report for reference
                    "_reportProfit": {
                        "laborProfit": item.get("laborProfit"),
                        "partsTotalProfit": item.get("partsTotalProfit"),
                        "subletProfit": item.get("subletProfit"),
                        "feesProfit": item.get("feesProfit"),
                        "totalProfit": item.get("totalProfit"),
                        "totalProfitMargin": item.get("totalProfitMargin")
                    }
                }
                all_ros.append(ro_summary)

            page_count += 1

            # Check for more pages
            if not response.get("hasNext"):
                break

            next_keys = response.get("nextKeys")
            if not next_keys:
                break

            # Safety limit
            if page_count > 50:
                break

        # Store discovery summary
        await sync.store_payload(
            endpoint="/api/reporting/profit-details-report",
            response={
                "pages_fetched": page_count,
                "total_ros_discovered": len(all_ros),
                "date_range": f"{start_date} to {end_date}"
            },
            request_params={"start": start_date, "end": end_date}
        )

    except Exception as e:
        sync.stats.add_error("discover_ros_report", None, str(e))

    return all_ros


async def sync_historical_repair_orders(
    tm_shop_id: int,
    start_date: str,
    end_date: str,
    store_raw: bool = False,
    limit: Optional[int] = None
) -> Dict:
    """
    Sync historical repair orders using profit-details-report endpoint.

    This is the preferred method for backfilling historical ROs as it
    discovers ALL posted ROs in a date range (not just active ones).

    Args:
        tm_shop_id: Tekmetric shop ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        store_raw: Store raw API responses for debugging
        limit: Max number of ROs to sync (for testing)

    Returns:
        Dict with sync results
    """
    sync = SyncBase()
    sync.store_raw_payloads = store_raw

    try:
        # Initialize shop
        shop_uuid = await sync.init_shop(tm_shop_id)

        # Start sync log
        await sync.start_sync(
            sync_type="historical",
            entity_type="repair_orders",
            metadata={
                "tm_shop_id": tm_shop_id,
                "start_date": start_date,
                "end_date": end_date,
                "method": "profit-details-report",
                "limit": limit
            }
        )

        # Discover ROs using report endpoint
        ros_discovered = await _discover_ros_via_report(
            sync, tm_shop_id, start_date, end_date
        )

        if limit:
            ros_discovered = ros_discovered[:limit]

        sync.stats.fetched = len(ros_discovered)

        # Track totals
        jobs_created = 0
        jobs_updated = 0
        parts_count = 0
        labor_count = 0
        sublets_count = 0
        fees_count = 0

        # Process each discovered RO
        for ro_summary in ros_discovered:
            tm_ro_id = ro_summary.get("id")
            if not tm_ro_id:
                sync.stats.skipped += 1
                continue

            try:
                # Fetch full RO data from TM
                ro_data = await sync.tm.get(
                    f"/api/shop/{tm_shop_id}/repair-order/{tm_ro_id}"
                )

                if not ro_data:
                    sync.stats.add_error("fetch_ro", tm_ro_id, "RO not found")
                    sync.stats.skipped += 1
                    continue

                # Sync the RO with full data
                result = await _sync_single_ro(sync, shop_uuid, tm_shop_id, ro_data)

                if result["status"] == "created":
                    sync.stats.created += 1
                elif result["status"] == "updated":
                    sync.stats.updated += 1
                else:
                    sync.stats.skipped += 1

                # Accumulate child entity counts
                jobs_created += result.get("jobs_created", 0)
                jobs_updated += result.get("jobs_updated", 0)
                parts_count += result.get("parts", 0)
                labor_count += result.get("labor", 0)
                sublets_count += result.get("sublets", 0)
                fees_count += result.get("fees", 0)

            except Exception as e:
                sync.stats.add_error("repair_order", tm_ro_id, str(e))
                sync.stats.skipped += 1

        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "entity_type": "repair_orders",
            "method": "historical (profit-details-report)",
            "date_range": f"{start_date} to {end_date}",
            "discovered": len(ros_discovered),
            "fetched": sync.stats.fetched,
            "created": sync.stats.created,
            "updated": sync.stats.updated,
            "skipped": sync.stats.skipped,
            "errors": len(sync.stats.errors),
            "child_entities": {
                "jobs_created": jobs_created,
                "jobs_updated": jobs_updated,
                "parts": parts_count,
                "labor": labor_count,
                "sublets": sublets_count,
                "fees": fees_count
            }
        }

    except Exception as e:
        await sync.fail_sync(str(e))
        return {
            "status": "failed",
            "shop_id": tm_shop_id,
            "entity_type": "repair_orders",
            "error": str(e)
        }


async def _sync_single_ro(
    sync: SyncBase,
    shop_uuid: str,
    tm_shop_id: int,
    ro_data: Dict
) -> Dict:
    """
    Sync a single repair order with all related data.

    1. Resolve/create customer
    2. Resolve/create vehicle
    3. Resolve advisor (employee)
    4. Fetch full estimate data
    5. Fetch profit/labor data
    6. Upsert RO with all fields
    7. Sync all jobs and line items
    """
    tm_ro_id = ro_data["id"]
    result = {
        "status": "skipped",
        "jobs_created": 0,
        "jobs_updated": 0,
        "parts": 0,
        "labor": 0,
        "sublets": 0,
        "fees": 0
    }

    # Extract IDs - TM API returns flat IDs from job-board but nested objects from individual RO endpoint
    # Handle both: customerId (flat) or customer.id (nested)
    customer_tm_id = ro_data.get("customerId")
    if not customer_tm_id and ro_data.get("customer"):
        customer_tm_id = ro_data["customer"].get("id")

    vehicle_tm_id = ro_data.get("vehicleId")
    if not vehicle_tm_id and ro_data.get("vehicle"):
        vehicle_tm_id = ro_data["vehicle"].get("id")

    advisor_tm_id = ro_data.get("serviceWriterId")
    if not advisor_tm_id and ro_data.get("serviceWriter"):
        advisor_tm_id = ro_data["serviceWriter"].get("id")

    # Normalize ro_data to have flat IDs for upsert_repair_order
    ro_data["customerId"] = customer_tm_id
    ro_data["vehicleId"] = vehicle_tm_id
    ro_data["serviceWriterId"] = advisor_tm_id

    # 1. Resolve customer
    customer_uuid = None
    if customer_tm_id:
        customer_uuid = await sync.warehouse.get_entity_uuid(
            "customers", shop_uuid, customer_tm_id
        )
        if not customer_uuid:
            customer_uuid = await sync_customer_by_id(sync, customer_tm_id)

    # 2. Resolve vehicle
    vehicle_uuid = None
    if vehicle_tm_id:
        vehicle_uuid = await sync.warehouse.get_entity_uuid(
            "vehicles", shop_uuid, vehicle_tm_id
        )
        if not vehicle_uuid:
            vehicle_uuid = await sync_vehicle_by_id(sync, vehicle_tm_id, customer_uuid)

    # 3. Resolve advisor
    advisor_uuid = None
    if advisor_tm_id:
        advisor_uuid = await sync.warehouse.get_entity_uuid(
            "employees", shop_uuid, advisor_tm_id
        )

    # 4. Fetch full estimate data
    try:
        estimate = await sync.tm.get(f"/api/repair-order/{tm_ro_id}/estimate")
        await sync.store_payload(
            endpoint=f"/api/repair-order/{tm_ro_id}/estimate",
            response=estimate,
            tm_entity_id=tm_ro_id
        )
    except Exception as e:
        sync.stats.add_error("estimate", tm_ro_id, str(e))
        estimate = {"jobs": []}

    # 5. Labor cost calculation now happens in warehouse_client using cached employee hourly_rate
    # This eliminates the need for /profit/labor API calls (33% reduction in API calls per RO)
    profit_data = None  # Labor costs calculated from employees.hourly_rate in upsert_job_labor

    # 6. Upsert RO
    ro_uuid, is_new = await sync.warehouse.upsert_repair_order(
        shop_uuid=shop_uuid,
        tm_data=ro_data,
        customer_uuid=customer_uuid,
        vehicle_uuid=vehicle_uuid,
        advisor_uuid=advisor_uuid,
        profit_data=profit_data
    )

    result["status"] = "created" if is_new else "updated"

    # Update RO with totals from estimate
    if estimate.get("jobs"):
        await sync.warehouse.update_ro_totals(ro_uuid, estimate)

    # 7. Sync jobs and line items
    jobs = estimate.get("jobs", [])
    profit_labor_items = {}

    # Index profit labor items by labor ID for cost lookup
    if profit_data and profit_data.get("labor"):
        for pl in profit_data["labor"]:
            # Try to match by name or index
            if pl.get("laborId"):
                profit_labor_items[pl["laborId"]] = pl

    for job_data in jobs:
        try:
            job_uuid, job_is_new = await sync.warehouse.upsert_job(
                shop_uuid=shop_uuid,
                ro_uuid=ro_uuid,
                tm_ro_id=tm_ro_id,
                tm_data=job_data
            )

            if job_is_new:
                result["jobs_created"] += 1
            else:
                result["jobs_updated"] += 1

            tm_job_id = job_data["id"]

            # Sync parts
            for part in job_data.get("parts", []):
                try:
                    await sync.warehouse.upsert_job_part(
                        shop_uuid=shop_uuid,
                        job_uuid=job_uuid,
                        ro_uuid=ro_uuid,
                        tm_job_id=tm_job_id,
                        tm_ro_id=tm_ro_id,
                        tm_data=part
                    )
                    result["parts"] += 1
                except Exception as e:
                    sync.stats.add_error("part", part.get("id"), str(e))

            # Sync labor
            for labor in job_data.get("labor", []):
                try:
                    # Try to get cost data from profit/labor
                    labor_profit = profit_labor_items.get(labor.get("id"))

                    # Resolve technician
                    tech_uuid = None
                    tech = labor.get("technician", {}) or {}
                    if tech.get("id"):
                        tech_uuid = await sync.warehouse.get_entity_uuid(
                            "employees", shop_uuid, tech["id"]
                        )

                    await sync.warehouse.upsert_job_labor(
                        shop_uuid=shop_uuid,
                        job_uuid=job_uuid,
                        ro_uuid=ro_uuid,
                        tm_job_id=tm_job_id,
                        tm_ro_id=tm_ro_id,
                        tm_data=labor,
                        technician_uuid=tech_uuid,
                        profit_labor_data=labor_profit
                    )
                    result["labor"] += 1
                except Exception as e:
                    sync.stats.add_error("labor", labor.get("id"), str(e))

            # Sync sublets
            for sublet in job_data.get("sublets", []):
                try:
                    await sync.warehouse.upsert_job_sublet(
                        shop_uuid=shop_uuid,
                        job_uuid=job_uuid,
                        ro_uuid=ro_uuid,
                        tm_job_id=tm_job_id,
                        tm_ro_id=tm_ro_id,
                        tm_data=sublet
                    )
                    result["sublets"] += 1
                except Exception as e:
                    sync.stats.add_error("sublet", sublet.get("id"), str(e))

            # Sync fees
            for fee in job_data.get("fees", []):
                try:
                    await sync.warehouse.upsert_job_fee(
                        shop_uuid=shop_uuid,
                        job_uuid=job_uuid,
                        ro_uuid=ro_uuid,
                        tm_job_id=tm_job_id,
                        tm_ro_id=tm_ro_id,
                        tm_data=fee
                    )
                    result["fees"] += 1
                except Exception as e:
                    sync.stats.add_error("fee", None, str(e))

        except Exception as e:
            sync.stats.add_error("job", job_data.get("id"), str(e))

    return result


async def sync_single_repair_order(
    tm_shop_id: int,
    tm_ro_id: int,
    store_raw: bool = False
) -> Dict:
    """
    Sync a single repair order by ID.
    Useful for on-demand sync of specific ROs.
    """
    sync = SyncBase()
    sync.store_raw_payloads = store_raw

    try:
        shop_uuid = await sync.init_shop(tm_shop_id)

        await sync.start_sync(
            sync_type="single",
            entity_type="repair_orders",
            metadata={"tm_shop_id": tm_shop_id, "tm_ro_id": tm_ro_id}
        )

        # Fetch RO from TM
        ro_data = await sync.tm.get(f"/api/shop/{tm_shop_id}/repair-order/{tm_ro_id}")

        if not ro_data:
            await sync.fail_sync(f"RO {tm_ro_id} not found")
            return {"status": "failed", "error": f"RO {tm_ro_id} not found"}

        sync.stats.fetched = 1

        result = await _sync_single_ro(sync, shop_uuid, tm_shop_id, ro_data)

        if result["status"] == "created":
            sync.stats.created = 1
        elif result["status"] == "updated":
            sync.stats.updated = 1

        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "ro_id": tm_ro_id,
            "ro_status": result["status"],
            "child_entities": {
                "jobs_created": result.get("jobs_created", 0),
                "jobs_updated": result.get("jobs_updated", 0),
                "parts": result.get("parts", 0),
                "labor": result.get("labor", 0),
                "sublets": result.get("sublets", 0),
                "fees": result.get("fees", 0)
            }
        }

    except Exception as e:
        await sync.fail_sync(str(e))
        return {
            "status": "failed",
            "shop_id": tm_shop_id,
            "ro_id": tm_ro_id,
            "error": str(e)
        }
