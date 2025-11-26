"""
Pydantic Models for Request/Response Validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Authorization Models
class AuthorizationRequest(BaseModel):
    """Request to authorize jobs"""
    method: str = Field(default="VERBAL_IN_PERSON", description="Authorization method")
    authorizer: str = Field(..., description="Customer name")
    date: str = Field(..., description="Authorization date (ISO 8601)")
    timezone: str = Field(default="America/New_York", description="Shop timezone")
    signature: Optional[str] = Field(None, description="Base64 PNG signature")
    all_pending_declined: bool = Field(default=False, description="Decline all pending")


class JobAuthStatus(BaseModel):
    """Job authorization status"""
    id: int
    authorized: bool
    selected: bool = True


# Payment Models
class PaymentRequest(BaseModel):
    """Request to create payment"""
    customer_name: str
    customer_id: int
    amount: int = Field(..., description="Amount in cents")
    payment_type_id: int = Field(..., description="Payment type ID")
    payment_date: str
    should_post: bool = False


class PaymentResponse(BaseModel):
    """Payment response"""
    id: int
    amount: int
    payment_date: str
    status: str
    payment_type_id: int


# Customer Models
class PhoneNumber(BaseModel):
    """Customer phone number"""
    number: str
    type: str = "Mobile"
    primary: bool = True


class Address(BaseModel):
    """Customer/shop address"""
    address1: str
    address2: Optional[str] = ""
    city: str
    state: str
    zip: str


class CustomerCreate(BaseModel):
    """Create customer request"""
    first_name: str
    last_name: str
    business_name: Optional[str] = ""
    email: List[str] = []
    phone: List[PhoneNumber]
    customer_type_id: int = 1  # 1 = PERSON, 2 = BUSINESS
    address: Optional[Address] = None
    tax_exempt: bool = False
    ok_for_marketing: bool = True
    lead_source: Optional[str] = None


class CustomerResponse(BaseModel):
    """Customer response"""
    id: int
    first_name: str
    last_name: str
    full_name: str
    email: List[str]
    shop_id: int


# Vehicle Models
class VehicleCreate(BaseModel):
    """Create vehicle request"""
    customer_id: int
    year: int
    make: str
    make_id: int
    model: str
    model_id: int
    sub_model: Optional[str] = None
    sub_model_id: Optional[int] = None
    vehicle_id: int
    base_vehicle_id: int
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    color: Optional[str] = None


# Dashboard Models
class DashboardSummary(BaseModel):
    """Dashboard summary metrics"""
    sold: int = Field(..., description="Sold amount in cents")
    posted: int = Field(..., description="Posted amount in cents")
    pending: int = Field(..., description="Pending amount in cents")
    declined: int = Field(..., description="Declined amount in cents")
    sold_job_count: int
    posted_job_count: int
    pending_job_count: int
    declined_job_count: int
    close_ratio: float
    average_ro: float


# RO Models
class ROListQuery(BaseModel):
    """Query parameters for RO list"""
    board: str = Field(default="ACTIVE", description="ACTIVE, POSTED, or COMPLETE")
    page: int = Field(default=0, ge=0)
    group_by: str = Field(default="ROSTATUS", description="ROSTATUS, SERVICEWRITER, TECHNICIAN, NONE")
    search: Optional[str] = None


class RepairOrderBasic(BaseModel):
    """Basic RO information"""
    id: int
    repair_order_number: int
    customer_full_name: str
    vehicle_description: str
    balance_due: int
    amount_paid: int
    status: str
    progress: float


# Share Models
class ShareEstimateRequest(BaseModel):
    """Request to share estimate"""
    email: Optional[List[str]] = None
    phone: Optional[str] = None
    message: Optional[str] = None
