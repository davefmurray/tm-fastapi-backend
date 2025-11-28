-- Migration: 012_daily_shop_metrics
-- Description: Create daily_shop_metrics aggregate table
-- Date: 2025-11-27

-- daily_shop_metrics: Aggregated FROM ro_snapshots, not recalculated from line items.
-- All money in cents.

CREATE TABLE IF NOT EXISTS daily_shop_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  metric_date DATE NOT NULL,           -- Shop-local calendar day

  -- RO counts
  ro_count INTEGER NOT NULL DEFAULT 0,
  ro_posted_count INTEGER DEFAULT 0,
  ro_completed_count INTEGER DEFAULT 0,

  -- AUTHORIZED revenue & profit (cents)
  authorized_revenue INTEGER NOT NULL DEFAULT 0,
  authorized_cost INTEGER NOT NULL DEFAULT 0,
  authorized_profit INTEGER NOT NULL DEFAULT 0,
  authorized_gp_percent DECIMAL(5,2),
  authorized_job_count INTEGER DEFAULT 0,

  -- Category breakdown (cents)
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

  -- Averages
  avg_ro_value INTEGER,                -- cents
  avg_ro_profit INTEGER,               -- cents
  avg_labor_rate INTEGER,              -- cents/hour
  gp_per_labor_hour INTEGER,           -- cents

  -- POTENTIAL metrics
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,
  authorization_rate DECIMAL(5,2),     -- authorized/potential * 100

  -- Source tracking
  calculation_method TEXT DEFAULT 'FROM_RO_SNAPSHOTS',
  source_snapshot_count INTEGER,       -- How many ro_snapshots aggregated

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_shop_metrics(shop_id, metric_date);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date_range ON daily_shop_metrics(shop_id, metric_date DESC);

COMMENT ON TABLE daily_shop_metrics IS 'Daily aggregated metrics from ro_snapshots. One row per shop per day. All money in cents.';
COMMENT ON COLUMN daily_shop_metrics.metric_date IS 'Shop-local calendar day (from shops.timezone)';
COMMENT ON COLUMN daily_shop_metrics.calculation_method IS 'How metrics were calculated: FROM_RO_SNAPSHOTS';
