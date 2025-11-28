"""
Sync Router

FastAPI endpoints for triggering warehouse sync operations.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import os
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.sync import (
    sync_employees,
    sync_customers,
    sync_vehicles,
    sync_repair_orders,
)
from app.sync.sync_repair_orders import sync_single_repair_order

router = APIRouter()

# Default shop ID from environment
DEFAULT_SHOP_ID = int(os.getenv("TM_SHOP_ID", "6212"))


@router.get("/status")
async def sync_status():
    """
    Check sync module status and configuration.
    """
    sync_enabled = os.getenv("SYNC_ENABLED", "true").lower() == "true"
    ro_interval = int(os.getenv("RO_SYNC_INTERVAL_MINUTES", "10"))
    emp_hour = int(os.getenv("EMPLOYEE_SYNC_HOUR", "6"))

    return {
        "status": "ok",
        "default_shop_id": DEFAULT_SHOP_ID,
        "supabase_url": os.getenv("SUPABASE_URL", "NOT SET"),
        "has_service_key": bool(os.getenv("SUPABASE_SERVICE_KEY")),
        "has_anon_key": bool(os.getenv("SUPABASE_KEY")),
        "tm_base_url": os.getenv("TM_BASE_URL", "NOT SET"),
        "tm_shop_id": os.getenv("TM_SHOP_ID", "NOT SET"),
        "scheduler": {
            "enabled": sync_enabled,
            "ro_sync_interval_minutes": ro_interval,
            "employee_sync_hour_utc": emp_hour,
        }
    }


@router.get("/employees")
async def trigger_employee_sync(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    store_raw: bool = Query(default=False, description="Store raw API responses for debugging")
):
    """
    Sync all employees for a shop.

    This syncs technicians and advisors needed for RO processing.
    Run this before syncing repair orders.
    """
    try:
        logger.info(f"Starting employee sync for shop_id={shop_id}")
        result = await sync_employees(shop_id, store_raw=store_raw)
        logger.info(f"Employee sync result: {result.get('status')}")

        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Employee sync error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}\n{error_trace}")


@router.get("/customers")
async def trigger_customer_sync(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    store_raw: bool = Query(default=False, description="Store raw API responses for debugging")
):
    """
    Sync all customers for a shop.

    Note: Customers are also synced on-demand during RO sync.
    This endpoint syncs ALL customers which may take time.
    """
    result = await sync_customers(shop_id, store_raw=store_raw)

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

    return result


@router.get("/vehicles")
async def trigger_vehicle_sync(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    store_raw: bool = Query(default=False, description="Store raw API responses for debugging")
):
    """
    Sync all vehicles for a shop.

    Note: Vehicles are also synced on-demand during RO sync.
    This endpoint syncs ALL vehicles which may take time.
    """
    result = await sync_vehicles(shop_id, store_raw=store_raw)

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

    return result


@router.get("/repair-orders")
async def trigger_ro_sync(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    days_back: int = Query(default=3, ge=1, le=365, description="Days back to sync"),
    board: str = Query(default="POSTED", description="Board to sync: ACTIVE, POSTED, or ALL"),
    limit: Optional[int] = Query(default=None, ge=1, le=1000, description="Max ROs to sync (for testing)"),
    store_raw: bool = Query(default=False, description="Store raw API responses for debugging")
):
    """
    Sync repair orders for a shop.

    This is the main sync endpoint that:
    1. Discovers ROs from the job board
    2. Fetches full estimate data for each RO
    3. Fetches profit/labor data for GP% calculations
    4. Syncs all jobs and line items (parts, labor, sublets, fees)
    5. Resolves customers, vehicles, and employees on-demand

    Recommended workflow:
    1. First run: `/sync/employees` to populate technicians and advisors
    2. Then run: `/sync/repair-orders?days_back=3&board=POSTED`

    Parameters:
    - days_back: How many days back to sync (filters by updatedDate)
    - board: ACTIVE (estimates/WIP), POSTED (invoiced), or ALL
    - limit: Cap on number of ROs for testing
    - store_raw: Store API responses in tm_raw_payloads for debugging
    """
    try:
        if board not in ["ACTIVE", "POSTED", "ALL"]:
            raise HTTPException(status_code=400, detail="board must be ACTIVE, POSTED, or ALL")

        logger.info(f"Starting RO sync for shop_id={shop_id}, days_back={days_back}, board={board}")
        result = await sync_repair_orders(
            tm_shop_id=shop_id,
            days_back=days_back,
            board=board,
            store_raw=store_raw,
            limit=limit
        )
        logger.info(f"RO sync result: {result.get('status')}")

        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"RO sync error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}\n{error_trace}")


@router.get("/repair-orders/{ro_id}")
async def trigger_single_ro_sync(
    ro_id: int,
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    store_raw: bool = Query(default=False, description="Store raw API responses for debugging")
):
    """
    Sync a single repair order by ID.

    Useful for:
    - On-demand sync of specific ROs
    - Testing sync logic
    - Debugging issues with specific ROs
    """
    result = await sync_single_repair_order(
        tm_shop_id=shop_id,
        tm_ro_id=ro_id,
        store_raw=store_raw
    )

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

    return result


@router.get("/full-backfill")
async def trigger_full_backfill(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    days_back: int = Query(default=30, ge=1, le=365, description="Days back to sync"),
    store_raw: bool = Query(default=False, description="Store raw API responses")
):
    """
    Run a full backfill sync for a shop.

    This runs:
    1. Employee sync
    2. Repair order sync (ALL boards)

    WARNING: This can take a while for large shops.
    Start with days_back=7 and increase if needed.
    """
    results = {}

    # 1. Sync employees first
    results["employees"] = await sync_employees(shop_id, store_raw=store_raw)

    if results["employees"]["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Employee sync failed: {results['employees'].get('error')}")

    # 2. Sync repair orders (ALL boards)
    results["repair_orders"] = await sync_repair_orders(
        tm_shop_id=shop_id,
        days_back=days_back,
        board="ALL",
        store_raw=store_raw
    )

    if results["repair_orders"]["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"RO sync failed: {results['repair_orders'].get('error')}")

    return {
        "status": "completed",
        "shop_id": shop_id,
        "days_back": days_back,
        "results": results
    }
