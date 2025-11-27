"""
Service Advisor Router (Tier 6)

Endpoints for service advisor performance tracking.
Provides sales, GP, and volume metrics per advisor.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from app.services.tm_client import get_tm_client
from app.services.gp_calculator import (
    calculate_ro_true_gp,
    aggregate_advisor_performance,
    get_shop_config,
    AdvisorPerformance,
    cents_to_dollars
)

router = APIRouter()


async def _get_ro_results(start_date: str, end_date: str, status_filter: List[int] = None):
    """Helper to fetch and calculate RO GP results."""
    client = get_tm_client()
    shop_config = await get_shop_config(client, client.shop_id)

    ros = await client.get_ros_for_period(
        start_date=start_date,
        end_date=end_date,
        status_filter=status_filter or [2, 5, 6]
    )

    results = []
    for ro in ros:
        try:
            gp = calculate_ro_true_gp(ro, shop_config)
            results.append(gp)
        except Exception as e:
            print(f"[Advisors] Error calculating GP for RO {ro.get('id')}: {e}")

    return results, client.shop_id


# =============================================================================
# ADVISOR PERFORMANCE ENDPOINTS
# =============================================================================

@router.get("/performance")
async def get_advisor_performance(
    start: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, description="Default days if no dates", ge=1, le=365)
):
    """
    Get service advisor performance metrics.

    Returns sales, GP, and volume metrics per advisor for the period.
    """
    try:
        # Parse dates
        if end:
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()

        if start:
            start_date = date.fromisoformat(start)
        else:
            start_date = end_date - timedelta(days=days)

        # Get RO results
        ro_results, shop_id = await _get_ro_results(
            start_date.isoformat(),
            end_date.isoformat()
        )

        if not ro_results:
            return {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "advisors": [],
                "summary": {
                    "advisor_count": 0,
                    "total_sales": 0,
                    "total_gp": 0,
                    "ros_analyzed": 0
                }
            }

        # Aggregate by advisor
        advisor_perf = aggregate_advisor_performance(ro_results)

        # Sort by sales descending
        advisors_list = sorted(
            advisor_perf.values(),
            key=lambda a: a.total_sales,
            reverse=True
        )

        # Convert to response format
        advisors_response = []
        for adv in advisors_list:
            advisors_response.append({
                "advisor_id": adv.advisor_id,
                "advisor_name": adv.advisor_name,
                "total_sales": cents_to_dollars(adv.total_sales),
                "total_cost": cents_to_dollars(adv.total_cost),
                "gross_profit": cents_to_dollars(adv.gross_profit),
                "gp_percentage": adv.gp_percentage,
                "ro_count": adv.ro_count,
                "job_count": adv.job_count,
                "aro": cents_to_dollars(adv.aro),
                "avg_job_value": cents_to_dollars(adv.avg_job_value),
                "category_breakdown": {
                    "parts": cents_to_dollars(adv.parts_sales),
                    "labor": cents_to_dollars(adv.labor_sales),
                    "sublet": cents_to_dollars(adv.sublet_sales),
                    "fees": cents_to_dollars(adv.fee_sales)
                }
            })

        # Summary stats
        total_sales = sum(a.total_sales for a in advisors_list)
        total_gp = sum(a.gross_profit for a in advisors_list)
        total_ros = sum(a.ro_count for a in advisors_list)

        return {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "advisors": advisors_response,
            "summary": {
                "advisor_count": len(advisors_list),
                "total_sales": cents_to_dollars(total_sales),
                "total_gp": cents_to_dollars(total_gp),
                "avg_gp_pct": round(total_gp / total_sales * 100, 2) if total_sales > 0 else 0,
                "ros_analyzed": total_ros
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_advisor_leaderboard(
    start: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(7, description="Default days if no dates", ge=1, le=90),
    sort_by: str = Query("sales", description="Sort by: sales, gp, gp_pct, aro, ro_count")
):
    """
    Get advisor leaderboard sorted by chosen metric.

    Great for weekly/monthly advisor rankings.
    """
    try:
        # Parse dates
        if end:
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()

        if start:
            start_date = date.fromisoformat(start)
        else:
            start_date = end_date - timedelta(days=days)

        # Get RO results
        ro_results, _ = await _get_ro_results(
            start_date.isoformat(),
            end_date.isoformat()
        )

        if not ro_results:
            return {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "leaderboard": [],
                "sort_by": sort_by
            }

        # Aggregate
        advisor_perf = aggregate_advisor_performance(ro_results)

        # Sort by chosen metric
        sort_key_map = {
            "sales": lambda a: a.total_sales,
            "gp": lambda a: a.gross_profit,
            "gp_pct": lambda a: a.gp_percentage,
            "aro": lambda a: a.aro,
            "ro_count": lambda a: a.ro_count
        }
        sort_key = sort_key_map.get(sort_by, sort_key_map["sales"])

        leaderboard = sorted(
            advisor_perf.values(),
            key=sort_key,
            reverse=True
        )

        # Build leaderboard response
        result = []
        for rank, adv in enumerate(leaderboard, 1):
            result.append({
                "rank": rank,
                "advisor_id": adv.advisor_id,
                "advisor_name": adv.advisor_name,
                "total_sales": cents_to_dollars(adv.total_sales),
                "gross_profit": cents_to_dollars(adv.gross_profit),
                "gp_percentage": adv.gp_percentage,
                "aro": cents_to_dollars(adv.aro),
                "ro_count": adv.ro_count,
                "job_count": adv.job_count
            })

        return {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "leaderboard": result,
            "sort_by": sort_by
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/advisor/{advisor_id}")
async def get_single_advisor_performance(
    advisor_id: int,
    start: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, description="Default days if no dates", ge=1, le=365)
):
    """
    Get detailed performance for a single advisor.

    Includes RO-level breakdown.
    """
    try:
        # Parse dates
        if end:
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()

        if start:
            start_date = date.fromisoformat(start)
        else:
            start_date = end_date - timedelta(days=days)

        # Get RO results
        ro_results, _ = await _get_ro_results(
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Filter to this advisor's ROs
        advisor_ros = [r for r in ro_results if r.advisor_id == advisor_id]

        if not advisor_ros:
            return {
                "advisor_id": advisor_id,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "message": "No ROs found for this advisor in the period",
                "ro_count": 0
            }

        # Get aggregated performance
        advisor_perf = aggregate_advisor_performance(advisor_ros)
        adv = advisor_perf.get(advisor_id)

        # Build RO list
        ro_list = []
        for ro in advisor_ros:
            ro_list.append({
                "ro_id": ro.ro_id,
                "ro_number": ro.ro_number,
                "customer": ro.customer_name,
                "vehicle": ro.vehicle_description,
                "total": cents_to_dollars(ro.total_retail),
                "gp": cents_to_dollars(ro.gross_profit),
                "gp_pct": ro.margin_pct,
                "jobs": ro.authorized_job_count
            })

        return {
            "advisor_id": advisor_id,
            "advisor_name": adv.advisor_name if adv else "Unknown",
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_sales": cents_to_dollars(adv.total_sales) if adv else 0,
                "gross_profit": cents_to_dollars(adv.gross_profit) if adv else 0,
                "gp_percentage": adv.gp_percentage if adv else 0,
                "ro_count": adv.ro_count if adv else 0,
                "job_count": adv.job_count if adv else 0,
                "aro": cents_to_dollars(adv.aro) if adv else 0
            },
            "category_breakdown": {
                "parts": cents_to_dollars(adv.parts_sales) if adv else 0,
                "labor": cents_to_dollars(adv.labor_sales) if adv else 0,
                "sublet": cents_to_dollars(adv.sublet_sales) if adv else 0,
                "fees": cents_to_dollars(adv.fee_sales) if adv else 0
            },
            "ros": ro_list
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_advisors(
    advisor_ids: str = Query(..., description="Comma-separated advisor IDs to compare"),
    start: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, description="Default days if no dates", ge=1, le=365)
):
    """
    Compare performance between multiple advisors.

    Useful for side-by-side analysis.
    """
    try:
        # Parse advisor IDs
        ids = [int(id.strip()) for id in advisor_ids.split(",")]

        # Parse dates
        if end:
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()

        if start:
            start_date = date.fromisoformat(start)
        else:
            start_date = end_date - timedelta(days=days)

        # Get RO results
        ro_results, _ = await _get_ro_results(
            start_date.isoformat(),
            end_date.isoformat()
        )

        # Aggregate
        advisor_perf = aggregate_advisor_performance(ro_results)

        # Build comparison
        comparison = []
        for aid in ids:
            adv = advisor_perf.get(aid)
            if adv:
                comparison.append({
                    "advisor_id": aid,
                    "advisor_name": adv.advisor_name,
                    "total_sales": cents_to_dollars(adv.total_sales),
                    "gross_profit": cents_to_dollars(adv.gross_profit),
                    "gp_percentage": adv.gp_percentage,
                    "ro_count": adv.ro_count,
                    "aro": cents_to_dollars(adv.aro),
                    "avg_job_value": cents_to_dollars(adv.avg_job_value)
                })
            else:
                comparison.append({
                    "advisor_id": aid,
                    "advisor_name": "Not Found",
                    "message": "No data for this advisor in period"
                })

        return {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "comparison": comparison
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/goals")
async def check_advisor_goals(
    sales_goal: float = Query(None, description="Sales goal in dollars"),
    gp_goal: float = Query(None, description="GP goal in dollars"),
    gp_pct_goal: float = Query(None, description="GP% goal"),
    ro_goal: int = Query(None, description="RO count goal"),
    start: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end: str = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, description="Default days", ge=1, le=365)
):
    """
    Check advisor performance against goals.

    Returns progress for each advisor against specified targets.
    """
    try:
        # Parse dates
        if end:
            end_date = date.fromisoformat(end)
        else:
            end_date = date.today()

        if start:
            start_date = date.fromisoformat(start)
        else:
            start_date = end_date - timedelta(days=days)

        # Get RO results
        ro_results, _ = await _get_ro_results(
            start_date.isoformat(),
            end_date.isoformat()
        )

        if not ro_results:
            return {
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "goals": {
                    "sales": sales_goal,
                    "gp": gp_goal,
                    "gp_pct": gp_pct_goal,
                    "ro_count": ro_goal
                },
                "advisors": []
            }

        # Aggregate
        advisor_perf = aggregate_advisor_performance(ro_results)

        # Build goal tracking
        advisors_progress = []
        for adv in advisor_perf.values():
            progress = {
                "advisor_id": adv.advisor_id,
                "advisor_name": adv.advisor_name,
                "current": {
                    "sales": cents_to_dollars(adv.total_sales),
                    "gp": cents_to_dollars(adv.gross_profit),
                    "gp_pct": adv.gp_percentage,
                    "ro_count": adv.ro_count
                },
                "progress": {}
            }

            if sales_goal:
                sales_current = cents_to_dollars(adv.total_sales)
                progress["progress"]["sales"] = {
                    "goal": sales_goal,
                    "current": sales_current,
                    "percent": round(sales_current / sales_goal * 100, 1),
                    "met": sales_current >= sales_goal
                }

            if gp_goal:
                gp_current = cents_to_dollars(adv.gross_profit)
                progress["progress"]["gp"] = {
                    "goal": gp_goal,
                    "current": gp_current,
                    "percent": round(gp_current / gp_goal * 100, 1),
                    "met": gp_current >= gp_goal
                }

            if gp_pct_goal:
                progress["progress"]["gp_pct"] = {
                    "goal": gp_pct_goal,
                    "current": adv.gp_percentage,
                    "met": adv.gp_percentage >= gp_pct_goal
                }

            if ro_goal:
                progress["progress"]["ro_count"] = {
                    "goal": ro_goal,
                    "current": adv.ro_count,
                    "percent": round(adv.ro_count / ro_goal * 100, 1),
                    "met": adv.ro_count >= ro_goal
                }

            advisors_progress.append(progress)

        return {
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "goals": {
                "sales": sales_goal,
                "gp": gp_goal,
                "gp_pct": gp_pct_goal,
                "ro_count": ro_goal
            },
            "advisors": advisors_progress
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
