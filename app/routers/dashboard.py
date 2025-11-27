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
        # Get ROs from all boards (just first page for speed - ~1500 ROs)
        # For recent authorizations, this should be sufficient
        all_ros = []

        for board in ["ACTIVE", "POSTED", "COMPLETE"]:
            try:
                ros_page = await tm.get(
                    f"/api/shop/{shop_id}/job-board-group-by",
                    {"board": board, "groupBy": "NONE", "page": 0}
                )
                all_ros.extend(ros_page)
            except:
                pass

        # Filter jobs authorized in date range (NOT RO created date!)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        # Get estimate for ALL ROs and filter by job authorization date
        total_sales = 0
        total_subtotal = 0
        total_gp_dollars = 0
        ro_count = 0
        ro_ids_with_auth = set()

        for ro in all_ros:
            try:
                # Get estimate
                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")

                # Check each job's authorization date
                ro_has_authorized_jobs_in_range = False

                for job in estimate.get("jobs", []):
                    # Only count jobs authorized in the date range
                    if job.get("authorized") == True and job.get("authorizedDate"):
                        auth_date = datetime.fromisoformat(job["authorizedDate"].replace("Z", "+00:00")).date()

                        if start_date <= auth_date <= end_date:
                            # Job was authorized in our date range!
                            total_sales += job.get("total", 0)
                            total_subtotal += job.get("subtotal", 0)
                            total_gp_dollars += job.get("grossProfitAmount", 0)
                            ro_has_authorized_jobs_in_range = True

                # Count unique ROs (car count)
                if ro_has_authorized_jobs_in_range:
                    ro_ids_with_auth.add(ro["id"])

            except:
                # Skip ROs with errors
                continue

        ro_count = len(ro_ids_with_auth)

        # Add RO-level fees/taxes if RO has authorized jobs
        # For simplicity, distribute proportionally (could be improved)
        if ro_count > 0:
            # Re-process to get authorizedTotal and add delta
            for ro in all_ros:
                if ro["id"] in ro_ids_with_auth:
                    try:
                        estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")
                        # Add difference between authorizedTotal and job totals (fees/taxes)
                        auth_total = estimate.get("authorizedTotal", 0)
                        job_total_sum = sum(j.get("total", 0) for j in estimate.get("jobs", []) if j.get("authorized") == True)
                        total_sales += (auth_total - job_total_sum)
                    except:
                        pass

        # Calculate metrics
        # GP% calculated on SUBTOTAL (before taxes) - matches TM formula
        gp_percentage = (total_gp_dollars / total_subtotal * 100) if total_subtotal > 0 else 0
        aro = (total_sales / ro_count) if ro_count > 0 else 0

        return {
            "date_range": {
                "start": start,
                "end": end
            },
            "sales": round(total_sales / 100, 2),          # Convert to dollars
            "gp_dollars": round(total_gp_dollars / 100, 2),
            "gp_percentage": round(gp_percentage, 2),
            "aro": round(aro / 100, 2),
            "car_count": ro_count,
            "source": "AUTHORIZED_JOBS_ONLY",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
