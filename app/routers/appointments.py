"""
Appointment & Calendar Endpoints

Calendar views and appointment management.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/calendar")
async def get_calendar(
    view: str = Query("week", description="View type: day, week, month"),
    start: str = Query(..., description="Start date (ISO 8601)"),
    end: str = Query(..., description="End date (ISO 8601)"),
    size: int = Query(10000, description="Max appointments")
):
    """
    Get calendar view of appointments

    - **view**: day, week, or month
    - **start**: Start date/time
    - **end**: End date/time
    - **size**: Max appointments to return
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    params = {
        "size": size,
        "view": view,
        "start": start,
        "end": end,
        "dayViewResource": "DEFAULT"
    }

    try:
        result = await tm.get(f"/api/shop/{shop_id}/appointments", params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: int):
    """
    Get appointment details

    - **appointment_id**: Appointment ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/appointment/{appointment_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_or_update_appointment(appointment_data: dict):
    """
    Create new appointment or update existing

    - Include "id" field to update existing appointment
    - Omit "id" to create new appointment
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    # Ensure shopId is set
    appointment_data["shopId"] = int(shop_id)

    try:
        result = await tm.post(f"/api/shop/{shop_id}/appointment", appointment_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_appointment_settings():
    """
    Get calendar settings (day start/end time, default duration, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/appointment-settings")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/colors")
async def get_appointment_colors():
    """
    Get appointment color labels (Drop, Wait, Loaner, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/appointment-colors")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
