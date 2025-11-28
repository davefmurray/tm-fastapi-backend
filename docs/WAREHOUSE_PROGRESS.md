# TM Data Warehouse Progress Log

This document tracks the implementation progress of the multi-shop Tekmetric data warehouse.

## Current Status: SCHEMA COMPLETE ✅

---

## 2025-11-27: Initial Schema Deployment

### Completed
- [x] Generated 15 SQL migration files from Supabase-warehouse-spec.md
- [x] Applied all migrations to Supabase (TM-VID-Magic project)
- [x] Verified 16 warehouse tables created with RLS enabled
- [x] Seeded JJ AUTO (shop_id 6212) in shops table
- [x] Created docs/schema_dump.sql with full DDL reference

### Tables Created (16 total)
| Table | Purpose | RLS | Rows |
|-------|---------|-----|------|
| shops | Root reference table | ✅ | 1 (JJ AUTO) |
| employees | TM employees | ✅ | 0 |
| customers | Customer records (PII) | ✅ | 0 |
| vehicles | Vehicle records | ✅ | 0 |
| repair_orders | Main transactional table | ✅ | 0 |
| jobs | Jobs within ROs | ✅ | 0 |
| job_parts | Parts line items | ✅ | 0 |
| job_labor | Labor line items | ✅ | 0 |
| job_sublets | Sublet line items | ✅ | 0 |
| job_fees | Fee line items | ✅ | 0 |
| ro_snapshots | Point-in-time RO metrics | ✅ | 0 |
| daily_shop_metrics | Daily aggregates | ✅ | 0 |
| tech_daily_metrics | Tech daily performance | ✅ | 0 |
| sync_cursors | Incremental sync tracking | ✅ | 0 |
| sync_log | Sync audit trail | ✅ | 0 |
| tm_raw_payloads | Debug payload storage | ✅ | 0 |

### Views Created
- `customers_analytics` - PII-free customer view for dashboards

### Migration Files
```
db/migrations/
├── 001_shops.sql
├── 002_employees.sql
├── 003_customers.sql
├── 004_vehicles.sql
├── 005_repair_orders.sql
├── 006_jobs.sql
├── 007_job_parts.sql
├── 008_job_labor.sql
├── 009_job_sublets.sql
├── 010_job_fees.sql
├── 011_ro_snapshots.sql
├── 012_daily_shop_metrics.sql
├── 013_tech_daily_metrics.sql
├── 014_sync_tables.sql
└── 015_views_and_rls.sql
```

### Supabase Project
- **Project:** TM-VID-Magic
- **ID:** oummojcsghoitfhpscnn
- **Total Migrations:** 21 (6 existing + 15 new)

---

## Next Steps

### Phase 2: Sync Service (Pending)
- [ ] Implement FastAPI sync service (`tm-fastapi-backend/app/`)
- [ ] Create entity sync modules for each table
- [ ] Implement incremental sync using sync_cursors
- [ ] Add /profit/labor integration for GP calculations
- [ ] Build snapshot creation on RO posted/completed

### Phase 3: Aggregation Pipeline (Pending)
- [ ] Implement ro_snapshots generation
- [ ] Build daily_shop_metrics aggregation
- [ ] Build tech_daily_metrics aggregation
- [ ] Add variance validation (our GP vs TM GP)

### Phase 4: Dashboard Integration (Pending)
- [ ] Expose metrics via FastAPI endpoints
- [ ] Connect moneyball-dashboard to warehouse
- [ ] Add real-time WIP tracking

---

## Key Design Decisions

### Money Storage
All monetary values stored as INTEGER in **cents** (not dollars):
- `17950` = $179.50
- `450` = $4.50

### authorized_total vs authorized_revenue
- `authorized_total`: Sum of authorized jobs from /estimate (retail prices)
- `authorized_revenue`: From /profit/labor endpoint (USE THIS for GP%)

### Date/Time Storage
- **TIMESTAMPTZ**: UTC timestamps (created_date, updated_date, promised_date)
- **DATE**: Shop-local calendar day (posted_date, completed_date, metric_date)

### Cascade Deletes
```
repair_orders → jobs → job_parts, job_labor, job_sublets, job_fees
repair_orders → ro_snapshots
```

### Row Level Security
- All 16 tables have RLS enabled
- Service role has full access via bypass policies
- Shop isolation policies ready (commented, enable when needed)

---

## Technical Notes

### Controlled Vocabularies
- **RO Status:** ESTIMATE, WORKINPROGRESS, POSTED, COMPLETE
- **Employee Role:** 1=Admin, 2=Advisor, 3=Tech, 4=Owner
- **Employee Status:** ACTIVE, INACTIVE
- **Snapshot Trigger:** posted, completed, manual
- **Rate Source:** assigned, shop_avg, default
- **Fee Type:** shop_supplies, environmental, disposal, hazmat, other

### Sync Strategy
1. Full backfill: Initial data load
2. Incremental: Use updatedDate cursor for daily syncs
3. Snapshot: Capture on status change (posted/completed)

### Data Flow
```
TM API → sync service → repair_orders + jobs + line items
                     ↓
              ro_snapshots (on posted/completed)
                     ↓
              daily_shop_metrics (aggregated)
              tech_daily_metrics (aggregated)
```
