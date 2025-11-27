"""
Gross Profit Calculator Service - Tier 1 + Tier 2 Implementation

Tier 1 - Accurate GP calculations:
- Quantity-aware parts profit (Fix 1.1)
- Tech rate fallback logic (Fix 1.2)
- Fee inclusion in GP (Fix 1.3)
- Discount handling (Fix 1.4)

Tier 2 - Structural improvements:
- Tax attribution by category (Fix 2.3)
- Fee breakdown with categorization (Fix 2.4)
- Caching for shop config (Fix 2.5)

All monetary values are in CENTS internally.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio


# Default fallback rate when no tech assigned and no shop average available
DEFAULT_TECH_RATE_CENTS = 2500  # $25/hr in cents
DEFAULT_TAX_RATE = 0.075  # 7.5%

# Cache TTL
CACHE_TTL_SECONDS = 300  # 5 minutes


# ============== Tier 2: Fee Categories ==============

def classify_fee(fee_name: str) -> str:
    """Classify fee by name into category"""
    name_lower = fee_name.lower()
    if "shop" in name_lower and "suppl" in name_lower:
        return "shop_supplies"
    elif "environ" in name_lower:
        return "environmental"
    elif "hazard" in name_lower or "haz" in name_lower:
        return "hazardous_waste"
    elif "dispos" in name_lower:
        return "disposal"
    return "other"


# ============== Dataclasses ==============

@dataclass
class PartProfit:
    """Part profit calculation result"""
    part_id: int
    name: str
    quantity: float
    cost_per_unit: int  # cents
    retail_per_unit: int  # cents
    total_cost: int  # cents
    total_retail: int  # cents
    profit: int  # cents
    margin_pct: float


@dataclass
class LaborProfit:
    """Labor profit calculation result"""
    labor_id: int
    name: str
    hours: float
    rate: int  # cents per hour (retail)
    tech_rate: int  # cents per hour (cost)
    tech_rate_source: str  # 'assigned', 'shop_average', 'default'
    tech_name: Optional[str]  # Tier 2: track tech name
    total_retail: int  # cents
    total_cost: int  # cents
    profit: int  # cents
    margin_pct: float


@dataclass
class FeeDetail:
    """Tier 2: Detailed fee with categorization"""
    fee_name: str
    category: str  # shop_supplies, environmental, hazardous_waste, disposal, other
    amount: int  # cents
    profit: int  # cents (100% margin)
    percentage: float  # original percentage rate
    cap: int  # cents
    taxable: bool


@dataclass
class FeeBreakdown:
    """Tier 2: Complete fee breakdown"""
    fees: List[FeeDetail] = field(default_factory=list)
    total_fees: int = 0  # cents
    total_fee_profit: int = 0  # cents
    taxable_fees: int = 0  # cents
    by_category: Dict[str, int] = field(default_factory=dict)


@dataclass
class TaxBreakdown:
    """Tier 2: Tax attribution by category"""
    parts_tax: int = 0  # cents
    labor_tax: int = 0  # cents
    fees_tax: int = 0  # cents
    sublet_tax: int = 0  # cents
    total_tax: int = 0  # cents
    tax_rate: float = 0.0


@dataclass
class SubletProfit:
    """Tier 2: Sublet with full details"""
    sublet_id: int
    name: str
    vendor: Optional[str]
    cost: int  # cents
    retail: int  # cents
    profit: int  # cents
    margin_pct: float


@dataclass
class JobGP:
    """Job-level GP calculation result"""
    job_id: int
    job_name: str
    authorized: bool
    authorized_date: Optional[str]
    # Parts
    parts_retail: int
    parts_cost: int
    parts_profit: int
    parts_detail: List[PartProfit] = field(default_factory=list)
    # Labor
    labor_retail: int
    labor_cost: int
    labor_profit: int
    labor_detail: List[LaborProfit] = field(default_factory=list)
    # Sublets
    sublet_retail: int
    sublet_cost: int
    sublet_profit: int
    sublet_detail: List[SubletProfit] = field(default_factory=list)
    # Totals
    discount_amount: int = 0
    subtotal: int = 0
    gross_profit: int = 0
    margin_pct: float = 0.0


@dataclass
class ROTrueGP:
    """RO-level true GP calculation result - Tier 2 enhanced"""
    ro_id: int
    ro_number: int
    customer_name: str
    vehicle_description: Optional[str]
    # Revenue
    total_retail: int
    total_cost: int
    gross_profit: int
    margin_pct: float
    # Category breakdowns
    parts_retail: int = 0
    parts_cost: int = 0
    parts_profit: int = 0
    labor_retail: int = 0
    labor_cost: int = 0
    labor_profit: int = 0
    sublet_retail: int = 0
    sublet_cost: int = 0
    sublet_profit: int = 0
    # Tier 2: Fee breakdown
    fee_breakdown: Optional[FeeBreakdown] = None
    fee_profit: int = 0
    # Tier 2: Tax breakdown
    tax_breakdown: Optional[TaxBreakdown] = None
    tax_total: int = 0
    # Discounts
    job_discounts: int = 0
    ro_discount: int = 0
    discount_total: int = 0
    # Balance
    balance_due: int = 0
    # Jobs
    jobs: List[JobGP] = field(default_factory=list)
    authorized_job_count: int = 0
    total_job_count: int = 0
    # Meta
    calculation_notes: List[str] = field(default_factory=list)


@dataclass
class ShopConfig:
    """Tier 2: Cached shop configuration"""
    shop_id: str
    shop_name: Optional[str]
    avg_tech_rate: int  # cents
    tech_rates: Dict[int, int] = field(default_factory=dict)  # employee_id -> rate
    tech_names: Dict[int, str] = field(default_factory=dict)  # employee_id -> name
    tax_rate: float = DEFAULT_TAX_RATE
    cached_at: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        return (datetime.now() - self.cached_at).total_seconds() > CACHE_TTL_SECONDS


# ============== Cache ==============

_shop_config_cache: Dict[str, ShopConfig] = {}


async def get_shop_config(tm_client, shop_id: str, force_refresh: bool = False) -> ShopConfig:
    """
    Tier 2: Get cached shop configuration.
    
    Caches tech rates, shop info to reduce API calls.
    """
    global _shop_config_cache
    
    # Check cache
    if not force_refresh and shop_id in _shop_config_cache:
        cached = _shop_config_cache[shop_id]
        if not cached.is_expired():
            return cached
    
    # Fetch fresh data
    try:
        employees = await tm_client.get(
            f"/api/shop/{shop_id}/employees-lite",
            {"size": 500, "status": "ACTIVE"}
        )
        
        tech_rates = {}
        tech_names = {}
        rate_values = []
        
        for emp in employees:
            emp_id = emp.get('id')
            # Technicians (role = 3)
            if emp.get('role') == 3 and emp.get('hourlyRate'):
                rate = int(emp['hourlyRate'])
                tech_rates[emp_id] = rate
                tech_names[emp_id] = f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip()
                rate_values.append(rate)
        
        avg_rate = int(sum(rate_values) / len(rate_values)) if rate_values else DEFAULT_TECH_RATE_CENTS
        
        config = ShopConfig(
            shop_id=shop_id,
            shop_name=None,  # Could fetch from shop endpoint if needed
            avg_tech_rate=avg_rate,
            tech_rates=tech_rates,
            tech_names=tech_names,
            tax_rate=DEFAULT_TAX_RATE,
            cached_at=datetime.now()
        )
        
        _shop_config_cache[shop_id] = config
        return config
        
    except Exception as e:
        print(f"[GP Calculator] Error fetching shop config: {e}")
        # Return default config
        return ShopConfig(
            shop_id=shop_id,
            shop_name=None,
            avg_tech_rate=DEFAULT_TECH_RATE_CENTS,
            cached_at=datetime.now()
        )


def clear_shop_config_cache(shop_id: Optional[str] = None):
    """Clear shop config cache"""
    global _shop_config_cache
    if shop_id:
        _shop_config_cache.pop(shop_id, None)
    else:
        _shop_config_cache.clear()


# ============== Calculation Functions ==============

def detect_cost_format(part: dict) -> Tuple[int, int, str]:
    """
    Detect if part cost is per-unit or already multiplied by quantity.
    Returns: (cost_per_unit, retail_per_unit, detection_method)
    """
    cost = int(part.get('cost', 0))
    retail = int(part.get('retail', 0))
    quantity = float(part.get('quantity', 1.0))
    total_field = int(part.get('total', 0))

    if quantity <= 0:
        quantity = 1.0

    if total_field > 0 and quantity > 1:
        calculated_total = retail * quantity
        if abs(calculated_total - total_field) / total_field < 0.01:
            return cost, retail, 'per_unit_validated'
        if abs(retail - total_field) / total_field < 0.01:
            return int(cost / quantity), int(retail / quantity), 'total_divided'

    return cost, retail, 'assumed_per_unit'


def calculate_part_profit(part: dict) -> PartProfit:
    """Calculate part profit with quantity awareness (Fix 1.1)."""
    part_id = part.get('id', 0)
    name = part.get('name', 'Unknown Part')
    quantity = float(part.get('quantity', 1.0))

    if quantity <= 0:
        quantity = 1.0

    cost_per_unit, retail_per_unit, _ = detect_cost_format(part)

    total_cost = int(cost_per_unit * quantity)
    total_retail = int(retail_per_unit * quantity)
    profit = total_retail - total_cost
    margin_pct = (profit / total_retail * 100) if total_retail > 0 else 0.0

    return PartProfit(
        part_id=part_id,
        name=name,
        quantity=quantity,
        cost_per_unit=cost_per_unit,
        retail_per_unit=retail_per_unit,
        total_cost=total_cost,
        total_retail=total_retail,
        profit=profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_labor_cost(
    labor: dict,
    shop_config: Optional[ShopConfig] = None
) -> LaborProfit:
    """
    Calculate labor profit with 3-level tech rate fallback (Fix 1.2).
    Tier 2: Uses ShopConfig for cached rates and tech names.
    """
    labor_id = labor.get('id', 0)
    name = labor.get('name', 'Labor')
    hours = float(labor.get('hours', 0))
    rate = int(labor.get('rate', 0))

    tech_rate = 0
    tech_rate_source = 'default'
    tech_name = None

    technician = labor.get('technician')
    if technician:
        tech_id = technician.get('id')
        if technician.get('hourlyRate'):
            tech_rate = int(technician['hourlyRate'])
            tech_rate_source = 'assigned'
            tech_name = f"{technician.get('firstName', '')} {technician.get('lastName', '')}".strip()
        elif shop_config and tech_id in shop_config.tech_rates:
            tech_rate = shop_config.tech_rates[tech_id]
            tech_name = shop_config.tech_names.get(tech_id)
            tech_rate_source = 'assigned'
    
    if tech_rate == 0:
        if shop_config and shop_config.avg_tech_rate > 0:
            tech_rate = shop_config.avg_tech_rate
            tech_rate_source = 'shop_average'
        else:
            tech_rate = DEFAULT_TECH_RATE_CENTS
            tech_rate_source = 'default'

    total_retail = int(hours * rate)
    total_cost = int(hours * tech_rate)
    profit = total_retail - total_cost
    margin_pct = (profit / total_retail * 100) if total_retail > 0 else 0.0

    return LaborProfit(
        labor_id=labor_id,
        name=name,
        hours=hours,
        rate=rate,
        tech_rate=tech_rate,
        tech_rate_source=tech_rate_source,
        tech_name=tech_name,
        total_retail=total_retail,
        total_cost=total_cost,
        profit=profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_fee_detail(fee: dict, subtotal: int) -> FeeDetail:
    """
    Tier 2: Calculate fee with categorization.
    """
    fee_name = fee.get('name', 'Fee')
    percentage = float(fee.get('percentage', 0))
    cap = int(fee.get('cap', 0))
    taxable = fee.get('taxable', False)
    category = classify_fee(fee_name)

    if percentage > 0 and subtotal > 0:
        calculated = int(subtotal * percentage / 100)
        amount = min(calculated, cap) if cap > 0 else calculated
    else:
        amount = int(fee.get('amount', 0))

    return FeeDetail(
        fee_name=fee_name,
        category=category,
        amount=amount,
        profit=amount,  # 100% margin
        percentage=percentage,
        cap=cap,
        taxable=taxable
    )


def calculate_fee_breakdown(fees_data: List[dict], subtotal: int) -> FeeBreakdown:
    """
    Tier 2: Calculate complete fee breakdown with categorization.
    """
    fees = []
    total_fees = 0
    taxable_fees = 0
    by_category: Dict[str, int] = {}
    
    for fee in fees_data:
        fd = calculate_fee_detail(fee, subtotal)
        fees.append(fd)
        total_fees += fd.amount
        if fd.taxable:
            taxable_fees += fd.amount
        by_category[fd.category] = by_category.get(fd.category, 0) + fd.amount
    
    return FeeBreakdown(
        fees=fees,
        total_fees=total_fees,
        total_fee_profit=total_fees,  # 100% margin
        taxable_fees=taxable_fees,
        by_category=by_category
    )


def calculate_tax_breakdown(estimate: dict, parts_retail: int, labor_retail: int, 
                           fee_taxable: int, sublet_retail: int) -> TaxBreakdown:
    """
    Tier 2: Calculate tax attribution by category.
    
    Uses per-job tax fields if available, otherwise estimates from tax rate.
    """
    total_tax = int(estimate.get('tax', 0))
    tax_rate = float(estimate.get('taxRate', DEFAULT_TAX_RATE))
    
    # Try to get per-job breakdown
    parts_tax = 0
    labor_tax = 0
    fees_tax = 0
    sublet_tax = 0
    
    for job in estimate.get('jobs', []):
        if job.get('authorized'):
            parts_tax += int(job.get('partsTaxTotal', 0))
            labor_tax += int(job.get('laborTaxTotal', 0))
            fees_tax += int(job.get('feesTaxTotal', 0))
    
    # If breakdown available, use it
    attributed_tax = parts_tax + labor_tax + fees_tax
    
    if attributed_tax > 0:
        # We have detailed breakdown, estimate sublet tax from remainder
        sublet_tax = total_tax - attributed_tax
    else:
        # Estimate tax distribution based on retail values
        taxable_total = parts_retail + labor_retail + fee_taxable + sublet_retail
        if taxable_total > 0 and total_tax > 0:
            parts_tax = int(total_tax * parts_retail / taxable_total)
            labor_tax = int(total_tax * labor_retail / taxable_total)
            fees_tax = int(total_tax * fee_taxable / taxable_total)
            sublet_tax = total_tax - parts_tax - labor_tax - fees_tax
    
    return TaxBreakdown(
        parts_tax=parts_tax,
        labor_tax=labor_tax,
        fees_tax=fees_tax,
        sublet_tax=sublet_tax,
        total_tax=total_tax,
        tax_rate=tax_rate
    )


def calculate_sublet_profit(sublet: dict) -> SubletProfit:
    """Tier 2: Calculate sublet profit with full details."""
    sublet_id = sublet.get('id', 0)
    name = sublet.get('name', 'Sublet')
    vendor = sublet.get('vendor', {}).get('name') if sublet.get('vendor') else None
    retail = int(sublet.get('retail', 0))
    cost = int(sublet.get('cost', 0))
    profit = retail - cost
    margin_pct = (profit / retail * 100) if retail > 0 else 0.0
    
    return SubletProfit(
        sublet_id=sublet_id,
        name=name,
        vendor=vendor,
        cost=cost,
        retail=retail,
        profit=profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_job_gp(
    job: dict,
    shop_config: Optional[ShopConfig] = None
) -> JobGP:
    """Calculate GP for a single job including all line items."""
    job_id = job.get('id', 0)
    job_name = job.get('name', 'Unknown Job')
    authorized = job.get('authorized', False)
    authorized_date = job.get('authorizedDate')

    # Parts
    parts_detail = []
    parts_retail = 0
    parts_cost = 0
    for part in job.get('parts', []):
        pp = calculate_part_profit(part)
        parts_detail.append(pp)
        parts_retail += pp.total_retail
        parts_cost += pp.total_cost
    parts_profit = parts_retail - parts_cost

    # Labor
    labor_detail = []
    labor_retail = 0
    labor_cost = 0
    for labor in job.get('labor', []):
        lp = calculate_labor_cost(labor, shop_config)
        labor_detail.append(lp)
        labor_retail += lp.total_retail
        labor_cost += lp.total_cost
    labor_profit = labor_retail - labor_cost

    # Sublets
    sublet_detail = []
    sublet_retail = 0
    sublet_cost = 0
    for sublet in job.get('sublets', []):
        sp = calculate_sublet_profit(sublet)
        sublet_detail.append(sp)
        sublet_retail += sp.retail
        sublet_cost += sp.cost
    sublet_profit = sublet_retail - sublet_cost

    # Discount
    discount_amount = int(job.get('discount', 0))

    # Subtotal and GP
    subtotal = parts_retail + labor_retail + sublet_retail - discount_amount
    total_cost = parts_cost + labor_cost + sublet_cost
    gross_profit = subtotal - total_cost
    margin_pct = (gross_profit / subtotal * 100) if subtotal > 0 else 0.0

    return JobGP(
        job_id=job_id,
        job_name=job_name,
        authorized=authorized,
        authorized_date=authorized_date,
        parts_retail=parts_retail,
        parts_cost=parts_cost,
        parts_profit=parts_profit,
        parts_detail=parts_detail,
        labor_retail=labor_retail,
        labor_cost=labor_cost,
        labor_profit=labor_profit,
        labor_detail=labor_detail,
        sublet_retail=sublet_retail,
        sublet_cost=sublet_cost,
        sublet_profit=sublet_profit,
        sublet_detail=sublet_detail,
        discount_amount=discount_amount,
        subtotal=subtotal,
        gross_profit=gross_profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_ro_true_gp(
    estimate: dict,
    shop_config: Optional[ShopConfig] = None,
    shop_average_rate: Optional[int] = None,  # Legacy param
    authorized_only: bool = True
) -> ROTrueGP:
    """
    Calculate TRUE GP for an entire RO.
    
    Tier 1 + Tier 2: Full GP calculation with:
    - Quantity-aware parts
    - Tech rate fallback
    - Fee breakdown with categorization
    - Tax attribution by category
    - Discount handling
    """
    # Build shop config if only rate provided (legacy support)
    if shop_config is None and shop_average_rate:
        shop_config = ShopConfig(
            shop_id="",
            shop_name=None,
            avg_tech_rate=shop_average_rate
        )
    
    ro_id = estimate.get('id', 0)
    ro_number = estimate.get('repairOrderNumber', 0)
    customer = estimate.get('customer', {})
    customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
    
    vehicle = estimate.get('vehicle', {})
    vehicle_description = None
    if vehicle:
        vehicle_description = f"{vehicle.get('year', '')} {vehicle.get('make', '')} {vehicle.get('model', '')}".strip()

    notes = []
    job_results = []

    # Aggregate from jobs
    total_parts_retail = 0
    total_parts_cost = 0
    total_labor_retail = 0
    total_labor_cost = 0
    total_sublet_retail = 0
    total_sublet_cost = 0
    job_discounts = 0
    authorized_count = 0
    total_job_count = len(estimate.get('jobs', []))

    for job in estimate.get('jobs', []):
        job_gp = calculate_job_gp(job, shop_config)
        
        if authorized_only and not job_gp.authorized:
            continue

        job_results.append(job_gp)
        authorized_count += 1

        total_parts_retail += job_gp.parts_retail
        total_parts_cost += job_gp.parts_cost
        total_labor_retail += job_gp.labor_retail
        total_labor_cost += job_gp.labor_cost
        total_sublet_retail += job_gp.sublet_retail
        total_sublet_cost += job_gp.sublet_cost
        job_discounts += job_gp.discount_amount

    # Subtotal before fees
    subtotal_before_fees = (
        total_parts_retail +
        total_labor_retail +
        total_sublet_retail -
        job_discounts
    )

    # Tier 2: Fee breakdown
    fees_data = estimate.get('fees', {}).get('data', [])
    fee_breakdown = calculate_fee_breakdown(fees_data, subtotal_before_fees)
    
    for fd in fee_breakdown.fees:
        if fd.amount > 0:
            notes.append(f"Fee '{fd.fee_name}' ({fd.category}): ${fd.amount/100:.2f}")

    # RO-level discount
    ro_discount = int(estimate.get('discount', 0))
    total_discount = job_discounts + ro_discount
    if ro_discount > 0:
        notes.append(f"RO-level discount: ${ro_discount/100:.2f}")

    # Total retail
    total_retail = subtotal_before_fees + fee_breakdown.total_fees - ro_discount

    # Total cost (fees have no cost)
    total_cost = total_parts_cost + total_labor_cost + total_sublet_cost

    # Gross profit
    gross_profit = total_retail - total_cost

    # Tier 2: Tax breakdown
    tax_breakdown = calculate_tax_breakdown(
        estimate,
        total_parts_retail,
        total_labor_retail,
        fee_breakdown.taxable_fees,
        total_sublet_retail
    )

    # Balance due
    balance_due = int(estimate.get('balanceDue', 0))

    # Margin
    margin_pct = (gross_profit / total_retail * 100) if total_retail > 0 else 0.0

    # Summary note
    if authorized_only:
        notes.insert(0, f"Authorized jobs: {authorized_count}/{total_job_count}")

    return ROTrueGP(
        ro_id=ro_id,
        ro_number=ro_number,
        customer_name=customer_name,
        vehicle_description=vehicle_description,
        total_retail=total_retail,
        total_cost=total_cost,
        gross_profit=gross_profit,
        margin_pct=round(margin_pct, 2),
        parts_retail=total_parts_retail,
        parts_cost=total_parts_cost,
        parts_profit=total_parts_retail - total_parts_cost,
        labor_retail=total_labor_retail,
        labor_cost=total_labor_cost,
        labor_profit=total_labor_retail - total_labor_cost,
        sublet_retail=total_sublet_retail,
        sublet_cost=total_sublet_cost,
        sublet_profit=total_sublet_retail - total_sublet_cost,
        fee_breakdown=fee_breakdown,
        fee_profit=fee_breakdown.total_fee_profit,
        tax_breakdown=tax_breakdown,
        tax_total=tax_breakdown.total_tax,
        job_discounts=job_discounts,
        ro_discount=ro_discount,
        discount_total=total_discount,
        balance_due=balance_due,
        jobs=job_results,
        authorized_job_count=authorized_count,
        total_job_count=total_job_count,
        calculation_notes=notes
    )


# ============== Legacy Functions (backwards compatibility) ==============

async def get_shop_average_tech_rate(tm_client, shop_id: str) -> int:
    """
    Legacy function for Tier 1 compatibility.
    Use get_shop_config() for Tier 2.
    """
    config = await get_shop_config(tm_client, shop_id)
    return config.avg_tech_rate


def to_dict(obj) -> dict:
    """Convert dataclass to dictionary for JSON serialization."""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if isinstance(value, list):
                result[field_name] = [to_dict(item) for item in value]
            elif hasattr(value, '__dataclass_fields__'):
                result[field_name] = to_dict(value)
            elif isinstance(value, datetime):
                result[field_name] = value.isoformat()
            else:
                result[field_name] = value
        return result
    return obj


def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars with 2 decimal places"""
    return round(cents / 100, 2)


def to_dollars_dict(obj) -> dict:
    """Convert dataclass to dict with cents converted to dollars."""
    d = to_dict(obj)
    return _convert_cents_to_dollars(d)


def _convert_cents_to_dollars(d: Any) -> Any:
    """Recursively convert cent fields to dollars."""
    if isinstance(d, dict):
        result = {}
        for k, v in d.items():
            # Fields that are in cents
            if any(x in k for x in ['cost', 'retail', 'profit', 'amount', 'tax', 'discount', 'fee', 'due', 'subtotal', 'total']) and isinstance(v, (int, float)) and 'pct' not in k and 'rate' not in k.lower() and 'count' not in k:
                result[k] = round(v / 100, 2)
            elif k == 'rate' or k == 'tech_rate' or k == 'avg_tech_rate':
                result[k] = round(v / 100, 2)
            elif k == 'cap' and isinstance(v, (int, float)):
                result[k] = round(v / 100, 2)
            else:
                result[k] = _convert_cents_to_dollars(v)
        return result
    elif isinstance(d, list):
        return [_convert_cents_to_dollars(item) for item in d]
    return d
