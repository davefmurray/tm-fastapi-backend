"""
Employee Sync Module

Syncs employees from Tekmetric to warehouse.
Now fetches FULL employee details including hourlyRate, salary, payType.
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone

from app.sync.sync_base import SyncBase


async def sync_employees(
    tm_shop_id: int,
    store_raw: bool = False
) -> Dict:
    """
    Sync all employees for a shop with FULL details.

    Two-phase sync:
    1. Get employee list from /employees-lite (1 API call)
    2. Get full details from /employee/{id} for each (N API calls)

    This gives us hourlyRate, salary, payType which -lite doesn't return.

    Args:
        tm_shop_id: Tekmetric shop ID
        store_raw: Store raw API responses for debugging

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
            sync_type="full",
            entity_type="employees",
            metadata={"tm_shop_id": tm_shop_id}
        )

        # Phase 1: Get employee list from -lite endpoint
        # This returns both ACTIVE and DEACTIVATED employees (important for historical ROs!)
        employees_lite = await sync.tm.get(
            f"/api/shop/{tm_shop_id}/employees-lite",
            params={"status": "ALL", "size": 500}
        )

        if not isinstance(employees_lite, list):
            employees_lite = employees_lite.get("content", []) if isinstance(employees_lite, dict) else []

        sync.stats.fetched = len(employees_lite)

        # Store raw payload if debugging
        await sync.store_payload(
            endpoint=f"/api/shop/{tm_shop_id}/employees-lite",
            response={"count": len(employees_lite), "sample": employees_lite[:3]}
        )

        # Phase 2: Fetch full details for each employee
        for i, emp_lite in enumerate(employees_lite):
            emp_id = emp_lite.get("id")
            if not emp_id:
                sync.stats.skipped += 1
                continue

            try:
                # Fetch full employee details (includes hourlyRate, salary, payType)
                emp_full = await sync.tm.get(f"/api/shop/{tm_shop_id}/employee/{emp_id}")

                # Merge lite and full data (full takes precedence)
                emp_data = {**emp_lite, **emp_full}

                # Upsert to warehouse
                emp_uuid, is_new = await sync.warehouse.upsert_employee(shop_uuid, emp_data)

                if is_new:
                    sync.stats.created += 1
                else:
                    sync.stats.updated += 1

            except Exception as e:
                # If individual fetch fails, fall back to lite data
                error_msg = str(e)
                if "404" in error_msg:
                    # Employee might be deleted - use lite data
                    try:
                        emp_uuid, is_new = await sync.warehouse.upsert_employee(shop_uuid, emp_lite)
                        if is_new:
                            sync.stats.created += 1
                        else:
                            sync.stats.updated += 1
                    except Exception as e2:
                        sync.stats.add_error("employee", emp_id, str(e2))
                        sync.stats.skipped += 1
                else:
                    sync.stats.add_error("employee", emp_id, error_msg)
                    sync.stats.skipped += 1

        # Update cursor
        await sync.update_cursor(
            entity_type="employees",
            last_tm_updated=datetime.now(timezone.utc)
        )

        # Complete sync
        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "entity_type": "employees",
            "fetched": sync.stats.fetched,
            "created": sync.stats.created,
            "updated": sync.stats.updated,
            "skipped": sync.stats.skipped,
            "errors": len(sync.stats.errors),
            "api_calls": 1 + sync.stats.fetched  # 1 for lite + N for full details
        }

    except Exception as e:
        await sync.fail_sync(str(e))
        return {
            "status": "failed",
            "shop_id": tm_shop_id,
            "entity_type": "employees",
            "error": str(e)
        }
