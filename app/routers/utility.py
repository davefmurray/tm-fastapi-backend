"""
Utility Endpoints

Miscellaneous utility endpoints (email status, insights, etc.)
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.post("/email/status")
async def check_email_status(email_data: dict):
    """
    Check email delivery status

    - **email_data**: Email addresses to check
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.post("/api/email/status", email_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights")
async def track_insights(insight_data: dict):
    """
    Track user insights/analytics

    - **insight_data**: Insight tracking data
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.post("/api/insights", insight_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile")
async def get_user_profile():
    """
    Get current user profile
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get("/api/profile")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/shop/{shop_id}")
async def get_shop_token(shop_id: int):
    """
    Get shop-specific token info

    - **shop_id**: Shop ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/token/shop/{shop_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
