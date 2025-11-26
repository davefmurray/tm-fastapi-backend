"""
Fleet Management & Advanced Features

Fleet customer operations, AR management, and notifications.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.tm_client import get_tm_client

router = APIRouter()


# AR Balance
@router.get("/customer/{customer_id}/ar-balance")
async def get_customer_ar_balance(customer_id: int):
    """
    Get customer's AR (Accounts Receivable) balance

    - **customer_id**: Customer ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/customer/{customer_id}/ar-balance")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Store Credit
@router.get("/customer/{customer_id}/store-credit")
async def get_customer_store_credit(customer_id: int):
    """
    Get customer's store credit balance

    - **customer_id**: Customer ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Store credit is in customer details
        result = await tm.get(f"/api/shop/{shop_id}/customer/{customer_id}")
        return {
            "customer_id": customer_id,
            "store_credit_balance": result.get("storeCreditBalance", 0),
            "store_credit_age": result.get("storeCreditBalanceAge", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Notifications
@router.get("/notifications/unread-count")
async def get_unread_notifications(employee_id: int = Query(..., description="Employee ID")):
    """
    Get unread notification count for employee

    - **employee_id**: Employee ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/notification/shop/{shop_id}/employee/{employee_id}/notifications/unread/count"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications")
async def get_notifications(
    employee_id: int = Query(..., description="Employee ID"),
    size: int = Query(25, description="Number of notifications")
):
    """
    Get notifications for employee

    - **employee_id**: Employee ID
    - **size**: Number of notifications
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/notification/shop/{shop_id}/employee/{employee_id}/notifications",
            {"size": size}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Billing/Subscription
@router.get("/shop/billing/subscription")
async def get_subscription_plan():
    """
    Get shop's Tekmetric subscription plan
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/billing/subscription/plan")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Disputes (TekMerchant)
@router.get("/shop/disputes")
async def get_active_disputes():
    """
    Get active payment disputes
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/tekmerchant/shop/{shop_id}/disputes/active")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
