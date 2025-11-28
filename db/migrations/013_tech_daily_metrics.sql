-- Migration: 013_tech_daily_metrics
-- Description: Create tech_daily_metrics aggregate table
-- Date: 2025-11-27

-- tech_daily_metrics: Technician performance aggregated from job_labor.
-- All money in cents.

CREATE TABLE IF NOT EXISTS tech_daily_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  technician_id UUID NOT NULL REFERENCES employees(id),
  metric_date DATE NOT NULL,           -- Shop-local calendar day

  -- Performance
  hours_billed DECIMAL(10,2) NOT NULL DEFAULT 0,
  hourly_rate INTEGER,                 -- Avg cents/hour (retail)
  hourly_cost INTEGER,                 -- Avg cents/hour (cost)

  -- Revenue (cents)
  labor_revenue INTEGER NOT NULL DEFAULT 0,
  labor_cost INTEGER NOT NULL DEFAULT 0,
  labor_profit INTEGER NOT NULL DEFAULT 0,
  labor_gp_percent DECIMAL(5,2),
  gp_per_hour INTEGER,                 -- cents

  -- Volume
  jobs_worked INTEGER DEFAULT 0,
  ros_worked INTEGER DEFAULT 0,

  -- Rate source breakdown
  rate_sources JSONB,                  -- {"assigned": 5, "shop_avg": 2, "default": 1}

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, technician_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_tech_metrics_date ON tech_daily_metrics(shop_id, metric_date);
CREATE INDEX IF NOT EXISTS idx_tech_metrics_tech ON tech_daily_metrics(shop_id, technician_id);
CREATE INDEX IF NOT EXISTS idx_tech_metrics_date_range ON tech_daily_metrics(shop_id, metric_date DESC);

COMMENT ON TABLE tech_daily_metrics IS 'Daily technician performance metrics. One row per tech per day. All money in cents.';
COMMENT ON COLUMN tech_daily_metrics.rate_sources IS 'Breakdown of how labor costs were sourced: {"assigned": N, "shop_avg": N, "default": N}';
