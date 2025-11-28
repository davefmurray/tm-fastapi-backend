"""
RO Snapshot Builder

Builds ro_snapshots from repair_orders and their line items.
Follows TRUE_GP calculation rules from METRIC_CONTRACTS.md.

Key rules:
- authorized_* fields come from repair_orders (originally from /profit/labor endpoint)
- category breakdowns calculated from job_parts, job_labor, etc. for AUTHORIZED jobs
- potential_* calculated from ALL jobs regardless of authorization
"""

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

from supabase import create_client, Client


class SnapshotBuilder:
    """Builds RO snapshots from warehouse data."""

    def __init__(self):
        """Initialize Supabase client."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_KEY required")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def _to_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to int."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    def _to_decimal(self, value: Any, default: float = 0.0) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None:
            return Decimal(str(default))
        try:
            return Decimal(str(value))
        except:
            return Decimal(str(default))

    def get_shop_uuid(self, shop_id: int) -> Optional[str]:
        """Get shop UUID from tm_id."""
        result = self.supabase.table("shops").select("id").eq("tm_id", shop_id).execute()
        if result.data:
            return result.data[0]["id"]
        return None

    def get_qualifying_ros(
        self,
        shop_uuid: str,
        days_back: int = 3,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Find repair_orders with posted_date or completed_date in the date range.

        Args:
            shop_uuid: The shop UUID
            days_back: Number of days back from today (ignored if dates provided)
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            List of qualifying repair_orders
        """
        if start_date and end_date:
            date_start = start_date
            date_end = end_date
        else:
            today = date.today()
            date_end = today.isoformat()
            date_start = (today - timedelta(days=days_back)).isoformat()

        # Get ROs with posted_date OR completed_date in range
        # Using OR filter via Supabase
        query = self.supabase.table("repair_orders").select(
            "id, tm_id, ro_number, status, posted_date, completed_date, "
            "customer_id, vehicle_id, service_advisor_id, "
            "authorized_revenue, authorized_cost, authorized_profit, authorized_gp_percent, "
            "authorized_job_count, authorized_total, authorized_tax, "
            "potential_total, potential_job_count, potential_tax"
        ).eq("shop_id", shop_uuid)

        # Filter: posted_date in range OR completed_date in range
        # We'll fetch both and filter in code since Supabase OR is limited
        result_posted = self.supabase.table("repair_orders").select(
            "id, tm_id, ro_number, status, posted_date, completed_date, "
            "customer_id, vehicle_id, service_advisor_id, "
            "authorized_revenue, authorized_cost, authorized_profit, authorized_gp_percent, "
            "authorized_job_count, authorized_total, authorized_tax, "
            "potential_total, potential_job_count, potential_tax"
        ).eq("shop_id", shop_uuid).gte("posted_date", date_start).lte("posted_date", date_end).execute()

        result_completed = self.supabase.table("repair_orders").select(
            "id, tm_id, ro_number, status, posted_date, completed_date, "
            "customer_id, vehicle_id, service_advisor_id, "
            "authorized_revenue, authorized_cost, authorized_profit, authorized_gp_percent, "
            "authorized_job_count, authorized_total, authorized_tax, "
            "potential_total, potential_job_count, potential_tax"
        ).eq("shop_id", shop_uuid).gte("completed_date", date_start).lte("completed_date", date_end).execute()

        # Deduplicate by RO id
        ros_by_id = {}
        for ro in result_posted.data:
            ros_by_id[ro["id"]] = ro
        for ro in result_completed.data:
            ros_by_id[ro["id"]] = ro

        return list(ros_by_id.values())

    def get_ro_line_items(self, shop_uuid: str, ro_uuid: str) -> Dict[str, List[Dict]]:
        """Get all line items for an RO, grouped by authorized status."""
        # Get jobs for this RO
        jobs_result = self.supabase.table("jobs").select(
            "id, tm_id, name, authorized, parts_total, parts_cost, labor_total, labor_hours, "
            "sublet_total, sublet_cost, fees_total, total"
        ).eq("shop_id", shop_uuid).eq("repair_order_id", ro_uuid).execute()

        authorized_jobs = []
        all_jobs = []

        for job in jobs_result.data:
            all_jobs.append(job)
            if job.get("authorized"):
                authorized_jobs.append(job)

        # Get parts for authorized jobs
        parts_result = self.supabase.table("job_parts").select(
            "id, tm_id, job_id, retail, cost, quantity, total"
        ).eq("shop_id", shop_uuid).eq("repair_order_id", ro_uuid).execute()

        # Get labor for authorized jobs
        labor_result = self.supabase.table("job_labor").select(
            "id, tm_id, job_id, hours, rate, total, labor_cost, technician_name"
        ).eq("shop_id", shop_uuid).eq("repair_order_id", ro_uuid).execute()

        # Get sublets
        sublets_result = self.supabase.table("job_sublets").select(
            "id, tm_id, job_id, retail, cost"
        ).eq("shop_id", shop_uuid).eq("repair_order_id", ro_uuid).execute()

        # Get fees
        fees_result = self.supabase.table("job_fees").select(
            "id, job_id, total"
        ).eq("shop_id", shop_uuid).eq("repair_order_id", ro_uuid).execute()

        # Map job_ids to authorized status
        authorized_job_ids = {j["id"] for j in authorized_jobs}

        return {
            "all_jobs": all_jobs,
            "authorized_jobs": authorized_jobs,
            "parts": parts_result.data,
            "labor": labor_result.data,
            "sublets": sublets_result.data if sublets_result.data else [],
            "fees": fees_result.data if fees_result.data else [],
            "authorized_job_ids": authorized_job_ids
        }

    def get_customer_name(self, customer_id: Optional[str]) -> str:
        """Get customer name from customer_id."""
        if not customer_id:
            return "Unknown"
        result = self.supabase.table("customers").select("first_name, last_name").eq("id", customer_id).execute()
        if result.data:
            c = result.data[0]
            first = c.get("first_name") or ""
            last = c.get("last_name") or ""
            return f"{first} {last}".strip() or "Unknown"
        return "Unknown"

    def get_vehicle_description(self, vehicle_id: Optional[str]) -> str:
        """Get vehicle description from vehicle_id."""
        if not vehicle_id:
            return "Unknown"
        result = self.supabase.table("vehicles").select("year, make, model").eq("id", vehicle_id).execute()
        if result.data:
            v = result.data[0]
            year = v.get("year") or ""
            make = v.get("make") or ""
            model = v.get("model") or ""
            return f"{year} {make} {model}".strip() or "Unknown"
        return "Unknown"

    def get_advisor_name(self, advisor_id: Optional[str]) -> str:
        """Get advisor name from employee_id."""
        if not advisor_id:
            return "Unknown"
        result = self.supabase.table("employees").select("first_name, last_name").eq("id", advisor_id).execute()
        if result.data:
            e = result.data[0]
            first = e.get("first_name") or ""
            last = e.get("last_name") or ""
            return f"{first} {last}".strip() or "Unknown"
        return "Unknown"

    def calculate_category_breakdown(
        self,
        line_items: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Calculate category breakdown from line items.

        Returns breakdown for AUTHORIZED items only.
        """
        authorized_job_ids = line_items["authorized_job_ids"]

        # Parts breakdown (authorized only)
        parts_revenue = 0
        parts_cost = 0
        for part in line_items["parts"]:
            if part["job_id"] in authorized_job_ids:
                parts_revenue += self._to_int(part.get("total"))
                # Cost is per unit, quantity may vary
                cost = self._to_int(part.get("cost"))
                qty = self._to_int(part.get("quantity"), 1)
                parts_cost += cost * qty

        # Labor breakdown (authorized only)
        labor_revenue = 0
        labor_cost = 0
        labor_hours = Decimal("0")
        for labor in line_items["labor"]:
            if labor["job_id"] in authorized_job_ids:
                labor_revenue += self._to_int(labor.get("total"))
                labor_cost += self._to_int(labor.get("labor_cost"))
                labor_hours += self._to_decimal(labor.get("hours"))

        # Sublet breakdown (authorized only)
        sublet_revenue = 0
        sublet_cost = 0
        for sublet in line_items["sublets"]:
            if sublet["job_id"] in authorized_job_ids:
                sublet_revenue += self._to_int(sublet.get("retail"))
                sublet_cost += self._to_int(sublet.get("cost"))

        # Fees (authorized only)
        fees_total = 0
        for fee in line_items["fees"]:
            if fee["job_id"] in authorized_job_ids:
                fees_total += self._to_int(fee.get("total"))

        return {
            "parts_revenue": parts_revenue,
            "parts_cost": parts_cost,
            "parts_profit": parts_revenue - parts_cost,
            "labor_revenue": labor_revenue,
            "labor_cost": labor_cost,
            "labor_profit": labor_revenue - labor_cost,
            "labor_hours": float(labor_hours),
            "sublet_revenue": sublet_revenue,
            "sublet_cost": sublet_cost,
            "fees_total": fees_total
        }

    def build_snapshot(
        self,
        shop_uuid: str,
        ro: Dict,
        snapshot_trigger: str = "manual"
    ) -> Dict[str, Any]:
        """
        Build a single RO snapshot.

        Args:
            shop_uuid: Shop UUID
            ro: Repair order data
            snapshot_trigger: 'posted', 'completed', or 'manual'

        Returns:
            Snapshot row data
        """
        # Get line items
        line_items = self.get_ro_line_items(shop_uuid, ro["id"])

        # Determine snapshot date
        if snapshot_trigger == "posted" and ro.get("posted_date"):
            snapshot_date = ro["posted_date"]
        elif snapshot_trigger == "completed" and ro.get("completed_date"):
            snapshot_date = ro["completed_date"]
        elif ro.get("posted_date"):
            snapshot_date = ro["posted_date"]
            snapshot_trigger = "posted"
        elif ro.get("completed_date"):
            snapshot_date = ro["completed_date"]
            snapshot_trigger = "completed"
        else:
            snapshot_date = date.today().isoformat()
            snapshot_trigger = "manual"

        # Get display names
        customer_name = self.get_customer_name(ro.get("customer_id"))
        vehicle_desc = self.get_vehicle_description(ro.get("vehicle_id"))
        advisor_name = self.get_advisor_name(ro.get("service_advisor_id"))

        # Get authorized metrics from RO (already calculated from /profit/labor)
        authorized_revenue = self._to_int(ro.get("authorized_revenue"))
        authorized_cost = self._to_int(ro.get("authorized_cost"))
        authorized_profit = self._to_int(ro.get("authorized_profit"))
        authorized_gp_percent = ro.get("authorized_gp_percent")
        authorized_job_count = self._to_int(ro.get("authorized_job_count"))

        # Calculate category breakdown from line items
        breakdown = self.calculate_category_breakdown(line_items)

        # Potential metrics from RO
        potential_revenue = self._to_int(ro.get("potential_total"))
        potential_job_count = self._to_int(ro.get("potential_job_count"))

        # Tax
        tax_total = self._to_int(ro.get("authorized_tax"))

        # TM reported GP% for validation
        tm_reported_gp_percent = authorized_gp_percent

        # Calculate variance (our calc vs TM)
        our_gp_percent = None
        variance_percent = None
        variance_reason = None

        if authorized_revenue > 0:
            our_gp_percent = round((authorized_profit / authorized_revenue) * 100, 2)
            if tm_reported_gp_percent is not None:
                variance_percent = round(float(our_gp_percent) - float(tm_reported_gp_percent), 2)
                if abs(variance_percent) > 0.5:
                    variance_reason = f"Our calc: {our_gp_percent}%, TM: {tm_reported_gp_percent}%"

        return {
            "shop_id": shop_uuid,
            "repair_order_id": ro["id"],
            "tm_repair_order_id": self._to_int(ro["tm_id"]),
            "snapshot_date": snapshot_date,
            "snapshot_trigger": snapshot_trigger,
            "ro_status": ro.get("status") or "UNKNOWN",
            "ro_number": self._to_int(ro.get("ro_number")),
            "customer_name": customer_name,
            "vehicle_description": vehicle_desc,
            "advisor_name": advisor_name,
            "authorized_revenue": authorized_revenue,
            "authorized_cost": authorized_cost,
            "authorized_profit": authorized_profit,
            "authorized_gp_percent": authorized_gp_percent,
            "authorized_job_count": authorized_job_count,
            "parts_revenue": breakdown["parts_revenue"],
            "parts_cost": breakdown["parts_cost"],
            "parts_profit": breakdown["parts_profit"],
            "labor_revenue": breakdown["labor_revenue"],
            "labor_cost": breakdown["labor_cost"],
            "labor_profit": breakdown["labor_profit"],
            "labor_hours": breakdown["labor_hours"],
            "sublet_revenue": breakdown["sublet_revenue"],
            "sublet_cost": breakdown["sublet_cost"],
            "fees_total": breakdown["fees_total"],
            "tax_total": tax_total,
            "potential_revenue": potential_revenue,
            "potential_job_count": potential_job_count,
            "tm_reported_gp_percent": tm_reported_gp_percent,
            "variance_percent": variance_percent,
            "variance_reason": variance_reason,
            "calculation_method": "TRUE_GP"
        }

    def upsert_snapshot(self, snapshot: Dict) -> Tuple[str, bool]:
        """
        Upsert a snapshot row.

        Returns:
            Tuple of (snapshot_id, was_created)
        """
        # Check if snapshot exists
        existing = self.supabase.table("ro_snapshots").select("id").eq(
            "shop_id", snapshot["shop_id"]
        ).eq(
            "repair_order_id", snapshot["repair_order_id"]
        ).eq(
            "snapshot_date", snapshot["snapshot_date"]
        ).eq(
            "snapshot_trigger", snapshot["snapshot_trigger"]
        ).execute()

        if existing.data:
            # Update existing
            snap_id = existing.data[0]["id"]
            self.supabase.table("ro_snapshots").update(snapshot).eq("id", snap_id).execute()
            return snap_id, False
        else:
            # Insert new
            result = self.supabase.table("ro_snapshots").insert(snapshot).execute()
            return result.data[0]["id"], True

    def build_snapshots_for_period(
        self,
        shop_id: int,
        days_back: int = 3,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build snapshots for all qualifying ROs in a date range.

        Args:
            shop_id: TM shop ID
            days_back: Days back from today
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Summary of what was built
        """
        shop_uuid = self.get_shop_uuid(shop_id)
        if not shop_uuid:
            return {
                "status": "error",
                "message": f"Shop {shop_id} not found"
            }

        ros = self.get_qualifying_ros(shop_uuid, days_back, start_date, end_date)

        created = 0
        updated = 0
        errors = []

        for ro in ros:
            try:
                # Determine trigger based on which date is in range
                trigger = "posted" if ro.get("posted_date") else "completed"

                snapshot = self.build_snapshot(shop_uuid, ro, trigger)
                snap_id, was_created = self.upsert_snapshot(snapshot)

                if was_created:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append({
                    "ro_id": ro.get("tm_id"),
                    "error": str(e)
                })

        return {
            "status": "completed",
            "shop_id": shop_id,
            "qualifying_ros": len(ros),
            "snapshots_created": created,
            "snapshots_updated": updated,
            "errors": len(errors),
            "error_details": errors[:10] if errors else []
        }


def get_snapshot_builder() -> SnapshotBuilder:
    """Factory function for SnapshotBuilder."""
    return SnapshotBuilder()
