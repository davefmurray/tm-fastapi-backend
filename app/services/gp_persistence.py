"""
GP Persistence Service (Tier 4)

Stores GP calculation results to Supabase for historical tracking and analysis.
Enables trend analysis, period comparisons, and audit trail.

Database Schema (create in Supabase Dashboard):
-----------------------------------------------

-- GP Daily Snapshots (aggregated daily totals)
CREATE TABLE gp_daily_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,

    -- Revenue & Profit
    total_revenue INTEGER NOT NULL,      -- cents
    total_cost INTEGER NOT NULL,         -- cents
    total_gp_dollars INTEGER NOT NULL,   -- cents
    gp_percentage DECIMAL(5,2) NOT NULL,

    -- RO Stats
    ro_count INTEGER NOT NULL,
    aro_cents INTEGER NOT NULL,          -- Average Repair Order in cents

    -- Category Breakdown
    parts_revenue INTEGER DEFAULT 0,
    parts_cost INTEGER DEFAULT 0,
    parts_profit INTEGER DEFAULT 0,
    labor_revenue INTEGER DEFAULT 0,
    labor_cost INTEGER DEFAULT 0,
    labor_profit INTEGER DEFAULT 0,
    sublet_revenue INTEGER DEFAULT 0,
    sublet_cost INTEGER DEFAULT 0,
    sublet_profit INTEGER DEFAULT 0,
    fees_total INTEGER DEFAULT 0,
    taxes_total INTEGER DEFAULT 0,

    -- Tech Stats
    tech_hours_billed DECIMAL(10,2) DEFAULT 0,
    avg_tech_rate INTEGER DEFAULT 0,     -- cents per hour

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    calculation_method TEXT DEFAULT 'TRUE_GP_TIER4',

    UNIQUE(shop_id, snapshot_date)
);

-- GP Individual RO Records (detailed per-RO history)
CREATE TABLE gp_ro_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    ro_id INTEGER NOT NULL,
    ro_number TEXT,
    snapshot_date DATE NOT NULL,

    -- RO Details
    customer_name TEXT,
    vehicle_description TEXT,
    ro_status TEXT,

    -- GP Metrics
    total_revenue INTEGER NOT NULL,      -- cents
    total_cost INTEGER NOT NULL,         -- cents
    gp_dollars INTEGER NOT NULL,         -- cents
    gp_percentage DECIMAL(5,2) NOT NULL,

    -- TM vs True GP Comparison
    tm_reported_gp_pct DECIMAL(5,2),
    variance_pct DECIMAL(5,2),
    variance_reason TEXT,

    -- Category Breakdown (JSON for flexibility)
    parts_breakdown JSONB,
    labor_breakdown JSONB,
    sublet_breakdown JSONB,
    fee_breakdown JSONB,
    tax_breakdown JSONB,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(shop_id, ro_id, snapshot_date)
);

-- Tech Performance History
CREATE TABLE gp_tech_performance (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    tech_id INTEGER NOT NULL,
    tech_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL,

    -- Performance Metrics
    hours_billed DECIMAL(10,2) NOT NULL,
    hourly_rate INTEGER NOT NULL,        -- cents
    labor_revenue INTEGER NOT NULL,      -- cents
    labor_cost INTEGER NOT NULL,         -- cents
    labor_profit INTEGER NOT NULL,       -- cents
    labor_margin_pct DECIMAL(5,2) NOT NULL,
    gp_per_hour INTEGER NOT NULL,        -- cents

    -- Volume
    jobs_worked INTEGER DEFAULT 0,
    ros_worked INTEGER DEFAULT 0,

    -- Rate Sources (JSON)
    rate_source_counts JSONB,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(shop_id, tech_id, snapshot_date)
);

-- Indexes for common queries
CREATE INDEX idx_daily_snapshots_shop_date ON gp_daily_snapshots(shop_id, snapshot_date DESC);
CREATE INDEX idx_ro_history_shop_date ON gp_ro_history(shop_id, snapshot_date DESC);
CREATE INDEX idx_ro_history_ro_id ON gp_ro_history(ro_id);
CREATE INDEX idx_tech_performance_shop_date ON gp_tech_performance(shop_id, snapshot_date DESC);
CREATE INDEX idx_tech_performance_tech ON gp_tech_performance(tech_id, snapshot_date DESC);
"""

import os
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from dataclasses import asdict
import json

from supabase import create_client, Client

from app.services.gp_calculator import (
    ROTrueGP,
    TechPerformance,
    to_dict,
    cents_to_dollars
)


class GPPersistenceService:
    """
    Tier 4: Persist GP calculations to Supabase for historical analysis.

    Features:
    - Store daily GP snapshots (aggregated totals)
    - Store individual RO GP records
    - Store technician performance history
    - Query historical data for trends
    """

    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Table names (configurable)
        self.daily_table = os.getenv("GP_DAILY_TABLE", "gp_daily_snapshots")
        self.ro_table = os.getenv("GP_RO_TABLE", "gp_ro_history")
        self.tech_table = os.getenv("GP_TECH_TABLE", "gp_tech_performance")

    # =========================================================================
    # STORE METHODS
    # =========================================================================

    async def store_daily_snapshot(
        self,
        shop_id: int,
        snapshot_date: date,
        ro_results: List[ROTrueGP],
        tech_performance: Dict[int, TechPerformance]
    ) -> Dict[str, Any]:
        """
        Store aggregated daily GP snapshot.

        Args:
            shop_id: Shop identifier
            snapshot_date: Date of the snapshot
            ro_results: List of calculated RO GP results
            tech_performance: Dict of tech_id -> TechPerformance

        Returns:
            Created record with id
        """
        # Aggregate totals
        total_revenue = sum(r.total_revenue for r in ro_results)
        total_cost = sum(r.total_cost for r in ro_results)
        total_gp = sum(r.gp_dollars for r in ro_results)
        gp_pct = (total_gp / total_revenue * 100) if total_revenue > 0 else 0

        parts_revenue = sum(r.parts_summary.revenue for r in ro_results)
        parts_cost = sum(r.parts_summary.cost for r in ro_results)
        parts_profit = sum(r.parts_summary.profit for r in ro_results)

        labor_revenue = sum(r.labor_summary.revenue for r in ro_results)
        labor_cost = sum(r.labor_summary.cost for r in ro_results)
        labor_profit = sum(r.labor_summary.profit for r in ro_results)

        sublet_revenue = sum(r.sublet_summary.revenue for r in ro_results)
        sublet_cost = sum(r.sublet_summary.cost for r in ro_results)
        sublet_profit = sum(r.sublet_summary.profit for r in ro_results)

        fees_total = sum(r.fee_breakdown.total for r in ro_results)
        taxes_total = sum(r.tax_breakdown.total for r in ro_results)

        # Tech aggregates
        total_hours = sum(tp.hours_billed for tp in tech_performance.values())
        avg_rate = 0
        if tech_performance:
            total_labor_rev = sum(tp.labor_revenue for tp in tech_performance.values())
            if total_hours > 0:
                avg_rate = int(total_labor_rev / total_hours)

        record = {
            "shop_id": shop_id,
            "snapshot_date": snapshot_date.isoformat(),
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_gp_dollars": total_gp,
            "gp_percentage": round(gp_pct, 2),
            "ro_count": len(ro_results),
            "aro_cents": int(total_revenue / len(ro_results)) if ro_results else 0,
            "parts_revenue": parts_revenue,
            "parts_cost": parts_cost,
            "parts_profit": parts_profit,
            "labor_revenue": labor_revenue,
            "labor_cost": labor_cost,
            "labor_profit": labor_profit,
            "sublet_revenue": sublet_revenue,
            "sublet_cost": sublet_cost,
            "sublet_profit": sublet_profit,
            "fees_total": fees_total,
            "taxes_total": taxes_total,
            "tech_hours_billed": round(total_hours, 2),
            "avg_tech_rate": avg_rate,
            "calculation_method": "TRUE_GP_TIER4"
        }

        try:
            # Upsert (update if exists, insert if not)
            result = self.supabase.table(self.daily_table).upsert(
                record,
                on_conflict="shop_id,snapshot_date"
            ).execute()

            print(f"[GP Persistence] Stored daily snapshot for {snapshot_date}")
            return result.data[0] if result.data else record

        except Exception as e:
            print(f"[GP Persistence] Error storing daily snapshot: {e}")
            raise

    async def store_ro_history(
        self,
        shop_id: int,
        snapshot_date: date,
        ro_result: ROTrueGP,
        tm_reported_gp_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Store individual RO GP calculation for historical tracking.

        Args:
            shop_id: Shop identifier
            snapshot_date: Date of calculation
            ro_result: Calculated GP result for this RO
            tm_reported_gp_pct: TM's reported GP% for variance tracking

        Returns:
            Created record
        """
        variance_pct = None
        variance_reason = None

        if tm_reported_gp_pct is not None:
            variance_pct = round(ro_result.gp_percentage - tm_reported_gp_pct, 2)
            if abs(variance_pct) > 1:
                reasons = []
                if ro_result.labor_summary.cost > 0:
                    reasons.append("labor_cost_included")
                if ro_result.sublet_summary.cost > 0:
                    reasons.append("sublet_cost_included")
                if ro_result.fee_breakdown.total > 0:
                    reasons.append("fees_analyzed")
                variance_reason = ",".join(reasons) if reasons else "calculation_method"

        record = {
            "shop_id": shop_id,
            "ro_id": ro_result.ro_id,
            "ro_number": ro_result.ro_number,
            "snapshot_date": snapshot_date.isoformat(),
            "customer_name": ro_result.customer_name,
            "vehicle_description": ro_result.vehicle,
            "ro_status": ro_result.status,
            "total_revenue": ro_result.total_revenue,
            "total_cost": ro_result.total_cost,
            "gp_dollars": ro_result.gp_dollars,
            "gp_percentage": round(ro_result.gp_percentage, 2),
            "tm_reported_gp_pct": tm_reported_gp_pct,
            "variance_pct": variance_pct,
            "variance_reason": variance_reason,
            "parts_breakdown": json.dumps(to_dict(ro_result.parts_summary)),
            "labor_breakdown": json.dumps(to_dict(ro_result.labor_summary)),
            "sublet_breakdown": json.dumps(to_dict(ro_result.sublet_summary)),
            "fee_breakdown": json.dumps(to_dict(ro_result.fee_breakdown)),
            "tax_breakdown": json.dumps(to_dict(ro_result.tax_breakdown))
        }

        try:
            result = self.supabase.table(self.ro_table).upsert(
                record,
                on_conflict="shop_id,ro_id,snapshot_date"
            ).execute()

            print(f"[GP Persistence] Stored RO history for RO #{ro_result.ro_number}")
            return result.data[0] if result.data else record

        except Exception as e:
            print(f"[GP Persistence] Error storing RO history: {e}")
            raise

    async def store_tech_performance(
        self,
        shop_id: int,
        snapshot_date: date,
        tech_performance: Dict[int, TechPerformance]
    ) -> List[Dict[str, Any]]:
        """
        Store technician performance metrics for the period.

        Args:
            shop_id: Shop identifier
            snapshot_date: Date of calculation
            tech_performance: Dict of tech_id -> TechPerformance

        Returns:
            List of created records
        """
        records = []

        for tech_id, perf in tech_performance.items():
            record = {
                "shop_id": shop_id,
                "tech_id": tech_id,
                "tech_name": perf.tech_name,
                "snapshot_date": snapshot_date.isoformat(),
                "hours_billed": round(perf.hours_billed, 2),
                "hourly_rate": perf.hourly_rate,
                "labor_revenue": perf.labor_revenue,
                "labor_cost": perf.labor_cost,
                "labor_profit": perf.labor_profit,
                "labor_margin_pct": round(perf.labor_margin_pct, 2),
                "gp_per_hour": perf.gp_per_hour,
                "jobs_worked": perf.jobs_worked,
                "ros_worked": perf.ros_worked,
                "rate_source_counts": json.dumps(perf.rate_source_counts)
            }
            records.append(record)

        if not records:
            return []

        try:
            result = self.supabase.table(self.tech_table).upsert(
                records,
                on_conflict="shop_id,tech_id,snapshot_date"
            ).execute()

            print(f"[GP Persistence] Stored {len(records)} tech performance records")
            return result.data if result.data else records

        except Exception as e:
            print(f"[GP Persistence] Error storing tech performance: {e}")
            raise

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    async def get_daily_snapshots(
        self,
        shop_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Get daily GP snapshots for a date range.

        Args:
            shop_id: Shop identifier
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            List of daily snapshot records
        """
        try:
            result = self.supabase.table(self.daily_table) \
                .select("*") \
                .eq("shop_id", shop_id) \
                .gte("snapshot_date", start_date.isoformat()) \
                .lte("snapshot_date", end_date.isoformat()) \
                .order("snapshot_date", desc=True) \
                .execute()

            return result.data or []

        except Exception as e:
            print(f"[GP Persistence] Error fetching daily snapshots: {e}")
            return []

    async def get_ro_history(
        self,
        shop_id: int,
        ro_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get RO GP history records.

        Args:
            shop_id: Shop identifier
            ro_id: Optional specific RO to query
            start_date: Optional start of date range
            end_date: Optional end of date range
            limit: Max records to return

        Returns:
            List of RO history records
        """
        try:
            query = self.supabase.table(self.ro_table) \
                .select("*") \
                .eq("shop_id", shop_id)

            if ro_id:
                query = query.eq("ro_id", ro_id)
            if start_date:
                query = query.gte("snapshot_date", start_date.isoformat())
            if end_date:
                query = query.lte("snapshot_date", end_date.isoformat())

            result = query.order("snapshot_date", desc=True).limit(limit).execute()

            return result.data or []

        except Exception as e:
            print(f"[GP Persistence] Error fetching RO history: {e}")
            return []

    async def get_tech_performance_history(
        self,
        shop_id: int,
        tech_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get technician performance history.

        Args:
            shop_id: Shop identifier
            tech_id: Optional specific technician
            start_date: Optional start of date range
            end_date: Optional end of date range

        Returns:
            List of tech performance records
        """
        try:
            query = self.supabase.table(self.tech_table) \
                .select("*") \
                .eq("shop_id", shop_id)

            if tech_id:
                query = query.eq("tech_id", tech_id)
            if start_date:
                query = query.gte("snapshot_date", start_date.isoformat())
            if end_date:
                query = query.lte("snapshot_date", end_date.isoformat())

            result = query.order("snapshot_date", desc=True).execute()

            return result.data or []

        except Exception as e:
            print(f"[GP Persistence] Error fetching tech history: {e}")
            return []

    async def get_trend_summary(
        self,
        shop_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get GP trend summary for the specified period.

        Args:
            shop_id: Shop identifier
            days: Number of days to analyze

        Returns:
            Trend analysis with averages and changes
        """
        from datetime import timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        snapshots = await self.get_daily_snapshots(shop_id, start_date, end_date)

        if not snapshots:
            return {
                "period_days": days,
                "data_points": 0,
                "message": "No historical data available"
            }

        # Calculate averages
        avg_gp_pct = sum(s["gp_percentage"] for s in snapshots) / len(snapshots)
        avg_revenue = sum(s["total_revenue"] for s in snapshots) / len(snapshots)
        avg_aro = sum(s["aro_cents"] for s in snapshots) / len(snapshots)
        total_ros = sum(s["ro_count"] for s in snapshots)

        # Calculate trend (first half vs second half)
        mid = len(snapshots) // 2
        if mid > 0:
            first_half = snapshots[mid:]  # Older (sorted desc)
            second_half = snapshots[:mid]  # Newer

            first_avg_gp = sum(s["gp_percentage"] for s in first_half) / len(first_half)
            second_avg_gp = sum(s["gp_percentage"] for s in second_half) / len(second_half)
            gp_trend = second_avg_gp - first_avg_gp
        else:
            gp_trend = 0

        return {
            "period_days": days,
            "data_points": len(snapshots),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "average_gp_percentage": round(avg_gp_pct, 2),
            "average_daily_revenue": cents_to_dollars(int(avg_revenue)),
            "average_aro": cents_to_dollars(int(avg_aro)),
            "total_ros": total_ros,
            "gp_trend": round(gp_trend, 2),
            "trend_direction": "up" if gp_trend > 0.5 else ("down" if gp_trend < -0.5 else "stable")
        }


# Singleton instance
_persistence_service: Optional[GPPersistenceService] = None


def get_persistence_service() -> GPPersistenceService:
    """Get or create GP persistence service"""
    global _persistence_service
    if _persistence_service is None:
        _persistence_service = GPPersistenceService()
    return _persistence_service
