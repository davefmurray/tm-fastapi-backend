"""
Dashboard Endpoints

Custom dashboard with accurate metric calculations from raw TM data.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    start: Optional[str] = Query(None, description="Start date (ISO 8601)"),
    end: Optional[str] = Query(None, description="End date (ISO 8601)"),
    timezone: str = Query("America/New_York", description="Timezone")
):
    """
    Get dashboard summary metrics for a date range

    Returns TODAY's data if start/end not provided.
    Uses TM's aggregate endpoint for speed.
    """
    tm = get_tm_client()

    # Ensure token is loaded before accessing shop_id
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    # Default to today if not provided
    if not start or not end:
        from datetime import timezone as tz, timedelta
        # Get timezone offset
        offset_hours = -5  # EST (adjust based on timezone param)
        offset = timedelta(hours=offset_hours)
        tzinfo = tz(offset)

        today = datetime.now(tzinfo)
        start = today.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end = today.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

    params = {
        "viewType": "JOBBOARDPOSTED",
        "metric": "SALES",
        "shopIds": shop_id,
        "start": start,
        "end": end,
        "timezone": timezone,
        "useCustomRoLabel": "true"
    }

    try:
        result = await tm.get("/api/reporting/shop-dashboard/aggregate/summary", params)
        return {
            "sold_amount": result.get("sold", 0),
            "posted_amount": result.get("posted", 0),
            "pending_amount": result.get("pending", 0),
            "declined_amount": result.get("declined", 0),
            "sold_job_count": result.get("soldJobCount", 0),
            "posted_job_count": result.get("postedJobCount", 0),
            "pending_job_count": result.get("pendingJobCount", 0),
            "declined_job_count": result.get("declinedJobCount", 0),
            "close_ratio": result.get("closeRatio", 0),
            "average_ro": result.get("averageRo", 0),
            "car_count": result.get("carCount", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breakdown")
async def get_dashboard_breakdown(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    timezone: str = Query("America/New_York")
):
    """
    Get dashboard breakdown by RO status/label

    Returns breakdown for each RO custom label.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    # Default to today
    if not start or not end:
        from datetime import timezone as tz, timedelta
        offset_hours = -5  # EST
        offset = timedelta(hours=offset_hours)
        tzinfo = tz(offset)

        today = datetime.now(tzinfo)
        start = today.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end = today.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

    params = {
        "viewType": "JOBBOARDPOSTED",
        "metric": "SALES",
        "shopIds": shop_id,
        "start": start,
        "end": end,
        "timezone": timezone,
        "useCustomRoLabel": "true",
        "sortBy": "REPAIR_ORDER_CUSTOM_LABEL",
        "sortOrder": "DESC",
        "size": "1000"
    }

    try:
        result = await tm.get("/api/reporting/shop-dashboard/aggregate", params)
        return result.get("content", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accurate-today")
async def get_accurate_dashboard():
    """
    Get ACCURATE dashboard metrics by pulling raw data

    Calculates metrics from source data (not TM aggregates).
    Use this for accurate sales tracking.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get all posted ROs
        posted_ros = await tm.get(
            f"/api/shop/{shop_id}/job-board-group-by",
            {"board": "POSTED", "groupBy": "NONE"}
        )

        # Filter to today
        today = datetime.now().date()
        today_posted = [
            ro for ro in posted_ros
            if ro.get("postedDate") and
            datetime.fromisoformat(ro["postedDate"].replace("Z", "+00:00")).date() == today
        ]

        # Get detailed estimates for accurate totals
        total_sales = 0
        total_paid = 0

        for ro in today_posted:
            # Get estimate for accurate total
            estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")
            total_sales += estimate.get("total", 0)
            total_paid += ro.get("amountPaid", 0)

        return {
            "posted_count": len(today_posted),
            "total_sales": total_sales,
            "total_paid": total_paid,
            "total_ar": total_sales - total_paid,
            "average_ticket": total_sales / len(today_posted) if today_posted else 0,
            "ros": today_posted,
            "source": "ACCURATE_RAW_DATA",
            "calculated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accurate-authorized")
async def get_accurate_authorized_metrics(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Get ACCURATE metrics based on AUTHORIZED sales only

    Calculates from raw data:
    - Sales (authorized jobs total)
    - GP$ (gross profit dollars)
    - GP% (gross profit percentage)
    - ARO (average repair order)
    - Car Count (ROs created in date range)

    - **start**: Start date (YYYY-MM-DD)
    - **end**: End date (YYYY-MM-DD)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get all active ROs
        active_ros = await tm.get(
            f"/api/shop/{shop_id}/job-board-group-by",
            {"board": "ACTIVE", "groupBy": "NONE"}
        )

        # Get all posted ROs
        posted_ros = await tm.get(
            f"/api/shop/{shop_id}/job-board-group-by",
            {"board": "POSTED", "groupBy": "NONE"}
        )

        all_ros = active_ros + posted_ros

        # Filter ROs created in date range (for car count)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ros_in_range = []
        for ro in all_ros:
            if ro.get("createdDate"):
                created_date = datetime.fromisoformat(ro["createdDate"].replace("Z", "+00:00")).date()
                if start_date <= created_date <= end_date:
                    ros_in_range.append(ro)

        # Get estimate and profit for each RO
        total_sales = 0
        total_cost = 0
        ro_count = len(ros_in_range)

        for ro in ros_in_range:
            try:
                # Get estimate
                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")

                # Get profit breakdown
                profit = await tm.get(f"/api/repair-order/{ro['id']}/profit/labor")

                # Sum only AUTHORIZED jobs
                for job in estimate.get("jobs", []):
                    if job.get("authorized") == True:
                        total_sales += job.get("total", 0)

                # Total cost from profit breakdown
                total_cost += profit.get("totalCost", 0)

            except:
                # Skip ROs with errors
                continue

        # Calculate metrics
        gp_dollars = total_sales - total_cost
        gp_percentage = (gp_dollars / total_sales * 100) if total_sales > 0 else 0
        aro = (total_sales / ro_count) if ro_count > 0 else 0

        return {
            "date_range": {
                "start": start,
                "end": end
            },
            "sales": round(total_sales / 100, 2),          # Convert to dollars
            "gp_dollars": round(gp_dollars / 100, 2),
            "gp_percentage": round(gp_percentage, 2),
            "aro": round(aro / 100, 2),
            "car_count": ro_count,
            "source": "AUTHORIZED_JOBS_ONLY",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
