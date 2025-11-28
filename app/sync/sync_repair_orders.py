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
        days_back: How many days back to sync (filters by updatedDate)
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
        for ro_data in ros_to_sync:
            try:
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
                sync.stats.add_error("repair_order", ro_data.get("id"), str(e))
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
    Filters by updatedDate to get recently changed ROs.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    all_ros = []

    boards_to_fetch = ["ACTIVE", "POSTED"] if board == "ALL" else [board]

    for b in boards_to_fetch:
        try:
            # Fetch from job-board endpoint
            ros = await sync.tm.get(
                f"/api/shop/{tm_shop_id}/job-board-group-by",
                params={
                    "view": "list",
                    "board": b,
                    "page": 0,
                    "groupBy": "NONE"
                }
            )

            if not isinstance(ros, list):
                ros = ros.get("content", []) if isinstance(ros, dict) else []

            # Filter by updatedDate
            for ro in ros:
                updated_str = ro.get("updatedDate")
                if updated_str:
                    try:
                        updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                        if updated >= cutoff_date:
                            all_ros.append(ro)
                    except:
                        # Include if we can't parse date
                        all_ros.append(ro)
                else:
                    all_ros.append(ro)

            # Store raw if debugging
            await sync.store_payload(
                endpoint=f"/api/shop/{tm_shop_id}/job-board-group-by",
                response={"board": b, "count": len(ros)},
                request_params={"board": b}
            )

        except Exception as e:
            sync.stats.add_error("discover_ros", b, str(e))

    return all_ros


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

    # 1. Resolve customer
    customer_uuid = None
    if ro_data.get("customerId"):
        customer_uuid = await sync.warehouse.get_entity_uuid(
            "customers", shop_uuid, ro_data["customerId"]
        )
        if not customer_uuid:
            customer_uuid = await sync_customer_by_id(sync, ro_data["customerId"])

    # 2. Resolve vehicle
    vehicle_uuid = None
    if ro_data.get("vehicleId"):
        vehicle_uuid = await sync.warehouse.get_entity_uuid(
            "vehicles", shop_uuid, ro_data["vehicleId"]
        )
        if not vehicle_uuid:
            vehicle_uuid = await sync_vehicle_by_id(sync, ro_data["vehicleId"], customer_uuid)

    # 3. Resolve advisor
    advisor_uuid = None
    if ro_data.get("serviceWriterId"):
        advisor_uuid = await sync.warehouse.get_entity_uuid(
            "employees", shop_uuid, ro_data["serviceWriterId"]
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

    # 5. Fetch profit/labor data for GP% calculations
    profit_data = None
    try:
        profit_data = await sync.tm.get(f"/api/repair-order/{tm_ro_id}/profit/labor")
        await sync.store_payload(
            endpoint=f"/api/repair-order/{tm_ro_id}/profit/labor",
            response=profit_data,
            tm_entity_id=tm_ro_id
        )
    except Exception as e:
        # profit/labor may not be available for all ROs
        sync.stats.add_error("profit_labor", tm_ro_id, str(e))

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
