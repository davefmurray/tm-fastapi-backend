-- Migration: 008_job_labor
-- Description: Create job_labor line item table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS job_labor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,

  -- Labor info
  name TEXT NOT NULL,
  description TEXT,
  labor_type TEXT,                     -- Diag, Repair, R&R, etc.

  -- Time & Rate (cents)
  hours DECIMAL(10,2) NOT NULL DEFAULT 0,
  rate INTEGER NOT NULL DEFAULT 0,     -- Retail rate per hour
  total INTEGER NOT NULL DEFAULT 0,    -- hours * rate

  -- Technician assignment
  technician_id UUID REFERENCES employees(id),
  tm_technician_id INTEGER,
  technician_name TEXT,                -- Denormalized for reporting

  -- Cost calculation
  tech_hourly_cost INTEGER,            -- Actual tech rate (cents)
  labor_cost INTEGER,                  -- hours * tech_hourly_cost
  rate_source TEXT,                    -- 'assigned', 'shop_avg', 'default'

  -- Skill level
  skill_level TEXT,                    -- A, B, C tech

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_labor_unique ON job_labor(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_job_labor_ro ON job_labor(shop_id, repair_order_id);
CREATE INDEX IF NOT EXISTS idx_job_labor_job ON job_labor(shop_id, job_id);
CREATE INDEX IF NOT EXISTS idx_job_labor_tech ON job_labor(shop_id, technician_id);

COMMENT ON TABLE job_labor IS 'Labor entries within jobs. All money in cents. Cascades delete from jobs and repair_orders.';
COMMENT ON COLUMN job_labor.rate_source IS 'How tech cost was determined: assigned, shop_avg, default';
