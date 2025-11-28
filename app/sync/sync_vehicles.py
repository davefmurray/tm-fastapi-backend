"""
Vehicle Sync Module

Syncs vehicles from Tekmetric to warehouse.
Called as needed when processing repair orders.
"""

from typing import Optional, Dict
from datetime import datetime, timezone

from app.sync.sync_base import SyncBase


async def sync_vehicle_by_id(
    sync: SyncBase,
    tm_vehicle_id: int,
    customer_uuid: Optional[str] = None
) -> Optional[str]:
    """
    Sync a single vehicle by TM ID.
    Returns vehicle UUID if successful.
    """
    if not sync.shop_uuid:
        return None

    # Check if already exists
    existing_uuid = await sync.warehouse.get_entity_uuid(
        "vehicles", sync.shop_uuid, tm_vehicle_id
    )
    if existing_uuid:
        return existing_uuid

    try:
        # Fetch vehicle from TM
        vehicle = await sync.tm.get(f"/api/shop/{sync.tm_shop_id}/vehicle/{tm_vehicle_id}")

        if not vehicle:
            return None

        # Store raw if debugging
        await sync.store_payload(
            endpoint=f"/api/shop/{sync.tm_shop_id}/vehicle/{tm_vehicle_id}",
            response=vehicle,
            tm_entity_id=tm_vehicle_id
        )

        # Upsert vehicle
        vehicle_uuid, is_new = await sync.warehouse.upsert_vehicle(
            sync.shop_uuid,
            vehicle,
            customer_uuid=customer_uuid
        )

        if is_new:
            sync.stats.created += 1
        else:
            sync.stats.updated += 1

        return vehicle_uuid

    except Exception as e:
        sync.stats.add_error("vehicle", tm_vehicle_id, str(e))
        return None


async def sync_vehicles(
    tm_shop_id: int,
    store_raw: bool = False
) -> Dict:
    """
    Sync all vehicles for a shop (paginated).

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
            entity_type="vehicles",
            metadata={"tm_shop_id": tm_shop_id}
        )

        # Fetch vehicles from TM (paginated)
        page = 0
        page_size = 100
        total_fetched = 0

        while True:
            try:
                response = await sync.tm.get(
                    f"/api/shop/{tm_shop_id}/vehicle",
                    params={"page": page, "size": page_size}
                )

                if isinstance(response, dict):
                    vehicles = response.get("content", [])
                    total_pages = response.get("totalPages", 1)
                else:
                    vehicles = response if isinstance(response, list) else []
                    total_pages = 1

                if not vehicles:
                    break

                total_fetched += len(vehicles)
                sync.stats.fetched = total_fetched

                # Process each vehicle
                for veh in vehicles:
                    try:
                        # Try to resolve customer UUID
                        customer_uuid = None
                        if veh.get("customerId"):
                            customer_uuid = await sync.warehouse.get_entity_uuid(
                                "customers", shop_uuid, veh["customerId"]
                            )

                        veh_uuid, is_new = await sync.warehouse.upsert_vehicle(
                            shop_uuid, veh, customer_uuid=customer_uuid
                        )
                        if is_new:
                            sync.stats.created += 1
                        else:
                            sync.stats.updated += 1
                    except Exception as e:
                        sync.stats.add_error("vehicle", veh.get("id"), str(e))
                        sync.stats.skipped += 1

                page += 1
                if page >= total_pages:
                    break

            except Exception as e:
                sync.stats.add_error("vehicle_page", page, str(e))
                break

        # Update cursor
        await sync.update_cursor(
            entity_type="vehicles",
            last_tm_updated=datetime.now(timezone.utc)
        )

        await sync.complete_sync()

        return {
            "status": "completed",
            "shop_id": tm_shop_id,
            "entity_type": "vehicles",
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
            "entity_type": "vehicles",
            "error": str(e)
        }
