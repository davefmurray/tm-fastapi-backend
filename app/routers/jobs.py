"""
Job Creation & Management Endpoints

Create jobs, add parts/labor, assign technicians.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.post("/")
async def create_or_update_job(job_data: dict):
    """
    Create new job or update existing job

    Single endpoint handles:
    - Creating jobs
    - Adding parts to jobs
    - Adding labor to jobs
    - Assigning technicians
    - Updating jobs

    Include "id" field to update existing job.
    Omit "id" to create new job.

    Required fields for new job:
    - name: Job name
    - repairOrderId: RO ID
    - syncPartsAttachedToNonQuotedOrders: false

    Parts array items need tempId (Math.random()) for new parts.
    Labor array items need tempId for new labor.
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.post(f"/api/shop/{shop_id}/job", job_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(job_id: int):
    """
    Delete a job from repair order

    - **job_id**: Job ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.delete(f"/api/shop/{shop_id}/job?jobId={job_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profit/{ro_id}")
async def get_profit_breakdown(ro_id: int):
    """
    Get profit breakdown for repair order

    Returns labor costs, parts costs, margins, GP%

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()

    try:
        result = await tm.get(f"/api/repair-order/{ro_id}/profit/labor")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/canned")
async def get_canned_jobs(
    search: str = Query("", description="Search term"),
    size: int = Query(20, description="Results per page")
):
    """
    Get canned jobs (job templates)

    - **search**: Search term
    - **size**: Number of results
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/canned-jobs",
            {"search": search, "size": size}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_job_categories():
    """
    Get all job categories (Oil Change, Brake Service, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/job-categories")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/favorite")
async def get_favorite_jobs():
    """
    Get favorite jobs for quick access
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/favorite-jobs")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
