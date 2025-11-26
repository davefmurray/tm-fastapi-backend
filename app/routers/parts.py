"""
Parts Hub & Purchase Order Endpoints

Parts ordering, vendor integration, and order receiving.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/integration-config")
async def get_parts_integration_config():
    """
    Get parts integration configuration (PartsTech, Worldpac, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/part-integration-config",
            {"checkConnection": "false"}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proxy")
async def parts_tech_proxy(http_method: str, path: str):
    """
    Proxy request to PartsTech API

    - **http_method**: HTTP method (GET, POST, etc.)
    - **path**: PartsTech API path
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    request_body = {
        "shopId": int(shop_id),
        "httpMethod": http_method,
        "path": path
    }

    try:
        result = await tm.post(f"/api/shop/{shop_id}/parts-tech/proxy", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vendors")
async def search_vendors(
    search: str = Query("", description="Search term"),
    size: int = Query(50, description="Results per page")
):
    """
    Search or list vendors

    - **search**: Vendor name search
    - **size**: Number of results
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/vendors",
            {"search": search, "size": size}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders")
async def create_manual_order(order_data: dict):
    """
    Create manual purchase order

    Order data should include:
    - orderNumber
    - vendor (with id)
    - parts array
    - quote (boolean)
    - tax, delivery, notes
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.post(f"/api/shop/{shop_id}/orders", order_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/orders/{order_id}/receive")
async def mark_order_received(
    order_id: int,
    invoice_number: str = Query(..., description="Invoice number"),
    invoice_date: str = Query(..., description="Invoice date (ISO 8601)")
):
    """
    Mark purchase order as received

    - **order_id**: Order ID
    - **invoice_number**: Vendor invoice number
    - **invoice_date**: Invoice date
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    request_body = {
        "data": [
            {
                "id": order_id,
                "orderStatus": {"id": 2},  # 2 = RECEIVED
                "notifyTechnicians": False,
                "invoiceNumber": invoice_number,
                "invoiceDate": invoice_date
            }
        ]
    }

    try:
        result = await tm.patch(f"/api/shop/{shop_id}/orders/status", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
