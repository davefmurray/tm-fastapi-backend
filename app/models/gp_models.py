"""
Gross Profit Pydantic Models - Tier 2

Normalized response schemas for GP endpoints with:
- Tax attribution by category
- Fee breakdown with categorization
- Consistent decimal formatting (dollars, not cents)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TechRateSource(str, Enum):
    """Source of technician rate used in GP calculation"""
    ASSIGNED = "assigned"
    SHOP_AVERAGE = "shop_average"
    DEFAULT = "default"


class FeeCategory(str, Enum):
    """Fee categories for attribution"""
    SHOP_SUPPLIES = "shop_supplies"
    ENVIRONMENTAL = "environmental"
    HAZARDOUS_WASTE = "hazardous_waste"
    DISPOSAL = "disposal"
    OTHER = "other"


# ============== Tax Attribution Models ==============

class TaxBreakdown(BaseModel):
    """Tax breakdown by category"""
    parts_tax: float = Field(..., description="Tax on parts (dollars)")
    labor_tax: float = Field(..., description="Tax on labor (dollars)")
    fees_tax: float = Field(..., description="Tax on fees (dollars)")
    sublet_tax: float = Field(..., description="Tax on sublets (dollars)")
    total_tax: float = Field(..., description="Total tax (dollars)")
    tax_rate: float = Field(..., description="Tax rate as percentage")


# ============== Fee Attribution Models ==============

class FeeDetail(BaseModel):
    """Individual fee with categorization"""
    name: str
    category: FeeCategory
    amount: float = Field(..., description="Fee amount (dollars)")
    profit: float = Field(..., description="Fee profit - always 100% (dollars)")
    percentage: Optional[float] = Field(None, description="Percentage rate if applicable")
    cap: Optional[float] = Field(None, description="Cap amount if applicable (dollars)")
    taxable: bool = Field(default=False)


class FeeBreakdown(BaseModel):
    """Complete fee breakdown"""
    fees: List[FeeDetail] = []
    total_fees: float = Field(..., description="Total fees (dollars)")
    total_fee_profit: float = Field(..., description="Total fee profit (dollars)")
    taxable_fees: float = Field(..., description="Taxable fees amount (dollars)")


# ============== Part/Labor/Sublet Models ==============

class PartGP(BaseModel):
    """Part profit calculation result"""
    part_id: int
    name: str
    quantity: float
    cost_per_unit: float = Field(..., description="Cost per unit (dollars)")
    retail_per_unit: float = Field(..., description="Retail per unit (dollars)")
    total_cost: float = Field(..., description="Total cost (dollars)")
    total_retail: float = Field(..., description="Total retail (dollars)")
    profit: float = Field(..., description="Profit (dollars)")
    margin_pct: float = Field(..., description="Margin percentage")


class LaborGP(BaseModel):
    """Labor profit calculation result"""
    labor_id: int
    name: str
    hours: float
    retail_rate: float = Field(..., description="Retail rate per hour (dollars)")
    tech_rate: float = Field(..., description="Tech cost rate per hour (dollars)")
    tech_rate_source: TechRateSource
    tech_name: Optional[str] = Field(None, description="Assigned technician name")
    total_retail: float = Field(..., description="Total retail (dollars)")
    total_cost: float = Field(..., description="Total cost (dollars)")
    profit: float = Field(..., description="Profit (dollars)")
    margin_pct: float = Field(..., description="Margin percentage")


class SubletGP(BaseModel):
    """Sublet profit calculation result"""
    sublet_id: int
    name: str
    vendor: Optional[str] = None
    cost: float = Field(..., description="Cost (dollars)")
    retail: float = Field(..., description="Retail (dollars)")
    profit: float = Field(..., description="Profit (dollars)")
    margin_pct: float = Field(..., description="Margin percentage")


# ============== Job-Level Models ==============

class JobGPDetail(BaseModel):
    """Detailed job GP breakdown"""
    job_id: int
    job_name: str
    authorized: bool
    authorized_date: Optional[str] = None

    # Parts breakdown
    parts: List[PartGP] = []
    parts_retail: float
    parts_cost: float
    parts_profit: float
    parts_margin_pct: float

    # Labor breakdown
    labor: List[LaborGP] = []
    labor_retail: float
    labor_cost: float
    labor_profit: float
    labor_margin_pct: float

    # Sublet breakdown
    sublets: List[SubletGP] = []
    sublet_retail: float
    sublet_cost: float
    sublet_profit: float

    # Job totals
    discount: float = Field(default=0, description="Job-level discount (dollars)")
    subtotal: float = Field(..., description="Subtotal before tax (dollars)")
    gross_profit: float = Field(..., description="Job GP (dollars)")
    margin_pct: float = Field(..., description="Job margin percentage")


class JobGPSummary(BaseModel):
    """Summary job GP (without line-item detail)"""
    job_id: int
    job_name: str
    authorized: bool
    authorized_date: Optional[str] = None
    subtotal: float
    gross_profit: float
    margin_pct: float


# ============== RO-Level Models ==============

class ROGPDetail(BaseModel):
    """Complete RO GP with all breakdowns"""
    ro_id: int
    ro_number: int
    customer_name: str
    vehicle_description: Optional[str] = None

    # Revenue
    total_retail: float = Field(..., description="Total retail before tax (dollars)")
    total_cost: float = Field(..., description="Total cost (dollars)")
    gross_profit: float = Field(..., description="Total GP (dollars)")
    margin_pct: float = Field(..., description="Overall margin percentage")

    # Breakdowns
    parts_summary: dict = Field(..., description="Parts totals")
    labor_summary: dict = Field(..., description="Labor totals")
    sublet_summary: dict = Field(..., description="Sublet totals")
    fee_breakdown: FeeBreakdown
    tax_breakdown: TaxBreakdown

    # Discounts
    job_discounts: float = Field(default=0, description="Sum of job-level discounts")
    ro_discount: float = Field(default=0, description="RO-level discount")
    total_discount: float = Field(default=0, description="Total discounts")

    # Jobs
    jobs: List[JobGPSummary] = []
    authorized_job_count: int
    total_job_count: int

    # Metadata
    calculation_notes: List[str] = []


# ============== API Response Models ==============

class TrueMetricsResponse(BaseModel):
    """Response for /true-metrics endpoint"""
    date_range: dict

    # Core metrics (all in dollars)
    metrics: dict = Field(..., description="Aggregated metrics")

    # Breakdowns
    parts_total: float
    labor_total: float
    sublet_total: float
    fee_total: float
    discount_total: float

    # Tax attribution
    tax_breakdown: TaxBreakdown

    # Fee attribution
    fee_breakdown: FeeBreakdown

    # Calculation info
    calculation_info: dict

    # Optional details
    ro_details: Optional[List[ROGPDetail]] = None

    source: str = "TRUE_GP_TIER2"
    calculated_at: str


class CompareMetricsResponse(BaseModel):
    """Response for /compare-metrics endpoint"""
    date_range: dict
    tm_aggregates: dict
    true_metrics: dict
    deltas: dict

    # Detailed variance analysis
    variance_notes: List[str] = []

    calculated_at: str


class ShopConfigCache(BaseModel):
    """Cached shop configuration"""
    shop_id: str
    shop_name: Optional[str] = None
    avg_tech_rate: float = Field(..., description="Average tech rate (dollars/hr)")
    tech_rates: dict = Field(default_factory=dict, description="Individual tech rates by ID")
    tax_rate: float = Field(default=0.075, description="Default tax rate")
    fee_config: List[dict] = Field(default_factory=list, description="Fee configuration")
    cached_at: str
    expires_at: str


# ============== Helper Functions ==============

def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars with 2 decimal places"""
    return round(cents / 100, 2)


def dollars_to_cents(dollars: float) -> int:
    """Convert dollars to cents"""
    return int(dollars * 100)
