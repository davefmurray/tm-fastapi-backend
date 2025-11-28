-- Migration: 001_shops
-- Description: Create shops reference table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS shops (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tm_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',

  -- Shop configuration
  default_labor_rate INTEGER,          -- cents/hour
  default_parts_margin DECIMAL(5,4),   -- e.g., 0.40 = 40%
  default_tax_rate DECIMAL(5,4),       -- e.g., 0.0750 = 7.5%

  -- TM metadata (store everything TM returns)
  tm_metadata JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(tm_id)
);

CREATE INDEX IF NOT EXISTS idx_shops_tm_id ON shops(tm_id);

-- Insert default shop for JJ AUTO (shop_id 6212)
INSERT INTO shops (tm_id, name, timezone, default_labor_rate)
VALUES (6212, 'JJ AUTO - SERVICE & TIRES', 'America/New_York', 17950)
ON CONFLICT (tm_id) DO NOTHING;

COMMENT ON TABLE shops IS 'Reference table for shops. Each shop has a unique tm_id from Tekmetric.';
COMMENT ON COLUMN shops.default_labor_rate IS 'Default labor rate in cents per hour';
