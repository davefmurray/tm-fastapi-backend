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
    # NOTE: This endpoint returns nested objects, not flat fields:
    # - labor_profit: { hours, retail, cost, profit, margin }
    # - parts_profit: { quantity, retail, cost, profit, margin }
    # - total_profit: { retail, cost, profit, margin }
    try:
        profit_labor = await tm.get(f"/api/repair-order/{ro_id}/profit/labor")

        # Extract from nested structure
        labor_obj = profit_labor.get("labor_profit", {}) or {}
        parts_obj = profit_labor.get("parts_profit", {}) or {}
        total_obj = profit_labor.get("total_profit", {}) or {}

        audit_record["data_sources"]["profit_labor"] = {
            "labor_revenue": labor_obj.get("retail"),
            "labor_cost": labor_obj.get("cost"),
            "labor_profit": labor_obj.get("profit"),
            "labor_margin": labor_obj.get("margin"),
            "parts_revenue": parts_obj.get("retail"),
            "parts_cost": parts_obj.get("cost"),
            "parts_profit": parts_obj.get("profit"),
            "parts_margin": parts_obj.get("margin"),
            "total_revenue": total_obj.get("retail"),
            "total_cost": total_obj.get("cost"),
            "total_profit": total_obj.get("profit"),
            "total_margin": total_obj.get("margin")
        }

        # Compare profit/labor values with our calculations
        if "calculated_values" in audit_record:
            calc = audit_record["calculated_values"]

            # Check labor revenue (from nested labor_profit.retail)
            labor_rev_reported = labor_obj.get("retail") or 0
            labor_rev_calc = int(calc["labor_total"] * 100)
            if abs(labor_rev_reported - labor_rev_calc) > 100:
                audit_record["discrepancies"].append({
                    "type": "cross_endpoint_disagreements",
                    "field": "labor_revenue",
                    "calculated": cents_to_dollars(labor_rev_calc),
                    "profit_labor_reported": cents_to_dollars(labor_rev_reported),
                    "difference": cents_to_dollars(labor_rev_calc - labor_rev_reported),
                    "suspected_cause": "profit/labor endpoint disagrees with line item sum"
                })

            # Check parts revenue (from nested parts_profit.retail)
            parts_rev_reported = parts_obj.get("retail") or 0
            parts_rev_calc = int(calc["parts_total"] * 100)
            if abs(parts_rev_reported - parts_rev_calc) > 100:
                audit_record["discrepancies"].append({
                    "type": "cross_endpoint_disagreements",
                    "field": "parts_revenue",
                    "calculated": cents_to_dollars(parts_rev_calc),
                    "profit_labor_reported": cents_to_dollars(parts_rev_reported),
                    "difference": cents_to_dollars(parts_rev_calc - parts_rev_reported),
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
