"""
Gross Profit Calculator Service - Tier 1 Implementation

Accurate GP calculations accounting for:
- Quantity-aware parts profit (Fix 1.1)
- Tech rate fallback logic (Fix 1.2)
- Fee inclusion in GP (Fix 1.3)
- Discount handling (Fix 1.4)

All monetary values are in CENTS.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# Default fallback rate when no tech assigned and no shop average available
DEFAULT_TECH_RATE_CENTS = 2500  # $25/hr in cents


@dataclass
class PartProfit:
    """Part profit calculation result"""
    part_id: int
    name: str
    quantity: float
    cost_per_unit: int  # cents
    retail_per_unit: int  # cents
    total_cost: int  # cents (cost_per_unit * quantity)
    total_retail: int  # cents (retail_per_unit * quantity)
    profit: int  # cents (total_retail - total_cost)
    margin_pct: float  # (profit / total_retail) * 100


@dataclass
class LaborProfit:
    """Labor profit calculation result"""
    labor_id: int
    name: str
    hours: float
    rate: int  # cents per hour (retail)
    tech_rate: int  # cents per hour (cost)
    tech_rate_source: str  # 'assigned', 'shop_average', 'default'
    total_retail: int  # cents (hours * rate)
    total_cost: int  # cents (hours * tech_rate)
    profit: int  # cents
    margin_pct: float


@dataclass
class FeeProfit:
    """Fee profit calculation result"""
    fee_name: str
    amount: int  # cents
    profit: int  # cents (100% margin, so profit = amount)
    taxable: bool


@dataclass
class JobGP:
    """Job-level GP calculation result"""
    job_id: int
    job_name: str
    authorized: bool
    authorized_date: Optional[str]
    parts_retail: int
    parts_cost: int
    parts_profit: int
    labor_retail: int
    labor_cost: int
    labor_profit: int
    sublet_retail: int
    sublet_cost: int
    sublet_profit: int
    discount_amount: int  # job-level discount
    subtotal: int  # before tax
    gross_profit: int  # total GP for job
    margin_pct: float


@dataclass
class ROTrueGP:
    """RO-level true GP calculation result"""
    ro_id: int
    ro_number: int
    customer_name: str
    total_retail: int  # sum of all job totals + fees
    total_cost: int
    gross_profit: int
    fee_profit: int
    discount_total: int  # all discounts applied
    tax_total: int
    balance_due: int
    margin_pct: float
    jobs: List[JobGP]
    calculation_notes: List[str]


def detect_cost_format(part: dict) -> Tuple[int, int, str]:
    """
    Detect if part cost is per-unit or already multiplied by quantity.

    TM API inconsistently returns:
    - Some endpoints: cost = per-unit cost
    - Some endpoints: cost = total cost (already multiplied)

    Heuristic: If cost * quantity is vastly different from 'total' field,
    cost is likely already the total.

    Returns: (cost_per_unit, retail_per_unit, detection_method)
    """
    cost = int(part.get('cost', 0))
    retail = int(part.get('retail', 0))
    quantity = float(part.get('quantity', 1.0))
    total_field = int(part.get('total', 0))

    if quantity <= 0:
        quantity = 1.0

    # If total field exists, use it to validate
    if total_field > 0 and quantity > 1:
        # Check if retail * quantity matches total
        calculated_total = retail * quantity

        # Allow 1% tolerance for rounding
        if abs(calculated_total - total_field) / total_field < 0.01:
            # retail is per-unit, assume cost is also per-unit
            return cost, retail, 'per_unit_validated'

        # If retail matches total, it's already multiplied
        if abs(retail - total_field) / total_field < 0.01:
            # retail and cost are likely totals, divide by quantity
            return int(cost / quantity), int(retail / quantity), 'total_divided'

    # Default: assume per-unit (most common in estimate endpoint)
    return cost, retail, 'assumed_per_unit'


def calculate_part_profit(part: dict) -> PartProfit:
    """
    Calculate part profit with quantity awareness (Fix 1.1).

    Handles TM API inconsistency where cost/retail may be:
    - Per-unit values (need to multiply by quantity)
    - Already multiplied totals (use as-is or divide)
    """
    part_id = part.get('id', 0)
    name = part.get('name', 'Unknown Part')
    quantity = float(part.get('quantity', 1.0))

    if quantity <= 0:
        quantity = 1.0

    # Detect format and get normalized per-unit values
    cost_per_unit, retail_per_unit, method = detect_cost_format(part)

    # Calculate totals
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
    shop_average_rate: Optional[int] = None
) -> LaborProfit:
    """
    Calculate labor profit with 3-level tech rate fallback (Fix 1.2).

    Tech rate hierarchy:
    1. Assigned technician's hourlyRate
    2. Shop average tech rate (if provided)
    3. Default fallback ($25/hr)

    This prevents 100% GP% when no tech is assigned.
    """
    labor_id = labor.get('id', 0)
    name = labor.get('name', 'Labor')
    hours = float(labor.get('hours', 0))
    rate = int(labor.get('rate', 0))  # Retail rate (what customer pays)

    # Determine tech cost rate with fallback chain
    tech_rate = 0
    tech_rate_source = 'default'

    technician = labor.get('technician')
    if technician and technician.get('hourlyRate'):
        tech_rate = int(technician['hourlyRate'])
        tech_rate_source = 'assigned'
    elif shop_average_rate and shop_average_rate > 0:
        tech_rate = shop_average_rate
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
        total_retail=total_retail,
        total_cost=total_cost,
        profit=profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_fee_profit(fee: dict, subtotal: int) -> FeeProfit:
    """
    Calculate fee profit (Fix 1.3).

    Shop fees (supplies, environmental, etc.) are 100% margin.
    Handles percentage-based fees with caps.
    """
    fee_name = fee.get('name', 'Fee')
    percentage = float(fee.get('percentage', 0))
    cap = int(fee.get('cap', 0))
    taxable = fee.get('taxable', False)

    # Calculate fee amount
    if percentage > 0 and subtotal > 0:
        calculated = int(subtotal * percentage / 100)
        amount = min(calculated, cap) if cap > 0 else calculated
    else:
        # Fixed fee amount
        amount = int(fee.get('amount', 0))

    # Fees are 100% profit (no cost)
    return FeeProfit(
        fee_name=fee_name,
        amount=amount,
        profit=amount,
        taxable=taxable
    )


def calculate_sublet_profit(sublet: dict) -> Tuple[int, int, int]:
    """
    Calculate sublet profit.

    Returns: (retail, cost, profit) in cents
    """
    retail = int(sublet.get('retail', 0))
    cost = int(sublet.get('cost', 0))
    profit = retail - cost
    return retail, cost, profit


def calculate_job_gp(
    job: dict,
    shop_average_rate: Optional[int] = None
) -> JobGP:
    """
    Calculate GP for a single job including all line items.

    Includes:
    - All parts (qty-aware)
    - All labor (with tech rate fallback)
    - All sublets
    - Job-level discounts
    """
    job_id = job.get('id', 0)
    job_name = job.get('name', 'Unknown Job')
    authorized = job.get('authorized', False)
    authorized_date = job.get('authorizedDate')

    # Calculate parts
    parts_retail = 0
    parts_cost = 0
    for part in job.get('parts', []):
        pp = calculate_part_profit(part)
        parts_retail += pp.total_retail
        parts_cost += pp.total_cost
    parts_profit = parts_retail - parts_cost

    # Calculate labor
    labor_retail = 0
    labor_cost = 0
    for labor in job.get('labor', []):
        lp = calculate_labor_cost(labor, shop_average_rate)
        labor_retail += lp.total_retail
        labor_cost += lp.total_cost
    labor_profit = labor_retail - labor_cost

    # Calculate sublets
    sublet_retail = 0
    sublet_cost = 0
    for sublet in job.get('sublets', []):
        sr, sc, _ = calculate_sublet_profit(sublet)
        sublet_retail += sr
        sublet_cost += sc
    sublet_profit = sublet_retail - sublet_cost

    # Job-level discount (Fix 1.4)
    discount_amount = int(job.get('discount', 0))

    # Subtotal before tax
    subtotal = parts_retail + labor_retail + sublet_retail - discount_amount

    # Gross profit
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
        labor_retail=labor_retail,
        labor_cost=labor_cost,
        labor_profit=labor_profit,
        sublet_retail=sublet_retail,
        sublet_cost=sublet_cost,
        sublet_profit=sublet_profit,
        discount_amount=discount_amount,
        subtotal=subtotal,
        gross_profit=gross_profit,
        margin_pct=round(margin_pct, 2)
    )


def calculate_ro_true_gp(
    estimate: dict,
    shop_average_rate: Optional[int] = None,
    authorized_only: bool = True
) -> ROTrueGP:
    """
    Calculate TRUE GP for an entire RO (Fix 1.1-1.4 combined).

    Accounts for:
    - Quantity-aware parts profit
    - Tech rate fallback
    - Fee inclusion (100% margin)
    - Job and RO-level discounts

    Args:
        estimate: Full estimate object from TM API
        shop_average_rate: Fallback tech rate in cents
        authorized_only: If True, only count authorized jobs
    """
    ro_id = estimate.get('id', 0)
    ro_number = estimate.get('repairOrderNumber', 0)
    customer = estimate.get('customer', {})
    customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()

    notes = []
    job_results = []

    # Process jobs
    total_parts_retail = 0
    total_parts_cost = 0
    total_labor_retail = 0
    total_labor_cost = 0
    total_sublet_retail = 0
    total_sublet_cost = 0
    total_discount = 0

    for job in estimate.get('jobs', []):
        job_gp = calculate_job_gp(job, shop_average_rate)

        # Skip non-authorized if filtering
        if authorized_only and not job_gp.authorized:
            continue

        job_results.append(job_gp)

        total_parts_retail += job_gp.parts_retail
        total_parts_cost += job_gp.parts_cost
        total_labor_retail += job_gp.labor_retail
        total_labor_cost += job_gp.labor_cost
        total_sublet_retail += job_gp.sublet_retail
        total_sublet_cost += job_gp.sublet_cost
        total_discount += job_gp.discount_amount

    # Calculate subtotal (before fees)
    subtotal_before_fees = (
        total_parts_retail +
        total_labor_retail +
        total_sublet_retail -
        total_discount
    )

    # Process fees (Fix 1.3)
    fee_profit = 0
    fees_data = estimate.get('fees', {}).get('data', [])
    for fee in fees_data:
        fp = calculate_fee_profit(fee, subtotal_before_fees)
        fee_profit += fp.profit
        if fp.amount > 0:
            notes.append(f"Fee '{fp.fee_name}': ${fp.amount/100:.2f} (100% margin)")

    # RO-level discount (Fix 1.4)
    ro_discount = int(estimate.get('discount', 0))
    total_discount += ro_discount
    if ro_discount > 0:
        notes.append(f"RO-level discount: ${ro_discount/100:.2f}")

    # Total retail (what customer pays before tax)
    total_retail = subtotal_before_fees + fee_profit - ro_discount

    # Total cost
    total_cost = total_parts_cost + total_labor_cost + total_sublet_cost

    # Gross profit (includes fees as 100% profit)
    gross_profit = total_retail - total_cost

    # Tax (for reference, not included in GP)
    tax_total = int(estimate.get('tax', 0))

    # Balance due (includes tax)
    balance_due = int(estimate.get('balanceDue', 0))

    # Margin percentage
    margin_pct = (gross_profit / total_retail * 100) if total_retail > 0 else 0.0

    # Add summary note
    if authorized_only:
        auth_count = len(job_results)
        total_jobs = len(estimate.get('jobs', []))
        notes.insert(0, f"Authorized jobs: {auth_count}/{total_jobs}")

    return ROTrueGP(
        ro_id=ro_id,
        ro_number=ro_number,
        customer_name=customer_name,
        total_retail=total_retail,
        total_cost=total_cost,
        gross_profit=gross_profit,
        fee_profit=fee_profit,
        discount_total=total_discount,
        tax_total=tax_total,
        balance_due=balance_due,
        margin_pct=round(margin_pct, 2),
        jobs=job_results,
        calculation_notes=notes
    )


async def get_shop_average_tech_rate(tm_client, shop_id: str) -> int:
    """
    Calculate shop average tech rate from employee data.

    Used as Level 2 fallback when no tech is assigned to labor.
    """
    try:
        employees = await tm_client.get(
            f"/api/shop/{shop_id}/employees-lite",
            {"size": 500, "status": "ACTIVE"}
        )

        tech_rates = []
        for emp in employees:
            # Filter for technicians (role = 3)
            if emp.get('role') == 3 and emp.get('hourlyRate'):
                tech_rates.append(int(emp['hourlyRate']))

        if tech_rates:
            return int(sum(tech_rates) / len(tech_rates))

    except Exception as e:
        print(f"[GP Calculator] Error fetching tech rates: {e}")

    return DEFAULT_TECH_RATE_CENTS


def to_dict(obj) -> dict:
    """Convert dataclass to dictionary for JSON serialization."""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field in obj.__dataclass_fields__:
            value = getattr(obj, field)
            if isinstance(value, list):
                result[field] = [to_dict(item) for item in value]
            elif hasattr(value, '__dataclass_fields__'):
                result[field] = to_dict(value)
            else:
                result[field] = value
        return result
    return obj
