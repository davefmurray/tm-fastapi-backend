-- Migration: 007_job_parts
-- Description: Create job_parts line item table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS job_parts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,                       -- TM part ID (may be null for temp parts)
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,

  -- Part info
  name TEXT NOT NULL,
  part_number TEXT,
  description TEXT,

  -- Pricing (cents)
  quantity DECIMAL(10,4) NOT NULL DEFAULT 1,
  retail INTEGER NOT NULL DEFAULT 0,   -- Per unit
  cost INTEGER,                        -- Per unit (may be null or total)
  core_charge INTEGER,
  total INTEGER NOT NULL DEFAULT 0,    -- qty * retail

  -- Source
  vendor_id INTEGER,
  vendor_name TEXT,
  manufacturer TEXT,

  -- Status
  ordered BOOLEAN DEFAULT FALSE,
  received BOOLEAN DEFAULT FALSE,
  backordered BOOLEAN DEFAULT FALSE,

  -- Categorization
  part_type TEXT,                      -- OEM, Aftermarket, Used
  category TEXT,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Allow null tm_id for temp parts, but unique if present
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_parts_unique ON job_parts(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_job_parts_ro ON job_parts(shop_id, repair_order_id);
CREATE INDEX IF NOT EXISTS idx_job_parts_job ON job_parts(shop_id, job_id);

COMMENT ON TABLE job_parts IS 'Parts within jobs. All money in cents. Cascades delete from jobs and repair_orders.';
