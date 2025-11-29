"""
Warehouse Client for Supabase

Uses service_role key for full access to warehouse tables.
Handles upserts, sync cursor management, and logging.
"""

import os
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime, timezone
from supabase import create_client, Client
import json


class WarehouseClient:
    """Client for warehouse database operations"""

    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        # Use service role key for warehouse operations (bypasses RLS)
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.supabase: Client = create_client(supabase_url, supabase_key)
        self._shop_uuid_cache: Dict[int, str] = {}

    # =========================================================================
    # Shop Operations
    # =========================================================================

    async def get_shop_uuid(self, tm_shop_id: int) -> Optional[str]:
        """Get internal UUID for a TM shop ID"""
        if tm_shop_id in self._shop_uuid_cache:
            return self._shop_uuid_cache[tm_shop_id]

        result = self.supabase.table("shops") \
            .select("id") \
            .eq("tm_id", tm_shop_id) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            uuid = result.data[0]["id"]
            self._shop_uuid_cache[tm_shop_id] = uuid
            return uuid
        return None

    async def get_shop_timezone(self, shop_uuid: str) -> str:
        """Get timezone for a shop"""
        result = self.supabase.table("shops") \
            .select("timezone") \
            .eq("id", shop_uuid) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            return result.data[0].get("timezone", "America/New_York")
        return "America/New_York"

    # =========================================================================
    # Sync Cursor Operations
    # =========================================================================

    async def get_sync_cursor(self, shop_uuid: str, entity_type: str) -> Optional[Dict]:
        """Get sync cursor for an entity type"""
        result = self.supabase.table("sync_cursors") \
            .select("*") \
            .eq("shop_id", shop_uuid) \
            .eq("entity_type", entity_type) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    async def update_sync_cursor(
        self,
        shop_uuid: str,
        entity_type: str,
        last_tm_updated: Optional[datetime] = None,
        last_tm_id: Optional[int] = None,
        cursor_data: Optional[Dict] = None
    ) -> None:
        """Update or create sync cursor"""
        data = {
            "shop_id": shop_uuid,
            "entity_type": entity_type,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }
        if last_tm_updated:
            data["last_tm_updated"] = last_tm_updated.isoformat()
        if last_tm_id is not None:
            data["last_tm_id"] = last_tm_id
        if cursor_data:
            data["cursor_data"] = cursor_data

        self.supabase.table("sync_cursors") \
            .upsert(data, on_conflict="shop_id,entity_type") \
            .execute()

    # =========================================================================
    # Sync Log Operations
    # =========================================================================

    async def create_sync_log(
        self,
        shop_uuid: str,
        sync_type: str,
        entity_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Create a new sync log entry, returns the log ID"""
        data = {
            "shop_id": shop_uuid,
            "sync_type": sync_type,
            "entity_type": entity_type,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        result = self.supabase.table("sync_log") \
            .insert(data) \
            .execute()

        return result.data[0]["id"]

    async def update_sync_log(
        self,
        log_id: str,
        status: str,
        records_fetched: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        records_skipped: int = 0,
        error_count: int = 0,
        errors: Optional[List[Dict]] = None
    ) -> None:
        """Update sync log with results"""
        started_at = self.supabase.table("sync_log") \
            .select("started_at") \
            .eq("id", log_id) \
            .limit(1) \
            .execute()

        started = datetime.fromisoformat(started_at.data[0]["started_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        duration_ms = int((now - started).total_seconds() * 1000)

        data = {
            "status": status,
            "completed_at": now.isoformat(),
            "duration_ms": duration_ms,
            "records_fetched": records_fetched,
            "records_created": records_created,
            "records_updated": records_updated,
            "records_skipped": records_skipped,
            "error_count": error_count,
        }
        if errors:
            data["errors"] = errors

        self.supabase.table("sync_log") \
            .update(data) \
            .eq("id", log_id) \
            .execute()

    # =========================================================================
    # Raw Payload Storage (Debug)
    # =========================================================================

    async def store_raw_payload(
        self,
        shop_uuid: str,
        endpoint: str,
        response_payload: Dict,
        method: str = "GET",
        tm_entity_id: Optional[int] = None,
        request_params: Optional[Dict] = None,
        response_status: int = 200
    ) -> None:
        """Store raw TM API response for debugging"""
        data = {
            "shop_id": shop_uuid,
            "endpoint": endpoint,
            "method": method,
            "tm_entity_id": tm_entity_id,
            "request_params": request_params,
            "response_payload": response_payload,
            "response_status": response_status,
        }

        self.supabase.table("tm_raw_payloads") \
            .insert(data) \
            .execute()

    # =========================================================================
    # Entity Upsert Operations
    # =========================================================================

    async def upsert_employee(self, shop_uuid: str, tm_data: Dict) -> Tuple[str, bool]:
        """
        Upsert employee record.
        Returns (uuid, is_new).
        """
        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_data["id"],
            "first_name": tm_data.get("firstName"),
            "last_name": tm_data.get("lastName"),
            "email": tm_data.get("email"),
            "role": tm_data.get("employeeRole", {}).get("code") if tm_data.get("employeeRole") else None,
            "role_name": tm_data.get("employeeRole", {}).get("name") if tm_data.get("employeeRole") else None,
            "hourly_rate": tm_data.get("hourlyRate"),  # Already in cents from TM
            "salary": tm_data.get("salary"),  # Annual salary in cents
            "pay_type": tm_data.get("employeePayType", {}).get("code") if tm_data.get("employeePayType") else None,
            "can_perform_work": tm_data.get("canPerformWork"),  # True if technician
            "status": "INACTIVE" if tm_data.get("disabled") or tm_data.get("deactivated") else "ACTIVE",
            "username": tm_data.get("username"),
            "phone": tm_data.get("phone"),
            "can_clock_in": tm_data.get("canClockIn"),
            "can_sell": tm_data.get("canSell"),
            "can_tech": tm_data.get("canTech"),
            "tm_extra": {k: v for k, v in tm_data.items() if k not in [
                "id", "firstName", "lastName", "email", "employeeRole",
                "hourlyRate", "salary", "employeePayType", "canPerformWork",
                "disabled", "deactivated", "active", "username", "phone",
                "canClockIn", "canSell", "canTech", "account", "shop",
                "address", "permissions", "fullName", "certificationNumber",
                "accessRestricted", "commissionSetting", "createdDate", "updatedDate",
                "createdUser", "updatedUser"
            ]},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check if exists
        existing = self.supabase.table("employees") \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_data["id"]) \
            .limit(1) \
            .execute()

        is_new = len(existing.data) == 0

        result = self.supabase.table("employees") \
            .upsert(data, on_conflict="shop_id,tm_id") \
            .execute()

        return result.data[0]["id"], is_new

    async def upsert_customer(self, shop_uuid: str, tm_data: Dict) -> Tuple[str, bool]:
        """Upsert customer record. Returns (uuid, is_new)."""
        # Handle email as array
        emails = tm_data.get("email", [])
        if isinstance(emails, str):
            emails = [emails] if emails else []

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_data["id"],
            "first_name": tm_data.get("firstName"),
            "last_name": tm_data.get("lastName"),
            "company_name": tm_data.get("companyName"),
            "email": emails if emails else None,
            "phone_primary": None,
            "phone_primary_type": None,
            "phone_secondary": None,
            "phone_secondary_type": None,
            "customer_type_id": tm_data.get("customerType", {}).get("id") if tm_data.get("customerType") else None,
            "customer_type_name": tm_data.get("customerType", {}).get("name") if tm_data.get("customerType") else None,
            "tax_exempt": tm_data.get("taxExempt", False),
            "ok_for_marketing": tm_data.get("okForMarketing"),
            "notes": tm_data.get("notes"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Handle phones
        phones = tm_data.get("phone", [])
        if phones and len(phones) > 0:
            primary = next((p for p in phones if p.get("primary")), phones[0])
            data["phone_primary"] = primary.get("number")
            data["phone_primary_type"] = primary.get("type")
            secondary = next((p for p in phones if not p.get("primary")), None)
            if secondary:
                data["phone_secondary"] = secondary.get("number")
                data["phone_secondary_type"] = secondary.get("type")

        # Handle address
        address = tm_data.get("address", {}) or {}
        data["address_line1"] = address.get("address1")
        data["address_line2"] = address.get("address2")
        data["city"] = address.get("city")
        data["state"] = address.get("state")
        data["zip"] = address.get("zip")
        data["country"] = address.get("country")

        # Check if exists
        existing = self.supabase.table("customers") \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_data["id"]) \
            .limit(1) \
            .execute()

        is_new = len(existing.data) == 0

        result = self.supabase.table("customers") \
            .upsert(data, on_conflict="shop_id,tm_id") \
            .execute()

        return result.data[0]["id"], is_new

    def _extract_nested_field(self, data: Any, name_key: str = "name", id_key: str = "id") -> Tuple[Optional[str], Optional[int]]:
        """
        Extract name and id from a field that may be a string, dict, or None.
        TM API sometimes returns {"name": "Honda", "id": 1} and sometimes just "Honda".
        """
        if data is None:
            return None, None
        if isinstance(data, str):
            return data, None
        if isinstance(data, dict):
            return data.get(name_key), data.get(id_key)
        return str(data), None

    def _to_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        """
        Safely convert a value to integer.
        TM API sometimes returns floats like "0.0" or "8907.0" for integer fields.
        Database expects INTEGER.
        Returns None if value is None (for nullable fields).
        """
        if value is None:
            return default
        try:
            # Handle string floats like "0.0", "8907.0"
            return int(float(value))
        except (ValueError, TypeError):
            return default

    def _to_cents(self, value: Any, default: int = 0) -> int:
        """
        Safely convert a value to integer cents (for monetary fields).
        TM API sometimes returns floats like "0.0" or "8907.0" for cost fields.
        Database expects INTEGER.
        """
        if value is None:
            return default
        try:
            # Handle string floats like "0.0", "8907.0"
            return int(float(value))
        except (ValueError, TypeError):
            return default

    async def upsert_vehicle(
        self,
        shop_uuid: str,
        tm_data: Dict,
        customer_uuid: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Upsert vehicle record. Returns (uuid, is_new)."""
        # Extract make/model/engine - TM API can return string or object
        make_name, make_id = self._extract_nested_field(tm_data.get("make"))
        model_name, model_id = self._extract_nested_field(tm_data.get("model"))
        sub_model_name, sub_model_id = self._extract_nested_field(tm_data.get("subModel"))
        engine_name, engine_id = self._extract_nested_field(tm_data.get("engine"))

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_data["id"],
            "customer_id": customer_uuid,
            "tm_customer_id": tm_data.get("customerId"),
            "year": tm_data.get("year"),
            "make": make_name,
            "make_id": make_id,
            "model": model_name,
            "model_id": model_id,
            "sub_model": sub_model_name,
            "sub_model_id": sub_model_id,
            "engine": engine_name,
            "engine_id": engine_id,
            "transmission": tm_data.get("transmission"),
            "drive_type": tm_data.get("driveType"),
            "body_style": tm_data.get("bodyStyle"),
            "vin": tm_data.get("vin"),
            "license_plate": tm_data.get("licensePlate"),
            "license_state": tm_data.get("licenseState"),
            "unit_number": tm_data.get("unitNumber"),
            "color": tm_data.get("color"),
            "odometer": tm_data.get("odometer") or tm_data.get("milesIn"),
            "notes": tm_data.get("note"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check if exists
        existing = self.supabase.table("vehicles") \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_data["id"]) \
            .limit(1) \
            .execute()

        is_new = len(existing.data) == 0

        result = self.supabase.table("vehicles") \
            .upsert(data, on_conflict="shop_id,tm_id") \
            .execute()

        return result.data[0]["id"], is_new

    async def get_entity_uuid(self, table: str, shop_uuid: str, tm_id: int) -> Optional[str]:
        """Get internal UUID for a TM entity"""
        result = self.supabase.table(table) \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_id) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        return None

    async def upsert_repair_order(
        self,
        shop_uuid: str,
        tm_data: Dict,
        customer_uuid: Optional[str] = None,
        vehicle_uuid: Optional[str] = None,
        advisor_uuid: Optional[str] = None,
        profit_data: Optional[Dict] = None
    ) -> Tuple[str, bool]:
        """Upsert repair order. Returns (uuid, is_new)."""
        status_map = {1: "ESTIMATE", 2: "WORKINPROGRESS", 3: "COMPLETE", 5: "POSTED", 6: "ACCRECV"}
        status_id = tm_data.get("repairOrderStatus", {}).get("id") if tm_data.get("repairOrderStatus") else None

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_data["id"],
            "customer_id": customer_uuid,
            "vehicle_id": vehicle_uuid,
            "service_advisor_id": advisor_uuid,
            "tm_customer_id": tm_data.get("customerId"),
            "tm_vehicle_id": tm_data.get("vehicleId"),
            "tm_service_advisor_id": tm_data.get("serviceWriterId"),
            "ro_number": tm_data.get("repairOrderNumber"),
            "status": status_map.get(status_id, "UNKNOWN"),
            "status_id": status_id,
            "created_date": tm_data.get("createdDate"),
            "updated_date": tm_data.get("updatedDate"),
            "promised_date": tm_data.get("promisedDate"),
            "dropped_off_date": tm_data.get("droppedOffDate"),
            "picked_up_date": tm_data.get("pickedUpDate"),
            "amount_paid": tm_data.get("amountPaid", 0),
            "balance_due": tm_data.get("balanceDue", 0),
            "label": tm_data.get("repairOrderLabel", {}).get("name") if tm_data.get("repairOrderLabel") else None,
            "label_id": tm_data.get("repairOrderLabel", {}).get("id") if tm_data.get("repairOrderLabel") else None,
            "tm_extra": {},
            "tm_updated_at": tm_data.get("updatedDate"),
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Handle posted/completed dates (convert to DATE, shop-local)
        if tm_data.get("postedDate"):
            # Extract just the date portion
            posted = tm_data["postedDate"]
            if "T" in posted:
                data["posted_date"] = posted.split("T")[0]
            else:
                data["posted_date"] = posted

        if tm_data.get("completedDate"):
            completed = tm_data["completedDate"]
            if "T" in completed:
                data["completed_date"] = completed.split("T")[0]
            else:
                data["completed_date"] = completed

        # Add profit data if available
        if profit_data:
            total_profit = profit_data.get("totalProfit", {})
            labor_profit = profit_data.get("laborProfit", {})

            data["authorized_revenue"] = total_profit.get("retail")
            data["authorized_cost"] = total_profit.get("cost")
            data["authorized_profit"] = total_profit.get("profit")

            margin = total_profit.get("margin")
            if margin and margin != "NaN":
                data["authorized_gp_percent"] = round(float(margin) * 100, 2)

            data["authorized_labor_hours"] = labor_profit.get("hours")

        # Check if exists
        existing = self.supabase.table("repair_orders") \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_data["id"]) \
            .limit(1) \
            .execute()

        is_new = len(existing.data) == 0

        result = self.supabase.table("repair_orders") \
            .upsert(data, on_conflict="shop_id,tm_id") \
            .execute()

        return result.data[0]["id"], is_new

    async def update_ro_totals(
        self,
        ro_uuid: str,
        estimate_data: Dict
    ) -> None:
        """Update RO with totals from estimate endpoint"""
        # Calculate potential and authorized totals from jobs
        jobs = estimate_data.get("jobs", [])

        potential_total = 0
        potential_job_count = 0
        potential_parts = 0
        potential_labor = 0
        potential_sublet = 0
        potential_fees = 0

        authorized_total = 0
        authorized_job_count = 0
        authorized_parts = 0
        authorized_labor = 0
        authorized_sublet = 0
        authorized_fees = 0

        for job in jobs:
            job_total = job.get("total", 0) or 0
            is_authorized = job.get("authorized", False)

            potential_total += job_total
            potential_job_count += 1
            potential_parts += job.get("partsPrice", 0) or 0
            potential_labor += job.get("laborPrice", 0) or 0
            potential_sublet += job.get("subletPrice", 0) or 0
            potential_fees += job.get("feePrice", 0) or 0

            if is_authorized:
                authorized_total += job_total
                authorized_job_count += 1
                authorized_parts += job.get("partsPrice", 0) or 0
                authorized_labor += job.get("laborPrice", 0) or 0
                authorized_sublet += job.get("subletPrice", 0) or 0
                authorized_fees += job.get("feePrice", 0) or 0

        data = {
            "potential_total": potential_total,
            "potential_job_count": potential_job_count,
            "potential_parts_total": potential_parts,
            "potential_labor_total": potential_labor,
            "potential_sublet_total": potential_sublet,
            # CRITICAL: Use RO-level feesTotal, not job-level feePrice
            # TM applies fees (shop supplies, EPA) at RO level, not job level
            "potential_fees_total": estimate_data.get("feesTotal", 0),
            "potential_tax": estimate_data.get("taxes", 0),
            "potential_discount": estimate_data.get("discountTotal", 0),

            "authorized_total": authorized_total,
            "authorized_job_count": authorized_job_count,
            "authorized_parts_total": authorized_parts,
            "authorized_labor_total": authorized_labor,
            "authorized_sublet_total": authorized_sublet,
            # CRITICAL: Use RO-level feesTotal for authorized fees
            # This is where shop supplies and EPA fees come from
            "authorized_fees_total": estimate_data.get("feesTotal", 0) if authorized_job_count > 0 else 0,
            "authorized_tax": estimate_data.get("taxes", 0) if authorized_job_count > 0 else 0,
            "authorized_discount": estimate_data.get("discountTotal", 0) if authorized_job_count > 0 else 0,

            "shop_supplies_total": estimate_data.get("shopSuppliesTotal", 0),
            "epa_total": estimate_data.get("epaTotal", 0),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.supabase.table("repair_orders") \
            .update(data) \
            .eq("id", ro_uuid) \
            .execute()

    async def upsert_job(
        self,
        shop_uuid: str,
        ro_uuid: str,
        tm_ro_id: int,
        tm_data: Dict
    ) -> Tuple[str, bool]:
        """Upsert job record. Returns (uuid, is_new)."""
        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_data["id"],
            "repair_order_id": ro_uuid,
            "tm_repair_order_id": tm_ro_id,
            "name": tm_data.get("name", ""),
            "description": tm_data.get("description"),
            "job_category_id": tm_data.get("jobCategory", {}).get("id") if tm_data.get("jobCategory") else None,
            "job_category_name": tm_data.get("jobCategory", {}).get("name") if tm_data.get("jobCategory") else None,
            "canned_job_id": tm_data.get("cannedJobId"),
            # Handle explicit None values - TM API may return null for these booleans
            "authorized": bool(tm_data.get("authorized")) if tm_data.get("authorized") is not None else False,
            "authorized_date": tm_data.get("authorizedDate"),
            "declined": bool(tm_data.get("declined")) if tm_data.get("declined") is not None else False,
            "total": tm_data.get("total", 0) or 0,
            "subtotal": tm_data.get("subTotal"),
            "discount": tm_data.get("discount", 0) or 0,
            "tax": tm_data.get("tax"),
            "parts_total": tm_data.get("partsPrice", 0) or 0,
            "parts_cost": tm_data.get("partsCost", 0) or 0,
            "labor_total": tm_data.get("laborPrice", 0) or 0,
            "labor_hours": tm_data.get("laborHours", 0) or 0,
            "sublet_total": tm_data.get("subletPrice", 0) or 0,
            "sublet_cost": tm_data.get("subletCost", 0) or 0,
            "fees_total": tm_data.get("feePrice", 0) or 0,
            "gross_profit_amount": tm_data.get("grossProfitAmount"),
            "gross_profit_percent": round(tm_data.get("grossProfitPercentage", 0) * 100, 2) if tm_data.get("grossProfitPercentage") else None,
            "sort_order": tm_data.get("sortOrder"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check if exists
        existing = self.supabase.table("jobs") \
            .select("id") \
            .eq("shop_id", shop_uuid) \
            .eq("tm_id", tm_data["id"]) \
            .limit(1) \
            .execute()

        is_new = len(existing.data) == 0

        result = self.supabase.table("jobs") \
            .upsert(data, on_conflict="shop_id,tm_id") \
            .execute()

        return result.data[0]["id"], is_new

    async def upsert_job_part(
        self,
        shop_uuid: str,
        job_uuid: str,
        ro_uuid: str,
        tm_job_id: int,
        tm_ro_id: int,
        tm_data: Dict
    ) -> Tuple[str, bool]:
        """Upsert job part record."""
        # Convert all integer fields - TM API returns floats like "0.0", DB expects INTEGER
        # Also convert parameters as caller may pass floats from TM API data
        tm_id = self._to_int(tm_data.get("id"))
        safe_tm_job_id = self._to_int(tm_job_id)
        safe_tm_ro_id = self._to_int(tm_ro_id)
        retail = self._to_cents(tm_data.get("retail"))
        cost = self._to_cents(tm_data.get("cost"))
        core_charge = self._to_cents(tm_data.get("coreCharge"))
        vendor_id = self._to_int(tm_data.get("vendorId"))
        # quantity can also be a float like 1.0, 2.0 - convert to int
        quantity = self._to_int(tm_data.get("quantity"), default=1)
        # Calculate total as int (retail is already int, quantity now int)
        total = retail * quantity if retail else 0

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_id,
            "job_id": job_uuid,
            "repair_order_id": ro_uuid,
            "tm_job_id": safe_tm_job_id,
            "tm_repair_order_id": safe_tm_ro_id,
            "name": tm_data.get("name") or tm_data.get("brand") or "Unnamed Part",
            "part_number": tm_data.get("partNumber"),
            "description": tm_data.get("description"),
            "quantity": quantity,
            "retail": retail,
            "cost": cost,
            "core_charge": core_charge,
            "total": total,
            "vendor_id": vendor_id,
            "vendor_name": tm_data.get("vendorName"),
            "manufacturer": tm_data.get("brand"),
            "ordered": tm_data.get("ordered", False),
            "received": tm_data.get("received", False),
            "backordered": tm_data.get("backordered", False),
            "category": tm_data.get("category"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

        # Parts may not have TM ID - use explicit insert/update logic
        # (partial unique index doesn't work with ON CONFLICT column syntax)
        if tm_id:
            existing = self.supabase.table("job_parts") \
                .select("id") \
                .eq("shop_id", shop_uuid) \
                .eq("tm_id", tm_id) \
                .limit(1) \
                .execute()

            if existing.data and len(existing.data) > 0:
                # Update existing record
                is_new = False
                existing_id = existing.data[0]["id"]
                result = self.supabase.table("job_parts") \
                    .update(data) \
                    .eq("id", existing_id) \
                    .execute()
            else:
                # Insert new record
                is_new = True
                result = self.supabase.table("job_parts") \
                    .insert(data) \
                    .execute()
        else:
            # No TM ID, just insert
            is_new = True
            result = self.supabase.table("job_parts") \
                .insert(data) \
                .execute()

        return result.data[0]["id"], is_new

    async def upsert_job_labor(
        self,
        shop_uuid: str,
        job_uuid: str,
        ro_uuid: str,
        tm_job_id: int,
        tm_ro_id: int,
        tm_data: Dict,
        technician_uuid: Optional[str] = None,
        profit_labor_data: Optional[Dict] = None
    ) -> Tuple[str, bool]:
        """Upsert job labor record."""
        tech = tm_data.get("technician", {}) or {}

        # Convert all integer fields - TM API may return floats, DB expects INTEGER
        # Also convert parameters as caller may pass floats from TM API data
        tm_id = self._to_int(tm_data.get("id"))
        safe_tm_job_id = self._to_int(tm_job_id)
        safe_tm_ro_id = self._to_int(tm_ro_id)
        tm_technician_id = self._to_int(tech.get("id"))
        rate = self._to_cents(tm_data.get("rate"))
        total = self._to_cents(tm_data.get("total"))

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_id,
            "job_id": job_uuid,
            "repair_order_id": ro_uuid,
            "tm_job_id": safe_tm_job_id,
            "tm_repair_order_id": safe_tm_ro_id,
            "name": tm_data.get("name", "Labor"),
            "description": tm_data.get("description"),
            "labor_type": tm_data.get("laborType"),
            "hours": tm_data.get("hours", 0) or 0,  # NUMERIC field, keep as float
            "rate": rate,
            "total": total,
            "technician_id": technician_uuid,
            "tm_technician_id": tm_technician_id,
            "technician_name": tech.get("fullName"),
            "skill_level": tm_data.get("skillLevel"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

        # Calculate labor cost from employee hourly_rate (cached from TM)
        # This eliminates the need for /profit/labor API calls
        hours = tm_data.get("hours", 0) or 0

        if profit_labor_data:
            # Legacy path: use profit/labor data if provided
            job_tech = profit_labor_data.get("jobTechnician", {}) or {}
            data["tech_hourly_cost"] = self._to_cents(job_tech.get("hourlyRate"))
            data["labor_cost"] = self._to_cents(profit_labor_data.get("cost"))
            if job_tech.get("hourlyRate"):
                if tech.get("id") and job_tech.get("hourlyRate"):
                    data["rate_source"] = "assigned"
                else:
                    data["rate_source"] = "shop_avg"
            else:
                data["rate_source"] = "default"
        elif tm_technician_id:
            # New path: calculate from cached employee hourly_rate
            emp_result = self.supabase.table("employees")                 .select("hourly_rate")                 .eq("shop_id", shop_uuid)                 .eq("tm_id", tm_technician_id)                 .limit(1)                 .execute()

            if emp_result.data and emp_result.data[0].get("hourly_rate"):
                hourly_rate = emp_result.data[0]["hourly_rate"]  # Already in cents
                data["tech_hourly_cost"] = hourly_rate
                # Calculate: labor_cost = hours * hourly_rate (cents)
                labor_cost = int(hours * hourly_rate) if hours else 0
                data["labor_cost"] = labor_cost
                data["rate_source"] = "employee_cache"
            else:
                # No hourly rate found - leave cost fields null
                data["rate_source"] = "unknown"
        else:
            # No technician assigned
            data["rate_source"] = "unassigned"

        # Labor may not have TM ID - use explicit insert/update logic
        # (partial unique index doesn't work with ON CONFLICT column syntax)
        if tm_id:
            existing = self.supabase.table("job_labor") \
                .select("id") \
                .eq("shop_id", shop_uuid) \
                .eq("tm_id", tm_id) \
                .limit(1) \
                .execute()

            if existing.data and len(existing.data) > 0:
                # Update existing record
                is_new = False
                existing_id = existing.data[0]["id"]
                result = self.supabase.table("job_labor") \
                    .update(data) \
                    .eq("id", existing_id) \
                    .execute()
            else:
                # Insert new record
                is_new = True
                result = self.supabase.table("job_labor") \
                    .insert(data) \
                    .execute()
        else:
            is_new = True
            result = self.supabase.table("job_labor") \
                .insert(data) \
                .execute()

        return result.data[0]["id"], is_new

    async def upsert_job_sublet(
        self,
        shop_uuid: str,
        job_uuid: str,
        ro_uuid: str,
        tm_job_id: int,
        tm_ro_id: int,
        tm_data: Dict
    ) -> Tuple[str, bool]:
        """Upsert job sublet record."""
        # Convert all integer fields - TM API may return floats, DB expects INTEGER
        # Also convert parameters as caller may pass floats from TM API data
        tm_id = self._to_int(tm_data.get("id"))
        safe_tm_job_id = self._to_int(tm_job_id)
        safe_tm_ro_id = self._to_int(tm_ro_id)
        vendor_id = self._to_int(tm_data.get("vendorId"))
        cost = self._to_cents(tm_data.get("cost"))
        retail = self._to_cents(tm_data.get("retail"))

        data = {
            "shop_id": shop_uuid,
            "tm_id": tm_id,
            "job_id": job_uuid,
            "repair_order_id": ro_uuid,
            "tm_job_id": safe_tm_job_id,
            "tm_repair_order_id": safe_tm_ro_id,
            "name": tm_data.get("name", "Sublet"),
            "description": tm_data.get("description"),
            "vendor_id": vendor_id,
            "vendor_name": tm_data.get("vendorName"),
            "cost": cost,
            "retail": retail,
            "invoice_number": tm_data.get("invoiceNumber"),
            "po_number": tm_data.get("poNumber"),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

        # Sublets may not have TM ID - use explicit insert/update logic
        # (partial unique index doesn't work with ON CONFLICT column syntax)
        if tm_id:
            existing = self.supabase.table("job_sublets") \
                .select("id") \
                .eq("shop_id", shop_uuid) \
                .eq("tm_id", tm_id) \
                .limit(1) \
                .execute()

            if existing.data and len(existing.data) > 0:
                # Update existing record
                is_new = False
                existing_id = existing.data[0]["id"]
                result = self.supabase.table("job_sublets") \
                    .update(data) \
                    .eq("id", existing_id) \
                    .execute()
            else:
                # Insert new record
                is_new = True
                result = self.supabase.table("job_sublets") \
                    .insert(data) \
                    .execute()
        else:
            is_new = True
            result = self.supabase.table("job_sublets") \
                .insert(data) \
                .execute()

        return result.data[0]["id"], is_new

    async def upsert_job_fee(
        self,
        shop_uuid: str,
        job_uuid: str,
        ro_uuid: str,
        tm_job_id: int,
        tm_ro_id: int,
        tm_data: Dict
    ) -> Tuple[str, bool]:
        """Upsert job fee record."""
        # Convert integer fields - TM API may return floats, DB expects INTEGER
        safe_tm_job_id = self._to_int(tm_job_id)
        safe_tm_ro_id = self._to_int(tm_ro_id)
        amount = self._to_cents(tm_data.get("amount"))
        cap = self._to_cents(tm_data.get("cap"))
        total = self._to_cents(tm_data.get("total", 0) or 0)

        # Determine fee type
        name = (tm_data.get("name") or "").lower()
        fee_type = "other"
        if "shop" in name or "supply" in name:
            fee_type = "shop_supplies"
        elif "epa" in name or "environ" in name:
            fee_type = "environmental"
        elif "dispos" in name:
            fee_type = "disposal"
        elif "hazmat" in name or "hazard" in name:
            fee_type = "hazmat"

        data = {
            "shop_id": shop_uuid,
            "job_id": job_uuid,
            "repair_order_id": ro_uuid,
            "tm_job_id": safe_tm_job_id,
            "tm_repair_order_id": safe_tm_ro_id,
            "name": tm_data.get("name", "Fee"),
            "fee_type": fee_type,
            "amount": amount,
            "percentage": tm_data.get("percentage"),
            "cap": cap,
            "total": total,
            "taxable": tm_data.get("taxable", False),
            "tm_extra": {},
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

        # Fees typically don't have TM IDs, insert new each time
        # Delete existing fees for this job first
        self.supabase.table("job_fees") \
            .delete() \
            .eq("job_id", job_uuid) \
            .execute()

        result = self.supabase.table("job_fees") \
            .insert(data) \
            .execute()

        return result.data[0]["id"], True


# Singleton
_warehouse_client: Optional[WarehouseClient] = None


def get_warehouse_client() -> WarehouseClient:
    """Get or create warehouse client instance"""
    global _warehouse_client
    if _warehouse_client is None:
        _warehouse_client = WarehouseClient()
    return _warehouse_client
