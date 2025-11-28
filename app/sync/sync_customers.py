"""
Customer Sync Module

Syncs customers from Tekmetric to warehouse.
Called as needed when processing repair orders.
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone

from app.sync.sync_base import SyncBase


async def sync_customer_by_id(
    sync: SyncBase,
    tm_customer_id: int
) -> Optional[str]:
    """
    Sync a single customer by TM ID.
    Returns customer UUID if successful.
    """
    if not sync.shop_uuid:
        return None

    # Check if already exists
    existing_uuid = await sync.warehouse.get_entity_uuid(
        "customers", sync.shop_uuid, tm_customer_id
    )
    if existing_uuid:
        return existing_uuid

    try:
        # Fetch customer from TM
        customer = await sync.tm.get(f"/api/shop/{sync.tm_shop_id}/customer/{tm_customer_id}")

        if not customer:
            return None

        # Store raw if debugging
        await sync.store_payload(
            endpoint=f"/api/shop/{sync.tm_shop_id}/customer/{tm_customer_id}",
            response=customer,
            tm_entity_id=tm_customer_id
        )

        # Upsert customer
        customer_uuid, is_new = await sync.warehouse.upsert_customer(sync.shop_uuid, customer)

        if is_new:
            sync.stats.created += 1
        else:
            sync.stats.updated += 1

        return customer_uuid

    except Exception as e:
        sync.stats.add_error("customer", tm_customer_id, str(e))
        return None


async def sync_customers(
    tm_shop_id: int,
    store_raw: bool = False
) -> Dict:
    """
    Sync all customers for a shop (paginated).

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
            entity_type="customers",
            metadata={"tm_shop_id": tm_shop_id}
        )

        # Fetch customers from TM (paginated)
        page = 0
        page_size = 100
        total_fetched = 0

        while True:
            try:
                response = await sync.tm.get(
                    f"/api/shop/{tm_shop_id}/customer",
                    params={"page": page, "size": page_size}
                )

                if isinstance(response, dict):
                    customers = response.get("content", [])
                    total_pages = response.get("totalPages", 1)
                else:
                    customers = response if isinstance(response, list) else []
                    total_pages = 1

                if not customers:
                    break

                total_fetched += len(customers)
                sync.stats.fetched = total_fetched

                # Process each customer
                for cust in customers:
                    try:
                        cust_uuid, is_new = await sync.warehouse.upsert_customer(shop_uuid, cust)
                        if is_new:
                            sync.stats.created += 1
                        else:
                            sync.stats.updated += 1
                    except Exception as e:
                        sync.stats.add_error("customer", cust.get("id"), str(e))
                        sync.stats.skipped += 1

                page += 1
                if page >= total_pages:
                    break

            except Exception as e:
                sync.stats.add_error("customer_page", page, str(e))
                break

        # Update cursor
        await sync.update_cursor(
            entity_type="customers",
            last_tm_updated=datetime.now(timezone.utc)
        )

        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "entity_type": "customers",
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
            "entity_type": "customers",
            "error": str(e)
        }
