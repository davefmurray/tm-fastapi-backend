"""
Repair Order Operations

RO querying, details, estimates, and sharing.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.services.tm_client import get_tm_client
from app.models.schemas import ShareEstimateRequest

router = APIRouter()


@router.get("/list")
async def get_ro_list(
    board: str = Query("ACTIVE", description="ACTIVE, POSTED, or COMPLETE"),
    page: int = Query(0, ge=0),
    group_by: str = Query("ROSTATUS", description="ROSTATUS, SERVICEWRITER, TECHNICIAN, NONE"),
    search: Optional[str] = Query(None, description="Search term")
):
    """
    Get list of repair orders (raw data for custom dashboards)

    - **board**: Board type (ACTIVE, POSTED, COMPLETE)
    - **page**: Page number
    - **group_by**: Grouping method
    - **search**: Optional search term
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    params = {
        "view": "list",
        "board": board,
        "page": page,
        "groupBy": group_by
    }

    if search:
        params["search"] = search

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/job-board-group-by",
            params
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}")
async def get_ro_details(ro_id: int):
    """
    Get repair order details

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/repair-order/{ro_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/estimate")
async def get_ro_estimate(ro_id: int):
    """
    Get repair order estimate (jobs, parts, labor, pricing)

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()

    try:
        result = await tm.get(f"/api/repair-order/{ro_id}/estimate")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ro_id}/share/estimate")
async def share_estimate(ro_id: int, share_request: ShareEstimateRequest):
    """
    Send estimate to customer via email or SMS

    - **ro_id**: Repair order ID
    - **share_request**: Email list or phone/message
    """
    tm = get_tm_client()

    request_body = {}

    if share_request.email:
        request_body["email"] = share_request.email
    elif share_request.phone:
        request_body["phone"] = share_request.phone
        request_body["message"] = share_request.message

    try:
        result = await tm.post(f"/api/repair-order/{ro_id}/share", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/activity")
async def get_ro_activity(ro_id: int):
    """
    Get activity feed for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/activity/repair-order/{ro_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/job-history")
async def get_job_history(ro_id: int, vehicle_id: int = Query(..., description="Vehicle ID")):
    """
    Get job history for vehicle (past jobs across all ROs)

    - **ro_id**: Current repair order ID
    - **vehicle_id**: Vehicle ID to get history for
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/jobs/job-history",
            {
                "repairOrderId": ro_id,
                "vehicleIds": vehicle_id,
                "linkedCustomers": "",
                "size": 100
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/inspection-history")
async def get_inspection_history(vehicle_id: int = Query(..., description="Vehicle ID")):
    """
    Get inspection history for vehicle

    - **vehicle_id**: Vehicle ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/repair-order-inspections/history",
            {
                "vehicleId": vehicle_id,
                "linkedCustomers": "",
                "size": 100
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/appointments")
async def get_ro_appointments(ro_id: int):
    """
    Get appointments for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/appointments",
            {"repairOrderId": ro_id, "size": 100}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/purchase-orders")
async def get_ro_purchase_orders(ro_id: int):
    """
    Get purchase orders for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/orders/repair-order/{ro_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ro_id}/status")
async def update_ro_status(
    ro_id: int,
    status_id: int = Query(..., description="Status ID: 3=COMPLETE, 5=POSTED"),
    completed_date: Optional[str] = Query(None),
    posted_date: Optional[str] = Query(None),
    miles_in: Optional[int] = Query(None),
    miles_out: Optional[int] = Query(None)
):
    """
    Update RO status (Complete work or Post RO)

    - **ro_id**: Repair order ID
    - **status_id**: 3 = COMPLETE, 5 = POSTED
    """
    tm = get_tm_client()

    request_body = {
        "repairOrderStatus": {"id": status_id},
        "milesIn": miles_in,
        "milesOut": miles_out,
        "odometerInop": False,
        "leadSource": "API"
    }

    if status_id == 3 and completed_date:
        request_body["completedDate"] = completed_date
    elif status_id == 5 and posted_date:
        request_body["postedDate"] = posted_date

    try:
        result = await tm.put(f"/api/repair-order/{ro_id}/status", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
