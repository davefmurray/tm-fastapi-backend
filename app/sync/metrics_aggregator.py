"""
Daily Shop Metrics Aggregator

Aggregates ro_snapshots into daily_shop_metrics.
Follows TRUE_GP calculation rules from METRIC_CONTRACTS.md.

Key rules:
- daily_shop_metrics is ALWAYS computed FROM ro_snapshots, not raw line items
- This ensures consistent metric definitions across all levels
- Idempotent: safe to re-run for any date range
"""

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

from supabase import create_client, Client


class MetricsAggregator:
    """Aggregates ro_snapshots into daily_shop_metrics."""

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

    def get_snapshots_for_date(self, shop_uuid: str, metric_date: str) -> List[Dict]:
        """
        Get all ro_snapshots for a specific date.

        Args:
            shop_uuid: Shop UUID
            metric_date: Date string (YYYY-MM-DD)

        Returns:
            List of snapshot records
        """
        result = self.supabase.table("ro_snapshots").select("*").eq(
            "shop_id", shop_uuid
        ).eq(
            "snapshot_date", metric_date
        ).execute()

        return result.data or []

    def aggregate_daily_metrics(
        self,
        shop_uuid: str,
        snapshots: List[Dict],
        metric_date: str
    ) -> Dict[str, Any]:
        """
        Aggregate snapshots into daily metrics.

        Args:
            shop_uuid: Shop UUID
            snapshots: List of ro_snapshots for the date
            metric_date: The date being aggregated

        Returns:
            daily_shop_metrics row data
        """
        # Count by trigger type
        ro_posted_count = sum(1 for s in snapshots if s.get("snapshot_trigger") == "posted")
        ro_completed_count = sum(1 for s in snapshots if s.get("snapshot_trigger") == "completed")

        # Sum authorized metrics
        authorized_revenue = sum(self._to_int(s.get("authorized_revenue")) for s in snapshots)
        authorized_cost = sum(self._to_int(s.get("authorized_cost")) for s in snapshots)
        authorized_profit = sum(self._to_int(s.get("authorized_profit")) for s in snapshots)
        authorized_job_count = sum(self._to_int(s.get("authorized_job_count")) for s in snapshots)

        # GP percent (weighted by revenue)
        authorized_gp_percent = None
        if authorized_revenue > 0:
            authorized_gp_percent = round((authorized_profit / authorized_revenue) * 100, 2)

        # Category breakdowns
        parts_revenue = sum(self._to_int(s.get("parts_revenue")) for s in snapshots)
        parts_cost = sum(self._to_int(s.get("parts_cost")) for s in snapshots)
        parts_profit = sum(self._to_int(s.get("parts_profit")) for s in snapshots)

        labor_revenue = sum(self._to_int(s.get("labor_revenue")) for s in snapshots)
        labor_cost = sum(self._to_int(s.get("labor_cost")) for s in snapshots)
        labor_profit = sum(self._to_int(s.get("labor_profit")) for s in snapshots)
        labor_hours = float(sum(self._to_decimal(s.get("labor_hours")) for s in snapshots))

        sublet_revenue = sum(self._to_int(s.get("sublet_revenue")) for s in snapshots)
        sublet_cost = sum(self._to_int(s.get("sublet_cost")) for s in snapshots)

        fees_total = sum(self._to_int(s.get("fees_total")) for s in snapshots)
        tax_total = sum(self._to_int(s.get("tax_total")) for s in snapshots)

        # Potential metrics
        potential_revenue = sum(self._to_int(s.get("potential_revenue")) for s in snapshots)
        potential_job_count = sum(self._to_int(s.get("potential_job_count")) for s in snapshots)

        # Authorization rate
        authorization_rate = None
        if potential_revenue > 0:
            authorization_rate = round((authorized_revenue / potential_revenue) * 100, 2)

        # Averages
        ro_count = len(snapshots)
        avg_ro_value = None
        avg_ro_profit = None
        avg_labor_rate = None
        gp_per_labor_hour = None

        if ro_count > 0:
            avg_ro_value = authorized_revenue // ro_count
            avg_ro_profit = authorized_profit // ro_count

        if labor_hours > 0:
            avg_labor_rate = int(labor_revenue / labor_hours)
            gp_per_labor_hour = int(labor_profit / labor_hours)

        return {
            "shop_id": shop_uuid,
            "metric_date": metric_date,
            "ro_count": ro_count,
            "ro_posted_count": ro_posted_count,
            "ro_completed_count": ro_completed_count,
            "authorized_revenue": authorized_revenue,
            "authorized_cost": authorized_cost,
            "authorized_profit": authorized_profit,
            "authorized_gp_percent": authorized_gp_percent,
            "authorized_job_count": authorized_job_count,
            "parts_revenue": parts_revenue,
            "parts_cost": parts_cost,
            "parts_profit": parts_profit,
            "labor_revenue": labor_revenue,
            "labor_cost": labor_cost,
            "labor_profit": labor_profit,
            "labor_hours": labor_hours,
            "sublet_revenue": sublet_revenue,
            "sublet_cost": sublet_cost,
            "fees_total": fees_total,
            "tax_total": tax_total,
            "avg_ro_value": avg_ro_value,
            "avg_ro_profit": avg_ro_profit,
            "avg_labor_rate": avg_labor_rate,
            "gp_per_labor_hour": gp_per_labor_hour,
            "potential_revenue": potential_revenue,
            "potential_job_count": potential_job_count,
            "authorization_rate": authorization_rate,
            "calculation_method": "FROM_RO_SNAPSHOTS",
            "source_snapshot_count": ro_count,
            "updated_at": datetime.utcnow().isoformat()
        }

    def upsert_daily_metrics(self, metrics: Dict) -> Tuple[str, bool]:
        """
        Upsert daily metrics row.

        Returns:
            Tuple of (metrics_id, was_created)
        """
        # Check if row exists
        existing = self.supabase.table("daily_shop_metrics").select("id").eq(
            "shop_id", metrics["shop_id"]
        ).eq(
            "metric_date", metrics["metric_date"]
        ).execute()

        if existing.data:
            # Update existing
            metrics_id = existing.data[0]["id"]
            self.supabase.table("daily_shop_metrics").update(metrics).eq("id", metrics_id).execute()
            return metrics_id, False
        else:
            # Insert new
            result = self.supabase.table("daily_shop_metrics").insert(metrics).execute()
            return result.data[0]["id"], True

    def rebuild_daily_metrics(
        self,
        shop_id: int,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Rebuild daily_shop_metrics for a date range from ro_snapshots.

        Args:
            shop_id: TM shop ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Summary of what was built
        """
        shop_uuid = self.get_shop_uuid(shop_id)
        if not shop_uuid:
            return {
                "status": "error",
                "message": f"Shop {shop_id} not found"
            }

        # Parse dates and iterate through range
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        created = 0
        updated = 0
        skipped = 0
        errors = []
        sample_metrics = []

        current = start
        while current <= end:
            date_str = current.isoformat()

            try:
                snapshots = self.get_snapshots_for_date(shop_uuid, date_str)

                if not snapshots:
                    skipped += 1
                    current += timedelta(days=1)
                    continue

                metrics = self.aggregate_daily_metrics(shop_uuid, snapshots, date_str)
                metrics_id, was_created = self.upsert_daily_metrics(metrics)

                if was_created:
                    created += 1
                else:
                    updated += 1

                # Collect sample for response
                if len(sample_metrics) < 3:
                    sample_metrics.append({
                        "metric_date": date_str,
                        "ro_count": metrics["ro_count"],
                        "authorized_revenue": metrics["authorized_revenue"],
                        "authorized_profit": metrics["authorized_profit"],
                        "authorized_gp_percent": metrics["authorized_gp_percent"]
                    })

            except Exception as e:
                errors.append({
                    "date": date_str,
                    "error": str(e)
                })

            current += timedelta(days=1)

        return {
            "status": "completed",
            "shop_id": shop_id,
            "date_range": f"{start_date} to {end_date}",
            "days_processed": (end - start).days + 1,
            "metrics_created": created,
            "metrics_updated": updated,
            "days_skipped": skipped,
            "errors": len(errors),
            "error_details": errors[:10] if errors else [],
            "sample_metrics": sample_metrics
        }

    def get_daily_metrics(
        self,
        shop_id: int,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Get daily metrics for a date range.

        Args:
            shop_id: TM shop ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of daily_shop_metrics rows
        """
        shop_uuid = self.get_shop_uuid(shop_id)
        if not shop_uuid:
            return []

        result = self.supabase.table("daily_shop_metrics").select("*").eq(
            "shop_id", shop_uuid
        ).gte(
            "metric_date", start_date
        ).lte(
            "metric_date", end_date
        ).order(
            "metric_date", desc=True
        ).execute()

        return result.data or []


def get_metrics_aggregator() -> MetricsAggregator:
    """Factory function for MetricsAggregator."""
    return MetricsAggregator()
