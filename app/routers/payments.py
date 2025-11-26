"""
Payment Endpoints

Payment creation, listing, and void operations.
"""

from fastapi import APIRouter, HTTPException
from app.services.tm_client import get_tm_client
from app.models.schemas import PaymentRequest

router = APIRouter()


@router.post("/{ro_id}")
async def create_payment(ro_id: int, payment: PaymentRequest):
    """
    Create payment for a repair order

    - **ro_id**: Repair order ID
    - **payment**: Payment details (amount in cents, type, customer info)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    request_body = {
        "customerName": payment.customer_name,
        "paymentTypeId": payment.payment_type_id,
        "shopId": int(shop_id),
        "amount": payment.amount,
        "paymentMetadata": {
            "repairOrderIds": [ro_id],
            "shopId": int(shop_id)
        },
        "paymentProviderType": "NON_INTEGRATED",
        "paymentDate": payment.payment_date,
        "shouldPost": payment.should_post,
        "overpaymentAmount": 0,
        "customerId": payment.customer_id,
        "convertToStoreCredit": False
    }

    try:
        # Create payment attempt
        result = await tm.post(
            f"/api/tekmerchant/shop/{shop_id}/repair-orders/{ro_id}/payment-attempt",
            request_body
        )

        # Get payment status
        attempt_id = result.get("id")
        status = await tm.get(
            f"/api/tekmerchant/shop/{shop_id}/payment-attempts/{attempt_id}"
        )

        return {
            "attempt_id": attempt_id,
            "status": status.get("status"),
            "payment_id": status.get("paymentId"),
            "details": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ro_id}")
async def get_payments(ro_id: int):
    """
    Get all payments for a repair order

    - **ro_id**: Repair order ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/tekmerchant/shop/{shop_id}/repair-order/{ro_id}/payments"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{payment_id}/void")
async def void_payment(payment_id: int):
    """
    Void a payment

    - **payment_id**: Payment ID
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.put(
            f"/api/tekmerchant/shop/{shop_id}/repair-orders/payment/{payment_id}/void-attempt",
            {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def get_payment_types():
    """
    Get all payment types configured for shop

    Returns list of payment types with IDs (Cash, Credit Card, etc.)
    """
    tm = get_tm_client()
    await tm._ensure_token()
    shop_id = tm.get_shop_id()

    try:
        result = await tm.get(
            f"/api/tekmerchant/shop/{shop_id}/payment-settings/other-payment-types"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
