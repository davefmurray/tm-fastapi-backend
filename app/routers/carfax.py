"""
Carfax Integration Endpoints

Vehicle history, maintenance tracking, and recall data.
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/vehicle/{vin}")
async def get_vehicle_history(vin: str):
    """
    Get Carfax vehicle history report

    - **vin**: Vehicle VIN
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/carfax/vehicle/{vin}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicle/{vin}/maintenance")
async def get_maintenance_schedule(vin: str):
    """
    Get Carfax maintenance schedule and history

    - **vin**: Vehicle VIN
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/carfax/vehicle/{vin}/maintenance")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicle/{vin}/recalls")
async def get_recalls(vin: str):
    """
    Get recall data for vehicle

    - **vin**: Vehicle VIN
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/carfax/vehicle/{vin}/recalls")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
