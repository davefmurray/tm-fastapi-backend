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
from app.sync.snapshot_builder import get_snapshot_builder
from app.sync.metrics_aggregator import get_metrics_aggregator

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


# =============================================================================
# SNAPSHOT AND METRICS ENDPOINTS
# =============================================================================

@router.post("/snapshots/build")
async def build_ro_snapshots(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    days_back: int = Query(default=3, ge=1, le=365, description="Days back to build snapshots"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)")
):
    """
    Build RO snapshots for repair orders with posted_date or completed_date in the date range.

    This builds ro_snapshots from repair_orders and their line items.
    Snapshots capture point-in-time metrics for each RO.

    The snapshot key (shop_id, repair_order_id, snapshot_date, snapshot_trigger)
    is respected - repeated runs update existing snapshots (idempotent).

    Parameters:
    - shop_id: TM shop ID
    - days_back: Days back from today (ignored if dates provided)
    - start_date: Optional explicit start date (YYYY-MM-DD)
    - end_date: Optional explicit end date (YYYY-MM-DD)
    """
    try:
        builder = get_snapshot_builder()
        result = builder.build_snapshots_for_period(
            shop_id=shop_id,
            days_back=days_back,
            start_date=start_date,
            end_date=end_date
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Build failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Snapshot build error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Build error: {str(e)}")


@router.post("/metrics/daily/rebuild")
async def rebuild_daily_metrics(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Rebuild daily_shop_metrics from ro_snapshots for a date range.

    This aggregates ro_snapshots into daily_shop_metrics.
    Metrics are unique on (shop_id, metric_date) - safe to re-run.

    IMPORTANT: Run /snapshots/build first to ensure ro_snapshots exist.

    Parameters:
    - shop_id: TM shop ID
    - start_date: Start date (YYYY-MM-DD)
    - end_date: End date (YYYY-MM-DD)
    """
    try:
        aggregator = get_metrics_aggregator()
        result = aggregator.rebuild_daily_metrics(
            shop_id=shop_id,
            start_date=start_date,
            end_date=end_date
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Rebuild failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Metrics rebuild error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Rebuild error: {str(e)}")


@router.get("/metrics/daily")
async def get_daily_metrics(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Get daily_shop_metrics for a date range.

    Returns aggregated daily metrics including:
    - authorized_revenue, authorized_cost, authorized_profit, authorized_gp_percent
    - Category breakdowns (parts, labor, sublet, fees, tax)
    - Averages (avg_ro_value, avg_ro_profit, gp_per_labor_hour)
    - Potential metrics and authorization_rate

    Parameters:
    - shop_id: TM shop ID
    - start_date: Start date (YYYY-MM-DD)
    - end_date: End date (YYYY-MM-DD)
    """
    try:
        aggregator = get_metrics_aggregator()
        metrics = aggregator.get_daily_metrics(
            shop_id=shop_id,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "status": "ok",
            "shop_id": shop_id,
            "date_range": f"{start_date} to {end_date}",
            "count": len(metrics),
            "metrics": metrics
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Get metrics error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


# =============================================================================
# DEBUG ENDPOINT - Check raw TM job-board response
# =============================================================================

@router.get("/debug/job-board")
async def debug_job_board(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    board: str = Query(default="POSTED", description="Board: ACTIVE, POSTED, or COMPLETE"),
    page: int = Query(default=0, ge=0, le=100, description="Page number")
):
    """
    DEBUG: Fetch raw job-board data from TM to diagnose sync issues.
    Shows exactly what TM returns without any filtering.
    """
    from app.sync.sync_base import SyncBase

    sync = SyncBase()

    try:
        ros = await sync.tm.get(
            f"/api/shop/{shop_id}/job-board-group-by",
            params={
                "view": "list",
                "board": board,
                "page": page,
                "groupBy": "NONE"
            }
        )

        if not isinstance(ros, list):
            ros = ros.get("content", []) if isinstance(ros, dict) else []

        # Extract key date fields from each RO
        ro_summary = []
        for ro in ros:
            ro_summary.append({
                "id": ro.get("id"),
                "roNumber": ro.get("roNumber"),
                "status": ro.get("repairOrderStatus", {}).get("statusCode") if ro.get("repairOrderStatus") else None,
                "createdDate": ro.get("createdDate"),
                "updatedDate": ro.get("updatedDate"),
                "postedDate": ro.get("postedDate"),
                "completedDate": ro.get("completedDate"),
            })

        return {
            "shop_id": shop_id,
            "board": board,
            "page": page,
            "count": len(ros),
            "ros": ro_summary
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Debug job-board error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")


@router.get("/debug/dashboard-aggregate")
async def debug_dashboard_aggregate(
    shop_id: int = Query(default=DEFAULT_SHOP_ID, description="TM Shop ID"),
    days_back: int = Query(default=30, ge=1, le=365, description="Days back")
):
    """
    DEBUG: Check TM dashboard aggregate to see reported car count for date range.
    This helps verify how many ROs TM says exist vs what job-board returns.
    """
    from app.sync.sync_base import SyncBase
    from datetime import datetime, timedelta

    sync = SyncBase()

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Format dates as TM expects
        start_str = start_date.strftime("%Y-%m-%dT00:00:00.000-05:00")
        end_str = end_date.strftime("%Y-%m-%dT23:59:59.999-05:00")

        # Query TM dashboard for POSTED board aggregate
        result = await sync.tm.get(
            "/api/reporting/shop-dashboard/aggregate/summary",
            params={
                "viewType": "JOBBOARDPOSTED",
                "metric": "SALES",
                "shopIds": str(shop_id),
                "start": start_str,
                "end": end_str,
                "timezone": "America/New_York",
                "useCustomRoLabel": "true"
            }
        )

        return {
            "shop_id": shop_id,
            "days_back": days_back,
            "date_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "tm_dashboard_response": result
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Debug dashboard error: {e}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")
