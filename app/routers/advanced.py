"""
Advanced Operations Endpoints

Sublets, fees, discounts, notes, and customer concerns.
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client

router = APIRouter()


# Customer Concerns
@router.get("/ro/{ro_id}/customer-concerns")
async def get_customer_concerns(ro_id: int):
    """
    Get customer concerns for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/repair-orders/{ro_id}/customer-concerns")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ro/{ro_id}/customer-concerns")
async def add_customer_concern(ro_id: int, concern_data: dict):
    """
    Add customer concern to repair order

    - **ro_id**: Repair order ID
    - **concern_data**: Concern details
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.post(f"/api/repair-orders/{ro_id}/customer-concerns", concern_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Technician Concerns
@router.get("/ro/{ro_id}/technician-concerns")
async def get_technician_concerns(ro_id: int):
    """
    Get technician concerns/findings for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/repair-orders/{ro_id}/technician-concerns")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Comments/Notes
@router.get("/ro/{ro_id}/comments")
async def get_ro_comments(ro_id: int):
    """
    Get comments/notes for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/repair-order/{ro_id}/comments")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Job Clocks (Time Tracking per Job)
@router.get("/ro/{ro_id}/job-clocks")
async def get_job_clocks(ro_id: int):
    """
    Get job clock entries (time tracking for jobs)

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/repair-order/{ro_id}/job-clocks")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Fluid Units
@router.get("/shop/fluid-units")
async def get_fluid_units():
    """
    Get fluid unit configuration (quarts, gallons, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/fluid-units")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Customer Settings
@router.get("/shop/customer-settings")
async def get_customer_settings():
    """
    Get customer-related settings and configuration
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/customer-settings")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# TekMessage Config
@router.get("/shop/tekmessage-config")
async def get_tekmessage_config():
    """
    Get TekMessage (SMS/Email) configuration
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/tekmessage/config")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# TekMessage Templates
@router.get("/shop/tekmessage-templates")
async def get_tekmessage_templates():
    """
    Get TekMessage templates for SMS/Email
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/tekmessage/template")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
