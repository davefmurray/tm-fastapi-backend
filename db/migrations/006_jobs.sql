-- Migration: 006_jobs
-- Description: Create jobs table (child of repair_orders)
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_repair_order_id INTEGER NOT NULL,

  -- Job info
  name TEXT NOT NULL,
  description TEXT,
  job_category_id INTEGER,
  job_category_name TEXT,
  canned_job_id INTEGER,

  -- CRITICAL: Authorization status (controlled vocabulary: true/false)
  authorized BOOLEAN NOT NULL DEFAULT FALSE,
  authorized_date TIMESTAMPTZ,
  declined BOOLEAN DEFAULT FALSE,
  declined_date TIMESTAMPTZ,
  declined_reason TEXT,

  -- Totals (cents)
  total INTEGER NOT NULL DEFAULT 0,
  subtotal INTEGER,
  discount INTEGER DEFAULT 0,
  tax INTEGER,

  -- Category breakdowns (cents, calculated)
  parts_total INTEGER DEFAULT 0,
  parts_cost INTEGER DEFAULT 0,
  labor_total INTEGER DEFAULT 0,
  labor_hours DECIMAL(10,2) DEFAULT 0,
  sublet_total INTEGER DEFAULT 0,
  sublet_cost INTEGER DEFAULT 0,
  fees_total INTEGER DEFAULT 0,

  -- Profit (if TM provides)
  gross_profit_amount INTEGER,
  gross_profit_percent DECIMAL(5,2),

  -- Sort order
  sort_order INTEGER,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_ro ON jobs(shop_id, repair_order_id);
CREATE INDEX IF NOT EXISTS idx_jobs_authorized ON jobs(shop_id, authorized, authorized_date);
CREATE INDEX IF NOT EXISTS idx_jobs_tm_id ON jobs(tm_id);

COMMENT ON TABLE jobs IS 'Jobs within repair orders. authorized=true means customer approved. Cascades delete from repair_orders.';
COMMENT ON COLUMN jobs.authorized IS 'Whether customer authorized this job (controlled vocabulary: true/false)';
