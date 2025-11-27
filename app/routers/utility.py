"""
Utility Endpoints

Miscellaneous utility endpoints (email status, insights, etc.)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.tm_client import get_tm_client, _tm_client
from app.services.supabase_client import get_token_manager
import app.services.tm_client as tm_client_module

router = APIRouter()


class TokenRefreshRequest(BaseModel):
    jwt_token: str
    shop_id: str


@router.post("/token/refresh")
async def refresh_token(request: TokenRefreshRequest):
    """
    Manually refresh JWT token in Supabase.

    Use this when Chrome extension token capture fails or for testing.
    Copy JWT from browser DevTools: Application > Storage > Local Storage > authUser

    - **jwt_token**: Fresh JWT token from Tekmetric
    - **shop_id**: Shop ID (e.g., "6212")
    """
    try:
        token_manager = get_token_manager()
        success = await token_manager.update_token(request.jwt_token, request.shop_id)

        if success:
            # Clear the cached TM client so it fetches new token
            tm_client_module._tm_client = None

            return {
                "status": "success",
                "message": f"Token updated for shop {request.shop_id}",
                "shop_id": request.shop_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update token in Supabase")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/status")
async def get_token_status():
    """
    Check current token status from Supabase.

    Returns when the token was last updated.
    """
    try:
        token_manager = get_token_manager()
        result = token_manager.supabase.table(token_manager.table_name) \
            .select("shop_id, updated_at") \
            .order("updated_at", desc=True) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            token_data = result.data[0]
            return {
                "status": "found",
                "shop_id": token_data.get("shop_id"),
                "updated_at": token_data.get("updated_at"),
                "message": "Token exists in Supabase"
            }
        else:
            return {
                "status": "missing",
                "message": "No token found in Supabase"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
