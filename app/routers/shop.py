"""
Shop Configuration Endpoints

Shop settings, labor rates, pricing matrices, and configuration.
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/config")
async def get_shop_config():
    """
    Get shop configuration (settings, integrations, features)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/config")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_shop_details():
    """
    Get shop details (name, address, contact info, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead-sources")
async def get_lead_sources():
    """
    Get configured lead sources (Google, Referral, Walk-in, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/lead-sources")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ro-custom-labels")
async def get_ro_custom_labels():
    """
    Get custom RO labels/statuses
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/ro-custom-labels")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profitability-goal")
async def get_profitability_goal():
    """
    Get shop's gross profit goal percentage
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/profitability-goal")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ro-advanced-settings")
async def get_ro_advanced_settings():
    """
    Get advanced RO settings
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/ro-advanced-settings")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labor-rates")
async def get_labor_rates():
    """
    Get shop's labor rate configuration
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/labor-rates")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tekmotor/tire-fitment/{vehicle_id}")
async def get_tire_fitment(vehicle_id: int):
    """
    Get tire fitment data for vehicle

    - **vehicle_id**: VCDB vehicle ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/tekmotor/tire/fitment/data", {"vehicleId": vehicle_id})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tekmotor/search/{base_vehicle_id}")
async def tekmotor_search(base_vehicle_id: int, search: str = Query("", description="Search term")):
    """
    Search TekMotor database for vehicle

    - **base_vehicle_id**: Base vehicle ID
    - **search**: Search term
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(
            f"/api/tekmotor/v2/{base_vehicle_id}/search",
            {"search": search, "isSmartJob": "true"}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
