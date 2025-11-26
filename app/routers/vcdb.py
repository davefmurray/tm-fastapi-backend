"""
VCDB (Vehicle Database) Lookup Endpoints

Year/Make/Model/Submodel lookups for vehicle creation.
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/years")
async def get_years():
    """
    Get all available vehicle years
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get("/api/vcdb/years")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/makes/{year}")
async def get_makes(year: int):
    """
    Get all makes for a specific year

    - **year**: Vehicle year
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/vcdb/years/{year}/makes")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{year}/{make_id}")
async def get_models(year: int, make_id: int):
    """
    Get all models for a year/make combination

    - **year**: Vehicle year
    - **make_id**: Make ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/vcdb/years/{year}/makes/{make_id}/models")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/submodels/{vehicle_id}")
async def get_submodels(vehicle_id: int):
    """
    Get all submodels (trims) for a vehicle

    - **vehicle_id**: Base vehicle ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/vcdb/vehicles/{vehicle_id}/submodels")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicle/{vehicle_id}")
async def get_vehicle_details(vehicle_id: int):
    """
    Get complete ACES vehicle specifications

    - **vehicle_id**: Vehicle ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/vcdb/vehicles/{vehicle_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
