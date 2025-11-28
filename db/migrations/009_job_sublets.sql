-- Migration: 009_job_sublets
-- Description: Create job_sublets line item table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS job_sublets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,

  -- Sublet info
  name TEXT NOT NULL,
  description TEXT,

  -- Vendor
  vendor_id INTEGER,
  vendor_name TEXT,

  -- Pricing (cents)
  cost INTEGER,
  retail INTEGER NOT NULL DEFAULT 0,

  -- Tracking
  invoice_number TEXT,
  po_number TEXT,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_sublets_unique ON job_sublets(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_job_sublets_ro ON job_sublets(shop_id, repair_order_id);
CREATE INDEX IF NOT EXISTS idx_job_sublets_job ON job_sublets(shop_id, job_id);

COMMENT ON TABLE job_sublets IS 'Sublet work within jobs (outsourced to other vendors). All money in cents.';
