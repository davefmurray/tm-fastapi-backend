"""
Reports & Analytics Endpoints

Financial reports, employee reports, and analytics.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/sales-summary")
async def get_sales_summary(
    start: str = Query(..., description="Start date (ISO 8601)"),
    end: str = Query(..., description="End date (ISO 8601)")
):
    """
    Get sales summary report for date range

    - **start**: Start date
    - **end**: End date
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/reporting/sales-summary",
            {"shopId": shop_id, "start": start, "end": end}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer-list")
async def get_customer_list_report(
    customer_id: int = Query(..., description="Customer ID")
):
    """
    Get customer report (RO history, totals, etc.)

    - **customer_id**: Customer ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/reporting/customer-list-report/individual",
            {"customerId": customer_id, "shopIds": shop_id}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ar-aging")
async def get_ar_aging_report():
    """
    Get accounts receivable aging report
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/reporting/ar-aging",
            {"shopId": shop_id}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee-productivity")
async def get_employee_productivity(
    employee_id: int = Query(..., description="Employee ID"),
    start: str = Query(..., description="Start date"),
    end: str = Query(..., description="End date")
):
    """
    Get employee productivity report

    - **employee_id**: Employee ID
    - **start**: Start date
    - **end**: End date
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/reporting/employee-productivity",
            {"employeeId": employee_id, "shopId": shop_id, "start": start, "end": end}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parts-purchased")
async def get_parts_purchased_report(
    start: str = Query(..., description="Start date"),
    end: str = Query(..., description="End date")
):
    """
    Get parts purchased report (vendor spending analysis)

    - **start**: Start date
    - **end**: End date
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/reporting/parts-purchased",
            {"shopId": shop_id, "start": start, "end": end}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
