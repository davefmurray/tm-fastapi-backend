"""
Analytics Endpoints - Tier 3 Implementation

Advanced analytics for GP performance tracking:
- Fix 3.1: Technician profit tracking
- Fix 3.2: Service advisor performance metrics
- Fix 3.3: Parts margin analysis by category
- Fix 3.4: Labor efficiency metrics
- Fix 3.5: Enhanced variance analysis
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List
from app.services.tm_client import get_tm_client
from app.services.gp_calculator import (
    calculate_ro_true_gp,
    get_shop_config,
    to_dict,
    to_dollars_dict,
    cents_to_dollars,
    aggregate_tech_performance,
    aggregate_parts_margin,
    aggregate_labor_efficiency,
    ROTrueGP
)

router = APIRouter()


async def _get_ro_results(
    tm_client,
    shop_id: str,
    start_date,
    end_date,
    shop_config
) -> List[ROTrueGP]:
    """Helper to fetch and calculate RO results for a date range."""
    all_ros = []
    for board in ["ACTIVE", "POSTED", "COMPLETE"]:
        try:
            ros_page = await tm_client.get(
                f"/api/shop/{shop_id}/job-board-group-by",
                {"board": board, "groupBy": "NONE", "page": 0, "size": 200}
            )
            all_ros.extend(ros_page)
        except:
            pass

    # Filter to recent ROs
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

    # Calculate GP for each RO
    ro_results = []
    for ro in recent_ros:
        try:
            estimate = await tm_client.get(f"/api/repair-order/{ro['id']}/estimate")

            # Check for authorized jobs in date range
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

            ro_gp = calculate_ro_true_gp(
                estimate,
                shop_config=shop_config,
                authorized_only=True
            )

            if ro_gp.total_retail > 0:
                ro_results.append(ro_gp)

        except Exception as e:
            print(f"[Analytics] Error processing RO {ro.get('id')}: {e}")
            continue

    return ro_results


@router.get("/tech-performance")
async def get_tech_performance(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Tier 3: Get technician performance metrics.

    Returns profit metrics per technician including:
    - Hours billed
    - Labor revenue and cost
    - Labor profit and margin %
    - GP per hour
    - Jobs and ROs worked
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        shop_config = await get_shop_config(tm, shop_id)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ro_results = await _get_ro_results(tm, shop_id, start_date, end_date, shop_config)

        # Aggregate tech performance
        tech_perf = aggregate_tech_performance(ro_results)

        # Convert to response format
        tech_list = []
        for tech_id, perf in tech_perf.items():
            tech_list.append({
                "tech_id": perf.tech_id,
                "tech_name": perf.tech_name,
                "hourly_rate": cents_to_dollars(perf.hourly_rate),
                "hours_billed": perf.hours_billed,
                "labor_revenue": cents_to_dollars(perf.labor_revenue),
                "labor_cost": cents_to_dollars(perf.labor_cost),
                "labor_profit": cents_to_dollars(perf.labor_profit),
                "labor_margin_pct": perf.labor_margin_pct,
                "gp_per_hour": cents_to_dollars(perf.gp_per_hour),
                "jobs_worked": perf.jobs_worked,
                "ros_worked": perf.ros_worked,
                "rate_source_counts": perf.rate_source_counts
            })

        # Sort by profit descending
        tech_list.sort(key=lambda x: x['labor_profit'], reverse=True)

        return {
            "date_range": {"start": start, "end": end},
            "technicians": tech_list,
            "summary": {
                "tech_count": len(tech_list),
                "total_hours": sum(t['hours_billed'] for t in tech_list),
                "total_labor_revenue": sum(t['labor_revenue'] for t in tech_list),
                "total_labor_profit": sum(t['labor_profit'] for t in tech_list),
                "ros_analyzed": len(ro_results)
            },
            "source": "TRUE_GP_TIER3",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parts-margin")
async def get_parts_margin_analysis(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Tier 3: Analyze parts margins.

    Returns:
    - Overall parts margin
    - Single vs multi-quantity comparison
    - Highest and lowest margin parts
    - Quantity distribution
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        shop_config = await get_shop_config(tm, shop_id)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ro_results = await _get_ro_results(tm, shop_id, start_date, end_date, shop_config)

        # Aggregate parts margin
        parts_analysis = aggregate_parts_margin(ro_results)

        # Convert highest/lowest to dollars
        def convert_part(p):
            return {
                'name': p['name'],
                'quantity': p['quantity'],
                'cost': cents_to_dollars(p['cost']),
                'retail': cents_to_dollars(p['retail']),
                'profit': cents_to_dollars(p['profit']),
                'margin_pct': p['margin_pct']
            }

        return {
            "date_range": {"start": start, "end": end},
            "summary": {
                "total_retail": cents_to_dollars(parts_analysis.total_parts_retail),
                "total_cost": cents_to_dollars(parts_analysis.total_parts_cost),
                "total_profit": cents_to_dollars(parts_analysis.total_parts_profit),
                "overall_margin_pct": parts_analysis.overall_margin_pct,
                "total_line_items": parts_analysis.total_line_items,
                "avg_quantity": parts_analysis.avg_quantity
            },
            "by_quantity": {
                "single_items": {
                    "count": parts_analysis.single_items.get('count', 0),
                    "retail": cents_to_dollars(parts_analysis.single_items.get('retail', 0)),
                    "cost": cents_to_dollars(parts_analysis.single_items.get('cost', 0)),
                    "profit": cents_to_dollars(parts_analysis.single_items.get('profit', 0)),
                    "margin_pct": parts_analysis.single_items.get('margin_pct', 0)
                },
                "multi_items": {
                    "count": parts_analysis.multi_items.get('count', 0),
                    "retail": cents_to_dollars(parts_analysis.multi_items.get('retail', 0)),
                    "cost": cents_to_dollars(parts_analysis.multi_items.get('cost', 0)),
                    "profit": cents_to_dollars(parts_analysis.multi_items.get('profit', 0)),
                    "margin_pct": parts_analysis.multi_items.get('margin_pct', 0)
                }
            },
            "highest_margin_parts": [convert_part(p) for p in parts_analysis.highest_margin_parts],
            "lowest_margin_parts": [convert_part(p) for p in parts_analysis.lowest_margin_parts],
            "ros_analyzed": len(ro_results),
            "source": "TRUE_GP_TIER3",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labor-efficiency")
async def get_labor_efficiency(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Tier 3: Analyze labor efficiency metrics.

    Returns:
    - Total hours, revenue, cost, profit
    - Average retail and tech cost rates
    - Effective spread (retail - cost)
    - Breakdown by rate source (assigned, shop_average, default)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        shop_config = await get_shop_config(tm, shop_id)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ro_results = await _get_ro_results(tm, shop_id, start_date, end_date, shop_config)

        # Aggregate labor efficiency
        labor_eff = aggregate_labor_efficiency(ro_results)

        # Convert rate sources to dollars
        by_source = {}
        for source, data in labor_eff.by_rate_source.items():
            by_source[source] = {
                'hours': round(data['hours'], 2),
                'revenue': cents_to_dollars(data['revenue']),
                'cost': cents_to_dollars(data['cost']),
                'profit': cents_to_dollars(data['revenue'] - data['cost']),
                'margin_pct': data.get('margin_pct', 0),
                'count': data['count']
            }

        return {
            "date_range": {"start": start, "end": end},
            "summary": {
                "total_hours_billed": labor_eff.total_hours_billed,
                "total_revenue": cents_to_dollars(labor_eff.total_labor_revenue),
                "total_cost": cents_to_dollars(labor_eff.total_labor_cost),
                "total_profit": cents_to_dollars(labor_eff.total_labor_profit),
                "overall_margin_pct": labor_eff.overall_margin_pct,
                "total_labor_items": labor_eff.total_labor_items
            },
            "rates": {
                "avg_retail_rate": cents_to_dollars(labor_eff.avg_retail_rate),
                "avg_tech_cost_rate": cents_to_dollars(labor_eff.avg_tech_cost_rate),
                "effective_spread": cents_to_dollars(labor_eff.effective_spread),
                "gp_per_hour": cents_to_dollars(int(labor_eff.total_labor_profit / labor_eff.total_hours_billed)) if labor_eff.total_hours_billed > 0 else 0
            },
            "by_rate_source": by_source,
            "rate_source_note": {
                "assigned": "Tech rate from labor assignment",
                "shop_average": "Fallback to shop average tech rate",
                "default": "Fallback to $25/hr default"
            },
            "ros_analyzed": len(ro_results),
            "source": "TRUE_GP_TIER3",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variance-analysis")
async def get_variance_analysis(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Tier 3: Enhanced variance analysis between TM aggregates and true calculations.

    Identifies and explains differences between:
    - TM's dashboard aggregates
    - True GP calculations (Tier 2)

    Returns detailed variance breakdown with explanations.
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

        # Get TM aggregates
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

        # Get true calculations
        shop_config = await get_shop_config(tm, shop_id)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ro_results = await _get_ro_results(tm, shop_id, start_date, end_date, shop_config)

        # Aggregate true metrics
        true_sales = sum(ro.total_retail for ro in ro_results)
        true_cost = sum(ro.total_cost for ro in ro_results)
        true_gp = sum(ro.gross_profit for ro in ro_results)
        true_car_count = len(ro_results)
        true_gp_pct = (true_gp / true_sales * 100) if true_sales > 0 else 0
        true_aro = (true_sales // true_car_count) if true_car_count > 0 else 0

        # TM values
        tm_sold = tm_summary.get("sold", 0)
        tm_car_count = tm_summary.get("carCount", 0)
        tm_aro = int(tm_summary.get("averageRo", 0) * 100)  # Convert to cents

        # Calculate deltas
        sales_delta = true_sales - tm_sold
        car_count_delta = true_car_count - tm_car_count
        aro_delta = true_aro - tm_aro

        # Variance reasons
        variance_reasons = []

        if abs(car_count_delta) > 0:
            variance_reasons.append(
                f"Car count differs by {car_count_delta}: TM uses postedDate, we use authorizedDate"
            )

        if abs(sales_delta) > 1000:  # More than $10 difference
            variance_reasons.append(
                f"Sales differ by ${abs(sales_delta)/100:.2f}: Check date filtering and RO inclusion criteria"
            )

        # Check rate source distribution
        labor_eff = aggregate_labor_efficiency(ro_results)
        assigned_count = labor_eff.by_rate_source.get('assigned', {}).get('count', 0)
        fallback_count = (
            labor_eff.by_rate_source.get('shop_average', {}).get('count', 0) +
            labor_eff.by_rate_source.get('default', {}).get('count', 0)
        )

        if fallback_count > 0:
            variance_reasons.append(
                f"Tech rate fallback used for {fallback_count}/{assigned_count + fallback_count} labor items - affects GP calculation"
            )

        # Check parts quantity issues
        parts_analysis = aggregate_parts_margin(ro_results)
        multi_count = parts_analysis.multi_items.get('count', 0)
        if multi_count > 0:
            variance_reasons.append(
                f"{multi_count} parts with qty > 1 - potential TM quantity handling issues"
            )

        # Fee profit
        total_fee_profit = sum(ro.fee_profit for ro in ro_results)
        if total_fee_profit > 0:
            variance_reasons.append(
                f"Fee profit of ${total_fee_profit/100:.2f} included (100% margin) - may not match TM GP"
            )

        return {
            "date_range": {"start": start, "end": end},
            "tm_aggregates": {
                "sales": cents_to_dollars(tm_sold),
                "car_count": tm_car_count,
                "average_ro": cents_to_dollars(tm_aro),
                "source": "TM Dashboard API"
            },
            "true_calculations": {
                "sales": cents_to_dollars(true_sales),
                "cost": cents_to_dollars(true_cost),
                "gross_profit": cents_to_dollars(true_gp),
                "gp_percentage": round(true_gp_pct, 2),
                "car_count": true_car_count,
                "average_ro": cents_to_dollars(true_aro),
                "source": "TRUE_GP_TIER3"
            },
            "variance": {
                "sales_delta": cents_to_dollars(sales_delta),
                "sales_delta_pct": round(sales_delta / tm_sold * 100, 2) if tm_sold > 0 else 0,
                "car_count_delta": car_count_delta,
                "aro_delta": cents_to_dollars(aro_delta)
            },
            "variance_reasons": variance_reasons,
            "analysis_details": {
                "labor_rate_sources": {
                    "assigned": labor_eff.by_rate_source.get('assigned', {}).get('count', 0),
                    "shop_average": labor_eff.by_rate_source.get('shop_average', {}).get('count', 0),
                    "default": labor_eff.by_rate_source.get('default', {}).get('count', 0)
                },
                "parts_by_quantity": {
                    "single": parts_analysis.single_items.get('count', 0),
                    "multi": multi_count
                },
                "fee_profit_included": cents_to_dollars(total_fee_profit)
            },
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-analysis")
async def get_full_analysis(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Tier 3: Complete analysis combining all metrics.

    Returns a comprehensive report with:
    - True GP metrics
    - Tech performance
    - Parts margin analysis
    - Labor efficiency
    - Category breakdowns
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        shop_config = await get_shop_config(tm, shop_id)
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()

        ro_results = await _get_ro_results(tm, shop_id, start_date, end_date, shop_config)

        # Aggregate all metrics
        total_sales = sum(ro.total_retail for ro in ro_results)
        total_cost = sum(ro.total_cost for ro in ro_results)
        total_gp = sum(ro.gross_profit for ro in ro_results)

        tech_perf = aggregate_tech_performance(ro_results)
        parts_analysis = aggregate_parts_margin(ro_results)
        labor_eff = aggregate_labor_efficiency(ro_results)

        # Top techs
        top_techs = sorted(
            [{"name": p.tech_name, "profit": cents_to_dollars(p.labor_profit), "hours": p.hours_billed}
             for p in tech_perf.values()],
            key=lambda x: x['profit'],
            reverse=True
        )[:5]

        return {
            "date_range": {"start": start, "end": end},
            "summary": {
                "total_sales": cents_to_dollars(total_sales),
                "total_cost": cents_to_dollars(total_cost),
                "gross_profit": cents_to_dollars(total_gp),
                "gp_percentage": round(total_gp / total_sales * 100, 2) if total_sales > 0 else 0,
                "car_count": len(ro_results),
                "aro": cents_to_dollars(total_sales // len(ro_results)) if ro_results else 0
            },
            "category_breakdown": {
                "parts": {
                    "revenue": cents_to_dollars(parts_analysis.total_parts_retail),
                    "cost": cents_to_dollars(parts_analysis.total_parts_cost),
                    "profit": cents_to_dollars(parts_analysis.total_parts_profit),
                    "margin_pct": parts_analysis.overall_margin_pct
                },
                "labor": {
                    "revenue": cents_to_dollars(labor_eff.total_labor_revenue),
                    "cost": cents_to_dollars(labor_eff.total_labor_cost),
                    "profit": cents_to_dollars(labor_eff.total_labor_profit),
                    "margin_pct": labor_eff.overall_margin_pct,
                    "hours": labor_eff.total_hours_billed
                },
                "fees": {
                    "revenue": cents_to_dollars(sum(ro.fee_profit for ro in ro_results)),
                    "cost": 0,
                    "profit": cents_to_dollars(sum(ro.fee_profit for ro in ro_results)),
                    "margin_pct": 100.0
                }
            },
            "top_technicians": top_techs,
            "labor_rate_effectiveness": {
                "avg_retail_rate": cents_to_dollars(labor_eff.avg_retail_rate),
                "avg_cost_rate": cents_to_dollars(labor_eff.avg_tech_cost_rate),
                "spread": cents_to_dollars(labor_eff.effective_spread),
                "gp_per_hour": cents_to_dollars(int(labor_eff.total_labor_profit / labor_eff.total_hours_billed)) if labor_eff.total_hours_billed > 0 else 0
            },
            "parts_insights": {
                "total_line_items": parts_analysis.total_line_items,
                "avg_quantity": parts_analysis.avg_quantity,
                "multi_qty_items": parts_analysis.multi_items.get('count', 0)
            },
            "source": "TRUE_GP_TIER3",
            "calculated_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
