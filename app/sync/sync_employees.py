"""
Employee Sync Module

Syncs employees from Tekmetric to warehouse.
Minimal sync - just enough to resolve technician and advisor IDs.
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone

from app.sync.sync_base import SyncBase


async def sync_employees(
    tm_shop_id: int,
    store_raw: bool = False
) -> Dict:
    """
    Sync all employees for a shop.

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
            sync_type="incremental",
            entity_type="employees",
            metadata={"tm_shop_id": tm_shop_id}
        )

        # Fetch employees from TM
        # TM endpoint: GET /api/shop/{shopId}/employee
        employees = await sync.tm.get(f"/api/shop/{tm_shop_id}/employee")

        if not isinstance(employees, list):
            employees = employees.get("content", []) if isinstance(employees, dict) else []

        sync.stats.fetched = len(employees)

        # Store raw payload if debugging
        await sync.store_payload(
            endpoint=f"/api/shop/{tm_shop_id}/employee",
            response={"employees": employees[:5]} if len(employees) > 5 else {"employees": employees}
        )

        # Process each employee
        for emp in employees:
            try:
                emp_uuid, is_new = await sync.warehouse.upsert_employee(shop_uuid, emp)

                if is_new:
                    sync.stats.created += 1
                else:
                    sync.stats.updated += 1

            except Exception as e:
                sync.stats.add_error("employee", emp.get("id"), str(e))
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
            "errors": len(sync.stats.errors)
        }

    except Exception as e:
        await sync.fail_sync(str(e))
        return {
            "status": "failed",
            "shop_id": tm_shop_id,
            "entity_type": "employees",
            "error": str(e)
        }
