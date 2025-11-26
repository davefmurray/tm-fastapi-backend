"""
Customer & Vehicle Endpoints

CRUD operations for customers and vehicles.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.tm_client import get_tm_client
from app.models.schemas import CustomerCreate, VehicleCreate

router = APIRouter()


@router.post("/")
async def create_customer(customer: CustomerCreate):
    """
    Create a new customer

    - **customer**: Customer details (name, email, phone, address, etc.)
    """
    tm = get_tm_client()
    shop_id = tm.shop_id

    request_body = {
        "shopId": int(shop_id),
        "firstName": customer.first_name,
        "lastName": customer.last_name,
        "businessName": customer.business_name,
        "email": customer.email,
        "phone": [
            {
                "number": phone.number,
                "type": phone.type,
                "primary": phone.primary,
                "tempId": 0.5  # Random temp ID for new phones
            }
            for phone in customer.phone
        ],
        "customerType": {"id": customer.customer_type_id},
        "contactFirstName": None,
        "contactLastName": None,
        "address": customer.address.dict() if customer.address else {},
        "taxExempt": customer.tax_exempt,
        "arCreditLimit": 0,
        "notes": "",
        "okForMarketing": customer.ok_for_marketing,
        "referrerId": None,
        "referrerName": None,
        "birthday": None,
        "requiredFieldValidationBypassed": False,
        "leadSource": customer.lead_source
    }

    try:
        result = await tm.post(
            f"/api/shop/{shop_id}/customers?checkForDuplicates=true",
            request_body
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_customers(
    q: str = Query(..., description="Search query"),
    size: int = Query(25, description="Results per page")
):
    """
    Search for customers

    - **q**: Search term (name, phone, email)
    - **size**: Number of results
    """
    tm = get_tm_client()
    shop_id = tm.shop_id

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/customers",
            {"search": q, "size": size}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}")
async def get_customer(customer_id: int):
    """
    Get customer details

    - **customer_id**: Customer ID
    """
    tm = get_tm_client()
    shop_id = tm.shop_id

    try:
        result = await tm.get(f"/api/shop/{shop_id}/customer/{customer_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vehicles")
async def create_vehicle(vehicle: VehicleCreate):
    """
    Create a new vehicle for a customer

    - **vehicle**: Vehicle details (year, make, model, customer_id, etc.)
    """
    tm = get_tm_client()
    shop_id = tm.shop_id

    # Get VCDB vehicle data first
    try:
        vcdb_data = await tm.get(f"/api/vcdb/vehicles/{vehicle.vehicle_id}")
    except:
        vcdb_data = {}

    request_body = {
        "customerId": vehicle.customer_id,
        "year": vehicle.year,
        "makeId": vehicle.make_id,
        "make": vehicle.make,
        "modelId": vehicle.model_id,
        "model": vehicle.model,
        "subModelId": vehicle.sub_model_id,
        "subModel": vehicle.sub_model,
        "baseVehicleId": vehicle.base_vehicle_id,
        "vehicleId": vehicle.vehicle_id,
        "vin": vehicle.vin,
        "licensePlate": vehicle.license_plate,
        "color": vehicle.color,
        "custom": False,
        **vcdb_data  # Include VCDB ACES data
    }

    try:
        result = await tm.post(
            f"/api/shop/{shop_id}/customer/vehicle?checkForDuplicateVehicle=true",
            request_body
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}/vehicles")
async def get_customer_vehicles(customer_id: int):
    """
    Get all vehicles for a customer

    - **customer_id**: Customer ID
    """
    tm = get_tm_client()
    shop_id = tm.shop_id

    try:
        result = await tm.get(
            f"/api/shop/{shop_id}/customer/{customer_id}/vehicles-search",
            {"archivedOnly": "false", "size": "100"}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
