"""
Dashboard Endpoints

Custom dashboard with accurate metric calculations from raw TM data.

Tier 1 Implementation:
- Fix 1.1: Quantity-aware parts profit
- Fix 1.2: Tech rate fallback logic
- Fix 1.3: Fee inclusion in GP
- Fix 1.4: Discount handling
- Fix 1.5: Date-filtered true metrics endpoint

Tier 2 Implementation:
- Fix 2.3: Tax attribution by category
- Fix 2.4: Fee breakdown with categorization
- Fix 2.5: Caching for shop config and tech rates
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List
from app.services.tm_client import get_tm_client
from app.services.gp_calculator import (
    calculate_ro_true_gp,
    get_shop_config,
    get_shop_average_tech_rate,
    to_dict,
    to_dollars_dict,
    cents_to_dollars
)

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
    Get ACCURATE metrics based on AUTHORIZED sales only (legacy endpoint)

    NOTE: Use /true-metrics for Tier 1 corrected calculations.

    - **start**: Start date (YYYY-MM-DD)
    - **end**: End date (YYYY-MM-DD)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get ROs from all boards (first page only)
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

        # Filter to ROs updated in date range
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        # Filter ROs by update date first (performance optimization)
        recent_ros = []
        for ro in all_ros:
            if ro.get("updatedDate"):
                updated_date = datetime.fromisoformat(ro["updatedDate"].replace("Z", "+00:00")).date()
                if (start_date - timedelta(days=7)) <= updated_date <= (end_date + timedelta(days=1)):
                    recent_ros.append(ro)

        # Get estimate for recent ROs and filter by job authorization date
        total_sales = 0
        total_subtotal = 0
        total_gp_dollars = 0
        ro_ids_with_auth = set()

        for ro in recent_ros:
            try:
                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")
                ro_has_authorized_jobs_in_range = False

                for job in estimate.get("jobs", []):
                    if job.get("authorized") == True and job.get("authorizedDate"):
                        auth_date = datetime.fromisoformat(job["authorizedDate"].replace("Z", "+00:00")).date()
                        if start_date <= auth_date <= end_date:
                            total_sales += job.get("total", 0)
                            total_subtotal += job.get("subtotal", 0)
                            total_gp_dollars += job.get("grossProfitAmount", 0)
                            ro_has_authorized_jobs_in_range = True

                if ro_has_authorized_jobs_in_range:
                    ro_ids_with_auth.add(ro["id"])
            except:
                continue

        ro_count = len(ro_ids_with_auth)

        if ro_count > 0:
            for ro in recent_ros:
                if ro["id"] in ro_ids_with_auth:
                    try:
                        estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")
                        auth_total = estimate.get("authorizedTotal", 0)
                        job_total_sum = sum(j.get("total", 0) for j in estimate.get("jobs", []) if j.get("authorized") == True)
                        total_sales += (auth_total - job_total_sum)
                    except:
                        pass

        gp_percentage = (total_gp_dollars / total_subtotal * 100) if total_subtotal > 0 else 0
        aro = (total_sales / ro_count) if ro_count > 0 else 0

        return {
            "date_range": {"start": start, "end": end},
            "sales": round(total_sales / 100, 2),
            "gp_dollars": round(total_gp_dollars / 100, 2),
            "gp_percentage": round(gp_percentage, 2),
            "aro": round(aro / 100, 2),
            "car_count": ro_count,
            "source": "AUTHORIZED_JOBS_ONLY",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/true-metrics")
async def get_true_metrics(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    include_details: bool = Query(False, description="Include per-RO breakdown")
):
    """
    Get TRUE gross profit metrics using Tier 2 calculation engine.

    This endpoint applies all Tier 1 + Tier 2 fixes:
    - Fix 1.1: Quantity-aware parts profit (handles TM API inconsistencies)
    - Fix 1.2: Tech rate fallback (assigned -> shop avg -> $25 default)
    - Fix 1.3: Fee inclusion (shop supplies, environmental at 100% margin)
    - Fix 1.4: Discount handling (job-level and RO-level)
    - Fix 1.5: Date filtering by job authorization date
    - Fix 2.3: Tax attribution by category (parts, labor, fees, sublet)
    - Fix 2.4: Fee breakdown with categorization
    - Fix 2.5: Caching for shop config (5-minute TTL)

    Returns:
    - sales: Total authorized sales (before tax)
    - gross_profit: True GP including fees, with correct tech costs
    - gp_percentage: GP% calculated on subtotal
    - aro: Average repair order value
    - car_count: Unique ROs with authorized jobs in range
    - fee_profit: Total profit from fees (100% margin)
    - tax_breakdown: Tax attributed by category (parts, labor, fees, sublet)
    - fee_breakdown: Fees categorized (shop_supplies, environmental, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Tier 2: Use cached shop config
        shop_config = await get_shop_config(tm, shop_id)

        all_ros = []
        for board in ["ACTIVE", "POSTED", "COMPLETE"]:
            try:
                ros_page = await tm.get(
                    f"/api/shop/{shop_id}/job-board-group-by",
                    {"board": board, "groupBy": "NONE", "page": 0, "size": 200}
                )
                all_ros.extend(ros_page)
            except:
                pass

        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        recent_ros = []
        for ro in all_ros:
            if ro.get("updatedDate"):
                try:
                    updated_date = datetime.fromisoformat(
                        ro["updatedDate"].replace("Z", "+00:00")
                    ).date()
                    if (start_date - timedelta(days=14)) <= updated_date <= (end_date + timedelta(days=1)):
                        recent_ros.append(ro)
                except:
                    pass

        # Aggregates
        total_sales = 0
        total_cost = 0
        total_gp = 0
        total_fee_profit = 0
        total_discount = 0

        # Tier 2: Category breakdowns
        total_parts_retail = 0
        total_parts_cost = 0
        total_labor_retail = 0
        total_labor_cost = 0
        total_sublet_retail = 0
        total_sublet_cost = 0

        # Tier 2: Tax aggregates
        agg_parts_tax = 0
        agg_labor_tax = 0
        agg_fees_tax = 0
        agg_sublet_tax = 0
        agg_total_tax = 0

        # Tier 2: Fee category aggregates
        fee_by_category = {}
        total_fees = 0

        ro_details = []
        ro_ids_counted = set()

        for ro in recent_ros:
            try:
                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")

                has_auth_in_range = False
                for job in estimate.get("jobs", []):
                    if job.get("authorized") and job.get("authorizedDate"):
                        try:
                            auth_date = datetime.fromisoformat(
                                job["authorizedDate"].replace("Z", "+00:00")
                            ).date()
                            if start_date <= auth_date <= end_date:
                                has_auth_in_range = True
                                break
                        except:
                            pass

                if not has_auth_in_range:
                    continue

                # Tier 2: Use ShopConfig
                ro_gp = calculate_ro_true_gp(
                    estimate,
                    shop_config=shop_config,
                    authorized_only=True
                )

                if ro_gp.total_retail > 0:
                    ro_ids_counted.add(ro["id"])
                    total_sales += ro_gp.total_retail
                    total_cost += ro_gp.total_cost
                    total_gp += ro_gp.gross_profit
                    total_fee_profit += ro_gp.fee_profit
                    total_discount += ro_gp.discount_total

                    # Tier 2: Category breakdowns
                    total_parts_retail += ro_gp.parts_retail
                    total_parts_cost += ro_gp.parts_cost
                    total_labor_retail += ro_gp.labor_retail
                    total_labor_cost += ro_gp.labor_cost
                    total_sublet_retail += ro_gp.sublet_retail
                    total_sublet_cost += ro_gp.sublet_cost

                    # Tier 2: Tax aggregates
                    if ro_gp.tax_breakdown:
                        agg_parts_tax += ro_gp.tax_breakdown.parts_tax
                        agg_labor_tax += ro_gp.tax_breakdown.labor_tax
                        agg_fees_tax += ro_gp.tax_breakdown.fees_tax
                        agg_sublet_tax += ro_gp.tax_breakdown.sublet_tax
                        agg_total_tax += ro_gp.tax_breakdown.total_tax

                    # Tier 2: Fee category aggregates
                    if ro_gp.fee_breakdown:
                        total_fees += ro_gp.fee_breakdown.total_fees
                        for cat, amt in ro_gp.fee_breakdown.by_category.items():
                            fee_by_category[cat] = fee_by_category.get(cat, 0) + amt

                    if include_details:
                        ro_details.append(to_dollars_dict(ro_gp))

            except Exception as e:
                print(f"[True Metrics] Error processing RO {ro.get('id')}: {e}")
                continue

        car_count = len(ro_ids_counted)
        gp_pct = (total_gp / total_sales * 100) if total_sales > 0 else 0
        aro = (total_sales / car_count) if car_count > 0 else 0

        response = {
            "date_range": {"start": start, "end": end},
            "metrics": {
                "sales": cents_to_dollars(total_sales),
                "cost": cents_to_dollars(total_cost),
                "gross_profit": cents_to_dollars(total_gp),
                "gp_percentage": round(gp_pct, 2),
                "aro": cents_to_dollars(aro),
                "car_count": car_count,
                "fee_profit": cents_to_dollars(total_fee_profit),
                "discount_total": cents_to_dollars(total_discount)
            },
            # Tier 2: Category breakdown
            "parts_summary": {
                "retail": cents_to_dollars(total_parts_retail),
                "cost": cents_to_dollars(total_parts_cost),
                "profit": cents_to_dollars(total_parts_retail - total_parts_cost),
                "margin_pct": round((total_parts_retail - total_parts_cost) / total_parts_retail * 100, 2) if total_parts_retail > 0 else 0
            },
            "labor_summary": {
                "retail": cents_to_dollars(total_labor_retail),
                "cost": cents_to_dollars(total_labor_cost),
                "profit": cents_to_dollars(total_labor_retail - total_labor_cost),
                "margin_pct": round((total_labor_retail - total_labor_cost) / total_labor_retail * 100, 2) if total_labor_retail > 0 else 0
            },
            "sublet_summary": {
                "retail": cents_to_dollars(total_sublet_retail),
                "cost": cents_to_dollars(total_sublet_cost),
                "profit": cents_to_dollars(total_sublet_retail - total_sublet_cost),
                "margin_pct": round((total_sublet_retail - total_sublet_cost) / total_sublet_retail * 100, 2) if total_sublet_retail > 0 else 0
            },
            # Tier 2: Tax breakdown
            "tax_breakdown": {
                "parts_tax": cents_to_dollars(agg_parts_tax),
                "labor_tax": cents_to_dollars(agg_labor_tax),
                "fees_tax": cents_to_dollars(agg_fees_tax),
                "sublet_tax": cents_to_dollars(agg_sublet_tax),
                "total_tax": cents_to_dollars(agg_total_tax)
            },
            # Tier 2: Fee breakdown
            "fee_breakdown": {
                "total_fees": cents_to_dollars(total_fees),
                "by_category": {k: cents_to_dollars(v) for k, v in fee_by_category.items()}
            },
            "calculation_info": {
                "shop_avg_tech_rate": cents_to_dollars(shop_config.avg_tech_rate),
                "tech_count": len(shop_config.tech_rates),
                "cache_status": "hit" if shop_config.cached_at else "miss",
                "ros_processed": len(recent_ros),
                "ros_with_auth_in_range": car_count,
                "fixes_applied": [
                    "Fix 1.1: Quantity-aware parts profit",
                    f"Fix 1.2: Tech rate fallback (shop avg: ${shop_config.avg_tech_rate / 100:.2f}/hr)",
                    "Fix 1.3: Fee inclusion (100% margin)",
                    "Fix 1.4: Discount handling",
                    "Fix 1.5: Date filtering by auth date",
                    "Fix 2.3: Tax attribution by category",
                    "Fix 2.4: Fee categorization",
                    "Fix 2.5: Shop config caching (5min TTL)"
                ]
            },
            "source": "TRUE_GP_TIER2",
            "calculated_at": datetime.now().isoformat()
        }

        if include_details:
            response["ro_details"] = ro_details

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare-metrics")
async def compare_metrics(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Compare TM aggregate metrics vs TRUE calculated metrics.

    Shows the difference between:
    1. TM's dashboard aggregates (may have issues)
    2. Our Tier 2 true GP calculation
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        from datetime import timezone as tz
        offset = timedelta(hours=-5)
        tzinfo = tz(offset)

        start_dt = datetime.fromisoformat(start).replace(hour=0, minute=0, second=0, tzinfo=tzinfo)
        end_dt = datetime.fromisoformat(end).replace(hour=23, minute=59, second=59, tzinfo=tzinfo)

        tm_params = {
            "viewType": "JOBBOARDPOSTED",
            "metric": "SALES",
            "shopIds": shop_id,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "timezone": "America/New_York",
            "useCustomRoLabel": "true"
        }

        tm_summary = await tm.get("/api/reporting/shop-dashboard/aggregate/summary", tm_params)

        # Tier 2: Use cached shop config
        shop_config = await get_shop_config(tm, shop_id)

        all_ros = []
        for board in ["ACTIVE", "POSTED", "COMPLETE"]:
            try:
                ros_page = await tm.get(
                    f"/api/shop/{shop_id}/job-board-group-by",
                    {"board": board, "groupBy": "NONE", "page": 0, "size": 200}
                )
                all_ros.extend(ros_page)
            except:
                pass

        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        total_sales = 0
        total_gp = 0
        ro_ids = set()

        for ro in all_ros:
            if not ro.get("updatedDate"):
                continue
            try:
                updated_date = datetime.fromisoformat(ro["updatedDate"].replace("Z", "+00:00")).date()
                if not ((start_date - timedelta(days=14)) <= updated_date <= (end_date + timedelta(days=1))):
                    continue

                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")

                has_auth_in_range = False
                for job in estimate.get("jobs", []):
                    if job.get("authorized") and job.get("authorizedDate"):
                        try:
                            auth_date = datetime.fromisoformat(job["authorizedDate"].replace("Z", "+00:00")).date()
                            if start_date <= auth_date <= end_date:
                                has_auth_in_range = True
                                break
                        except:
                            pass

                if not has_auth_in_range:
                    continue

                # Tier 2: Use ShopConfig
                ro_gp = calculate_ro_true_gp(estimate, shop_config=shop_config, authorized_only=True)
                if ro_gp.total_retail > 0:
                    ro_ids.add(ro["id"])
                    total_sales += ro_gp.total_retail
                    total_gp += ro_gp.gross_profit
            except:
                continue

        car_count = len(ro_ids)
        true_gp_pct = (total_gp / total_sales * 100) if total_sales > 0 else 0
        true_aro = (total_sales / car_count) if car_count > 0 else 0

        tm_sold = tm_summary.get("sold", 0) / 100
        tm_car_count = tm_summary.get("carCount", 0)
        tm_aro = tm_summary.get("averageRo", 0)

        return {
            "date_range": {"start": start, "end": end},
            "tm_aggregates": {
                "sold": tm_sold,
                "car_count": tm_car_count,
                "average_ro": tm_aro,
                "note": "TM aggregates may include lifetime data or have date filtering issues"
            },
            "true_metrics": {
                "sales": cents_to_dollars(total_sales),
                "gross_profit": cents_to_dollars(total_gp),
                "gp_percentage": round(true_gp_pct, 2),
                "car_count": car_count,
                "average_ro": cents_to_dollars(true_aro)
            },
            "deltas": {
                "sales_diff": round(cents_to_dollars(total_sales) - tm_sold, 2),
                "car_count_diff": car_count - tm_car_count,
                "aro_diff": round(cents_to_dollars(true_aro) - tm_aro, 2)
            },
            "source": "TRUE_GP_TIER2",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live")
async def get_live_authorized_work(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Get LIVE authorized work - daily sales activity.

    Shows all jobs authorized in the date range, regardless of RO status:
    - Fetches from ALL boards (ACTIVE, POSTED, COMPLETE)
    - Filtered by job authorization date in range
    - Shows "new work sold" for the period

    Use this to see daily/weekly sales activity.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Fetch from ALL boards to get complete sales activity
        all_ros = []
        for board in ["ACTIVE", "POSTED", "COMPLETE"]:
            try:
                ros_page = await tm.get(
                    f"/api/shop/{shop_id}/job-board-group-by",
                    {"board": board, "groupBy": "NONE", "page": 0, "size": 500}
                )
                # Tag each RO with its board status
                for ro in ros_page:
                    ro["_board"] = board
                all_ros.extend(ros_page)
            except:
                pass

        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        # Track authorized work
        total_authorized = 0
        total_labor = 0
        total_parts = 0
        total_fees = 0
        ro_count = 0
        job_count = 0

        ro_details = []
        processed_ro_ids = set()  # Deduplicate ROs across boards

        for ro in all_ros:
            # Skip if we already processed this RO from another board
            ro_id = ro.get("id")
            if ro_id in processed_ro_ids:
                continue
            processed_ro_ids.add(ro_id)
            try:
                estimate = await tm.get(f"/api/repair-order/{ro['id']}/estimate")

                ro_authorized = 0
                ro_labor = 0
                ro_parts = 0
                ro_fees = 0
                ro_jobs = []
                has_auth_in_range = False

                for job in estimate.get("jobs", []):
                    if not job.get("authorized"):
                        continue

                    # Check if authorized in date range
                    auth_date_str = job.get("authorizedDate")
                    if auth_date_str:
                        try:
                            auth_date = datetime.fromisoformat(
                                auth_date_str.replace("Z", "+00:00")
                            ).date()
                            if start_date <= auth_date <= end_date:
                                has_auth_in_range = True

                                job_total = job.get("total", 0)
                                labor_total = sum(l.get("total", 0) for l in job.get("labor", []))
                                parts_total = sum(p.get("total", 0) for p in job.get("parts", []))
                                fees_total = sum(f.get("total", 0) for f in job.get("fees", []))

                                ro_authorized += job_total
                                ro_labor += labor_total
                                ro_parts += parts_total
                                ro_fees += fees_total
                                job_count += 1

                                ro_jobs.append({
                                    "name": job.get("name", ""),
                                    "authorized_date": auth_date.isoformat(),
                                    "total": round(job_total / 100, 2),
                                    "labor": round(labor_total / 100, 2),
                                    "parts": round(parts_total / 100, 2)
                                })
                        except:
                            pass

                if has_auth_in_range:
                    ro_count += 1
                    total_authorized += ro_authorized
                    total_labor += ro_labor
                    total_parts += ro_parts
                    total_fees += ro_fees

                    # Get customer/vehicle info
                    customer = estimate.get("customer", {})
                    vehicle = estimate.get("vehicle", {})

                    # Map board to display status
                    board = ro.get("_board", "ACTIVE")
                    status_map = {"ACTIVE": "WIP", "POSTED": "Invoiced", "COMPLETE": "Complete"}

                    ro_details.append({
                        "ro_number": ro.get("roNumber") or ro.get("repairOrderNumber"),
                        "ro_id": ro.get("id"),
                        "customer": f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                        "vehicle": f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip(),
                        "authorized_total": round(ro_authorized / 100, 2),
                        "jobs": ro_jobs,
                        "status": status_map.get(board, "WIP")
                    })

            except Exception as e:
                print(f"[Live] Error processing RO {ro.get('id')}: {e}")
                continue

        # Sort by authorized total descending
        ro_details.sort(key=lambda x: x["authorized_total"], reverse=True)

        avg_ticket = total_authorized / ro_count if ro_count > 0 else 0

        return {
            "period": {
                "start": start,
                "end": end
            },
            "summary": {
                "total_authorized": round(total_authorized / 100, 2),
                "labor_total": round(total_labor / 100, 2),
                "parts_total": round(total_parts / 100, 2),
                "fees_total": round(total_fees / 100, 2),
                "ro_count": ro_count,
                "job_count": job_count,
                "avg_ticket": round(avg_ticket / 100, 2)
            },
            "ros": ro_details[:50],  # Top 50 ROs
            "source": "LIVE_AUTHORIZED_ALL_BOARDS",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
