-- Migration: 005_repair_orders
-- Description: Create repair_orders transactional table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS repair_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,

  -- References
  customer_id UUID REFERENCES customers(id),
  vehicle_id UUID REFERENCES vehicles(id),
  service_advisor_id UUID REFERENCES employees(id),
  tm_customer_id INTEGER,              -- Denormalized
  tm_vehicle_id INTEGER,
  tm_service_advisor_id INTEGER,

  -- RO identifiers
  ro_number INTEGER NOT NULL,

  -- Status (controlled vocabulary: ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE)
  status TEXT NOT NULL,
  status_id INTEGER,

  -- Dates (all from TM)
  -- TIMESTAMPTZ fields are stored in UTC
  -- DATE fields are interpreted in shop's local timezone
  created_date TIMESTAMPTZ,
  updated_date TIMESTAMPTZ,
  posted_date DATE,                    -- KEY for reports (shop-local calendar day)
  completed_date DATE,
  promised_date TIMESTAMPTZ,
  dropped_off_date TIMESTAMPTZ,
  picked_up_date TIMESTAMPTZ,

  -- POTENTIAL metrics (all jobs, cents)
  potential_total INTEGER NOT NULL DEFAULT 0,
  potential_subtotal INTEGER,          -- Often null in TM
  potential_tax INTEGER,
  potential_discount INTEGER DEFAULT 0,
  potential_job_count INTEGER NOT NULL DEFAULT 0,
  potential_parts_total INTEGER DEFAULT 0,
  potential_labor_total INTEGER DEFAULT 0,
  potential_sublet_total INTEGER DEFAULT 0,
  potential_fees_total INTEGER DEFAULT 0,

  -- AUTHORIZED metrics (authorized jobs only, cents)
  -- NOTE: authorized_total comes from /estimate endpoint. It is the sum of authorized
  -- jobs' retail totals (parts + labor + fees - discounts). This is what TM shows as
  -- the "authorized" amount on the estimate screen.
  authorized_total INTEGER NOT NULL DEFAULT 0,
  authorized_subtotal INTEGER,
  authorized_tax INTEGER,
  authorized_discount INTEGER DEFAULT 0,
  authorized_job_count INTEGER NOT NULL DEFAULT 0,
  authorized_parts_total INTEGER DEFAULT 0,
  authorized_labor_total INTEGER DEFAULT 0,
  authorized_sublet_total INTEGER DEFAULT 0,
  authorized_fees_total INTEGER DEFAULT 0,

  -- Profit (from /profit/labor endpoint - AUTHORIZED ONLY)
  -- NOTE: authorized_revenue comes from /profit/labor totalProfit.retail. This is the
  -- canonical revenue figure for GP% calculations per METRIC_CONTRACTS.md.
  -- IMPORTANT: Use authorized_revenue (NOT authorized_total) for GP% and profit calcs.
  authorized_revenue INTEGER,          -- totalProfit.retail (USE THIS for GP%)
  authorized_cost INTEGER,             -- totalProfit.cost
  authorized_profit INTEGER,           -- totalProfit.profit
  authorized_gp_percent DECIMAL(5,2),  -- totalProfit.margin * 100
  authorized_labor_hours DECIMAL(10,2),

  -- Payment
  amount_paid INTEGER DEFAULT 0,
  balance_due INTEGER DEFAULT 0,

  -- Shop info
  shop_supplies_total INTEGER DEFAULT 0,
  epa_total INTEGER DEFAULT 0,

  -- Labels/Tags
  label TEXT,
  label_id INTEGER,

  -- Notes
  customer_concern TEXT,
  tech_notes TEXT,
  recommendation TEXT,
  internal_notes TEXT,

  -- TM overflow
  tm_extra JSONB,

  -- Sync tracking
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sync_hash TEXT,                      -- For change detection

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

-- Critical indexes for dashboard queries
CREATE INDEX IF NOT EXISTS idx_ro_shop_posted ON repair_orders(shop_id, posted_date);
CREATE INDEX IF NOT EXISTS idx_ro_shop_status ON repair_orders(shop_id, status);
CREATE INDEX IF NOT EXISTS idx_ro_shop_created ON repair_orders(shop_id, created_date);
CREATE INDEX IF NOT EXISTS idx_ro_shop_updated ON repair_orders(shop_id, updated_date);
CREATE INDEX IF NOT EXISTS idx_ro_shop_advisor ON repair_orders(shop_id, service_advisor_id);
CREATE INDEX IF NOT EXISTS idx_ro_tm_id ON repair_orders(tm_id);
CREATE INDEX IF NOT EXISTS idx_ro_number ON repair_orders(shop_id, ro_number);

COMMENT ON TABLE repair_orders IS 'Repair orders from TM. Status: ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE. All money in cents.';
COMMENT ON COLUMN repair_orders.authorized_total IS 'From /estimate - sum of authorized jobs retail totals';
COMMENT ON COLUMN repair_orders.authorized_revenue IS 'From /profit/labor - USE THIS for GP% calculations';
COMMENT ON COLUMN repair_orders.posted_date IS 'Shop-local calendar day when RO was posted';
