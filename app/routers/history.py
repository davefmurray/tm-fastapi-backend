"""
GP History Router (Tier 4)

Endpoints for persisting and retrieving historical GP calculations.
Enables trend analysis, period comparisons, and audit trails.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
from typing import Optional, List, Dict, Any

from app.services.tm_client import get_tm_client
from app.services.gp_calculator import (
    calculate_ro_true_gp,
    aggregate_tech_performance,
    ROTrueGP,
    to_dollars_dict,
    cents_to_dollars
)
from app.services.gp_persistence import get_persistence_service

router = APIRouter()


# =============================================================================
# SNAPSHOT CREATION ENDPOINTS
# =============================================================================

@router.post("/snapshot/daily")
async def create_daily_snapshot(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD), default today"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD), default today")
):
    """
    Create a daily GP snapshot from current RO data.

    This endpoint:
    1. Fetches all completed/posted ROs for the date range
    2. Calculates True GP for each RO
    3. Stores aggregated daily snapshot to Supabase
    4. Stores individual RO history records
    5. Stores technician performance records

    Run this daily (e.g., via cron) to build historical data.
    """
    try:
        # Parse dates
        if end_date:
            end_dt = date.fromisoformat(end_date)
        else:
            end_dt = date.today()

        if start_date:
            start_dt = date.fromisoformat(start_date)
        else:
            start_dt = end_dt

        # Get TM client
        client = await get_tm_client()

        # Fetch ROs for period (completed/posted only)
        ros = await client.get_ros_for_period(
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            status_filter=[5, 6]  # POSTED, COMPLETED
        )

        if not ros:
            return {
                "success": True,
                "message": "No completed ROs found for period",
                "period": {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat()
                },
                "records_created": 0
            }

        # Calculate True GP for each RO
        ro_results: List[ROTrueGP] = []
        for ro in ros:
            try:
                result = await calculate_ro_true_gp(ro, client)
                ro_results.append(result)
            except Exception as e:
                print(f"[History] Error calculating GP for RO {ro.get('id')}: {e}")
                continue

        if not ro_results:
            return {
                "success": False,
                "error": "Failed to calculate GP for any ROs",
                "ro_count": len(ros)
            }

        # Aggregate tech performance
        tech_performance = aggregate_tech_performance(ro_results)

        # Get persistence service
        persistence = get_persistence_service()
        shop_id = int(client.shop_id)

        # Store daily snapshot
        daily_record = await persistence.store_daily_snapshot(
            shop_id=shop_id,
            snapshot_date=end_dt,
            ro_results=ro_results,
            tech_performance=tech_performance
        )

        # Store individual RO records
        ro_records_stored = 0
        for result in ro_results:
            try:
                await persistence.store_ro_history(
                    shop_id=shop_id,
                    snapshot_date=end_dt,
                    ro_result=result
                )
                ro_records_stored += 1
            except Exception as e:
                print(f"[History] Error storing RO {result.ro_id}: {e}")

        # Store tech performance
        tech_records = await persistence.store_tech_performance(
            shop_id=shop_id,
            snapshot_date=end_dt,
            tech_performance=tech_performance
        )

        return {
            "success": True,
            "message": "Daily snapshot created successfully",
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat()
            },
            "summary": {
                "ros_processed": len(ro_results),
                "ro_records_stored": ro_records_stored,
                "tech_records_stored": len(tech_records),
                "total_revenue": cents_to_dollars(daily_record.get("total_revenue", 0)),
                "gp_percentage": daily_record.get("gp_percentage", 0)
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot creation failed: {str(e)}")


# =============================================================================
# DAILY SNAPSHOT RETRIEVAL
# =============================================================================

@router.get("/snapshots/daily")
async def get_daily_snapshots(
    days: int = Query(30, description="Number of days to retrieve", ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Override: Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Override: End date (YYYY-MM-DD)")
):
    """
    Get historical daily GP snapshots.

    Returns aggregated daily totals for trend analysis.
    """
    try:
        # Parse dates
        if end_date:
            end_dt = date.fromisoformat(end_date)
        else:
            end_dt = date.today()

        if start_date:
            start_dt = date.fromisoformat(start_date)
        else:
            start_dt = end_dt - timedelta(days=days)

        # Get client for shop_id
        client = await get_tm_client()
        shop_id = int(client.shop_id)

        # Query persistence
        persistence = get_persistence_service()
        snapshots = await persistence.get_daily_snapshots(shop_id, start_dt, end_dt)

        # Convert cents to dollars for response
        for snapshot in snapshots:
            snapshot["total_revenue"] = cents_to_dollars(snapshot.get("total_revenue", 0))
            snapshot["total_cost"] = cents_to_dollars(snapshot.get("total_cost", 0))
            snapshot["total_gp_dollars"] = cents_to_dollars(snapshot.get("total_gp_dollars", 0))
            snapshot["aro"] = cents_to_dollars(snapshot.get("aro_cents", 0))
            snapshot["parts_revenue"] = cents_to_dollars(snapshot.get("parts_revenue", 0))
            snapshot["parts_cost"] = cents_to_dollars(snapshot.get("parts_cost", 0))
            snapshot["parts_profit"] = cents_to_dollars(snapshot.get("parts_profit", 0))
            snapshot["labor_revenue"] = cents_to_dollars(snapshot.get("labor_revenue", 0))
            snapshot["labor_cost"] = cents_to_dollars(snapshot.get("labor_cost", 0))
            snapshot["labor_profit"] = cents_to_dollars(snapshot.get("labor_profit", 0))
            snapshot["avg_tech_rate"] = cents_to_dollars(snapshot.get("avg_tech_rate", 0))

        return {
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "days": (end_dt - start_dt).days + 1
            },
            "count": len(snapshots),
            "snapshots": snapshots
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RO HISTORY RETRIEVAL
# =============================================================================

@router.get("/ro/{ro_id}")
async def get_ro_history(
    ro_id: int,
    limit: int = Query(10, description="Max history records to return", ge=1, le=100)
):
    """
    Get GP calculation history for a specific RO.

    Shows how GP has been calculated over time for auditing.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)

        persistence = get_persistence_service()
        history = await persistence.get_ro_history(
            shop_id=shop_id,
            ro_id=ro_id,
            limit=limit
        )

        if not history:
            return {
                "ro_id": ro_id,
                "history_count": 0,
                "message": "No history found. Run /snapshot/daily to create records.",
                "history": []
            }

        # Convert cents to dollars
        for record in history:
            record["total_revenue"] = cents_to_dollars(record.get("total_revenue", 0))
            record["total_cost"] = cents_to_dollars(record.get("total_cost", 0))
            record["gp_dollars"] = cents_to_dollars(record.get("gp_dollars", 0))

        return {
            "ro_id": ro_id,
            "ro_number": history[0].get("ro_number") if history else None,
            "history_count": len(history),
            "history": history
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ros")
async def get_ros_history(
    days: int = Query(7, description="Number of days to retrieve", ge=1, le=90),
    limit: int = Query(100, description="Max records", ge=1, le=500),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get recent RO GP history records.

    Returns individual RO calculations for detailed analysis.
    """
    try:
        # Parse dates
        if end_date:
            end_dt = date.fromisoformat(end_date)
        else:
            end_dt = date.today()

        if start_date:
            start_dt = date.fromisoformat(start_date)
        else:
            start_dt = end_dt - timedelta(days=days)

        client = await get_tm_client()
        shop_id = int(client.shop_id)

        persistence = get_persistence_service()
        records = await persistence.get_ro_history(
            shop_id=shop_id,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit
        )

        # Convert and summarize
        total_revenue = 0
        total_gp = 0

        for record in records:
            total_revenue += record.get("total_revenue", 0)
            total_gp += record.get("gp_dollars", 0)

            record["total_revenue"] = cents_to_dollars(record.get("total_revenue", 0))
            record["total_cost"] = cents_to_dollars(record.get("total_cost", 0))
            record["gp_dollars"] = cents_to_dollars(record.get("gp_dollars", 0))

        return {
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat()
            },
            "count": len(records),
            "summary": {
                "total_revenue": cents_to_dollars(total_revenue),
                "total_gp": cents_to_dollars(total_gp),
                "avg_gp_pct": round(total_gp / total_revenue * 100, 2) if total_revenue > 0 else 0
            },
            "records": records
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TECH PERFORMANCE HISTORY
# =============================================================================

@router.get("/tech-performance")
async def get_tech_performance_history(
    days: int = Query(30, description="Number of days", ge=1, le=365),
    tech_id: Optional[int] = Query(None, description="Filter by technician ID")
):
    """
    Get technician performance history.

    Track how each technician's metrics have changed over time.
    """
    try:
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=days)

        client = await get_tm_client()
        shop_id = int(client.shop_id)

        persistence = get_persistence_service()
        records = await persistence.get_tech_performance_history(
            shop_id=shop_id,
            tech_id=tech_id,
            start_date=start_dt,
            end_date=end_dt
        )

        # Convert cents to dollars
        for record in records:
            record["hourly_rate"] = cents_to_dollars(record.get("hourly_rate", 0))
            record["labor_revenue"] = cents_to_dollars(record.get("labor_revenue", 0))
            record["labor_cost"] = cents_to_dollars(record.get("labor_cost", 0))
            record["labor_profit"] = cents_to_dollars(record.get("labor_profit", 0))
            record["gp_per_hour"] = cents_to_dollars(record.get("gp_per_hour", 0))

        # Group by tech if not filtered
        if tech_id is None:
            by_tech: Dict[int, List] = {}
            for record in records:
                tid = record.get("tech_id")
                if tid not in by_tech:
                    by_tech[tid] = []
                by_tech[tid].append(record)

            return {
                "period": {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat()
                },
                "technicians": len(by_tech),
                "total_records": len(records),
                "by_technician": by_tech
            }

        return {
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat()
            },
            "tech_id": tech_id,
            "record_count": len(records),
            "records": records
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TREND ANALYSIS
# =============================================================================

@router.get("/trends")
async def get_gp_trends(
    days: int = Query(30, description="Analysis period in days", ge=7, le=365)
):
    """
    Get GP trend analysis for the period.

    Returns:
    - Average GP% over period
    - Trend direction (up/down/stable)
    - Daily averages
    - Best/worst performing days
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)

        persistence = get_persistence_service()
        trend_data = await persistence.get_trend_summary(shop_id, days)

        if trend_data.get("data_points", 0) == 0:
            return {
                "success": False,
                "message": "No historical data available. Run POST /snapshot/daily to create records.",
                "period_days": days
            }

        return {
            "success": True,
            "analysis": trend_data,
            "recommendations": _generate_recommendations(trend_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_recommendations(trend_data: Dict[str, Any]) -> List[str]:
    """Generate actionable recommendations from trend data."""
    recommendations = []

    gp_pct = trend_data.get("average_gp_percentage", 0)
    trend = trend_data.get("trend_direction", "stable")

    if gp_pct < 45:
        recommendations.append("GP% below 45% - Review labor costs and parts pricing")
    elif gp_pct < 50:
        recommendations.append("GP% below 50% - Consider markup adjustments")
    elif gp_pct >= 55:
        recommendations.append("Strong GP% - Maintain current pricing strategy")

    if trend == "down":
        recommendations.append("Downward trend detected - Investigate recent cost increases")
    elif trend == "up":
        recommendations.append("Positive trend - Document recent changes for best practices")

    if not recommendations:
        recommendations.append("GP metrics within normal range - Continue monitoring")

    return recommendations


# =============================================================================
# COMPARISON ENDPOINTS
# =============================================================================

@router.get("/compare/periods")
async def compare_periods(
    period1_start: str = Query(..., description="Period 1 start (YYYY-MM-DD)"),
    period1_end: str = Query(..., description="Period 1 end (YYYY-MM-DD)"),
    period2_start: str = Query(..., description="Period 2 start (YYYY-MM-DD)"),
    period2_end: str = Query(..., description="Period 2 end (YYYY-MM-DD)")
):
    """
    Compare GP metrics between two time periods.

    Useful for:
    - Month-over-month comparison
    - Year-over-year analysis
    - Before/after pricing changes
    """
    try:
        p1_start = date.fromisoformat(period1_start)
        p1_end = date.fromisoformat(period1_end)
        p2_start = date.fromisoformat(period2_start)
        p2_end = date.fromisoformat(period2_end)

        client = await get_tm_client()
        shop_id = int(client.shop_id)

        persistence = get_persistence_service()

        # Get snapshots for both periods
        period1_data = await persistence.get_daily_snapshots(shop_id, p1_start, p1_end)
        period2_data = await persistence.get_daily_snapshots(shop_id, p2_start, p2_end)

        def summarize_period(snapshots):
            if not snapshots:
                return None
            return {
                "days": len(snapshots),
                "total_revenue": cents_to_dollars(sum(s.get("total_revenue", 0) for s in snapshots)),
                "total_gp": cents_to_dollars(sum(s.get("total_gp_dollars", 0) for s in snapshots)),
                "avg_gp_pct": round(sum(s.get("gp_percentage", 0) for s in snapshots) / len(snapshots), 2),
                "total_ros": sum(s.get("ro_count", 0) for s in snapshots),
                "avg_aro": cents_to_dollars(
                    int(sum(s.get("aro_cents", 0) for s in snapshots) / len(snapshots))
                )
            }

        p1_summary = summarize_period(period1_data)
        p2_summary = summarize_period(period2_data)

        # Calculate changes
        changes = None
        if p1_summary and p2_summary:
            changes = {
                "gp_pct_change": round(p2_summary["avg_gp_pct"] - p1_summary["avg_gp_pct"], 2),
                "revenue_change_pct": round(
                    (p2_summary["total_revenue"] - p1_summary["total_revenue"]) / p1_summary["total_revenue"] * 100, 2
                ) if p1_summary["total_revenue"] > 0 else 0,
                "aro_change_pct": round(
                    (p2_summary["avg_aro"] - p1_summary["avg_aro"]) / p1_summary["avg_aro"] * 100, 2
                ) if p1_summary["avg_aro"] > 0 else 0
            }

        return {
            "period_1": {
                "start": period1_start,
                "end": period1_end,
                "summary": p1_summary or {"message": "No data available"}
            },
            "period_2": {
                "start": period2_start,
                "end": period2_end,
                "summary": p2_summary or {"message": "No data available"}
            },
            "comparison": changes or {"message": "Insufficient data for comparison"}
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
