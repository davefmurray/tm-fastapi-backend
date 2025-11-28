-- Migration: 003_customers
-- Description: Create customers reference table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,

  -- Name
  first_name TEXT,
  last_name TEXT,
  company_name TEXT,

  -- Contact (PII - consider RLS views)
  email TEXT[],                        -- Array of emails
  phone_primary TEXT,
  phone_primary_type TEXT,             -- Mobile, Home, Business
  phone_secondary TEXT,
  phone_secondary_type TEXT,

  -- Address (PII)
  address_line1 TEXT,
  address_line2 TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  country TEXT,

  -- Preferences
  customer_type_id INTEGER,
  customer_type_name TEXT,
  tax_exempt BOOLEAN DEFAULT FALSE,
  ok_for_marketing BOOLEAN,
  preferred_contact_method TEXT,

  -- Source tracking
  lead_source TEXT,
  lead_source_id INTEGER,
  referral_source TEXT,

  -- Notes
  notes TEXT,
  internal_notes TEXT,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  tm_created_at TIMESTAMPTZ,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

CREATE INDEX IF NOT EXISTS idx_customers_shop ON customers(shop_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(shop_id, last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_customers_tm_id ON customers(tm_id);

COMMENT ON TABLE customers IS 'Customer records from TM. Contains PII - use customers_analytics view for dashboards.';
