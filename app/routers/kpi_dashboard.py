"""
KPI Dashboard Endpoints (Warehouse-Backed)

NEW dashboard that reads EXCLUSIVELY from warehouse tables:
- daily_shop_metrics
- ro_snapshots

NO direct Tekmetric API calls in this router.

Per sync9.txt/sync10.txt requirements:
- Top KPIs: Revenue, Car Count, GP%, GP$, Billed Hours, GP$/Hour
- Date ranges: Today (default), WTD, Last 7, MTD, Last 30, Custom
- Views: Owner, Advisor, Tech, Warranty/No-Charge
- Layout: Multi-page
"""

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from supabase import create_client, Client

router = APIRouter()


def get_supabase() -> Client:
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return create_client(url, key)


def get_shop_uuid(supabase: Client, shop_id: int) -> str:
    """Get shop UUID from TM shop ID."""
    result = supabase.table("shops").select("id").eq("tm_id", shop_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")
    return result.data[0]["id"]


def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars."""
    return round(cents / 100, 2) if cents else 0.0


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default."""
    return numerator / denominator if denominator else default


class DateRange(str, Enum):
    """Predefined date ranges."""
    TODAY = "today"
    WTD = "wtd"  # Week to date (M-F)
    LAST_7 = "last_7"
    MTD = "mtd"
    LAST_30 = "last_30"
    CUSTOM = "custom"


def resolve_date_range(
    range_type: DateRange,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> tuple[str, str]:
    """
    Resolve date range to start/end dates.

    Returns (start_date, end_date) as YYYY-MM-DD strings.
    """
    today = date.today()

    if range_type == DateRange.TODAY:
        return today.isoformat(), today.isoformat()

    elif range_type == DateRange.WTD:
        # Week to date (Monday to today, business days only)
        # Find Monday of current week
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday.isoformat(), today.isoformat()

    elif range_type == DateRange.LAST_7:
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()

    elif range_type == DateRange.MTD:
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()

    elif range_type == DateRange.LAST_30:
        start = today - timedelta(days=29)
        return start.isoformat(), today.isoformat()

    elif range_type == DateRange.CUSTOM:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date required for custom range"
            )
        return start_date, end_date

    # Default to today
    return today.isoformat(), today.isoformat()


@router.get("/summary")
async def get_kpi_summary(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.TODAY, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)")
):
    """
    Owner Summary View - Top KPIs for the period.

    Returns:
    - revenue: Total authorized sales ($)
    - car_count: Number of ROs
    - gp_percent: Gross profit margin (%)
    - gp_dollars: Total gross profit ($)
    - billed_hours: Labor hours sold
    - gp_per_hour: GP dollars per billed hour ($)
    - aro: Average repair order ($)
    - effective_labor_rate: Revenue per hour ($)
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    # Query daily_shop_metrics for the range
    result = supabase.table("daily_shop_metrics").select(
        "metric_date, ro_count, authorized_revenue, authorized_cost, authorized_profit, "
        "authorized_gp_percent, labor_hours, labor_revenue, labor_profit, "
        "parts_revenue, parts_profit, avg_ro_value, authorization_rate"
    ).eq("shop_id", shop_uuid).gte("metric_date", start).lte("metric_date", end).execute()

    rows = result.data or []

    if not rows:
        return {
            "period": {"start": start, "end": end, "range_type": range_type, "days_with_data": 0},
            "kpis": {
                "revenue": 0,
                "car_count": 0,
                "gp_percent": 0,
                "gp_dollars": 0,
                "billed_hours": 0,
                "gp_per_hour": 0,
                "aro": 0,
                "effective_labor_rate": 0
            },
            "breakdown": {
                "labor": {"revenue": 0, "profit": 0, "gp_percent": 0},
                "parts": {"revenue": 0, "profit": 0, "gp_percent": 0}
            },
            "source": "daily_shop_metrics",
            "message": "No data for this period"
        }

    # Aggregate across all days
    total_revenue = sum(r.get("authorized_revenue") or 0 for r in rows)
    total_cost = sum(r.get("authorized_cost") or 0 for r in rows)
    total_profit = sum(r.get("authorized_profit") or 0 for r in rows)
    total_car_count = sum(r.get("ro_count") or 0 for r in rows)
    total_hours = sum(float(r.get("labor_hours") or 0) for r in rows)
    total_labor_revenue = sum(r.get("labor_revenue") or 0 for r in rows)
    total_labor_profit = sum(r.get("labor_profit") or 0 for r in rows)
    total_parts_revenue = sum(r.get("parts_revenue") or 0 for r in rows)
    total_parts_profit = sum(r.get("parts_profit") or 0 for r in rows)

    # Calculate derived KPIs
    gp_percent = safe_div(total_profit * 100, total_revenue)
    aro = safe_div(total_revenue, total_car_count)
    gp_per_hour = safe_div(total_profit, total_hours * 100)  # cents to dollars
    effective_labor_rate = safe_div(total_labor_revenue, total_hours * 100)

    # Parts and labor margins
    parts_gp_percent = safe_div(total_parts_profit * 100, total_parts_revenue)
    labor_gp_percent = safe_div(total_labor_profit * 100, total_labor_revenue)

    return {
        "period": {
            "start": start,
            "end": end,
            "range_type": range_type,
            "days_with_data": len(rows)
        },
        "kpis": {
            "revenue": cents_to_dollars(total_revenue),
            "car_count": total_car_count,
            "gp_percent": round(gp_percent, 2),
            "gp_dollars": cents_to_dollars(total_profit),
            "billed_hours": round(total_hours, 1),
            "gp_per_hour": round(gp_per_hour, 2),
            "aro": cents_to_dollars(int(aro)),
            "effective_labor_rate": round(effective_labor_rate, 2)
        },
        "breakdown": {
            "labor": {
                "revenue": cents_to_dollars(total_labor_revenue),
                "profit": cents_to_dollars(total_labor_profit),
                "gp_percent": round(labor_gp_percent, 2)
            },
            "parts": {
                "revenue": cents_to_dollars(total_parts_revenue),
                "profit": cents_to_dollars(total_parts_profit),
                "gp_percent": round(parts_gp_percent, 2)
            }
        },
        "source": "daily_shop_metrics"
    }


@router.get("/daily")
async def get_daily_breakdown(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.LAST_7, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)")
):
    """
    Daily breakdown for trend charts.

    Returns array of daily metrics for charting.
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    result = supabase.table("daily_shop_metrics").select("*").eq(
        "shop_id", shop_uuid
    ).gte("metric_date", start).lte("metric_date", end).order(
        "metric_date", desc=False
    ).execute()

    rows = result.data or []

    daily_data = []
    for r in rows:
        revenue = r.get("authorized_revenue") or 0
        profit = r.get("authorized_profit") or 0
        hours = float(r.get("labor_hours") or 0)
        ro_count = r.get("ro_count") or 0

        daily_data.append({
            "date": r.get("metric_date"),
            "revenue": cents_to_dollars(revenue),
            "profit": cents_to_dollars(profit),
            "gp_percent": round(safe_div(profit * 100, revenue), 2),
            "car_count": ro_count,
            "billed_hours": round(hours, 1),
            "aro": cents_to_dollars(int(safe_div(revenue, ro_count))),
            "gp_per_hour": round(safe_div(profit, hours * 100), 2) if hours > 0 else 0
        })

    return {
        "period": {"start": start, "end": end, "range_type": range_type},
        "daily": daily_data,
        "count": len(daily_data)
    }


@router.get("/advisors")
async def get_advisor_performance(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.MTD, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)")
):
    """
    Advisor View - Performance by service advisor.

    Aggregates ro_snapshots by advisor_name.
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    # Get ro_snapshots for the period
    result = supabase.table("ro_snapshots").select(
        "advisor_name, authorized_revenue, authorized_profit, labor_hours, "
        "parts_revenue, parts_profit, labor_revenue, labor_profit"
    ).eq("shop_id", shop_uuid).gte("snapshot_date", start).lte("snapshot_date", end).execute()

    rows = result.data or []

    # Aggregate by advisor
    advisor_data: Dict[str, Dict] = {}
    for r in rows:
        name = r.get("advisor_name") or "Unknown"
        if name not in advisor_data:
            advisor_data[name] = {
                "name": name,
                "ro_count": 0,
                "revenue": 0,
                "profit": 0,
                "hours": 0,
                "parts_revenue": 0,
                "parts_profit": 0,
                "labor_revenue": 0,
                "labor_profit": 0
            }

        advisor_data[name]["ro_count"] += 1
        advisor_data[name]["revenue"] += r.get("authorized_revenue") or 0
        advisor_data[name]["profit"] += r.get("authorized_profit") or 0
        advisor_data[name]["hours"] += float(r.get("labor_hours") or 0)
        advisor_data[name]["parts_revenue"] += r.get("parts_revenue") or 0
        advisor_data[name]["parts_profit"] += r.get("parts_profit") or 0
        advisor_data[name]["labor_revenue"] += r.get("labor_revenue") or 0
        advisor_data[name]["labor_profit"] += r.get("labor_profit") or 0

    # Format output
    advisors = []
    for name, data in advisor_data.items():
        revenue = data["revenue"]
        profit = data["profit"]
        ro_count = data["ro_count"]
        hours = data["hours"]

        advisors.append({
            "name": name,
            "ro_count": ro_count,
            "revenue": cents_to_dollars(revenue),
            "profit": cents_to_dollars(profit),
            "gp_percent": round(safe_div(profit * 100, revenue), 2),
            "aro": cents_to_dollars(int(safe_div(revenue, ro_count))),
            "billed_hours": round(hours, 1),
            "gp_per_hour": round(safe_div(profit, hours * 100), 2) if hours > 0 else 0,
            "labor_revenue": cents_to_dollars(data["labor_revenue"]),
            "parts_revenue": cents_to_dollars(data["parts_revenue"])
        })

    # Sort by revenue descending
    advisors.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "period": {"start": start, "end": end, "range_type": range_type},
        "advisors": advisors,
        "count": len(advisors)
    }


@router.get("/techs")
async def get_tech_performance(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.MTD, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)")
):
    """
    Tech View - Technician productivity.

    Aggregates job_labor by technician.
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    # Get job_labor for ROs in the period
    # First get ro_snapshots to find qualifying RO IDs
    snapshots = supabase.table("ro_snapshots").select(
        "repair_order_id"
    ).eq("shop_id", shop_uuid).gte("snapshot_date", start).lte("snapshot_date", end).execute()

    ro_ids = [s["repair_order_id"] for s in (snapshots.data or [])]

    if not ro_ids:
        return {
            "period": {"start": start, "end": end, "range_type": range_type},
            "techs": [],
            "count": 0,
            "message": "No data for this period"
        }

    # Get labor records for these ROs
    # Note: Supabase doesn't support IN queries easily, so we'll fetch all and filter
    labor_result = supabase.table("job_labor").select(
        "technician_name, hours, total, labor_cost, repair_order_id"
    ).eq("shop_id", shop_uuid).execute()

    labor_rows = [r for r in (labor_result.data or []) if r.get("repair_order_id") in ro_ids]

    # Aggregate by technician
    tech_data: Dict[str, Dict] = {}
    for r in labor_rows:
        name = r.get("technician_name") or "Unknown"
        if name not in tech_data:
            tech_data[name] = {
                "name": name,
                "billed_hours": 0,
                "labor_revenue": 0,
                "labor_cost": 0,
                "job_count": 0
            }

        tech_data[name]["billed_hours"] += float(r.get("hours") or 0)
        tech_data[name]["labor_revenue"] += r.get("total") or 0
        tech_data[name]["labor_cost"] += r.get("labor_cost") or 0
        tech_data[name]["job_count"] += 1

    # Format output
    techs = []
    for name, data in tech_data.items():
        revenue = data["labor_revenue"]
        cost = data["labor_cost"]
        profit = revenue - cost
        hours = data["billed_hours"]

        techs.append({
            "name": name,
            "billed_hours": round(hours, 1),
            "labor_revenue": cents_to_dollars(revenue),
            "labor_cost": cents_to_dollars(cost),
            "labor_profit": cents_to_dollars(profit),
            "labor_gp_percent": round(safe_div(profit * 100, revenue), 2),
            "effective_rate": round(safe_div(revenue, hours * 100), 2) if hours > 0 else 0,
            "job_count": data["job_count"]
        })

    # Sort by hours descending
    techs.sort(key=lambda x: x["billed_hours"], reverse=True)

    return {
        "period": {"start": start, "end": end, "range_type": range_type},
        "techs": techs,
        "count": len(techs)
    }


@router.get("/ros")
async def get_ro_list(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.TODAY, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=500, description="Max ROs to return"),
    sort_by: str = Query(default="revenue", description="Sort by: revenue, profit, date")
):
    """
    Individual RO list from ro_snapshots.

    For drilling down into specific repair orders.
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    # Build query
    query = supabase.table("ro_snapshots").select(
        "ro_number, snapshot_date, customer_name, vehicle_description, advisor_name, "
        "authorized_revenue, authorized_profit, authorized_gp_percent, labor_hours, "
        "parts_revenue, labor_revenue, tm_repair_order_id"
    ).eq("shop_id", shop_uuid).gte("snapshot_date", start).lte("snapshot_date", end)

    # Sort
    if sort_by == "profit":
        query = query.order("authorized_profit", desc=True)
    elif sort_by == "date":
        query = query.order("snapshot_date", desc=True)
    else:
        query = query.order("authorized_revenue", desc=True)

    result = query.limit(limit).execute()
    rows = result.data or []

    ros = []
    for r in rows:
        revenue = r.get("authorized_revenue") or 0
        profit = r.get("authorized_profit") or 0
        hours = float(r.get("labor_hours") or 0)

        ros.append({
            "ro_number": r.get("ro_number"),
            "tm_ro_id": r.get("tm_repair_order_id"),
            "date": r.get("snapshot_date"),
            "customer": r.get("customer_name"),
            "vehicle": r.get("vehicle_description"),
            "advisor": r.get("advisor_name"),
            "revenue": cents_to_dollars(revenue),
            "profit": cents_to_dollars(profit),
            "gp_percent": r.get("authorized_gp_percent"),
            "billed_hours": round(hours, 1),
            "gp_per_hour": round(safe_div(profit, hours * 100), 2) if hours > 0 else 0
        })

    return {
        "period": {"start": start, "end": end, "range_type": range_type},
        "ros": ros,
        "count": len(ros)
    }


@router.get("/warranty")
async def get_warranty_view(
    shop_id: int = Query(default=6212, description="TM Shop ID"),
    range_type: DateRange = Query(default=DateRange.MTD, description="Date range preset"),
    start_date: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)"),
    exclude_warranty: bool = Query(default=True, description="Exclude warranty/no-charge ROs")
):
    """
    Warranty/No-Charge View.

    Filter metrics to exclude (or show only) warranty and no-charge work.

    Note: This requires RO labels or specific job types to be synced.
    Currently filters by GP% (warranty/no-charge typically has 0% GP).
    """
    supabase = get_supabase()
    shop_uuid = get_shop_uuid(supabase, shop_id)

    start, end = resolve_date_range(range_type, start_date, end_date)

    # Get all snapshots for the period
    result = supabase.table("ro_snapshots").select(
        "ro_number, snapshot_date, customer_name, vehicle_description, advisor_name, "
        "authorized_revenue, authorized_profit, authorized_gp_percent, labor_hours"
    ).eq("shop_id", shop_uuid).gte("snapshot_date", start).lte("snapshot_date", end).execute()

    rows = result.data or []

    # Filter based on GP% (warranty/no-charge typically has GP <= 5%)
    WARRANTY_GP_THRESHOLD = 5.0

    if exclude_warranty:
        # Exclude low-margin (warranty) work
        filtered = [r for r in rows if (r.get("authorized_gp_percent") or 0) > WARRANTY_GP_THRESHOLD]
        filter_label = "Excluding Warranty/No-Charge"
    else:
        # Show only warranty/no-charge
        filtered = [r for r in rows if (r.get("authorized_gp_percent") or 0) <= WARRANTY_GP_THRESHOLD]
        filter_label = "Warranty/No-Charge Only"

    # Aggregate
    total_revenue = sum(r.get("authorized_revenue") or 0 for r in filtered)
    total_profit = sum(r.get("authorized_profit") or 0 for r in filtered)
    total_hours = sum(float(r.get("labor_hours") or 0) for r in filtered)
    ro_count = len(filtered)

    return {
        "period": {"start": start, "end": end, "range_type": range_type},
        "filter": filter_label,
        "summary": {
            "ro_count": ro_count,
            "revenue": cents_to_dollars(total_revenue),
            "profit": cents_to_dollars(total_profit),
            "gp_percent": round(safe_div(total_profit * 100, total_revenue), 2),
            "billed_hours": round(total_hours, 1),
            "aro": cents_to_dollars(int(safe_div(total_revenue, ro_count))),
            "gp_per_hour": round(safe_div(total_profit, total_hours * 100), 2) if total_hours > 0 else 0
        },
        "total_ros_in_period": len(rows),
        "filtered_ros": ro_count,
        "excluded_ros": len(rows) - ro_count
    }
