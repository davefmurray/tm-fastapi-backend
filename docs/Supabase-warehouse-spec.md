# Supabase Data Warehouse Specification

**Version:** 1.1
**Date:** November 27, 2025
**Status:** APPROVED FOR IMPLEMENTATION

---

## 1. Design Principles

### 1.1 Full Data Capture
**Rule:** If TM returns a field, store it. If TM doesn't return it, store NULL. If TM sometimes returns it, make the column nullable.

This is a warehouse, not an operational database. We capture everything upstream provides for future analysis, even fields we don't use today.

### 1.2 Multi-Shop from Day One
Every table has `shop_id` as part of its identity. Adding new shops requires zero schema changes.

### 1.3 Internal Primary Keys
All major tables use internal `UUID` or `BIGSERIAL` primary keys. TM IDs are stored as `tm_id` with a `UNIQUE(shop_id, tm_id)` constraint. This provides:
- Flexibility if TM ever changes ID schemes
- Ability to ingest non-TM data sources later
- Idempotent upserts via the unique constraint

### 1.4 Snapshot Data Flow
```
line items (parts/labor/fees/sublets)
    ↓
jobs (with authorized flag)
    ↓
repair_orders (potential_* and authorized_* rollups)
    ↓
ro_snapshots (computed on RO state change: posted/complete)
    ↓
daily_shop_metrics (aggregated FROM ro_snapshots)
```

This avoids double-calculation and makes debugging straightforward.

### 1.5 Money Fields (Cents as INTEGER)
All monetary values are stored as `INTEGER` in **cents** (not dollars). This matches TM's API format and avoids floating-point precision issues.

Examples:
- `$179.50` stored as `17950`
- `$4.50` stored as `450`
- `$200/hr` stored as `20000`

**Future Scaling Note:** For very large multi-shop or multi-year data volumes, these fields may be migrated to `BIGINT`. This is a future scaling concern and not required now.

### 1.6 Controlled Vocabularies
Status and type fields are stored as `TEXT` for flexibility, but the following values are expected. Dashboards and queries should use these exact values for consistency:

| Field | Expected Values |
|-------|-----------------|
| `repair_orders.status` | `ESTIMATE`, `WORKINPROGRESS`, `POSTED`, `COMPLETE` |
| `ro_snapshots.snapshot_trigger` | `posted`, `completed`, `manual` |
| `job_fees.fee_type` | `shop_supplies`, `environmental`, `disposal`, `hazmat`, `other` |
| `employees.role` | `1` (Admin), `2` (Advisor), `3` (Tech), `4` (Owner) |
| `employees.role_name` | `Admin`, `Service Advisor`, `Technician`, `Owner` |
| `employees.status` | `ACTIVE`, `INACTIVE` |
| `jobs.authorized` | `true`, `false` |

These are controlled vocabularies even though stored as TEXT/INTEGER.

### 1.7 Date and Time Semantics
- **TIMESTAMPTZ fields** are stored in **UTC**. Examples: `created_at`, `updated_at`, `authorized_date`, `tm_updated_at`
- **DATE fields** are interpreted in the **shop's local timezone** (from `shops.timezone`). Examples: `posted_date`, `metric_date`, `snapshot_date`

Daily metrics and RO posted dates must reflect the shop-local calendar day, not UTC. When converting timestamps to dates for aggregation, always apply the shop's timezone first.

### 1.8 Foreign Key Delete Behavior
- **TM is the system of record.** We do not perform application-initiated hard deletes of customers, vehicles, or employees. These tables are long-lived reference data.
- **Cascade deletes** from `repair_orders` to `jobs` and line-item tables (`job_parts`, `job_labor`, `job_sublets`, `job_fees`) are correct. Removing an RO removes its children.
- If TM deletes an entity, our sync process will handle it (either soft-flag or remove based on policy).

### 1.9 Metric Contracts as Canonical Definitions
**`METRIC_CONTRACTS.md` defines the canonical formulas** for:
- Authorized revenue
- Authorized profit
- GP percent
- Potential revenue
- Pending revenue

Any dashboard, report, or query must use those formulas directly or derive from fields computed using those formulas. This ensures there is **only one definition of GP%** and related metrics across the entire system.

Reference: `docs/METRIC_CONTRACTS.md`

---

## 2. Row-Level Security (RLS)

All tables enforce RLS so users can only access rows where `shop_id` is in their allowed list.

```sql
-- Example RLS policy (applied to all tables)
ALTER TABLE repair_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY shop_isolation ON repair_orders
  FOR ALL
  USING (shop_id IN (SELECT shop_id FROM user_shop_access WHERE user_id = auth.uid()));
```

### PII Considerations
Full PII (email, phone, address) is stored in `customers` table. For analytics dashboards that don't need PII, create views:

```sql
CREATE VIEW customers_analytics AS
SELECT
  id, shop_id, tm_id, first_name, last_name,
  -- Omit: email, phone_*, address_*
  tax_exempt, ok_for_marketing, created_at
FROM customers;
```

---

## 3. Schema Definition

### 3.1 Reference Tables

#### `shops`
```sql
CREATE TABLE shops (
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

CREATE INDEX idx_shops_tm_id ON shops(tm_id);
```

---

#### `employees`
```sql
CREATE TABLE employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,

  -- Core fields
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  role INTEGER,                        -- 1=Admin, 2=Advisor, 3=Tech, 4=Owner
  role_name TEXT,                      -- Human readable
  hourly_rate INTEGER,                 -- cents (for technicians)
  status TEXT,                         -- ACTIVE, INACTIVE

  -- Store all TM fields
  username TEXT,
  phone TEXT,
  hire_date DATE,
  termination_date DATE,
  commission_rate DECIMAL(5,4),
  can_clock_in BOOLEAN,
  can_sell BOOLEAN,
  can_tech BOOLEAN,

  -- TM overflow (any fields we don't have columns for)
  tm_extra JSONB,

  -- Sync tracking
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

CREATE INDEX idx_employees_shop_role ON employees(shop_id, role);
CREATE INDEX idx_employees_shop_status ON employees(shop_id, status);
```

---

#### `customers`
```sql
CREATE TABLE customers (
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

CREATE INDEX idx_customers_shop ON customers(shop_id);
CREATE INDEX idx_customers_name ON customers(shop_id, last_name, first_name);
```

---

#### `vehicles`
```sql
CREATE TABLE vehicles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  customer_id UUID REFERENCES customers(id),
  tm_customer_id INTEGER,              -- Denormalized for sync

  -- Vehicle info
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

  -- Identifiers
  vin TEXT,
  license_plate TEXT,
  license_state TEXT,
  unit_number TEXT,
  fleet_number TEXT,

  -- Appearance
  color TEXT,
  interior_color TEXT,

  -- Odometer
  odometer INTEGER,
  odometer_unit TEXT,                  -- miles, km
  odometer_date DATE,

  -- Custom
  custom_description TEXT,
  notes TEXT,

  -- TM references
  base_vehicle_id INTEGER,

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

CREATE INDEX idx_vehicles_shop ON vehicles(shop_id);
CREATE INDEX idx_vehicles_customer ON vehicles(shop_id, customer_id);
CREATE INDEX idx_vehicles_vin ON vehicles(shop_id, vin) WHERE vin IS NOT NULL;
```

---

### 3.2 Transactional Tables

#### `repair_orders`
```sql
CREATE TABLE repair_orders (
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

  -- Status
  status TEXT NOT NULL,                -- ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE
  status_id INTEGER,

  -- Dates (all from TM)
  created_date TIMESTAMPTZ,
  updated_date TIMESTAMPTZ,
  posted_date DATE,                    -- KEY for reports
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
CREATE INDEX idx_ro_shop_posted ON repair_orders(shop_id, posted_date);
CREATE INDEX idx_ro_shop_status ON repair_orders(shop_id, status);
CREATE INDEX idx_ro_shop_created ON repair_orders(shop_id, created_date);
CREATE INDEX idx_ro_shop_updated ON repair_orders(shop_id, updated_date);
CREATE INDEX idx_ro_shop_advisor ON repair_orders(shop_id, service_advisor_id);
```

---

#### `jobs`
```sql
CREATE TABLE jobs (
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

  -- CRITICAL: Authorization status
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

CREATE INDEX idx_jobs_ro ON jobs(shop_id, repair_order_id);
CREATE INDEX idx_jobs_authorized ON jobs(shop_id, authorized, authorized_date);
```

---

#### `job_parts`
```sql
CREATE TABLE job_parts (
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
CREATE UNIQUE INDEX idx_job_parts_unique ON job_parts(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX idx_job_parts_ro ON job_parts(shop_id, repair_order_id);
CREATE INDEX idx_job_parts_job ON job_parts(shop_id, job_id);
```

---

#### `job_labor`
```sql
CREATE TABLE job_labor (
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

CREATE UNIQUE INDEX idx_job_labor_unique ON job_labor(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX idx_job_labor_ro ON job_labor(shop_id, repair_order_id);
CREATE INDEX idx_job_labor_job ON job_labor(shop_id, job_id);
CREATE INDEX idx_job_labor_tech ON job_labor(shop_id, technician_id);
```

---

#### `job_sublets`
```sql
CREATE TABLE job_sublets (
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

CREATE UNIQUE INDEX idx_job_sublets_unique ON job_sublets(shop_id, tm_id) WHERE tm_id IS NOT NULL;
CREATE INDEX idx_job_sublets_ro ON job_sublets(shop_id, repair_order_id);
```

---

#### `job_fees`
```sql
CREATE TABLE job_fees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_job_id INTEGER NOT NULL,
  tm_repair_order_id INTEGER NOT NULL,

  -- Fee info (TM has no fee ID, use composite key)
  name TEXT NOT NULL,
  fee_type TEXT,                       -- 'shop_supplies', 'environmental', 'disposal', 'hazmat', 'other'

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
CREATE UNIQUE INDEX idx_job_fees_unique ON job_fees(shop_id, tm_job_id, name);
CREATE INDEX idx_job_fees_ro ON job_fees(shop_id, repair_order_id);
```

---

### 3.3 Snapshot Tables

#### `ro_snapshots`
Computed once per RO state change (posted, complete). Source of truth for daily aggregation.

```sql
CREATE TABLE ro_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  repair_order_id UUID NOT NULL REFERENCES repair_orders(id) ON DELETE CASCADE,
  tm_repair_order_id INTEGER NOT NULL,

  -- Snapshot identity
  snapshot_date DATE NOT NULL,         -- posted_date or completed_date
  snapshot_trigger TEXT NOT NULL,      -- 'posted', 'completed', 'manual'
  ro_status TEXT NOT NULL,

  -- RO summary
  ro_number INTEGER NOT NULL,
  customer_name TEXT,
  vehicle_description TEXT,
  advisor_name TEXT,

  -- AUTHORIZED metrics (cents) - what we bill
  authorized_revenue INTEGER NOT NULL DEFAULT 0,
  authorized_cost INTEGER NOT NULL DEFAULT 0,
  authorized_profit INTEGER NOT NULL DEFAULT 0,
  authorized_gp_percent DECIMAL(5,2),
  authorized_job_count INTEGER NOT NULL DEFAULT 0,

  -- Category breakdown (authorized only, cents)
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

  -- POTENTIAL metrics (for comparison)
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,

  -- Validation
  tm_reported_gp_percent DECIMAL(5,2), -- From /profit/labor for comparison
  variance_percent DECIMAL(5,2),       -- Our calc vs TM
  variance_reason TEXT,

  -- Calculation metadata
  calculation_method TEXT DEFAULT 'TRUE_GP',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, repair_order_id, snapshot_date, snapshot_trigger)
);

CREATE INDEX idx_ro_snapshots_date ON ro_snapshots(shop_id, snapshot_date);
CREATE INDEX idx_ro_snapshots_ro ON ro_snapshots(shop_id, repair_order_id);
```

---

#### `daily_shop_metrics`
Aggregated FROM `ro_snapshots`, not recalculated from line items.

```sql
CREATE TABLE daily_shop_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  metric_date DATE NOT NULL,

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
  avg_ro_value INTEGER,                -- cents
  avg_ro_profit INTEGER,               -- cents
  avg_labor_rate INTEGER,              -- cents/hour
  gp_per_labor_hour INTEGER,           -- cents

  -- POTENTIAL metrics
  potential_revenue INTEGER DEFAULT 0,
  potential_job_count INTEGER DEFAULT 0,
  authorization_rate DECIMAL(5,2),     -- authorized/potential * 100

  -- Source tracking
  calculation_method TEXT DEFAULT 'FROM_RO_SNAPSHOTS',
  source_snapshot_count INTEGER,       -- How many ro_snapshots aggregated

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, metric_date)
);

CREATE INDEX idx_daily_metrics_date ON daily_shop_metrics(shop_id, metric_date);
```

---

#### `tech_daily_metrics`
Technician performance aggregated from `job_labor`.

```sql
CREATE TABLE tech_daily_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  technician_id UUID NOT NULL REFERENCES employees(id),
  metric_date DATE NOT NULL,

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

CREATE INDEX idx_tech_metrics_date ON tech_daily_metrics(shop_id, metric_date);
CREATE INDEX idx_tech_metrics_tech ON tech_daily_metrics(shop_id, technician_id);
```

---

### 3.4 Sync Management Tables

#### `sync_cursors`
Track where we left off for incremental syncs.

```sql
CREATE TABLE sync_cursors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  entity_type TEXT NOT NULL,           -- 'repair_orders', 'employees', etc.

  -- Cursor state
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_tm_updated TIMESTAMPTZ,         -- Max updatedDate seen from TM
  last_tm_id INTEGER,                  -- Last TM ID processed (for paging)

  -- Additional state
  cursor_data JSONB,

  UNIQUE(shop_id, entity_type)
);
```

---

#### `sync_log`
Audit trail for sync operations.

```sql
CREATE TABLE sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),

  -- Sync details
  sync_type TEXT NOT NULL,             -- 'full_backfill', 'incremental', 'snapshot_rebuild'
  entity_type TEXT,                    -- 'repair_orders', 'employees', etc.

  -- Timing
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,

  -- Status
  status TEXT NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed'

  -- Counts
  records_fetched INTEGER DEFAULT 0,
  records_created INTEGER DEFAULT 0,
  records_updated INTEGER DEFAULT 0,
  records_skipped INTEGER DEFAULT 0,

  -- Errors
  error_count INTEGER DEFAULT 0,
  errors JSONB,                        -- Array of error details

  -- Metadata
  metadata JSONB
);

CREATE INDEX idx_sync_log_shop ON sync_log(shop_id, started_at DESC);

-- Retention: Keep 30 days
-- (implement via scheduled job or Supabase function)
```

---

#### `tm_raw_payloads` (Optional Staging)
Store raw TM API responses for debugging and replay.

```sql
CREATE TABLE tm_raw_payloads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),

  -- Source
  endpoint TEXT NOT NULL,              -- '/api/repair-order/123/estimate'
  method TEXT NOT NULL DEFAULT 'GET',
  tm_entity_id INTEGER,                -- RO ID, customer ID, etc.

  -- Payload
  request_params JSONB,
  response_payload JSONB NOT NULL,
  response_status INTEGER,

  -- Timing
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Retention marker
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days')
);

CREATE INDEX idx_raw_payloads_shop ON tm_raw_payloads(shop_id, fetched_at DESC);
CREATE INDEX idx_raw_payloads_expires ON tm_raw_payloads(expires_at);

-- Retention: Auto-delete expired rows via scheduled job
```

**Decision:** Include `tm_raw_payloads` for debugging during initial development. Can disable/drop after system is stable. 7-day retention window keeps DB size manageable.

---

## 4. Data Flow & Sync Strategy

### 4.1 Initial Backfill

```
Phase 1: Reference Data
├── Create shop record (manual)
├── Sync employees from /api/shop/{shopId}/employees-lite
└── ~10 seconds

Phase 2: Historical ROs (batch)
├── For each board [COMPLETE, POSTED, ACTIVE]:
│   ├── Fetch RO list from /api/shop/{shopId}/job-board-group-by
│   ├── For each RO (10-20 concurrent):
│   │   ├── GET /api/repair-order/{roId}/estimate
│   │   │   ├── Upsert customer
│   │   │   ├── Upsert vehicle
│   │   │   ├── Upsert repair_order
│   │   │   ├── Upsert jobs
│   │   │   └── Upsert parts/labor/sublets/fees
│   │   ├── GET /api/repair-order/{roId}/profit/labor
│   │   │   └── Update repair_order with authorized_* profit fields
│   │   └── Update sync cursor
└── ~5-10 minutes for 500 ROs

Phase 3: Build Snapshots
├── For each RO with posted_date:
│   └── Create ro_snapshot
├── For each unique posted_date:
│   └── Aggregate daily_shop_metrics FROM ro_snapshots
└── ~1-2 minutes
```

### 4.2 Incremental Sync (Every 5 Minutes)

```python
async def sync_incremental(shop_id):
    # 1. Get cursor
    cursor = await get_sync_cursor(shop_id, 'repair_orders')

    # 2. Find changed ROs
    job_board = await fetch_all_boards(shop_id)
    changed = [ro for ro in job_board
               if ro.updated_date > cursor.last_tm_updated]

    # 3. Sync each changed RO
    for ro in changed:
        await sync_single_ro(shop_id, ro.id)

    # 4. Update cursor
    if changed:
        max_updated = max(ro.updated_date for ro in changed)
        await update_sync_cursor(shop_id, 'repair_orders', max_updated)
```

### 4.3 Snapshot Triggers

```
ro_snapshots created when:
├── RO status changes to POSTED (posted_date set)
├── RO status changes to COMPLETE (completed_date set)
└── Manual rebuild requested

daily_shop_metrics updated when:
├── Any ro_snapshot for that date is created/updated
└── Nightly rebuild job (ensure consistency)
```

### 4.4 Avoiding Duplicates

1. **UNIQUE constraints** on (shop_id, tm_id) for all entity tables
2. **Upserts only:** `INSERT ... ON CONFLICT (shop_id, tm_id) DO UPDATE`
3. **sync_hash:** MD5 of critical fields, skip update if unchanged
4. **Idempotent:** Same sync can run multiple times safely

---

## 5. Dashboard Query Migration

### 5.1 Current (Live TM Calls)

| Endpoint | Calls/Load | Latency |
|----------|------------|---------|
| /api/reports/profit-details | 1 | 2-5s |
| /api/analytics/tech-performance | 1 | 1-2s |
| /api/trends/daily | 1 | 1-2s |
| /api/dashboard/live | 1 | 2-3s |
| **Total** | **4+** | **6-12s** |

### 5.2 Future (Supabase Queries)

| View | Supabase Query | Latency |
|------|----------------|---------|
| KPI Cards | `SELECT * FROM daily_shop_metrics WHERE date BETWEEN...` | <50ms |
| Tech Perf | `SELECT * FROM tech_daily_metrics WHERE date BETWEEN...` | <50ms |
| Trend Chart | `SELECT metric_date, authorized_revenue, authorized_profit FROM daily_shop_metrics` | <50ms |
| RO Drill-down | `SELECT * FROM repair_orders JOIN jobs WHERE posted_date = ?` | <100ms |
| **Total** | | **<200ms** |

### 5.3 Metric Contract Alignment

All queries follow `METRIC_CONTRACTS.md`:

```sql
-- AUTHORIZED (committed sales, GP)
SELECT
  SUM(authorized_revenue) as revenue,
  SUM(authorized_profit) as profit,
  SUM(authorized_profit)::float / NULLIF(SUM(authorized_revenue), 0) * 100 as gp_pct
FROM daily_shop_metrics
WHERE shop_id = $1 AND metric_date BETWEEN $2 AND $3;

-- POTENTIAL (full estimate value)
SELECT SUM(potential_revenue) as potential
FROM daily_shop_metrics
WHERE shop_id = $1 AND metric_date BETWEEN $2 AND $3;

-- PENDING (derived)
SELECT SUM(potential_revenue - authorized_revenue) as pending
FROM daily_shop_metrics
WHERE shop_id = $1 AND metric_date BETWEEN $2 AND $3;
```

---

## 6. Background Jobs

| Job | Schedule | Duration | Description |
|-----|----------|----------|-------------|
| `sync_incremental` | Every 5 min | ~30s | Sync changed ROs |
| `rebuild_daily_snapshots` | 6:00 PM ET | ~2 min | Recalculate today's metrics |
| `sync_employees` | Daily 6 AM | ~10s | Refresh tech rates |
| `reconcile_full` | Sunday 2 AM | ~10 min | Full data validation |
| `cleanup_raw_payloads` | Daily 3 AM | ~5s | Delete expired raw payloads |
| `cleanup_sync_logs` | Daily 3 AM | ~5s | Delete logs > 30 days |

---

## 7. Validation & Smoke Tests

### Post-Implementation Validation

```sql
-- 1. Count check: ROs in Supabase vs TM job-board
SELECT COUNT(*) FROM repair_orders WHERE shop_id = ?;
-- Compare to: job-board-group-by total

-- 2. Revenue check: Sum matches TM
SELECT SUM(authorized_revenue) FROM repair_orders
WHERE shop_id = ? AND posted_date BETWEEN ? AND ?;
-- Compare to: profit-details report

-- 3. GP check: Our calculation vs /profit/labor
SELECT
  ro.ro_number,
  ro.authorized_profit as our_profit,
  ro.authorized_gp_percent as our_gp,
  -- Compare to audit results
FROM repair_orders ro
WHERE shop_id = ? AND posted_date = '2025-11-26';
```

### Smoke Test Script (Conceptual)

```python
async def smoke_test_week(shop_id, start_date, end_date):
    """
    Compare Supabase calculations to audit endpoint results.
    """
    # Get from Supabase
    sb_metrics = await supabase.query("""
        SELECT metric_date, authorized_revenue, authorized_profit, authorized_gp_percent
        FROM daily_shop_metrics
        WHERE shop_id = ? AND metric_date BETWEEN ? AND ?
    """, shop_id, start_date, end_date)

    # Get from audit endpoint
    for date in date_range(start_date, end_date):
        audit = await api.get(f"/api/audit/today?days_back={days_ago(date)}")

        sb = sb_metrics[date]
        assert abs(sb.authorized_revenue - audit.totals.authorized.revenue) < 100  # $1 tolerance
        assert abs(sb.authorized_profit - audit.totals.authorized.profit) < 100
        assert abs(sb.authorized_gp_percent - audit.totals.authorized.gp_percent) < 0.5

    print("Smoke test passed!")
```

---

## 8. Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Retention policy | 2 years detailed, then archive to cold storage |
| Multi-shop rollups | Not needed now, can add views later |
| Real-time WIP | Keep hitting TM for live board (5-min delay acceptable) |
| Customer PII | Store full PII, create analytics views that omit it |
| Soft deletes | No soft deletes for now; TM is source of truth |
| Raw payload storage | Yes, 7-day retention for debugging |

---

## 9. Implementation Order (After Approval)

1. **SQL Migrations** - Create all tables with indexes and constraints
2. **RLS Policies** - Enable row-level security
3. **Sync Service** - `sync_repair_orders(shop_id)` using cursor logic
4. **Snapshot Builder** - Create ro_snapshots and daily_shop_metrics
5. **Smoke Test** - Validate against audit endpoint for Nov 26-27
6. **Dashboard Migration** - Switch one view at a time to Supabase

---

**STATUS: APPROVED FOR IMPLEMENTATION**

Spec approved. Ready for implementation.
