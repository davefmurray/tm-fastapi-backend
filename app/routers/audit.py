"""
Data Audit Endpoints

Systematic audit of RO data across all endpoints to identify discrepancies.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.services.tm_client import get_tm_client

router = APIRouter()


def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars"""
    return round((cents or 0) / 100, 2)


def safe_get(obj: dict, *keys, default=0):
    """Safely get nested dict values"""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        else:
            return default
    return obj if obj is not None else default


@router.get("/daily")
async def audit_daily_ros(
    date: Optional[str] = Query(None, description="Date to audit (YYYY-MM-DD), defaults to today")
):
    """
    Full audit of all ROs for a specific day.

    Fetches from multiple endpoints, compares values, and identifies discrepancies.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    # Default to today
    if date:
        audit_date = datetime.fromisoformat(date).date()
    else:
        audit_date = datetime.now().date()

    audit_results = {
        "audit_date": audit_date.isoformat(),
        "audit_timestamp": datetime.now().isoformat(),
        "ros_audited": 0,
        "discrepancies_found": 0,
        "ros": [],
        "summary": {
            "total_issues": 0,
            "parts_math_errors": 0,
            "labor_math_errors": 0,
            "sum_mismatches": 0,
            "tax_mismatches": 0,
            "gp_mismatches": 0,
            "missing_data": 0,
            "cross_endpoint_disagreements": 0
        },
        "endpoint_trust": {}
    }

    try:
        # Fetch ROs from all boards
        all_ros = []
        for board in ["ACTIVE", "POSTED", "COMPLETE"]:
            try:
                ros_page = await tm.get(
                    f"/api/shop/{shop_id}/job-board-group-by",
                    {"board": board, "groupBy": "NONE", "page": 0, "size": 500}
                )
                for ro in ros_page:
                    ro["_board"] = board
                all_ros.extend(ros_page)
            except Exception as e:
                audit_results["endpoint_trust"][f"job-board-{board}"] = f"ERROR: {str(e)}"

        # Deduplicate by RO ID
        seen_ids = set()
        unique_ros = []
        for ro in all_ros:
            ro_id = ro.get("id")
            if ro_id and ro_id not in seen_ids:
                seen_ids.add(ro_id)
                unique_ros.append(ro)

        # Filter to ROs with activity on audit date
        # Check: createdDate, updatedDate, postedDate, or job authorizedDate
        ros_for_date = []
        for ro in unique_ros:
            # Check various date fields
            dates_to_check = [
                ro.get("createdDate"),
                ro.get("updatedDate"),
                ro.get("postedDate")
            ]

            for date_str in dates_to_check:
                if date_str:
                    try:
                        ro_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
                        if ro_date == audit_date:
                            ros_for_date.append(ro)
                            break
                    except:
                        pass

        # Audit each RO
        for ro in ros_for_date:
            ro_audit = await audit_single_ro(tm, ro, audit_date)
            audit_results["ros"].append(ro_audit)
            audit_results["ros_audited"] += 1

            # Count discrepancies
            if ro_audit.get("discrepancies"):
                audit_results["discrepancies_found"] += len(ro_audit["discrepancies"])
                for disc in ro_audit["discrepancies"]:
                    disc_type = disc.get("type", "unknown")
                    if disc_type in audit_results["summary"]:
                        audit_results["summary"][disc_type] += 1
                    audit_results["summary"]["total_issues"] += 1

        return audit_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def audit_single_ro(tm, ro_summary: dict, audit_date) -> dict:
    """
    Audit a single RO by fetching from multiple endpoints and comparing.
    """
    ro_id = ro_summary.get("id")
    ro_number = ro_summary.get("roNumber") or ro_summary.get("repairOrderNumber")

    audit_record = {
        "ro_id": ro_id,
        "ro_number": ro_number,
        "board": ro_summary.get("_board"),
        "discrepancies": [],
        "data_sources": {},
        "calculated_values": {},
        "comparison": {}
    }

    # Source 1: Job Board Summary Data
    audit_record["data_sources"]["job_board"] = {
        "total": ro_summary.get("total"),
        "subtotal": ro_summary.get("subtotal"),
        "authorized_total": ro_summary.get("authorizedTotal"),
        "amount_paid": ro_summary.get("amountPaid"),
        "status": ro_summary.get("status"),
        "posted_date": ro_summary.get("postedDate"),
        "updated_date": ro_summary.get("updatedDate")
    }

    # Source 2: Full Estimate
    try:
        estimate = await tm.get(f"/api/repair-order/{ro_id}/estimate")
        audit_record["data_sources"]["estimate"] = {
            "raw_total": estimate.get("total"),
            "raw_subtotal": estimate.get("subtotal"),
            "raw_authorized_total": estimate.get("authorizedTotal"),
            "raw_tax": estimate.get("tax"),
            "raw_discount": estimate.get("discount"),
            "job_count": len(estimate.get("jobs", []))
        }

        # Extract customer/vehicle
        customer = estimate.get("customer", {})
        vehicle = estimate.get("vehicle", {})
        audit_record["customer"] = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip() or "Unknown"
        audit_record["vehicle"] = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip() or "N/A"

        # Audit each job
        jobs_audit = []
        total_parts_calc = 0
        total_labor_calc = 0
        total_fees_calc = 0
        total_discount_calc = 0
        total_parts_cost = 0
        total_labor_cost = 0

        for job in estimate.get("jobs", []):
            job_audit = audit_job(job, audit_record["discrepancies"])
            jobs_audit.append(job_audit)

            total_parts_calc += job_audit["parts_total_calc"]
            total_labor_calc += job_audit["labor_total_calc"]
            total_fees_calc += job_audit["fees_total_calc"]
            total_discount_calc += job_audit.get("discount", 0)
            total_parts_cost += job_audit["parts_cost_calc"]
            total_labor_cost += job_audit["labor_cost_calc"]

        audit_record["jobs"] = jobs_audit

        # Calculate totals from line items
        subtotal_calc = total_parts_calc + total_labor_calc + total_fees_calc - total_discount_calc
        total_cost_calc = total_parts_cost + total_labor_cost
        gp_calc = (total_parts_calc + total_labor_calc) - total_cost_calc

        audit_record["calculated_values"] = {
            "parts_total": cents_to_dollars(total_parts_calc),
            "labor_total": cents_to_dollars(total_labor_calc),
            "fees_total": cents_to_dollars(total_fees_calc),
            "discount_total": cents_to_dollars(total_discount_calc),
            "subtotal": cents_to_dollars(subtotal_calc),
            "parts_cost": cents_to_dollars(total_parts_cost),
            "labor_cost": cents_to_dollars(total_labor_cost),
            "total_cost": cents_to_dollars(total_cost_calc),
            "gross_profit": cents_to_dollars(gp_calc),
            "gp_pct": round(gp_calc / subtotal_calc * 100, 2) if subtotal_calc > 0 else 0
        }

        # Compare with reported values
        # NOTE: TM often returns subtotal=null, so use total or authorizedTotal as fallback
        estimate_subtotal = estimate.get("subtotal") or 0
        estimate_total = estimate.get("total") or 0
        estimate_authorized = estimate.get("authorizedTotal") or 0

        # Use the best available comparison value
        # Priority: subtotal > total > authorizedTotal
        comparison_value = estimate_subtotal if estimate_subtotal else estimate_total
        comparison_field = "subtotal" if estimate_subtotal else "total"

        audit_record["comparison"]["subtotal"] = {
            "calculated": cents_to_dollars(subtotal_calc),
            "estimate_subtotal": cents_to_dollars(estimate_subtotal),
            "estimate_total": cents_to_dollars(estimate_total),
            "estimate_authorized": cents_to_dollars(estimate_authorized),
            "compared_against": comparison_field,
            "difference": cents_to_dollars(subtotal_calc - comparison_value),
            "match": abs(subtotal_calc - comparison_value) < 100  # Within $1
        }

        # Only flag discrepancy if we have a valid comparison and it doesn't match
        if comparison_value > 0 and not audit_record["comparison"]["subtotal"]["match"]:
            audit_record["discrepancies"].append({
                "type": "sum_mismatches",
                "field": comparison_field,
                "calculated": cents_to_dollars(subtotal_calc),
                "reported": cents_to_dollars(comparison_value),
                "difference": cents_to_dollars(subtotal_calc - comparison_value),
                "suspected_cause": f"Line item sum doesn't match estimate {comparison_field}"
            })

    except Exception as e:
        audit_record["data_sources"]["estimate"] = {"error": str(e)}

    # Source 3: Profit/Labor endpoint
    # NOTE: API uses camelCase and returns nested objects:
    # - laborProfit: { hours, retail, cost, profit, margin }
    # - totalProfit: { retail, cost, profit, margin }
    # - partsProfit is NOT returned - calculate as (total - labor)
    try:
        profit_labor = await tm.get(f"/api/repair-order/{ro_id}/profit/labor")

        # Extract from nested structure (camelCase keys!)
        labor_obj = profit_labor.get("laborProfit", {}) or {}
        total_obj = profit_labor.get("totalProfit", {}) or {}

        # Calculate parts from total - labor (no explicit partsProfit field)
        labor_revenue = labor_obj.get("retail") or 0
        total_revenue = total_obj.get("retail") or 0
        parts_revenue_implied = total_revenue - labor_revenue

        labor_cost = labor_obj.get("cost") or 0
        total_cost = total_obj.get("cost") or 0
        parts_cost_implied = total_cost - labor_cost

        audit_record["data_sources"]["profit_labor"] = {
            "labor_revenue": labor_revenue,
            "labor_cost": labor_cost,
            "labor_profit": labor_obj.get("profit"),
            "labor_margin": labor_obj.get("margin"),
            "parts_revenue": parts_revenue_implied,
            "parts_cost": parts_cost_implied,
            "parts_profit": (total_obj.get("profit") or 0) - (labor_obj.get("profit") or 0),
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_profit": total_obj.get("profit"),
            "total_margin": total_obj.get("margin")
        }

        # Compare profit/labor values with our calculations
        if "calculated_values" in audit_record:
            calc = audit_record["calculated_values"]

            # Check labor revenue
            labor_rev_calc = int(calc["labor_total"] * 100)
            if abs(labor_revenue - labor_rev_calc) > 100:
                audit_record["discrepancies"].append({
                    "type": "cross_endpoint_disagreements",
                    "field": "labor_revenue",
                    "calculated": cents_to_dollars(labor_rev_calc),
                    "profit_labor_reported": cents_to_dollars(labor_revenue),
                    "difference": cents_to_dollars(labor_rev_calc - labor_revenue),
                    "suspected_cause": "profit/labor endpoint disagrees with line item sum"
                })

            # Check parts revenue (implied from total - labor)
            parts_rev_calc = int(calc["parts_total"] * 100)
            if abs(parts_revenue_implied - parts_rev_calc) > 100:
                audit_record["discrepancies"].append({
                    "type": "cross_endpoint_disagreements",
                    "field": "parts_revenue",
                    "calculated": cents_to_dollars(parts_rev_calc),
                    "profit_labor_reported": cents_to_dollars(parts_revenue_implied),
                    "difference": cents_to_dollars(parts_rev_calc - parts_revenue_implied),
                    "suspected_cause": "profit/labor endpoint disagrees with line item sum"
                })

    except Exception as e:
        audit_record["data_sources"]["profit_labor"] = {"error": str(e)}

    # Source 4: Basic RO endpoint
    try:
        ro_basic = await tm.get(f"/api/repair-order/{ro_id}")
        audit_record["data_sources"]["ro_basic"] = {
            "status": ro_basic.get("status"),
            "advisor_id": safe_get(ro_basic, "serviceAdvisor", "id"),
            "advisor_name": f"{safe_get(ro_basic, 'serviceAdvisor', 'firstName', default='')} {safe_get(ro_basic, 'serviceAdvisor', 'lastName', default='')}".strip()
        }
        audit_record["advisor"] = audit_record["data_sources"]["ro_basic"]["advisor_name"] or "Unassigned"
    except Exception as e:
        audit_record["data_sources"]["ro_basic"] = {"error": str(e)}

    return audit_record


def audit_job(job: dict, discrepancies: list) -> dict:
    """
    Audit a single job's line items.
    """
    job_audit = {
        "job_id": job.get("id"),
        "job_name": job.get("name"),
        "authorized": job.get("authorized"),
        "authorized_date": job.get("authorizedDate"),
        "parts": [],
        "labor": [],
        "fees": [],
        "discount": job.get("discount", 0),
        "parts_total_calc": 0,
        "labor_total_calc": 0,
        "fees_total_calc": 0,
        "parts_cost_calc": 0,
        "labor_cost_calc": 0,
        "parts_issues": [],
        "labor_issues": []
    }

    # Audit parts
    for part in job.get("parts", []):
        part_id = part.get("id")
        part_name = part.get("name", "Unknown Part")
        qty = part.get("quantity", 1)
        retail = part.get("retail", 0)
        cost = part.get("cost", 0)
        total_reported = part.get("total", 0)

        # Calculate expected total
        total_calc = qty * retail

        part_record = {
            "id": part_id,
            "name": part_name,
            "qty": qty,
            "retail": cents_to_dollars(retail),
            "cost": cents_to_dollars(cost),
            "total_reported": cents_to_dollars(total_reported),
            "total_calculated": cents_to_dollars(total_calc),
            "match": abs(total_calc - total_reported) < 10  # Within 10 cents
        }
        job_audit["parts"].append(part_record)

        job_audit["parts_total_calc"] += total_calc
        job_audit["parts_cost_calc"] += qty * cost

        # Check for math error
        if not part_record["match"]:
            issue = {
                "type": "parts_math_errors",
                "job": job.get("name"),
                "part": part_name,
                "qty": qty,
                "retail": cents_to_dollars(retail),
                "expected": cents_to_dollars(total_calc),
                "reported": cents_to_dollars(total_reported),
                "suspected_cause": f"qty({qty}) × retail(${retail/100:.2f}) = ${total_calc/100:.2f}, but reported ${total_reported/100:.2f}"
            }
            job_audit["parts_issues"].append(issue)
            discrepancies.append(issue)

    # Audit labor
    for labor in job.get("labor", []):
        labor_id = labor.get("id")
        labor_name = labor.get("name", "Labor")
        hours = labor.get("hours", 0)
        rate = labor.get("rate", 0)
        total_reported = labor.get("total", 0)
        tech = labor.get("technician", {})
        tech_id = tech.get("id") if tech else None
        tech_name = f"{tech.get('firstName', '')} {tech.get('lastName', '')}".strip() if tech else None

        # Calculate expected total
        total_calc = int(hours * rate)

        labor_record = {
            "id": labor_id,
            "name": labor_name,
            "hours": hours,
            "rate": cents_to_dollars(rate),
            "total_reported": cents_to_dollars(total_reported),
            "total_calculated": cents_to_dollars(total_calc),
            "tech_id": tech_id,
            "tech_name": tech_name or "Unassigned",
            "match": abs(total_calc - total_reported) < 10
        }
        job_audit["labor"].append(labor_record)

        job_audit["labor_total_calc"] += total_calc

        # Estimate labor cost (if tech assigned, use their rate; otherwise flag)
        if tech_id:
            # We'd need tech rate here - for now estimate at $25/hr
            job_audit["labor_cost_calc"] += int(hours * 2500)
        else:
            job_audit["labor_cost_calc"] += int(hours * 2500)  # Default
            discrepancies.append({
                "type": "missing_data",
                "job": job.get("name"),
                "field": "technician",
                "labor_line": labor_name,
                "suspected_cause": "No technician assigned to labor line"
            })

        if not labor_record["match"]:
            issue = {
                "type": "labor_math_errors",
                "job": job.get("name"),
                "labor": labor_name,
                "hours": hours,
                "rate": cents_to_dollars(rate),
                "expected": cents_to_dollars(total_calc),
                "reported": cents_to_dollars(total_reported),
                "suspected_cause": f"hours({hours}) × rate(${rate/100:.2f}) = ${total_calc/100:.2f}, but reported ${total_reported/100:.2f}"
            }
            job_audit["labor_issues"].append(issue)
            discrepancies.append(issue)

    # Audit fees
    for fee in job.get("fees", []):
        fee_record = {
            "name": fee.get("name", "Fee"),
            "total": fee.get("total", 0)
        }
        job_audit["fees"].append(fee_record)
        job_audit["fees_total_calc"] += fee.get("total", 0)

    return job_audit


@router.get("/ro/{ro_id}")
async def audit_single_ro_by_id(ro_id: int):
    """
    Deep audit of a single RO by ID.
    """
    tm = get_tm_client()
    await tm._ensure_token()

    # Create a minimal ro_summary
    ro_summary = {"id": ro_id, "_board": "UNKNOWN"}

    try:
        audit_record = await audit_single_ro(tm, ro_summary, datetime.now().date())
        return audit_record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/date-range")
async def audit_date_range(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Audit all ROs in a date range, day by day.
    Returns summary of discrepancies across all days.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()

    range_results = {
        "start_date": start,
        "end_date": end,
        "days_audited": 0,
        "total_ros": 0,
        "total_discrepancies": 0,
        "daily_summaries": [],
        "recurring_patterns": [],
        "endpoint_reliability": {}
    }

    current_date = end_date
    while current_date >= start_date:
        # Audit this day
        day_result = await audit_daily_ros(date=current_date.isoformat())

        range_results["days_audited"] += 1
        range_results["total_ros"] += day_result["ros_audited"]
        range_results["total_discrepancies"] += day_result["discrepancies_found"]

        range_results["daily_summaries"].append({
            "date": current_date.isoformat(),
            "ros_audited": day_result["ros_audited"],
            "discrepancies": day_result["discrepancies_found"],
            "summary": day_result["summary"]
        })

        current_date -= timedelta(days=1)

    return range_results


@router.get("/today")
async def audit_today_ros(
    days_back: int = Query(0, description="Days back from today (0=today, 1=yesterday, etc.)")
):
    """
    Daily RO Audit View - The backbone for the owner dashboard.

    Returns every RO for the selected day with:
    - Clear separation of POTENTIAL vs AUTHORIZED metrics
    - Per-RO breakdown of revenue, profit, labor, parts
    - Discrepancy flags for dashboard alerts
    - Data shaped for direct frontend consumption

    This endpoint follows the Metric Contracts defined in METRIC_CONTRACTS.md
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    # Calculate target date
    target_date = (datetime.now() - timedelta(days=days_back)).date()

    # Build date range for TM queries (full day in ET timezone)
    start_dt = f"{target_date}T00:00:00.000-05:00"
    end_dt = f"{target_date}T23:59:59.999-05:00"

    result = {
        "date": target_date.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "days_back": days_back,

        # Summary totals (for KPI cards)
        "totals": {
            "potential": {
                "revenue": 0,
                "parts": 0,
                "labor": 0,
                "fees": 0,
                "discount": 0,
                "ro_count": 0,
                "job_count": 0
            },
            "authorized": {
                "revenue": 0,
                "parts": 0,
                "labor": 0,
                "profit": 0,
                "gp_percent": 0,
                "ro_count": 0,
                "job_count": 0
            },
            "pending": {
                "revenue": 0,
                "job_count": 0
            }
        },

        # Per-RO details
        "ros": [],

        # Issues summary
        "issues": {
            "total": 0,
            "ros_with_issues": 0,
            "by_type": {
                "missing_tech": 0,
                "subtotal_null": 0,
                "profit_mismatch": 0,
                "ro_404": 0
            }
        }
    }

    # Fetch all ROs from all boards
    all_ros = []
    seen_ids = set()

    for board in ["ACTIVE", "POSTED", "COMPLETE"]:
        try:
            ros_page = await tm.get(
                f"/api/shop/{shop_id}/job-board-group-by",
                {"board": board, "groupBy": "NONE", "page": 0, "size": 500}
            )
            for ro in ros_page:
                ro_id = ro.get("id")
                if ro_id and ro_id not in seen_ids:
                    seen_ids.add(ro_id)
                    ro["_board"] = board
                    all_ros.append(ro)
        except Exception as e:
            print(f"[Audit] Error fetching {board} board: {e}")

    # Filter to ROs with activity on target date
    # Check updatedDate, postedDate, or job authorizedDate
    for ro_summary in all_ros:
        ro_id = ro_summary.get("id")

        # Check if RO has activity on target date
        has_activity = False
        dates_to_check = [
            ro_summary.get("updatedDate"),
            ro_summary.get("postedDate"),
            ro_summary.get("createdDate")
        ]

        for date_str in dates_to_check:
            if date_str:
                try:
                    ro_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
                    if ro_date == target_date:
                        has_activity = True
                        break
                except:
                    pass

        if not has_activity:
            continue

        # Build detailed RO record
        ro_record = await build_ro_audit_record(tm, ro_id, ro_summary, target_date)

        if ro_record:
            result["ros"].append(ro_record)

            # Aggregate totals
            pot = ro_record["potential"]
            auth = ro_record["authorized"]

            result["totals"]["potential"]["revenue"] += pot["revenue"]
            result["totals"]["potential"]["parts"] += pot["parts"]
            result["totals"]["potential"]["labor"] += pot["labor"]
            result["totals"]["potential"]["fees"] += pot["fees"]
            result["totals"]["potential"]["discount"] += pot["discount"]
            result["totals"]["potential"]["job_count"] += pot["job_count"]
            result["totals"]["potential"]["ro_count"] += 1

            result["totals"]["authorized"]["revenue"] += auth["revenue"]
            result["totals"]["authorized"]["parts"] += auth["parts"]
            result["totals"]["authorized"]["labor"] += auth["labor"]
            result["totals"]["authorized"]["profit"] += auth["profit"]
            result["totals"]["authorized"]["job_count"] += auth["job_count"]
            if auth["revenue"] > 0:
                result["totals"]["authorized"]["ro_count"] += 1

            result["totals"]["pending"]["revenue"] += pot["revenue"] - auth["revenue"]
            result["totals"]["pending"]["job_count"] += pot["job_count"] - auth["job_count"]

            # Count issues
            if ro_record["issues"]:
                result["issues"]["ros_with_issues"] += 1
                result["issues"]["total"] += len(ro_record["issues"])
                for issue in ro_record["issues"]:
                    issue_type = issue.get("type", "other")
                    if issue_type in result["issues"]["by_type"]:
                        result["issues"]["by_type"][issue_type] += 1

    # Calculate aggregate GP%
    total_auth_rev = result["totals"]["authorized"]["revenue"]
    total_auth_profit = result["totals"]["authorized"]["profit"]
    if total_auth_rev > 0:
        result["totals"]["authorized"]["gp_percent"] = round(
            (total_auth_profit / total_auth_rev) * 100, 2
        )

    # Sort ROs by authorized revenue descending
    result["ros"].sort(key=lambda x: x["authorized"]["revenue"], reverse=True)

    return result


async def build_ro_audit_record(tm, ro_id: int, ro_summary: dict, target_date) -> Optional[dict]:
    """
    Build a complete audit record for a single RO.

    Fetches from estimate and profit/labor endpoints,
    calculates both potential and authorized metrics,
    and flags any issues.
    """
    record = {
        "ro_id": ro_id,
        "ro_number": ro_summary.get("roNumber") or ro_summary.get("repairOrderNumber"),
        "status": ro_summary.get("_board", "UNKNOWN"),
        "customer": "Unknown",
        "vehicle": "N/A",
        "advisor": "Unassigned",

        # POTENTIAL metrics (all jobs)
        "potential": {
            "revenue": 0,
            "parts": 0,
            "labor": 0,
            "fees": 0,
            "discount": 0,
            "job_count": 0,
            "jobs": []
        },

        # AUTHORIZED metrics (job.authorized = true only)
        "authorized": {
            "revenue": 0,
            "parts": 0,
            "labor": 0,
            "profit": 0,
            "gp_percent": 0,
            "job_count": 0,
            "jobs": []
        },

        # Raw endpoint values for comparison
        "endpoints": {
            "estimate_total": 0,
            "estimate_authorized_total": 0,
            "profit_labor_total": 0,
            "profit_labor_profit": 0
        },

        # Issues found
        "issues": []
    }

    # Fetch estimate
    try:
        estimate = await tm.get(f"/api/repair-order/{ro_id}/estimate")

        # Extract customer/vehicle
        customer = estimate.get("customer", {}) or {}
        vehicle = estimate.get("vehicle", {}) or {}
        record["customer"] = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip() or "Unknown"
        record["vehicle"] = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip() or "N/A"

        # Store raw endpoint values
        record["endpoints"]["estimate_total"] = cents_to_dollars(estimate.get("total") or 0)
        record["endpoints"]["estimate_authorized_total"] = cents_to_dollars(estimate.get("authorizedTotal") or 0)

        # Check for null subtotal issue
        if estimate.get("subtotal") is None:
            record["issues"].append({
                "type": "subtotal_null",
                "message": "estimate.subtotal is null - using total instead"
            })

        # Process each job
        for job in estimate.get("jobs", []):
            job_id = job.get("id")
            job_name = job.get("name", "Unnamed Job")
            is_authorized = job.get("authorized") == True
            auth_date = job.get("authorizedDate")

            # Calculate job totals
            parts_total = sum(p.get("total", 0) for p in job.get("parts", []))
            labor_total = sum(l.get("total", 0) for l in job.get("labor", []))
            fees_total = sum(f.get("total", 0) for f in job.get("fees", []))
            discount = job.get("discount", 0) or 0
            job_total = parts_total + labor_total + fees_total - discount

            # Check for missing technician
            for labor in job.get("labor", []):
                tech = labor.get("technician")
                if not tech or not tech.get("id"):
                    record["issues"].append({
                        "type": "missing_tech",
                        "message": f"No technician assigned: {job_name} - {labor.get('name', 'labor')}"
                    })

            job_summary = {
                "job_id": job_id,
                "name": job_name,
                "authorized": is_authorized,
                "authorized_date": auth_date,
                "parts": cents_to_dollars(parts_total),
                "labor": cents_to_dollars(labor_total),
                "fees": cents_to_dollars(fees_total),
                "discount": cents_to_dollars(discount),
                "total": cents_to_dollars(job_total)
            }

            # Add to POTENTIAL (all jobs)
            record["potential"]["revenue"] += cents_to_dollars(job_total)
            record["potential"]["parts"] += cents_to_dollars(parts_total)
            record["potential"]["labor"] += cents_to_dollars(labor_total)
            record["potential"]["fees"] += cents_to_dollars(fees_total)
            record["potential"]["discount"] += cents_to_dollars(discount)
            record["potential"]["job_count"] += 1
            record["potential"]["jobs"].append(job_summary)

            # Add to AUTHORIZED only if authorized
            if is_authorized:
                # Check if authorized on target date
                auth_on_target = False
                if auth_date:
                    try:
                        auth_dt = datetime.fromisoformat(auth_date.replace("Z", "+00:00")).date()
                        auth_on_target = (auth_dt == target_date)
                    except:
                        pass

                record["authorized"]["revenue"] += cents_to_dollars(job_total)
                record["authorized"]["parts"] += cents_to_dollars(parts_total)
                record["authorized"]["labor"] += cents_to_dollars(labor_total)
                record["authorized"]["job_count"] += 1
                record["authorized"]["jobs"].append({
                    **job_summary,
                    "authorized_on_target_date": auth_on_target
                })

    except Exception as e:
        record["issues"].append({
            "type": "estimate_error",
            "message": f"Failed to fetch estimate: {str(e)}"
        })
        return record

    # Fetch profit/labor for authorized GP
    try:
        profit_labor = await tm.get(f"/api/repair-order/{ro_id}/profit/labor")

        labor_obj = profit_labor.get("laborProfit", {}) or {}
        total_obj = profit_labor.get("totalProfit", {}) or {}

        pl_revenue = total_obj.get("retail") or 0
        pl_profit = total_obj.get("profit") or 0
        pl_margin = total_obj.get("margin") or 0

        record["endpoints"]["profit_labor_total"] = cents_to_dollars(pl_revenue)
        record["endpoints"]["profit_labor_profit"] = cents_to_dollars(pl_profit)

        # Use profit/labor as source of truth for authorized profit
        record["authorized"]["profit"] = cents_to_dollars(pl_profit)
        record["authorized"]["gp_percent"] = round(pl_margin * 100, 2)

        # Check for mismatch between our authorized calculation and profit/labor
        our_auth_rev = int(record["authorized"]["revenue"] * 100)
        if abs(our_auth_rev - pl_revenue) > 100:  # More than $1 difference
            record["issues"].append({
                "type": "profit_mismatch",
                "message": f"Authorized revenue mismatch: calculated ${record['authorized']['revenue']:.2f} vs profit/labor ${pl_revenue/100:.2f}",
                "calculated": record["authorized"]["revenue"],
                "profit_labor": cents_to_dollars(pl_revenue)
            })

    except Exception as e:
        record["issues"].append({
            "type": "profit_labor_error",
            "message": f"Failed to fetch profit/labor: {str(e)}"
        })

    # Try to get advisor from basic RO endpoint
    try:
        ro_basic = await tm.get(f"/api/repair-order/{ro_id}")
        advisor = ro_basic.get("serviceAdvisor", {}) or {}
        record["advisor"] = f"{advisor.get('firstName', '')} {advisor.get('lastName', '')}".strip() or "Unassigned"
    except Exception as e:
        # 404 is common for WIP ROs
        if "404" in str(e):
            record["issues"].append({
                "type": "ro_404",
                "message": "Basic RO endpoint returned 404 (common for WIP)"
            })

    return record
