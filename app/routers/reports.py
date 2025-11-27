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


@router.get("/profit-details")
async def get_profit_details_report(
    start: str = Query(..., description="Start datetime (ISO 8601 with timezone, e.g., 2025-11-01T00:00:00.000-05:00)"),
    end: str = Query(..., description="End datetime (ISO 8601 with timezone, e.g., 2025-11-27T23:59:59.999-05:00)"),
    metric: str = Query("TOTAL", description="AVG for averages, TOTAL for totals")
):
    """
    Get profit details report - MATCHES TM's official Profit Details Report exactly.

    This uses TM's native reporting API, so numbers will match the
    Reports > Financial > Profit Details page in Tekmetric.

    Returns:
    - summary: Labor, parts, sublet, fees, and total profit
    - count: Number of invoices in the period
    - All values in CENTS
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get summary (profit breakdown)
        summary = await tm.get(
            "/api/reporting/profit-details-report/summary",
            {
                "timezone": "America/New_York",
                "shopIds": shop_id,
                "start": start,
                "end": end,
                "metric": metric
            }
        )

        # Get count
        count_result = await tm.get(
            "/api/reporting/profit-details-report/count",
            {
                "shopIds": shop_id,
                "start": start,
                "end": end,
                "metric": metric
            }
        )

        invoice_count = count_result.get("count", 0)

        # Calculate totals if metric is AVG
        if metric == "AVG" and invoice_count > 0:
            total_labor = summary.get("laborProfit", 0) * invoice_count / 100
            total_parts = summary.get("partsTotalProfit", 0) * invoice_count / 100
            total_sublet = summary.get("subletProfit", 0) * invoice_count / 100
            total_fees = summary.get("feesProfit", 0) * invoice_count / 100
            total_profit = summary.get("totalProfit", 0) * invoice_count / 100
        else:
            total_labor = summary.get("laborProfit", 0) / 100
            total_parts = summary.get("partsTotalProfit", 0) / 100
            total_sublet = summary.get("subletProfit", 0) / 100
            total_fees = summary.get("feesProfit", 0) / 100
            total_profit = summary.get("totalProfit", 0) / 100

        return {
            "period": {
                "start": start,
                "end": end
            },
            "invoice_count": invoice_count,
            "averages": {
                "labor_profit": round(summary.get("laborProfit", 0) / 100, 2),
                "parts_profit": round(summary.get("partsTotalProfit", 0) / 100, 2),
                "sublet_profit": round(summary.get("subletProfit", 0) / 100, 2),
                "fees_profit": round(summary.get("feesProfit", 0) / 100, 2),
                "total_profit": round(summary.get("totalProfit", 0) / 100, 2)
            },
            "totals": {
                "labor_profit": round(total_labor, 2),
                "parts_profit": round(total_parts, 2),
                "sublet_profit": round(total_sublet, 2),
                "fees_profit": round(total_fees, 2),
                "total_profit": round(total_profit, 2)
            },
            "source": "TM_PROFIT_DETAILS_REPORT"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
