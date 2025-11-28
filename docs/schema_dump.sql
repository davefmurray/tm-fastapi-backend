-- ============================================================================
-- TM Data Warehouse Schema Dump
-- Generated: 2025-11-27
-- Supabase Project: TM-VID-Magic (oummojcsghoitfhpscnn)
-- ============================================================================

-- Migration History: 15 migrations applied
-- See db/migrations/ for individual migration files

-- ============================================================================
-- TABLE: shops (Root reference table)
-- ============================================================================
CREATE TABLE shops (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tm_id INTEGER NOT NULL UNIQUE,                    -- TM shop ID (e.g., 6212)
  name TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  default_labor_rate INTEGER,                        -- cents/hour
  default_parts_margin DECIMAL(5,4),
  default_tax_rate DECIMAL(5,4),
  tm_metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE shops IS 'Reference table for shops. Each shop has a unique tm_id from Tekmetric.';

-- Seeded with JJ AUTO (tm_id: 6212, timezone: America/New_York)

-- ============================================================================
-- TABLE: employees
-- ============================================================================
CREATE TABLE employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,                           -- TM employee ID
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  role INTEGER,                                     -- 1=Admin, 2=Advisor, 3=Tech, 4=Owner
  role_name TEXT,                                   -- Controlled: SERVICE_ADVISOR, TECHNICIAN, SHOP_ADMIN, OWNER
  hourly_rate INTEGER,                              -- Tech cost rate in cents
  status TEXT,                                      -- Controlled: ACTIVE, INACTIVE
  username TEXT,
  phone TEXT,
  hire_date DATE,
  termination_date DATE,
  commission_rate DECIMAL(5,4),
  can_clock_in BOOLEAN,
  can_sell BOOLEAN,
  can_tech BOOLEAN,
  tm_extra JSONB,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(shop_id, tm_id)
);
COMMENT ON TABLE employees IS 'Employees from TM. Role: 1=Admin, 2=Advisor, 3=Tech, 4=Owner. Status: ACTIVE, INACTIVE.';

-- ============================================================================
-- TABLE: customers
-- ============================================================================
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  first_name TEXT,
  last_name TEXT,
  company_name TEXT,
  email TEXT[],                                     -- Array of emails
  phone_primary TEXT,
  phone_primary_type TEXT,
  phone_secondary TEXT,
  phone_secondary_type TEXT,
  address_line1 TEXT,
  address_line2 TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  country TEXT,
  customer_type_id INTEGER,
  customer_type_name TEXT,                          -- fleet, retail, wholesale, etc.
  tax_exempt BOOLEAN DEFAULT FALSE,
  ok_for_marketing BOOLEAN,
  preferred_contact_method TEXT,
  lead_source TEXT,
  lead_source_id INTEGER,
  referral_source TEXT,
  notes TEXT,
  internal_notes TEXT,
  tm_extra JSONB,
  tm_created_at TIMESTAMPTZ,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(shop_id, tm_id)
);
COMMENT ON TABLE customers IS 'Customer records from TM. Contains PII - use customers_analytics view for dashboards.';

-- ============================================================================
-- TABLE: vehicles
-- ============================================================================
CREATE TABLE vehicles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  customer_id UUID REFERENCES customers(id),
  tm_customer_id INTEGER,
  year INTEGER,
  make TEXT,
  make_id INTEGER,
  model TEXT,
  model_id INTEGER,
  sub_model TEXT,
  sub_model_id INTEGER,
  engine TEXT,
  engine_id INTEGER,
  transmission TEXT,
  transmission_id INTEGER,
  drive_type TEXT,
  drive_type_id INTEGER,
  body_style TEXT,
  vin TEXT,
  license_plate TEXT,
  license_state TEXT,
  unit_number TEXT,
  fleet_number TEXT,
  color TEXT,
  interior_color TEXT,
  odometer INTEGER,
  odometer_unit TEXT,
  odometer_date DATE,
  custom_description TEXT,
  notes TEXT,
  base_vehicle_id INTEGER,
  tm_extra JSONB,
  tm_created_at TIMESTAMPTZ,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(shop_id, tm_id)
);
COMMENT ON TABLE vehicles IS 'Vehicle records from TM. Linked to customers via customer_id.';

-- ============================================================================
-- TABLE: repair_orders (Main transactional table)
-- ============================================================================
CREATE TABLE repair_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  customer_id UUID REFERENCES customers(id),
  vehicle_id UUID REFERENCES vehicles(id),
  service_advisor_id UUID REFERENCES employees(id),
  tm_customer_id INTEGER,
  tm_vehicle_id INTEGER,
  tm_service_advisor_id INTEGER,
  ro_number INTEGER NOT NULL,
  status TEXT NOT NULL,                             -- Controlled: ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE
  status_id INTEGER,

  -- Date fields (TIMESTAMPTZ stored in UTC, DATE in shop-local)
  created_date TIMESTAMPTZ,
  updated_date TIMESTAMPTZ,
  posted_date DATE,                                 -- Shop-local calendar day
  completed_date DATE,
  promised_date TIMESTAMPTZ,
  dropped_off_date TIMESTAMPTZ,
  picked_up_date TIMESTAMPTZ,

  -- POTENTIAL metrics (all jobs, cents)
  potential_total INTEGER NOT NULL DEFAULT 0,
  potential_subtotal INTEGER,
  potential_tax INTEGER,
  potential_discount INTEGER DEFAULT 0,
  potential_job_count INTEGER NOT NULL DEFAULT 0,
  potential_parts_total INTEGER DEFAULT 0,
  potential_labor_total INTEGER DEFAULT 0,
  potential_sublet_total INTEGER DEFAULT 0,
  potential_fees_total INTEGER DEFAULT 0,

  -- AUTHORIZED metrics (authorized jobs only, cents)
  authorized_total INTEGER NOT NULL DEFAULT 0,      -- From /estimate
  authorized_subtotal INTEGER,
  authorized_tax INTEGER,
  authorized_discount INTEGER DEFAULT 0,
  authorized_job_count INTEGER NOT NULL DEFAULT 0,
  authorized_parts_total INTEGER DEFAULT 0,
  authorized_labor_total INTEGER DEFAULT 0,
  authorized_sublet_total INTEGER DEFAULT 0,
  authorized_fees_total INTEGER DEFAULT 0,

  -- PROFITABILITY (from /profit/labor - USE THESE for GP%)
  authorized_revenue INTEGER,                       -- From /profit/labor
  authorized_cost INTEGER,
  authorized_profit INTEGER,
  authorized_gp_percent DECIMAL(5,2),
  authorized_labor_hours DECIMAL(10,2),

  -- Payment
  amount_paid INTEGER DEFAULT 0,
  balance_due INTEGER DEFAULT 0,
  shop_supplies_total INTEGER DEFAULT 0,
  epa_total INTEGER DEFAULT 0,

  -- Metadata
  label TEXT,
  label_id INTEGER,
  customer_concern TEXT,
  tech_notes TEXT,
  recommendation TEXT,
  internal_notes TEXT,
  tm_extra JSONB,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sync_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);
COMMENT ON TABLE repair_orders IS 'Repair orders from TM. Status: ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE. All money in cents.';
COMMENT ON COLUMN repair_orders.posted_date IS 'Shop-local calendar day when RO was posted';
COMMENT ON COLUMN repair_orders.authorized_total IS 'From /estimate - sum of authorized jobs retail totals';
COMMENT ON COLUMN repair_orders.authorized_revenue IS 'From /profit/labor - USE THIS for GP% calculations';

-- ============================================================================
-- TABLE: jobs (CASCADE DELETE from repair_orders)
-- ============================================================================
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_repair_order_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  job_category_id INTEGER,
  job_category_name TEXT,
  canned_job_id INTEGER,

  -- Authorization status
  authorized BOOLEAN NOT NULL DEFAULT FALSE,        -- Controlled: true/false
  authorized_date TIMESTAMPTZ,
  declined BOOLEAN DEFAULT FALSE,
  declined_date TIMESTAMPTZ,
  declined_reason TEXT,

  -- Totals (cents)
  total INTEGER NOT NULL DEFAULT 0,
  subtotal INTEGER,
  discount INTEGER DEFAULT 0,
  tax INTEGER,
  parts_total INTEGER DEFAULT 0,
  parts_cost INTEGER DEFAULT 0,
  labor_total INTEGER DEFAULT 0,
  labor_hours DECIMAL(10,2) DEFAULT 0,
  sublet_total INTEGER DEFAULT 0,
  sublet_cost INTEGER DEFAULT 0,
  fees_total INTEGER DEFAULT 0,
  gross_profit_amount INTEGER,
  gross_profit_percent DECIMAL(5,2),

  sort_order INTEGER,
  tm_extra JSONB,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);
COMMENT ON TABLE jobs IS 'Jobs within repair orders. authorized=true means customer approved. Cascades delete from repair_orders.';
COMMENT ON COLUMN jobs.authorized IS 'Whether customer authorized this job (controlled vocabulary: true/false)';

-- ============================================================================
-- TABLE: job_parts (CASCADE DELETE from jobs and repair_orders)
-- ============================================================================
CREATE TABLE job_parts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  part_number TEXT,
  description TEXT,
  quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
  retail INTEGER NOT NULL DEFAULT 0,                -- cents
  cost INTEGER,                                     -- cents
  core_charge INTEGER,
  total INTEGER NOT NULL DEFAULT 0,                 -- cents
  vendor_id INTEGER,
  vendor_name TEXT,
  manufacturer TEXT,
  ordered BOOLEAN DEFAULT FALSE,
  received BOOLEAN DEFAULT FALSE,
  backordered BOOLEAN DEFAULT FALSE,
  part_type TEXT,
  category TEXT,
  tm_extra JSONB,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE job_parts IS 'Parts within jobs. All money in cents. Cascades delete from jobs and repair_orders.';

-- ============================================================================
-- TABLE: job_labor (CASCADE DELETE from jobs and repair_orders)
-- ============================================================================
CREATE TABLE job_labor (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  labor_type TEXT,
  hours DECIMAL(10,2) NOT NULL DEFAULT 0,
  rate INTEGER NOT NULL DEFAULT 0,                  -- cents/hour
  total INTEGER NOT NULL DEFAULT 0,                 -- cents
  technician_id UUID REFERENCES employees(id),
  tm_technician_id INTEGER,
  technician_name TEXT,
  tech_hourly_cost INTEGER,                         -- cents
  labor_cost INTEGER,                               -- cents (hours * tech_hourly_cost)
  rate_source TEXT,                                 -- Controlled: assigned, shop_avg, default
  skill_level TEXT,
  tm_extra JSONB,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE job_labor IS 'Labor entries within jobs. All money in cents. Cascades delete from jobs and repair_orders.';
COMMENT ON COLUMN job_labor.rate_source IS 'How tech cost was determined: assigned, shop_avg, default';

-- ============================================================================
-- TABLE: job_sublets (CASCADE DELETE from jobs and repair_orders)
-- ============================================================================
CREATE TABLE job_sublets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER,
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  vendor_id INTEGER,
  vendor_name TEXT,
  cost INTEGER,                                     -- cents
  retail INTEGER NOT NULL DEFAULT 0,                -- cents
  invoice_number TEXT,
  po_number TEXT,
  tm_extra JSONB,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE job_sublets IS 'Sublet work within jobs (outsourced to other vendors). All money in cents.';

-- ============================================================================
-- TABLE: job_fees (CASCADE DELETE from jobs and repair_orders)
-- ============================================================================
CREATE TABLE job_fees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  fee_type TEXT,                                    -- Controlled: shop_supplies, environmental, disposal, hazmat, other
  amount INTEGER,
  percentage DECIMAL(5,4),
  cap INTEGER,
  total INTEGER NOT NULL DEFAULT 0,                 -- cents
  taxable BOOLEAN DEFAULT FALSE,
  tm_extra JSONB,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE job_fees IS 'Fees within jobs (shop supplies, EPA, etc). fee_type: shop_supplies, environmental, disposal, hazmat, other';

-- ============================================================================
-- TABLE: ro_snapshots (Point-in-time metrics)
-- ============================================================================
CREATE TABLE ro_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_repair_order_id INTEGER NOT NULL,
  snapshot_date DATE NOT NULL,                      -- Shop-local calendar day
  snapshot_trigger TEXT NOT NULL,                   -- Controlled: posted, completed, manual
  ro_status TEXT NOT NULL,
  ro_number INTEGER NOT NULL,
  customer_name TEXT,
  vehicle_description TEXT,
  advisor_name TEXT,

  -- AUTHORIZED metrics (cents)
  authorized_revenue INTEGER NOT NULL DEFAULT 0,
  authorized_cost INTEGER NOT NULL DEFAULT 0,
  authorized_profit INTEGER NOT NULL DEFAULT 0,
  authorized_gp_percent DECIMAL(5,2),
  authorized_job_count INTEGER NOT NULL DEFAULT 0,

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

  -- POTENTIAL (for comparison)
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,

  -- Validation
  tm_reported_gp_percent DECIMAL(5,2),
  variance_percent DECIMAL(5,2),
  variance_reason TEXT,
  calculation_method TEXT DEFAULT 'TRUE_GP',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, repair_order_id, snapshot_date, snapshot_trigger)
);
COMMENT ON TABLE ro_snapshots IS 'Point-in-time RO metrics captured on posted/complete. Used to build daily_shop_metrics. All money in cents.';
COMMENT ON COLUMN ro_snapshots.snapshot_trigger IS 'What triggered this snapshot: posted, completed, manual';
COMMENT ON COLUMN ro_snapshots.snapshot_date IS 'Shop-local calendar day (from shops.timezone)';

-- ============================================================================
-- TABLE: daily_shop_metrics (Daily aggregates from ro_snapshots)
-- ============================================================================
CREATE TABLE daily_shop_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  metric_date DATE NOT NULL,                        -- Shop-local calendar day

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
  avg_ro_value INTEGER,                             -- cents
  avg_ro_profit INTEGER,                            -- cents
  avg_labor_rate INTEGER,                           -- cents/hour
  gp_per_labor_hour INTEGER,                        -- cents

  -- POTENTIAL metrics
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,
  authorization_rate DECIMAL(5,2),

  -- Source tracking
  calculation_method TEXT DEFAULT 'FROM_RO_SNAPSHOTS',
  source_snapshot_count INTEGER,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, metric_date)
);
COMMENT ON TABLE daily_shop_metrics IS 'Daily aggregated metrics from ro_snapshots. One row per shop per day. All money in cents.';
COMMENT ON COLUMN daily_shop_metrics.metric_date IS 'Shop-local calendar day (from shops.timezone)';
COMMENT ON COLUMN daily_shop_metrics.calculation_method IS 'How metrics were calculated: FROM_RO_SNAPSHOTS';

-- ============================================================================
-- TABLE: tech_daily_metrics (Technician performance)
-- ============================================================================
CREATE TABLE tech_daily_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  technician_id UUID NOT NULL REFERENCES employees(id),
  metric_date DATE NOT NULL,                        -- Shop-local calendar day

  -- Performance
  hours_billed DECIMAL(10,2) NOT NULL DEFAULT 0,
  hourly_rate INTEGER,                              -- Avg cents/hour (retail)
  hourly_cost INTEGER,                              -- Avg cents/hour (cost)

  -- Revenue (cents)
  labor_revenue INTEGER NOT NULL DEFAULT 0,
  labor_cost INTEGER NOT NULL DEFAULT 0,
  labor_profit INTEGER NOT NULL DEFAULT 0,
  labor_gp_percent DECIMAL(5,2),
  gp_per_hour INTEGER,                              -- cents

  -- Volume
  jobs_worked INTEGER DEFAULT 0,
  ros_worked INTEGER DEFAULT 0,

  -- Rate source breakdown
  rate_sources JSONB,                               -- {"assigned": 5, "shop_avg": 2, "default": 1}

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, technician_id, metric_date)
);
COMMENT ON TABLE tech_daily_metrics IS 'Daily technician performance metrics. One row per tech per day. All money in cents.';
COMMENT ON COLUMN tech_daily_metrics.rate_sources IS 'Breakdown of how labor costs were sourced: {"assigned": N, "shop_avg": N, "default": N}';

-- ============================================================================
-- TABLE: sync_cursors (Incremental sync tracking)
-- ============================================================================
CREATE TABLE sync_cursors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  entity_type TEXT NOT NULL,                        -- 'repair_orders', 'employees', etc.
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_tm_updated TIMESTAMPTZ,                      -- Max updatedDate seen from TM
  last_tm_id INTEGER,                               -- Last TM ID processed (for paging)
  cursor_data JSONB,

  UNIQUE(shop_id, entity_type)
);
COMMENT ON TABLE sync_cursors IS 'Tracks sync progress for incremental updates. One row per shop per entity type.';

-- ============================================================================
-- TABLE: sync_log (Audit trail)
-- ============================================================================
CREATE TABLE sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  sync_type TEXT NOT NULL,                          -- 'full_backfill', 'incremental', 'snapshot_rebuild'
  entity_type TEXT,                                 -- 'repair_orders', 'employees', etc.
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,
  status TEXT NOT NULL DEFAULT 'running',           -- 'running', 'completed', 'failed'
  records_fetched INTEGER DEFAULT 0,
  records_created INTEGER DEFAULT 0,
  records_updated INTEGER DEFAULT 0,
  records_skipped INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0,
  errors JSONB,
  metadata JSONB
);
COMMENT ON TABLE sync_log IS 'Audit trail for all sync operations. Retain 30 days via scheduled cleanup.';

-- ============================================================================
-- TABLE: tm_raw_payloads (Debug storage)
-- ============================================================================
CREATE TABLE tm_raw_payloads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  endpoint TEXT NOT NULL,                           -- '/api/repair-order/123/estimate'
  method TEXT NOT NULL DEFAULT 'GET',
  tm_entity_id INTEGER,                             -- RO ID, customer ID, etc.
  request_params JSONB,
  response_payload JSONB NOT NULL,
  response_status INTEGER,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days')
);
COMMENT ON TABLE tm_raw_payloads IS 'Raw TM API responses for debugging. 7-day retention. Auto-delete via scheduled job.';
COMMENT ON COLUMN tm_raw_payloads.expires_at IS 'Records older than this are eligible for deletion';

-- ============================================================================
-- VIEW: customers_analytics (PII-free)
-- ============================================================================
CREATE OR REPLACE VIEW customers_analytics AS
SELECT
  id, shop_id, tm_id, first_name, last_name, company_name,
  customer_type_id, customer_type_name, tax_exempt, ok_for_marketing,
  lead_source, lead_source_id, referral_source,
  tm_created_at, tm_updated_at, created_at, updated_at
FROM customers;
COMMENT ON VIEW customers_analytics IS 'Customer data without PII (email, phone, address). Use for dashboards.';

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================
-- RLS enabled on all 16 warehouse tables
-- Service role bypass policies allow full access for backend sync

ALTER TABLE shops ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE repair_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_parts ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_labor ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_sublets ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_fees ENABLE ROW LEVEL SECURITY;
ALTER TABLE ro_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_shop_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE tech_daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_cursors ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE tm_raw_payloads ENABLE ROW LEVEL SECURITY;

-- Service role bypass (full access for backend)
CREATE POLICY service_role_shops ON shops FOR ALL TO service_role USING (true);
CREATE POLICY service_role_employees ON employees FOR ALL TO service_role USING (true);
CREATE POLICY service_role_customers ON customers FOR ALL TO service_role USING (true);
CREATE POLICY service_role_vehicles ON vehicles FOR ALL TO service_role USING (true);
CREATE POLICY service_role_repair_orders ON repair_orders FOR ALL TO service_role USING (true);
CREATE POLICY service_role_jobs ON jobs FOR ALL TO service_role USING (true);
CREATE POLICY service_role_job_parts ON job_parts FOR ALL TO service_role USING (true);
CREATE POLICY service_role_job_labor ON job_labor FOR ALL TO service_role USING (true);
CREATE POLICY service_role_job_sublets ON job_sublets FOR ALL TO service_role USING (true);
CREATE POLICY service_role_job_fees ON job_fees FOR ALL TO service_role USING (true);
CREATE POLICY service_role_ro_snapshots ON ro_snapshots FOR ALL TO service_role USING (true);
CREATE POLICY service_role_daily_shop_metrics ON daily_shop_metrics FOR ALL TO service_role USING (true);
CREATE POLICY service_role_tech_daily_metrics ON tech_daily_metrics FOR ALL TO service_role USING (true);
CREATE POLICY service_role_sync_cursors ON sync_cursors FOR ALL TO service_role USING (true);
CREATE POLICY service_role_sync_log ON sync_log FOR ALL TO service_role USING (true);
CREATE POLICY service_role_tm_raw_payloads ON tm_raw_payloads FOR ALL TO service_role USING (true);

-- ============================================================================
-- INDEXES (Created in individual migration files)
-- ============================================================================
-- See db/migrations/ for complete index definitions
-- Key indexes:
--   - All tables: idx_*_shop_id for shop isolation
--   - repair_orders: idx_ro_status, idx_ro_posted_date
--   - jobs: idx_jobs_ro_id, idx_jobs_authorized
--   - ro_snapshots: idx_ro_snapshots_date
--   - daily_shop_metrics: idx_daily_metrics_date_range
--   - tech_daily_metrics: idx_tech_metrics_date_range
--   - sync_log: idx_sync_log_status
--   - tm_raw_payloads: idx_raw_payloads_expires
