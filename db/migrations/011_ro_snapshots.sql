-- Migration: 011_ro_snapshots
-- Description: Create ro_snapshots table for point-in-time RO metrics
-- Date: 2025-11-27

-- ro_snapshots: Computed once per RO state change (posted, complete).
-- Source of truth for daily aggregation. All money in cents.

CREATE TABLE IF NOT EXISTS ro_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_repair_order_id INTEGER NOT NULL,

  -- Snapshot identity
  snapshot_date DATE NOT NULL,         -- posted_date or completed_date (shop-local)
  -- snapshot_trigger controlled vocabulary: posted, completed, manual
  snapshot_trigger TEXT NOT NULL,
  ro_status TEXT NOT NULL,

  -- RO summary
  ro_number INTEGER NOT NULL,
  customer_name TEXT,
  vehicle_description TEXT,
  advisor_name TEXT,

  -- AUTHORIZED metrics (cents) - what we bill
  authorized_revenue INTEGER NOT NULL DEFAULT 0,
  authorized_cost INTEGER NOT NULL DEFAULT 0,
  authorized_profit INTEGER NOT NULL DEFAULT 0,
  authorized_gp_percent DECIMAL(5,2),
  authorized_job_count INTEGER NOT NULL DEFAULT 0,

  -- Category breakdown (authorized only, cents)
  parts_revenue INTEGER DEFAULT 0,
  parts_cost INTEGER DEFAULT 0,
  parts_profit INTEGER DEFAULT 0,
  labor_revenue INTEGER DEFAULT 0,
  labor_cost INTEGER DEFAULT 0,
  labor_profit INTEGER DEFAULT 0,
  labor_hours DECIMAL(10,2) DEFAULT 0,
  sublet_revenue INTEGER DEFAULT 0,
  sublet_cost INTEGER DEFAULT 0,
  fees_total INTEGER DEFAULT 0,
  tax_total INTEGER DEFAULT 0,

  -- POTENTIAL metrics (for comparison)
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,

  -- Validation
  tm_reported_gp_percent DECIMAL(5,2), -- From /profit/labor for comparison
  variance_percent DECIMAL(5,2),       -- Our calc vs TM
  variance_reason TEXT,

  -- Calculation metadata
  calculation_method TEXT DEFAULT 'TRUE_GP',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, repair_order_id, snapshot_date, snapshot_trigger)
);

CREATE INDEX IF NOT EXISTS idx_ro_snapshots_date ON ro_snapshots(shop_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ro_snapshots_ro ON ro_snapshots(shop_id, repair_order_id);

COMMENT ON TABLE ro_snapshots IS 'Point-in-time RO metrics captured on posted/complete. Used to build daily_shop_metrics. All money in cents.';
COMMENT ON COLUMN ro_snapshots.snapshot_trigger IS 'What triggered this snapshot: posted, completed, manual';
COMMENT ON COLUMN ro_snapshots.snapshot_date IS 'Shop-local calendar day (from shops.timezone)';
