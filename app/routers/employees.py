"""
Employee Management Endpoints

Employee CRUD, time clock, and tech board.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/")
async def list_employees(
    size: int = Query(500, description="Results per page"),
    status: str = Query("ACTIVE", description="ACTIVE, ALL, INACTIVE")
):
    """
    List all employees

    - **size**: Number of results
    - **status**: Employee status filter
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/employees-lite",
            {"size": size, "status": status}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{employee_id}")
async def get_employee(employee_id: int):
    """
    Get employee details

    - **employee_id**: Employee ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/employee/{employee_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{employee_id}/time-card-active")
async def get_active_time_card(employee_id: int):
    """
    Get employee's current time card (clock status)

    - **employee_id**: Employee ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/employee/{employee_id}/time-card-active")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-board")
async def get_tech_board():
    """
    Get tech board view (work organized by technician)

    Returns all ROs with labor assigned to each technician.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/tech-board")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-board/config")
async def get_tech_board_config():
    """
    Get tech board configuration
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/tech-board/config")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
