"""
Repair Order Operations

RO querying, details, estimates, and sharing.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.services.tm_client import get_tm_client
from app.models.schemas import ShareEstimateRequest

router = APIRouter()


@router.post("/create")
async def create_repair_order(ro_data: dict):
    """
    Create a new repair order

    Required fields:
    - customerId: Customer ID
    - vehicleId: Vehicle ID
    - milesIn: Odometer reading
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.post("/api/repair-order/create", ro_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@router.put("/{ro_id}/complete")
async def complete_work(
    ro_id: int,
    completed_date: str = Query(..., description="Completion date (ISO 8601)"),
    miles_in: int = Query(..., description="Odometer in"),
    miles_out: int = Query(..., description="Odometer out")
):
    """
    Mark work as complete (before posting)

    - **ro_id**: Repair order ID
    - **completed_date**: When work was completed
    - **miles_in**: Odometer reading in
    - **miles_out**: Odometer reading out
    """
    tm = get_tm_client()

    request_body = {
        "repairOrderStatus": {"id": 3},
        "completedDate": completed_date,
        "milesIn": miles_in,
        "milesOut": miles_out,
        "odometerInop": False,
        "leadSource": "API"
    }

    try:
        result = await tm.put(f"/api/repair-order/{ro_id}/status", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ro_id}/post")
async def post_ro(
    ro_id: int,
    posted_date: str = Query(..., description="Posted date (ISO 8601)"),
    miles_in: int = Query(..., description="Odometer in"),
    miles_out: int = Query(..., description="Odometer out")
):
    """
    Post repair order (finalize and lock)

    - **ro_id**: Repair order ID
    - **posted_date**: When RO is being posted
    - **miles_in**: Odometer reading in
    - **miles_out**: Odometer reading out
    """
    tm = get_tm_client()

    request_body = {
        "repairOrderStatus": {"id": 5},
        "postedDate": posted_date,
        "milesIn": miles_in,
        "milesOut": miles_out,
        "odometerInop": False,
        "leadSource": "API"
    }

    try:
        result = await tm.put(f"/api/repair-order/{ro_id}/status", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ro_id}/unpost")
async def unpost_ro(ro_id: int):
    """
    Unpost repair order (reopen for editing)

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()

    try:
        result = await tm.put(f"/api/repair-order/{ro_id}/unpost", {"value": False})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ro_id}/share/invoice")
async def share_invoice(ro_id: int, share_request: ShareEstimateRequest):
    """
    Send invoice to customer via email

    - **ro_id**: Repair order ID
    - **share_request**: Email addresses
    """
    tm = get_tm_client()

    if not share_request.email:
        raise HTTPException(status_code=400, detail="Email addresses required")

    try:
        result = await tm.post(
            f"/api/repair-order/{ro_id}/invoice/share",
            {"email": share_request.email}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}/transparency-settings")
async def get_transparency_settings(ro_id: int):
    """
    Get transparency settings for RO (what shows on printed estimates/invoices)

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/repair-order/{ro_id}/transparency-settings")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ro_id}/transparency-settings")
async def update_transparency_settings(ro_id: int, settings: List[dict]):
    """
    Update transparency settings (configure what's visible on estimates/invoices)

    - **ro_id**: Repair order ID
    - **settings**: Array of transparency setting objects
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.put(f"/api/repair-order/{ro_id}/transparency-settings", settings)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public/estimate/{nonce}")
async def get_public_estimate(nonce: str, jobs: Optional[str] = Query(None, description="Comma-separated job IDs")):
    """
    Get public estimate view (no auth required - uses nonce)

    - **nonce**: RO nonce
    - **jobs**: Optional comma-separated job IDs
    """
    tm = get_tm_client()

    params = {}
    if jobs:
        params["jobs"] = jobs
        params["sublets"] = ""

    try:
        result = await tm.get(f"/api/public/estimate/{nonce}", params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public/inspection/{nonce}")
async def get_public_inspection(nonce: str):
    """
    Get public inspection view (no auth required - uses nonce)

    - **nonce**: RO nonce
    """
    tm = get_tm_client()

    try:
        result = await tm.get(f"/api/public/inspection/{nonce}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
