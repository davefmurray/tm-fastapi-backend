# TM FastAPI Backend - Deployment Log

## Current Production Deployment

| Property | Value |
|----------|-------|
| **Railway URL** | https://tm-fastapi-backend-production.up.railway.app |
| **Project ID** | 94a56b4c-dbf6-43c0-ad0b-fd9beec041a0 |
| **Service ID** | 224e06d0-aff4-4959-87bb-cd175ba76e88 |
| **Environment ID** | 42330ae1-971f-4f75-bba1-b54bda27f92e |
| **Supabase Project** | TM-VID-Magic (oummojcsghoitfhpscnn) |
| **Shop ID** | 6212 (JJ AUTO) |

---

## Environment Variables

The following environment variables are configured on Railway:

| Variable | Value | Description |
|----------|-------|-------------|
| `SUPABASE_URL` | https://oummojcsghoitfhpscnn.supabase.co | Supabase project URL |
| `SUPABASE_KEY` | (set) | Supabase anon key |
| `SUPABASE_TABLE_NAME` | shop_tokens | JWT token storage table |
| `USE_SUPABASE` | true | Enable Supabase auth |
| `TM_BASE_URL` | https://shop.tekmetric.com | Tekmetric API base URL |
| `TM_SHOP_ID` | 6212 | Default shop ID |
| `SYNC_ENABLED` | true | Enable automated sync |
| `RO_SYNC_INTERVAL_MINUTES` | 10 | RO sync frequency |
| `EMPLOYEE_SYNC_HOUR` | 6 | Daily employee sync hour (UTC) |

### Missing (Recommended)
- `SUPABASE_SERVICE_KEY` - Service role key for RLS bypass (currently using anon key with permissive policies)

---

## Automated Sync Schedule

The backend runs automated sync jobs via APScheduler:

| Job | Schedule | Description |
|-----|----------|-------------|
| **Daily Employee Sync** | Daily at 6:00 UTC | Syncs all employees for shop |
| **POSTED RO Sync** | Every 10 minutes | Syncs invoiced repair orders from last 1 day |
| **ACTIVE RO Sync** | Every 10 minutes (offset) | Syncs WIP repair orders from last 7 days |

---

## 2025-11-27: Initial Railway Deployment

### Deployment Details
- **Commit**: ab843fa (feat: Add APScheduler for automated sync jobs)
- **Deploy Time**: ~30 seconds build, instant deploy
- **Status**: SUCCESS

### What Was Deployed
1. FastAPI backend with all 27 routers
2. Warehouse sync service (`/api/sync/*` endpoints)
3. APScheduler for automated sync jobs
4. WebSocket real-time endpoint

### Initial Sync Results
Ran manual sync to verify:

```
GET /api/sync/employees?shop_id=6212
{
  "status": "completed",
  "fetched": 10,
  "created": 9,
  "updated": 0
}

GET /api/sync/repair-orders?shop_id=6212&days_back=7&board=POSTED&limit=10
{
  "status": "completed",
  "fetched": 10,
  "created": 20,
  "jobs_created": 31,
  "fees": 3
}
```

### Supabase Data After Initial Sync

| Table | Row Count |
|-------|-----------|
| repair_orders | 10 |
| jobs | 31 |
| employees | 9 |
| customers | 10 |
| job_fees | 2 |
| sync_log | 6 |

---

## API Endpoints

### Health Check
```
GET https://tm-fastapi-backend-production.up.railway.app/
GET https://tm-fastapi-backend-production.up.railway.app/health
```

### Sync Status
```
GET https://tm-fastapi-backend-production.up.railway.app/api/sync/status
```

### Manual Sync Triggers
```
GET /api/sync/employees?shop_id=6212
GET /api/sync/repair-orders?shop_id=6212&days_back=3&board=POSTED
GET /api/sync/repair-orders?shop_id=6212&days_back=7&board=ACTIVE
GET /api/sync/full-backfill?shop_id=6212&days_back=30
```

### API Documentation
```
https://tm-fastapi-backend-production.up.railway.app/docs
```

---

## Troubleshooting

### Check Scheduler Status
```bash
curl https://tm-fastapi-backend-production.up.railway.app/api/sync/status
```

### View Recent Syncs in Supabase
```sql
SELECT * FROM sync_log ORDER BY started_at DESC LIMIT 10;
```

### Check Sync Cursors
```sql
SELECT * FROM sync_cursors;
```

### Common Issues

1. **500 errors on sync endpoints**: Check deployment logs for traceback
2. **No data syncing**: Verify JWT token in `shop_tokens` table is fresh
3. **RLS errors**: Using anon key requires permissive RLS policies on warehouse tables

---

## Future TODOs

- [ ] Add SUPABASE_SERVICE_KEY for proper RLS bypass
- [ ] Fix parts/labor sync (133 errors in initial sync)
- [ ] Add ro_snapshots generation on status change
- [ ] Build daily_shop_metrics aggregation
- [ ] Connect moneyball-dashboard to warehouse
