"""
Trend Analysis Router (Tier 7)

Advanced trend analysis, forecasting, and period comparisons.
Uses historical data from Tier 4 persistence layer.

Features:
- Week-over-week (WoW) comparisons
- Month-over-month (MoM) comparisons
- Rolling averages (7-day, 30-day)
- Simple linear regression forecasting
- Day-of-week patterns
- Best/worst performing days
- Category-specific trends
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
import statistics

from app.services.gp_persistence import get_persistence_service
from app.services.tm_client import get_tm_client
from app.services.gp_calculator import cents_to_dollars

router = APIRouter()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def linear_regression(x: List[float], y: List[float]) -> Dict[str, float]:
    """
    Simple linear regression: y = mx + b

    Returns slope (m), intercept (b), and R-squared value.
    """
    n = len(x)
    if n < 2 or len(y) != n:
        return {"slope": 0, "intercept": 0, "r_squared": 0}

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate slope
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return {"slope": 0, "intercept": mean_y, "r_squared": 0}

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    # Calculate R-squared
    y_pred = [slope * x[i] + intercept for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r_squared": round(max(0, r_squared), 4)
    }


def calculate_rolling_average(
    values: List[float],
    window: int
) -> List[Optional[float]]:
    """Calculate rolling average with specified window size."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            window_values = values[i - window + 1:i + 1]
            result.append(round(sum(window_values) / len(window_values), 2))
    return result


def get_day_of_week_name(day_num: int) -> str:
    """Convert day number (0=Monday) to name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_num] if 0 <= day_num <= 6 else "Unknown"


# =============================================================================
# WEEK-OVER-WEEK COMPARISON
# =============================================================================

@router.get("/wow")
async def week_over_week_comparison(
    weeks_back: int = Query(4, description="Number of weeks to compare", ge=2, le=12)
):
    """
    Week-over-week GP comparison.

    Compares weekly metrics for the specified number of weeks.
    Identifies trends and highlights significant changes.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        # Calculate week boundaries
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())

        weeks_data = []

        for i in range(weeks_back):
            week_start = current_week_start - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)

            # Don't include future dates
            if week_end > today:
                week_end = today

            snapshots = await persistence.get_daily_snapshots(
                shop_id, week_start, week_end
            )

            if snapshots:
                total_revenue = sum(s.get("total_revenue", 0) for s in snapshots)
                total_gp = sum(s.get("total_gp_dollars", 0) for s in snapshots)
                total_ros = sum(s.get("ro_count", 0) for s in snapshots)
                avg_gp_pct = sum(s.get("gp_percentage", 0) for s in snapshots) / len(snapshots)

                weeks_data.append({
                    "week_number": i,
                    "week_label": f"Week of {week_start.isoformat()}",
                    "start_date": week_start.isoformat(),
                    "end_date": week_end.isoformat(),
                    "days_with_data": len(snapshots),
                    "metrics": {
                        "total_revenue": cents_to_dollars(total_revenue),
                        "total_gp": cents_to_dollars(total_gp),
                        "avg_gp_pct": round(avg_gp_pct, 2),
                        "ro_count": total_ros,
                        "aro": cents_to_dollars(int(total_revenue / total_ros)) if total_ros > 0 else 0
                    }
                })
            else:
                weeks_data.append({
                    "week_number": i,
                    "week_label": f"Week of {week_start.isoformat()}",
                    "start_date": week_start.isoformat(),
                    "end_date": week_end.isoformat(),
                    "days_with_data": 0,
                    "metrics": None
                })

        # Calculate WoW changes (comparing consecutive weeks)
        wow_changes = []
        for i in range(len(weeks_data) - 1):
            current = weeks_data[i]
            previous = weeks_data[i + 1]

            if current["metrics"] and previous["metrics"]:
                curr_m = current["metrics"]
                prev_m = previous["metrics"]

                wow_changes.append({
                    "period": f"{current['week_label']} vs {previous['week_label']}",
                    "revenue_change": round(curr_m["total_revenue"] - prev_m["total_revenue"], 2),
                    "revenue_change_pct": round(
                        (curr_m["total_revenue"] - prev_m["total_revenue"]) / prev_m["total_revenue"] * 100, 2
                    ) if prev_m["total_revenue"] > 0 else 0,
                    "gp_pct_change": round(curr_m["avg_gp_pct"] - prev_m["avg_gp_pct"], 2),
                    "ro_count_change": curr_m["ro_count"] - prev_m["ro_count"],
                    "aro_change": round(curr_m["aro"] - prev_m["aro"], 2)
                })

        # Summary insights
        valid_weeks = [w for w in weeks_data if w["metrics"]]
        insights = []

        if len(valid_weeks) >= 2:
            gp_pcts = [w["metrics"]["avg_gp_pct"] for w in valid_weeks]
            revenues = [w["metrics"]["total_revenue"] for w in valid_weeks]

            # GP trend
            if gp_pcts[0] > gp_pcts[-1] + 1:
                insights.append(f"GP% improved from {gp_pcts[-1]}% to {gp_pcts[0]}% over {len(valid_weeks)} weeks")
            elif gp_pcts[0] < gp_pcts[-1] - 1:
                insights.append(f"GP% declined from {gp_pcts[-1]}% to {gp_pcts[0]}% - investigate cost increases")

            # Revenue trend
            if revenues[0] > revenues[-1] * 1.1:
                insights.append("Revenue up >10% compared to oldest week")
            elif revenues[0] < revenues[-1] * 0.9:
                insights.append("Revenue down >10% - check car count and ARO")

        return {
            "analysis_type": "week_over_week",
            "weeks_analyzed": len(valid_weeks),
            "weeks_requested": weeks_back,
            "weeks": weeks_data,
            "wow_changes": wow_changes,
            "insights": insights,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MONTH-OVER-MONTH COMPARISON
# =============================================================================

@router.get("/mom")
async def month_over_month_comparison(
    months_back: int = Query(3, description="Number of months to compare", ge=2, le=12)
):
    """
    Month-over-month GP comparison.

    Compares monthly metrics for the specified number of months.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        today = date.today()
        months_data = []

        for i in range(months_back):
            # Calculate month boundaries
            if i == 0:
                month_end = today
                month_start = today.replace(day=1)
            else:
                # Go back i months
                target_date = today.replace(day=1) - timedelta(days=1)  # Last day of previous month
                for _ in range(i - 1):
                    target_date = target_date.replace(day=1) - timedelta(days=1)

                month_end = target_date
                month_start = target_date.replace(day=1)

            snapshots = await persistence.get_daily_snapshots(
                shop_id, month_start, month_end
            )

            month_label = month_start.strftime("%B %Y")

            if snapshots:
                total_revenue = sum(s.get("total_revenue", 0) for s in snapshots)
                total_gp = sum(s.get("total_gp_dollars", 0) for s in snapshots)
                total_ros = sum(s.get("ro_count", 0) for s in snapshots)
                avg_gp_pct = sum(s.get("gp_percentage", 0) for s in snapshots) / len(snapshots)

                # Category breakdown
                parts_profit = sum(s.get("parts_profit", 0) for s in snapshots)
                labor_profit = sum(s.get("labor_profit", 0) for s in snapshots)

                months_data.append({
                    "month_number": i,
                    "month_label": month_label,
                    "start_date": month_start.isoformat(),
                    "end_date": month_end.isoformat(),
                    "days_with_data": len(snapshots),
                    "metrics": {
                        "total_revenue": cents_to_dollars(total_revenue),
                        "total_gp": cents_to_dollars(total_gp),
                        "avg_gp_pct": round(avg_gp_pct, 2),
                        "ro_count": total_ros,
                        "aro": cents_to_dollars(int(total_revenue / total_ros)) if total_ros > 0 else 0,
                        "daily_avg_revenue": cents_to_dollars(int(total_revenue / len(snapshots))),
                        "parts_profit": cents_to_dollars(parts_profit),
                        "labor_profit": cents_to_dollars(labor_profit)
                    }
                })
            else:
                months_data.append({
                    "month_number": i,
                    "month_label": month_label,
                    "start_date": month_start.isoformat(),
                    "end_date": month_end.isoformat(),
                    "days_with_data": 0,
                    "metrics": None
                })

        # Calculate MoM changes
        mom_changes = []
        for i in range(len(months_data) - 1):
            current = months_data[i]
            previous = months_data[i + 1]

            if current["metrics"] and previous["metrics"]:
                curr_m = current["metrics"]
                prev_m = previous["metrics"]

                mom_changes.append({
                    "period": f"{current['month_label']} vs {previous['month_label']}",
                    "revenue_change_pct": round(
                        (curr_m["total_revenue"] - prev_m["total_revenue"]) / prev_m["total_revenue"] * 100, 2
                    ) if prev_m["total_revenue"] > 0 else 0,
                    "gp_pct_change": round(curr_m["avg_gp_pct"] - prev_m["avg_gp_pct"], 2),
                    "ro_count_change_pct": round(
                        (curr_m["ro_count"] - prev_m["ro_count"]) / prev_m["ro_count"] * 100, 2
                    ) if prev_m["ro_count"] > 0 else 0,
                    "aro_change_pct": round(
                        (curr_m["aro"] - prev_m["aro"]) / prev_m["aro"] * 100, 2
                    ) if prev_m["aro"] > 0 else 0
                })

        return {
            "analysis_type": "month_over_month",
            "months_analyzed": len([m for m in months_data if m["metrics"]]),
            "months": months_data,
            "mom_changes": mom_changes,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ROLLING AVERAGES
# =============================================================================

@router.get("/rolling-averages")
async def get_rolling_averages(
    days: int = Query(30, description="Number of days of data", ge=14, le=90),
    short_window: int = Query(7, description="Short-term rolling window", ge=3, le=14),
    long_window: int = Query(14, description="Long-term rolling window", ge=7, le=30)
):
    """
    Calculate rolling averages for GP metrics.

    Returns short-term and long-term rolling averages for:
    - GP percentage
    - Daily revenue
    - ARO

    Useful for identifying trend crossovers and smoothing daily noise.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if len(snapshots) < short_window:
            return {
                "error": "Insufficient data",
                "message": f"Need at least {short_window} data points, have {len(snapshots)}",
                "recommendation": "Run POST /api/history/snapshot/daily to build historical data"
            }

        # Sort by date ascending for rolling calc
        snapshots.sort(key=lambda x: x.get("snapshot_date", ""))

        # Extract time series
        dates = [s.get("snapshot_date") for s in snapshots]
        gp_pcts = [s.get("gp_percentage", 0) for s in snapshots]
        revenues = [s.get("total_revenue", 0) for s in snapshots]
        aros = [s.get("aro_cents", 0) for s in snapshots]

        # Calculate rolling averages
        gp_short_ma = calculate_rolling_average(gp_pcts, short_window)
        gp_long_ma = calculate_rolling_average(gp_pcts, long_window)
        revenue_short_ma = calculate_rolling_average(revenues, short_window)
        revenue_long_ma = calculate_rolling_average(revenues, long_window)

        # Build time series response
        time_series = []
        for i, dt in enumerate(dates):
            time_series.append({
                "date": dt,
                "gp_pct": gp_pcts[i],
                "gp_ma_short": gp_short_ma[i],
                "gp_ma_long": gp_long_ma[i],
                "revenue": cents_to_dollars(revenues[i]),
                "revenue_ma_short": cents_to_dollars(int(revenue_short_ma[i])) if revenue_short_ma[i] else None,
                "revenue_ma_long": cents_to_dollars(int(revenue_long_ma[i])) if revenue_long_ma[i] else None,
                "aro": cents_to_dollars(aros[i])
            })

        # Trend signals
        signals = []
        if len(gp_short_ma) >= 2 and gp_short_ma[-1] and gp_long_ma[-1]:
            if gp_short_ma[-1] > gp_long_ma[-1] and (gp_short_ma[-2] or 0) <= (gp_long_ma[-2] or 0):
                signals.append("BULLISH: Short-term GP% crossed above long-term - positive momentum")
            elif gp_short_ma[-1] < gp_long_ma[-1] and (gp_short_ma[-2] or 0) >= (gp_long_ma[-2] or 0):
                signals.append("BEARISH: Short-term GP% crossed below long-term - watch for decline")

        # Current status
        latest_gp = gp_pcts[-1] if gp_pcts else 0
        latest_short_ma = gp_short_ma[-1] if gp_short_ma[-1] else 0
        latest_long_ma = gp_long_ma[-1] if gp_long_ma[-1] else 0

        return {
            "analysis_type": "rolling_averages",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "data_points": len(snapshots)
            },
            "windows": {
                "short_term": short_window,
                "long_term": long_window
            },
            "current_values": {
                "gp_pct_actual": latest_gp,
                "gp_pct_short_ma": latest_short_ma,
                "gp_pct_long_ma": latest_long_ma,
                "trend": "up" if latest_short_ma > latest_long_ma else "down"
            },
            "signals": signals,
            "time_series": time_series,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FORECASTING
# =============================================================================

@router.get("/forecast")
async def forecast_gp_metrics(
    days_history: int = Query(30, description="Days of history to use", ge=14, le=90),
    days_forecast: int = Query(7, description="Days to forecast", ge=1, le=30)
):
    """
    Forecast GP metrics using linear regression.

    Uses historical data to project future values for:
    - GP percentage
    - Daily revenue
    - ARO

    Includes confidence indicators based on R-squared values.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(days=days_history)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if len(snapshots) < 7:
            return {
                "error": "Insufficient data for forecasting",
                "message": f"Need at least 7 data points, have {len(snapshots)}",
                "recommendation": "Build more historical data first"
            }

        # Sort ascending
        snapshots.sort(key=lambda x: x.get("snapshot_date", ""))

        # Prepare data for regression
        x_values = list(range(len(snapshots)))
        gp_values = [s.get("gp_percentage", 0) for s in snapshots]
        revenue_values = [s.get("total_revenue", 0) for s in snapshots]
        aro_values = [s.get("aro_cents", 0) for s in snapshots]

        # Run regressions
        gp_regression = linear_regression(x_values, gp_values)
        revenue_regression = linear_regression(x_values, revenue_values)
        aro_regression = linear_regression(x_values, aro_values)

        # Generate forecasts
        forecasts = []
        last_x = len(snapshots) - 1

        for i in range(1, days_forecast + 1):
            forecast_x = last_x + i
            forecast_date = end_date + timedelta(days=i)

            gp_forecast = gp_regression["slope"] * forecast_x + gp_regression["intercept"]
            revenue_forecast = revenue_regression["slope"] * forecast_x + revenue_regression["intercept"]
            aro_forecast = aro_regression["slope"] * forecast_x + aro_regression["intercept"]

            forecasts.append({
                "date": forecast_date.isoformat(),
                "day_number": i,
                "gp_pct_forecast": round(max(0, min(100, gp_forecast)), 2),
                "revenue_forecast": cents_to_dollars(int(max(0, revenue_forecast))),
                "aro_forecast": cents_to_dollars(int(max(0, aro_forecast)))
            })

        # Confidence assessment
        def get_confidence(r_squared: float) -> str:
            if r_squared >= 0.7:
                return "high"
            elif r_squared >= 0.4:
                return "medium"
            else:
                return "low"

        # Trend descriptions
        gp_trend = "stable"
        if gp_regression["slope"] > 0.1:
            gp_trend = "increasing"
        elif gp_regression["slope"] < -0.1:
            gp_trend = "decreasing"

        return {
            "analysis_type": "forecast",
            "model": "linear_regression",
            "training_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "data_points": len(snapshots)
            },
            "forecast_period": {
                "start": (end_date + timedelta(days=1)).isoformat(),
                "end": (end_date + timedelta(days=days_forecast)).isoformat(),
                "days": days_forecast
            },
            "model_metrics": {
                "gp_pct": {
                    "slope_per_day": gp_regression["slope"],
                    "r_squared": gp_regression["r_squared"],
                    "confidence": get_confidence(gp_regression["r_squared"]),
                    "trend": gp_trend
                },
                "revenue": {
                    "slope_per_day": cents_to_dollars(int(revenue_regression["slope"])),
                    "r_squared": revenue_regression["r_squared"],
                    "confidence": get_confidence(revenue_regression["r_squared"])
                },
                "aro": {
                    "slope_per_day": cents_to_dollars(int(aro_regression["slope"])),
                    "r_squared": aro_regression["r_squared"],
                    "confidence": get_confidence(aro_regression["r_squared"])
                }
            },
            "forecasts": forecasts,
            "disclaimer": "Forecasts are based on historical trends and should be used as guidance only",
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DAY-OF-WEEK PATTERNS
# =============================================================================

@router.get("/day-patterns")
async def analyze_day_of_week_patterns(
    weeks: int = Query(8, description="Number of weeks to analyze", ge=4, le=26)
):
    """
    Analyze GP patterns by day of week.

    Identifies:
    - Which days have highest/lowest GP%
    - Which days have highest/lowest revenue
    - Consistency of patterns
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(weeks=weeks)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if len(snapshots) < weeks:
            return {
                "error": "Insufficient data",
                "message": f"Need more historical data for pattern analysis"
            }

        # Group by day of week
        by_day = defaultdict(list)

        for snapshot in snapshots:
            snap_date = date.fromisoformat(snapshot.get("snapshot_date"))
            day_of_week = snap_date.weekday()

            by_day[day_of_week].append({
                "gp_pct": snapshot.get("gp_percentage", 0),
                "revenue": snapshot.get("total_revenue", 0),
                "ro_count": snapshot.get("ro_count", 0),
                "aro": snapshot.get("aro_cents", 0)
            })

        # Calculate statistics per day
        day_stats = []
        for day_num in range(7):
            day_data = by_day.get(day_num, [])

            if day_data:
                gp_values = [d["gp_pct"] for d in day_data]
                revenue_values = [d["revenue"] for d in day_data]
                ro_values = [d["ro_count"] for d in day_data]

                day_stats.append({
                    "day_number": day_num,
                    "day_name": get_day_of_week_name(day_num),
                    "sample_count": len(day_data),
                    "gp_pct": {
                        "avg": round(statistics.mean(gp_values), 2),
                        "min": round(min(gp_values), 2),
                        "max": round(max(gp_values), 2),
                        "std_dev": round(statistics.stdev(gp_values), 2) if len(gp_values) > 1 else 0
                    },
                    "revenue": {
                        "avg": cents_to_dollars(int(statistics.mean(revenue_values))),
                        "min": cents_to_dollars(min(revenue_values)),
                        "max": cents_to_dollars(max(revenue_values))
                    },
                    "ro_count": {
                        "avg": round(statistics.mean(ro_values), 1),
                        "total": sum(ro_values)
                    }
                })
            else:
                day_stats.append({
                    "day_number": day_num,
                    "day_name": get_day_of_week_name(day_num),
                    "sample_count": 0,
                    "gp_pct": None,
                    "revenue": None,
                    "ro_count": None
                })

        # Find best/worst days
        valid_days = [d for d in day_stats if d["gp_pct"]]

        best_gp_day = max(valid_days, key=lambda x: x["gp_pct"]["avg"]) if valid_days else None
        worst_gp_day = min(valid_days, key=lambda x: x["gp_pct"]["avg"]) if valid_days else None
        busiest_day = max(valid_days, key=lambda x: x["revenue"]["avg"]) if valid_days else None
        slowest_day = min(valid_days, key=lambda x: x["revenue"]["avg"]) if valid_days else None

        insights = []
        if best_gp_day and worst_gp_day:
            gp_spread = best_gp_day["gp_pct"]["avg"] - worst_gp_day["gp_pct"]["avg"]
            if gp_spread > 3:
                insights.append(f"GP% varies by {gp_spread:.1f}% between {best_gp_day['day_name']} and {worst_gp_day['day_name']}")

        if busiest_day and slowest_day:
            insights.append(f"{busiest_day['day_name']} is typically the busiest day")
            insights.append(f"{slowest_day['day_name']} is typically the slowest day")

        return {
            "analysis_type": "day_of_week_patterns",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "weeks_analyzed": weeks
            },
            "by_day": day_stats,
            "highlights": {
                "best_gp_day": best_gp_day["day_name"] if best_gp_day else None,
                "best_gp_avg": best_gp_day["gp_pct"]["avg"] if best_gp_day else None,
                "worst_gp_day": worst_gp_day["day_name"] if worst_gp_day else None,
                "worst_gp_avg": worst_gp_day["gp_pct"]["avg"] if worst_gp_day else None,
                "busiest_day": busiest_day["day_name"] if busiest_day else None,
                "busiest_revenue_avg": busiest_day["revenue"]["avg"] if busiest_day else None
            },
            "insights": insights,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BEST/WORST DAYS ANALYSIS
# =============================================================================

@router.get("/extremes")
async def get_extreme_days(
    days: int = Query(90, description="Days to analyze", ge=30, le=365),
    top_n: int = Query(5, description="Number of best/worst to return", ge=3, le=10)
):
    """
    Find best and worst performing days.

    Returns top N best and worst days by:
    - GP percentage
    - Total revenue
    - ARO
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if not snapshots:
            return {
                "error": "No data available",
                "recommendation": "Run POST /api/history/snapshot/daily to build historical data"
            }

        # Convert snapshots for sorting
        days_data = []
        for s in snapshots:
            days_data.append({
                "date": s.get("snapshot_date"),
                "gp_pct": s.get("gp_percentage", 0),
                "revenue": s.get("total_revenue", 0),
                "gp_dollars": s.get("total_gp_dollars", 0),
                "ro_count": s.get("ro_count", 0),
                "aro": s.get("aro_cents", 0)
            })

        # Sort by different metrics
        by_gp_pct = sorted(days_data, key=lambda x: x["gp_pct"], reverse=True)
        by_revenue = sorted(days_data, key=lambda x: x["revenue"], reverse=True)
        by_aro = sorted(days_data, key=lambda x: x["aro"], reverse=True)

        def format_day(d):
            return {
                "date": d["date"],
                "gp_pct": d["gp_pct"],
                "revenue": cents_to_dollars(d["revenue"]),
                "gross_profit": cents_to_dollars(d["gp_dollars"]),
                "ro_count": d["ro_count"],
                "aro": cents_to_dollars(d["aro"])
            }

        return {
            "analysis_type": "extreme_days",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "total_days_analyzed": len(days_data)
            },
            "by_gp_percentage": {
                "best": [format_day(d) for d in by_gp_pct[:top_n]],
                "worst": [format_day(d) for d in by_gp_pct[-top_n:]]
            },
            "by_revenue": {
                "best": [format_day(d) for d in by_revenue[:top_n]],
                "worst": [format_day(d) for d in by_revenue[-top_n:]]
            },
            "by_aro": {
                "best": [format_day(d) for d in by_aro[:top_n]],
                "worst": [format_day(d) for d in by_aro[-top_n:]]
            },
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CATEGORY TRENDS
# =============================================================================

@router.get("/category-trends")
async def analyze_category_trends(
    days: int = Query(30, description="Days to analyze", ge=14, le=90)
):
    """
    Analyze trends by revenue category (parts, labor, sublet, fees).

    Shows how each category's contribution to GP has changed over time.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if len(snapshots) < 7:
            return {
                "error": "Insufficient data",
                "message": "Need at least 7 data points for trend analysis"
            }

        # Sort ascending
        snapshots.sort(key=lambda x: x.get("snapshot_date", ""))

        # Calculate category margins over time
        time_series = []

        for s in snapshots:
            parts_rev = s.get("parts_revenue", 0)
            parts_cost = s.get("parts_cost", 0)
            labor_rev = s.get("labor_revenue", 0)
            labor_cost = s.get("labor_cost", 0)

            time_series.append({
                "date": s.get("snapshot_date"),
                "parts_margin_pct": round((parts_rev - parts_cost) / parts_rev * 100, 2) if parts_rev > 0 else 0,
                "labor_margin_pct": round((labor_rev - labor_cost) / labor_rev * 100, 2) if labor_rev > 0 else 0,
                "parts_profit": cents_to_dollars(s.get("parts_profit", 0)),
                "labor_profit": cents_to_dollars(s.get("labor_profit", 0)),
                "total_gp": cents_to_dollars(s.get("total_gp_dollars", 0))
            })

        # Calculate averages for first half vs second half
        mid = len(time_series) // 2
        first_half = time_series[:mid]
        second_half = time_series[mid:]

        def avg_margin(data, key):
            values = [d[key] for d in data if d[key] is not None]
            return round(sum(values) / len(values), 2) if values else 0

        category_trends = {
            "parts": {
                "first_half_margin_avg": avg_margin(first_half, "parts_margin_pct"),
                "second_half_margin_avg": avg_margin(second_half, "parts_margin_pct"),
                "trend": "improving" if avg_margin(second_half, "parts_margin_pct") > avg_margin(first_half, "parts_margin_pct") else "declining"
            },
            "labor": {
                "first_half_margin_avg": avg_margin(first_half, "labor_margin_pct"),
                "second_half_margin_avg": avg_margin(second_half, "labor_margin_pct"),
                "trend": "improving" if avg_margin(second_half, "labor_margin_pct") > avg_margin(first_half, "labor_margin_pct") else "declining"
            }
        }

        # Calculate contribution to total GP
        total_parts_profit = sum(s.get("parts_profit", 0) for s in snapshots)
        total_labor_profit = sum(s.get("labor_profit", 0) for s in snapshots)
        total_sublet_profit = sum(s.get("sublet_profit", 0) for s in snapshots)
        total_fees = sum(s.get("fees_total", 0) for s in snapshots)

        total_gp = total_parts_profit + total_labor_profit + total_sublet_profit + total_fees

        contribution = {
            "parts": round(total_parts_profit / total_gp * 100, 1) if total_gp > 0 else 0,
            "labor": round(total_labor_profit / total_gp * 100, 1) if total_gp > 0 else 0,
            "sublet": round(total_sublet_profit / total_gp * 100, 1) if total_gp > 0 else 0,
            "fees": round(total_fees / total_gp * 100, 1) if total_gp > 0 else 0
        }

        return {
            "analysis_type": "category_trends",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "data_points": len(snapshots)
            },
            "category_trends": category_trends,
            "gp_contribution_pct": contribution,
            "time_series": time_series,
            "insights": [
                f"Parts contribute {contribution['parts']}% of total GP",
                f"Labor contributes {contribution['labor']}% of total GP",
                f"Parts margin is {category_trends['parts']['trend']}",
                f"Labor margin is {category_trends['labor']['trend']}"
            ],
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUMMARY DASHBOARD
# =============================================================================

@router.get("/summary")
async def get_trend_summary_dashboard(
    days: int = Query(30, description="Days to analyze", ge=7, le=90)
):
    """
    Comprehensive trend summary dashboard.

    Combines key metrics from all trend analyses into a single view.
    Ideal for executive dashboards.
    """
    try:
        client = await get_tm_client()
        shop_id = int(client.shop_id)
        persistence = get_persistence_service()

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = await persistence.get_daily_snapshots(shop_id, start_date, end_date)

        if not snapshots:
            return {
                "error": "No historical data",
                "recommendation": "Run POST /api/history/snapshot/daily to build data"
            }

        # Sort ascending for trend calc
        snapshots.sort(key=lambda x: x.get("snapshot_date", ""))

        # Current period totals
        total_revenue = sum(s.get("total_revenue", 0) for s in snapshots)
        total_gp = sum(s.get("total_gp_dollars", 0) for s in snapshots)
        total_ros = sum(s.get("ro_count", 0) for s in snapshots)
        avg_gp_pct = sum(s.get("gp_percentage", 0) for s in snapshots) / len(snapshots)

        # Trend calculation (regression)
        x_values = list(range(len(snapshots)))
        gp_values = [s.get("gp_percentage", 0) for s in snapshots]
        gp_reg = linear_regression(x_values, gp_values)

        # WoW quick calc
        today = date.today()
        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start - timedelta(days=1)

        this_week_snaps = [s for s in snapshots if s.get("snapshot_date", "") >= this_week_start.isoformat()]
        last_week_snaps = [s for s in snapshots
                          if last_week_start.isoformat() <= s.get("snapshot_date", "") <= last_week_end.isoformat()]

        this_week_gp = sum(s.get("gp_percentage", 0) for s in this_week_snaps) / len(this_week_snaps) if this_week_snaps else 0
        last_week_gp = sum(s.get("gp_percentage", 0) for s in last_week_snaps) / len(last_week_snaps) if last_week_snaps else 0

        return {
            "analysis_type": "trend_summary",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
                "data_points": len(snapshots)
            },
            "current_metrics": {
                "total_revenue": cents_to_dollars(total_revenue),
                "total_gross_profit": cents_to_dollars(total_gp),
                "avg_gp_pct": round(avg_gp_pct, 2),
                "total_ros": total_ros,
                "avg_daily_revenue": cents_to_dollars(int(total_revenue / len(snapshots))),
                "aro": cents_to_dollars(int(total_revenue / total_ros)) if total_ros > 0 else 0
            },
            "trend_indicators": {
                "gp_trend": "up" if gp_reg["slope"] > 0.05 else ("down" if gp_reg["slope"] < -0.05 else "stable"),
                "gp_slope_per_day": round(gp_reg["slope"], 3),
                "trend_confidence": "high" if gp_reg["r_squared"] > 0.5 else "low",
                "r_squared": gp_reg["r_squared"]
            },
            "week_over_week": {
                "this_week_gp_pct": round(this_week_gp, 2),
                "last_week_gp_pct": round(last_week_gp, 2),
                "change": round(this_week_gp - last_week_gp, 2)
            },
            "alerts": _generate_alerts(avg_gp_pct, gp_reg["slope"], this_week_gp - last_week_gp),
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_alerts(avg_gp: float, slope: float, wow_change: float) -> List[str]:
    """Generate actionable alerts based on trend analysis."""
    alerts = []

    if avg_gp < 45:
        alerts.append({"level": "critical", "message": f"GP% at {avg_gp:.1f}% - below 45% threshold"})
    elif avg_gp < 50:
        alerts.append({"level": "warning", "message": f"GP% at {avg_gp:.1f}% - below 50% target"})

    if slope < -0.1:
        alerts.append({"level": "warning", "message": "Downward GP trend detected - losing ~0.1% per day"})

    if wow_change < -2:
        alerts.append({"level": "warning", "message": f"WoW GP dropped {abs(wow_change):.1f}% - investigate recent changes"})
    elif wow_change > 2:
        alerts.append({"level": "info", "message": f"WoW GP improved {wow_change:.1f}% - document what's working"})

    if not alerts:
        alerts.append({"level": "info", "message": "All metrics within normal range"})

    return alerts
