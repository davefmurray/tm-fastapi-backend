# TM Data Warehouse Progress Log

This document tracks the implementation progress of the multi-shop Tekmetric data warehouse.

## Current Status: SYNC SERVICE IMPLEMENTED ✅

---

## 2025-11-27: Sync Service Implementation

### Completed
- [x] Created `app/sync/` module structure
- [x] Implemented `warehouse_client.py` - Supabase client with service_role key for RLS bypass
- [x] Implemented `sync_base.py` - Base class with sync_cursors and sync_log management
- [x] Implemented `sync_employees.py` - Employee sync from TM
- [x] Implemented `sync_customers.py` - Customer sync with on-demand resolution
- [x] Implemented `sync_vehicles.py` - Vehicle sync with on-demand resolution
- [x] Implemented `sync_repair_orders.py` - Full RO sync with jobs and line items
- [x] Created `app/routers/sync.py` - FastAPI endpoints for sync operations
- [x] Integrated sync router into main.py

### Sync Module Architecture
```
app/sync/
├── __init__.py              # Module exports
├── warehouse_client.py      # Supabase warehouse operations (~830 lines)
├── sync_base.py             # Base class for sync operations
├── sync_employees.py        # Employee sync
├── sync_customers.py        # Customer sync (paginated + on-demand)
├── sync_vehicles.py         # Vehicle sync (paginated + on-demand)
└── sync_repair_orders.py    # RO sync with jobs/parts/labor/sublets/fees
```

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sync/employees` | GET | Sync all employees for shop |
| `/api/sync/customers` | GET | Sync all customers (paginated) |
| `/api/sync/vehicles` | GET | Sync all vehicles (paginated) |
| `/api/sync/repair-orders` | GET | Sync ROs by date range and board |
| `/api/sync/repair-orders/{ro_id}` | GET | Sync single RO by ID |
| `/api/sync/full-backfill` | GET | Run employees + RO sync |

### Key Parameters
- `shop_id`: TM shop ID (default: 6212)
- `days_back`: Days of history to sync (default: 3)
- `board`: ACTIVE, POSTED, or ALL
- `limit`: Max ROs to sync (for testing)
- `store_raw`: Store API payloads for debugging

### Sync Flow
```
1. /sync/employees          → employees table
2. /sync/repair-orders
   ├── Discover ROs via /job-board-group-by
   ├── For each RO:
   │   ├── Resolve customer (sync if missing)
   │   ├── Resolve vehicle (sync if missing)
   │   ├── Resolve advisor
   │   ├── Fetch /estimate for full data
   │   ├── Fetch /profit/labor for GP%
   │   ├── Upsert RO with profit data
   │   └── Sync jobs → parts, labor, sublets, fees
   └── Update sync_cursor
```

### Environment Setup Required
```bash
# Add to .env
SUPABASE_SERVICE_KEY=your_service_role_key_here  # For RLS bypass
```

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

### Phase 2: Sync Service ✅ COMPLETE
- [x] Implement FastAPI sync service (`tm-fastapi-backend/app/sync/`)
- [x] Create entity sync modules (employees, customers, vehicles, repair_orders)
- [x] Implement incremental sync using sync_cursors
- [x] Add /profit/labor integration for GP calculations
- [ ] Build snapshot creation on RO posted/completed (Phase 3)

### Phase 2.5: Initial Data Load (Ready to Run)
```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with Supabase service_role key

# 2. Start server
cd tm-fastapi-backend
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Run initial sync (recommended order)
curl "http://localhost:8000/api/sync/employees?shop_id=6212"
curl "http://localhost:8000/api/sync/repair-orders?shop_id=6212&days_back=3&board=POSTED"

# 4. Verify in Supabase
# - Check repair_orders, jobs, job_parts, job_labor rows
# - Verify authorized_revenue and gp_percent look reasonable
```

### Phase 3: Aggregation Pipeline (Pending)
- [ ] Implement ro_snapshots generation on status change
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
