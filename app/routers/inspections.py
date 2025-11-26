"""
Inspection & Media Upload Endpoints

Inspection management and photo/video uploads.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/{ro_id}")
async def get_inspections(ro_id: int):
    """
    Get all inspections for repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get RO details which includes inspections
        result = await tm.get(f"/api/shop/{shop_id}/repair-order/{ro_id}")
        return result.get("inspections", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/media/video-upload-url")
async def create_video_upload_url(
    file_type: str = Query("video/mp4", description="Video MIME type"),
    file_name: str = Query(..., description="File name")
):
    """
    Get S3 presigned URL for video upload

    - **file_type**: Video MIME type (video/mp4, video/quicktime, etc.)
    - **file_name**: File name for video
    """
    tm = get_tm_client()
    await tm._ensure_token()

    request_body = {
        "fileType": file_type,
        "fileName": file_name
    }

    try:
        result = await tm.post("/media/create-video-upload-url", request_body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{inspection_id}/tasks/{task_id}/media")
async def create_media_upload(
    inspection_id: int,
    task_id: int,
    ro_id: int = Query(..., description="Repair order ID"),
    media_type: str = Query(..., description="PHOTO or VIDEO"),
    file_type: str = Query(..., description="MIME type"),
    file_name: str = Query(..., description="File name")
):
    """
    Create media upload for inspection task

    - **inspection_id**: Inspection ID
    - **task_id**: Task ID
    - **ro_id**: Repair order ID
    - **media_type**: PHOTO or VIDEO
    - **file_type**: MIME type
    - **file_name**: File name
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    request_body = {
        "mediaType": media_type,
        "fileType": file_type,
        "fileName": file_name
    }

    try:
        result = await tm.post(
            f"/api/repair-order/{ro_id}/inspection/{inspection_id}/item/{task_id}/media",
            request_body
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{inspection_id}/tasks/{task_id}/media/{media_id}/confirm")
async def confirm_media_upload(
    inspection_id: int,
    task_id: int,
    media_id: int,
    ro_id: int = Query(..., description="Repair order ID")
):
    """
    Confirm media upload after S3 upload completes

    - **inspection_id**: Inspection ID
    - **task_id**: Task ID
    - **media_id**: Media ID
    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.post(
            f"/api/repair-order/{ro_id}/inspection/{inspection_id}/item/{task_id}/media/{media_id}/confirm",
            {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{inspection_id}/tasks/{task_id}")
async def update_inspection_task(
    inspection_id: int,
    task_id: int,
    ro_id: int = Query(..., description="Repair order ID"),
    task_data: dict = {}
):
    """
    Update inspection task (rating, notes, media, etc.)

    - **inspection_id**: Inspection ID
    - **task_id**: Task ID
    - **ro_id**: Repair order ID
    - **task_data**: Task update data
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.put(
            f"/api/shop/{shop_id}/repair-orders/{ro_id}/inspections/{inspection_id}/tasks/{task_id}",
            task_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{inspection_id}/tasks")
async def get_inspection_tasks(
    inspection_id: int,
    ro_id: int = Query(..., description="Repair order ID")
):
    """
    Get all tasks for an inspection

    - **inspection_id**: Inspection ID
    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        # Get full RO data which includes inspection tasks
        ro = await tm.get(f"/api/shop/{shop_id}/repair-order/{ro_id}")

        # Find the inspection
        inspections = ro.get("inspections", [])
        for insp in inspections:
            if insp.get("id") == inspection_id:
                return insp.get("tasks", [])

        raise HTTPException(status_code=404, detail="Inspection not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
