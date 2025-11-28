-- Migration: 015_views_and_rls
-- Description: Create analytics views (no PII) and RLS policies
-- Date: 2025-11-27

-- ============================================================================
-- Analytics Views (exclude PII)
-- ============================================================================

-- customers_analytics: Omits email, phone, address
CREATE OR REPLACE VIEW customers_analytics AS
SELECT
  id, shop_id, tm_id, first_name, last_name, company_name,
  customer_type_id, customer_type_name, tax_exempt, ok_for_marketing,
  lead_source, lead_source_id, referral_source,
  tm_created_at, tm_updated_at, created_at, updated_at
FROM customers;

COMMENT ON VIEW customers_analytics IS 'Customer data without PII (email, phone, address). Use for dashboards.';

-- ============================================================================
-- Row-Level Security (RLS)
-- ============================================================================

-- Enable RLS on all warehouse tables
-- Note: RLS policies are created but not enforced until FORCE is set
-- For now, we enable RLS but allow all access for service role

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

-- Service role bypass policies (allows full access for backend service)
-- These policies allow the service_role to bypass RLS

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

-- Anon/authenticated user policies (shop-scoped access)
-- These would be used if we add user-facing features with shop isolation
-- For now, commented out - enable when needed

/*
CREATE POLICY shop_isolation_repair_orders ON repair_orders
  FOR ALL
  USING (shop_id IN (SELECT shop_id FROM user_shop_access WHERE user_id = auth.uid()));
*/

COMMENT ON POLICY service_role_repair_orders ON repair_orders IS 'Allows service_role full access for backend sync operations';
