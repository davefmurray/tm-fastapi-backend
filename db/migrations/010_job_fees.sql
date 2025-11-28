-- Migration: 010_job_fees
-- Description: Create job_fees line item table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS job_fees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,

  -- Fee info (TM has no fee ID, use composite key)
  name TEXT NOT NULL,
  -- fee_type controlled vocabulary: shop_supplies, environmental, disposal, hazmat, other
  fee_type TEXT,

  -- Calculation
  amount INTEGER,                      -- Fixed amount (cents)
  percentage DECIMAL(5,4),             -- If percentage-based
  cap INTEGER,                         -- Max if percentage (cents)

  -- Result
  total INTEGER NOT NULL DEFAULT 0,    -- Final calculated amount (cents)
  taxable BOOLEAN DEFAULT FALSE,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite unique: one fee name per job
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_fees_unique ON job_fees(shop_id, tm_job_id, name);
CREATE INDEX IF NOT EXISTS idx_job_fees_ro ON job_fees(shop_id, repair_order_id);
CREATE INDEX IF NOT EXISTS idx_job_fees_job ON job_fees(shop_id, job_id);

COMMENT ON TABLE job_fees IS 'Fees within jobs (shop supplies, EPA, etc). fee_type: shop_supplies, environmental, disposal, hazmat, other';
