"""
Inventory Management Endpoints

Parts inventory tracking and search.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.services.tm_client import get_tm_client

router = APIRouter()


@router.get("/search")
async def search_inventory(
    part_numbers: str = Query(..., description="Comma-separated part numbers"),
    include_statistics: bool = Query(True, description="Include stock statistics")
):
    """
    Search inventory by part numbers

    - **part_numbers**: Comma-separated part numbers
    - **include_statistics**: Include stock levels
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/inventory/search/part-number-map",
            {
                "partNumbers": part_numbers,
                "includeStatistics": str(include_statistics).lower()
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/part/{part_id}")
async def get_inventory_part(part_id: int):
    """
    Get inventory part details

    - **part_id**: Inventory part ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(f"/api/shop/{shop_id}/inventory/part/{part_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
