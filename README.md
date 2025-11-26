# TM FastAPI Backend

FastAPI proxy backend for Tekmetric API with custom dashboard logic and accurate metric calculations.

**Status:** Phase 1-2 Complete - 84 Endpoints Implemented
**Coverage:** ~50% of documented TM APIs

---

## Features

- **Authorization Management** - Submit authorizations, view history
- **Custom Dashboard** - Accurate metrics calculated from raw data (not TM aggregates)
- **Payment Processing** - Create payments, void payments, list payment types
- **Customer/Vehicle CRUD** - Create and search customers/vehicles
- **RO Operations** - Query ROs, get estimates, share estimates

---

## Quick Start

### Local Development

1. **Clone repository:**
```bash
git clone https://github.com/davefmurray/tm-fastapi-backend.git
cd tm-fastapi-backend
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your TM_AUTH_TOKEN
```

4. **Run server:**
```bash
uvicorn main:app --reload
```

5. **Visit API docs:**
```
http://localhost:8000/docs
```

---

## Railway Deployment

### Option 1: Deploy via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Set environment variables
railway variables set TM_AUTH_TOKEN=your_jwt_token
railway variables set TM_SHOP_ID=6212

# Deploy
railway up
```

### Option 2: Deploy via GitHub

1. Push this repo to GitHub
2. Go to [Railway](https://railway.app)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repo
5. Add environment variables:
   - `TM_AUTH_TOKEN` - Your Tekmetric JWT token
   - `TM_SHOP_ID` - Your shop ID (e.g., 6212)
6. Deploy!

Railway will auto-detect FastAPI and deploy with the correct start command.

---

## Environment Variables

### Option A: Supabase (Recommended - Auto-Refreshing Tokens)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SUPABASE_URL` | Yes | Your Supabase project URL | `https://xyz.supabase.co` |
| `SUPABASE_KEY` | Yes | Supabase anon key | `eyJhbGc...` |
| `SUPABASE_TABLE_NAME` | No | Table storing JWT tokens | `jwt_tokens` (default) |
| `USE_SUPABASE` | No | Enable Supabase token fetching | `true` (default) |
| `TM_BASE_URL` | No | TM base URL | `https://shop.tekmetric.com` |
| `PORT` | No | Server port (Railway sets this) | `8000` |

**How it works:**
- Chrome extension captures JWT tokens from Tekmetric
- Extension syncs tokens to Supabase in real-time
- FastAPI backend pulls latest token from Supabase
- Tokens auto-refresh (no manual updates needed!)

### Option B: Manual Tokens (Fallback)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TM_AUTH_TOKEN` | Yes | Tekmetric JWT token | `eyJhbGc...` |
| `TM_SHOP_ID` | Yes | Your Tekmetric shop ID | `6212` |
| `TM_BASE_URL` | No | TM base URL | `https://shop.tekmetric.com` |
| `USE_SUPABASE` | No | Disable Supabase | `false` |

**Note:** Tokens expire! You'll need to update `TM_AUTH_TOKEN` manually when it expires.

---

## API Endpoints (84 Total)

### Authorization (3)
- POST `/api/auth/authorize/{nonce}` - Submit authorization
- GET `/api/auth/authorizations/{ro_id}` - Auth history
- PATCH `/api/auth/job/{job_id}/remove-auth` - Remove auth status

### Dashboard (3)
- GET `/api/dashboard/summary` - Metrics summary
- GET `/api/dashboard/breakdown` - Breakdown by status
- GET `/api/dashboard/accurate-today` - Accurate calculations

### Payments (4)
- GET `/api/payments/types` - Payment types
- POST `/api/payments/{ro_id}` - Create payment
- GET `/api/payments/{ro_id}` - List payments
- PUT `/api/payments/{payment_id}/void` - Void payment

### Customers (7)
- POST `/api/customers` - Create customer
- PUT `/api/customers/{customer_id}` - Update customer
- GET `/api/customers/search` - Search customers
- GET `/api/customers/{customer_id}` - Get customer
- POST `/api/customers/vehicles` - Create vehicle
- PUT `/api/customers/vehicles/{vehicle_id}` - Update vehicle
- GET `/api/customers/{customer_id}/vehicles` - List vehicles

### Repair Orders (18)
- GET `/api/ro/list` - List ROs
- GET `/api/ro/{ro_id}` - RO details
- GET `/api/ro/{ro_id}/estimate` - Estimate
- GET `/api/ro/{ro_id}/activity` - Activity feed
- GET `/api/ro/{ro_id}/job-history` - Job history
- GET `/api/ro/{ro_id}/inspection-history` - Inspection history
- GET `/api/ro/{ro_id}/appointments` - Appointments
- GET `/api/ro/{ro_id}/purchase-orders` - Purchase orders
- GET `/api/ro/{ro_id}/transparency-settings` - Transparency settings
- PUT `/api/ro/{ro_id}/transparency-settings` - Update transparency
- GET `/api/ro/public/estimate/{nonce}` - Public estimate
- GET `/api/ro/public/inspection/{nonce}` - Public inspection
- POST `/api/ro/{ro_id}/share/estimate` - Send estimate
- POST `/api/ro/{ro_id}/share/invoice` - Send invoice
- PUT `/api/ro/{ro_id}/complete` - Complete work
- PUT `/api/ro/{ro_id}/post` - Post RO
- PUT `/api/ro/{ro_id}/unpost` - Unpost RO

### Appointments (5)
- GET `/api/appointments/calendar` - Calendar view
- GET `/api/appointments/{id}` - Get appointment
- POST `/api/appointments` - Create/update
- GET `/api/appointments/settings` - Settings
- GET `/api/appointments/colors` - Color labels

### Parts & Orders (5)
- GET `/api/parts/integration-config` - Integration config
- POST `/api/parts/proxy` - PartsTech proxy
- GET `/api/parts/vendors` - Vendor search
- POST `/api/parts/orders` - Create order
- PATCH `/api/parts/orders/{id}/receive` - Mark received

### VCDB Lookups (5)
- GET `/api/vcdb/years` - Years
- GET `/api/vcdb/makes/{year}` - Makes
- GET `/api/vcdb/models/{year}/{make_id}` - Models
- GET `/api/vcdb/submodels/{vehicle_id}` - Submodels
- GET `/api/vcdb/vehicle/{vehicle_id}` - Vehicle details

### Jobs (6)
- POST `/api/jobs` - Create/update job
- DELETE `/api/jobs/{job_id}` - Delete job
- GET `/api/jobs/profit/{ro_id}` - Profit breakdown
- GET `/api/jobs/canned` - Canned jobs
- GET `/api/jobs/categories` - Job categories
- GET `/api/jobs/favorite` - Favorite jobs

### Inspections (7)
- GET `/api/inspections/{ro_id}` - Get inspections
- GET `/api/inspections/{id}/tasks` - Get tasks
- PUT `/api/inspections/{id}/tasks/{task_id}` - Update task
- POST `/api/inspections/media/video-upload-url` - Video upload URL
- POST `/api/inspections/{id}/tasks/{task_id}/media` - Create media
- POST `/api/inspections/{id}/tasks/{task_id}/media/{media_id}/confirm` - Confirm upload

### Employees (5)
- GET `/api/employees` - List employees
- GET `/api/employees/{id}` - Get employee
- GET `/api/employees/{id}/time-card-active` - Time card
- GET `/api/employees/tech-board` - Tech board
- GET `/api/employees/tech-board/config` - Tech board config

### Inventory (2)
- GET `/api/inventory/search` - Search parts
- GET `/api/inventory/part/{id}` - Get part

### Carfax (3)
- GET `/api/carfax/vehicle/{vin}` - Vehicle history
- GET `/api/carfax/vehicle/{vin}/maintenance` - Maintenance
- GET `/api/carfax/vehicle/{vin}/recalls` - Recalls

### Shop Configuration (6)
- GET `/api/shop/config` - Shop config
- GET `/api/shop` - Shop details
- GET `/api/shop/lead-sources` - Lead sources
- GET `/api/shop/ro-custom-labels` - Custom labels
- GET `/api/shop/profitability-goal` - GP goal
- GET `/api/shop/ro-advanced-settings` - Advanced settings

### Reports (5)
- GET `/api/reports/sales-summary` - Sales report
- GET `/api/reports/customer-list` - Customer report
- GET `/api/reports/ar-aging` - AR aging
- GET `/api/reports/employee-productivity` - Employee productivity
- GET `/api/reports/parts-purchased` - Parts spending

---

## Usage Examples

### Get Accurate Dashboard (Not TM's "Booty" Aggregates)

```bash
curl https://your-app.railway.app/api/dashboard/accurate-today
```

**Response:**
```json
{
  "posted_count": 23,
  "total_sales": 471028,
  "total_paid": 450000,
  "total_ar": 21028,
  "average_ticket": 20479,
  "source": "ACCURATE_RAW_DATA",
  "calculated_at": "2025-11-26T18:30:00"
}
```

### Create Payment

```bash
curl -X POST https://your-app.railway.app/api/payments/273790021 \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Smith",
    "customer_id": 12345,
    "amount": 50000,
    "payment_type_id": 2,
    "payment_date": "2025-11-26T18:00:00Z"
  }'
```

### Get RO List (Raw Data)

```bash
curl "https://your-app.railway.app/api/ro/list?board=ACTIVE&group_by=NONE"
```

---

## Architecture

```
Client Apps (Chrome Ext, Web Dashboard)
    ↓
FastAPI Backend (Railway)
    ↓
Tekmetric API (shop.tekmetric.com)
```

**Benefits:**
- ✅ Hide JWT tokens from clients
- ✅ Custom metric calculations
- ✅ Rate limiting protection
- ✅ Single source of truth
- ✅ Easy to extend

---

## Project Structure

```
tm-fastapi-backend/
├── main.py                      # FastAPI app entry point
├── app/
│   ├── routers/                 # API route handlers
│   │   ├── authorization.py     # Authorization endpoints
│   │   ├── dashboard.py         # Dashboard endpoints
│   │   ├── payments.py          # Payment endpoints
│   │   ├── customers.py         # Customer/vehicle endpoints
│   │   └── ro_operations.py     # RO operations
│   ├── services/
│   │   └── tm_client.py         # TM API client
│   └── models/
│       └── schemas.py           # Pydantic models
├── requirements.txt             # Python dependencies
├── railway.json                 # Railway deployment config
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

---

## Supabase Setup (Recommended)

**Architecture:**
```
Chrome Extension → Captures JWT → Supabase
                                     ↓
FastAPI Backend → Fetches JWT ←──────┘
                     ↓
            Tekmetric API
```

### 1. Supabase Table Setup

Create a table in Supabase:

```sql
CREATE TABLE jwt_tokens (
  id BIGSERIAL PRIMARY KEY,
  jwt_token TEXT NOT NULL,
  shop_id TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (Row Level Security)
ALTER TABLE jwt_tokens ENABLE ROW LEVEL SECURITY;

-- Create policy for anon access
CREATE POLICY "Allow anon read/write"
  ON jwt_tokens FOR ALL
  USING (true)
  WITH CHECK (true);
```

### 2. Chrome Extension Configuration

Configure the JWT extension to sync to your Supabase:
- Set `SUPABASE_URL` in extension
- Set `SUPABASE_KEY` in extension
- Extension will auto-capture and upload tokens

### 3. FastAPI Backend Configuration

Add to Railway environment variables:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
USE_SUPABASE=true
```

**That's it!** Backend will auto-fetch latest token from Supabase.

---

## Manual JWT Token (Without Supabase)

If not using Supabase:

1. Open Tekmetric in Chrome
2. Open DevTools (F12)
3. Go to Application tab → Local Storage → shop.tekmetric.com
4. Find `auth_token` or check Network tab requests for `x-auth-token` header
5. Copy the JWT token (starts with `eyJ...`)
6. Add to `.env` file or Railway environment variables:
   ```
   TM_AUTH_TOKEN=your_jwt_token_here
   TM_SHOP_ID=6212
   USE_SUPABASE=false
   ```

**Note:** Tokens expire! You'll need to update manually.

---

## Development

### Run locally:
```bash
uvicorn main:app --reload
```

### Test endpoints:
```bash
# Visit interactive docs
http://localhost:8000/docs

# Health check
curl http://localhost:8000/health
```

### Add new endpoints:
1. Create or update router in `app/routers/`
2. Import router in `main.py`
3. Add to `app.include_router()

`

---

## Next Steps (Future Phases)

**Phase 2: Advanced Features**
- Background data sync
- PostgreSQL database
- Caching layer
- Webhooks

**Phase 3: Analytics**
- Historical tracking
- Custom reports
- Trend analysis
- Predictions

---

## Documentation

Complete Tekmetric API documentation: https://github.com/davefmurray/tm-api-docs

**Reference Docs:**
- Authorization: `docs/api/tm_authorization_api.md`
- Payments: `docs/api/tm_payment_invoice_api.md`
- Dashboard: `docs/api/tm_dashboard_api.md`
- Customers: `docs/api/tm_customer_vehicle_crud_api.md`
- RO Operations: `docs/api/tm_ro_list_query_api.md`

---

## License

MIT

---

## Support

Issues: https://github.com/davefmurray/tm-fastapi-backend/issues
