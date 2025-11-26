"""
Authorization Endpoints

Customer and shop-side job authorization workflow.
"""

from fastapi import APIRouter, HTTPException
from typing import List
from app.services.tm_client import get_tm_client
from app.models.schemas import AuthorizationRequest, JobAuthStatus

router = APIRouter()


@router.post("/authorize/{nonce}")
async def submit_authorization(
    nonce: str,
    authorization: AuthorizationRequest,
    jobs: List[JobAuthStatus]
):
    """
    Submit customer or shop-side authorization

    - **nonce**: RO nonce (from RO data)
    - **authorization**: Authorization details (method, authorizer, date, etc.)
    - **jobs**: List of jobs with authorized status
    """
    tm = get_tm_client()

    # Build TM request body
    request_body = {
        "authorization": {
            "allPendingDeclined": authorization.all_pending_declined,
            "method": authorization.method,
            "authorizer": authorization.authorizer,
            "date": authorization.date,
            "timeZone": authorization.timezone,
            "smsConsentPhone": None,
            "notificationEmails": [],
        },
        "jobs": [
            {
                "id": job.id,
                "authorized": job.authorized,
                "selected": job.selected
            }
            for job in jobs
        ],
        "sublets": []
    }

    # Add signature if provided (digital signature)
    if authorization.signature:
        request_body["authorization"]["signature"] = authorization.signature

    try:
        result = await tm.post(f"/api/public/authorize/{nonce}", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/authorizations/{ro_id}")
async def get_authorization_history(ro_id: int):
    """
    Get authorization history for a repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/repair-order/{ro_id}/authorizations")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/job/{job_id}/remove-auth")
async def remove_auth_status(job_id: int):
    """
    Remove authorization status from job (reset to Pending)

    - **job_id**: Job ID
    """
    tm = get_tm_client()

    try:
        result = await tm.patch(f"/api/job/{job_id}", {"removeAuthStatus": True})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
