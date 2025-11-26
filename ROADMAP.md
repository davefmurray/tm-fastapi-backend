# TM FastAPI Backend - Roadmap

**Current Status:** 46 endpoints implemented
**Completion:** ~35% of documented TM APIs

---

## IMPLEMENTED ✅ (46 Endpoints)

### Authorization (3)
- ✅ POST `/api/auth/authorize/{nonce}` - Submit authorization
- ✅ GET `/api/auth/authorizations/{ro_id}` - Auth history
- ✅ PATCH `/api/auth/job/{job_id}/remove-auth` - Remove auth status

### Dashboard (3)
- ✅ GET `/api/dashboard/summary` - Metrics summary
- ✅ GET `/api/dashboard/breakdown` - Breakdown by status
- ✅ GET `/api/dashboard/accurate-today` - Accurate calculations

### Payments (4)
- ✅ GET `/api/payments/types` - Payment types
- ✅ POST `/api/payments/{ro_id}` - Create payment
- ✅ GET `/api/payments/{ro_id}` - List payments
- ✅ PUT `/api/payments/{payment_id}/void` - Void payment

### Customers (7)
- ✅ POST `/api/customers` - Create customer
- ✅ PUT `/api/customers/{customer_id}` - Update customer
- ✅ GET `/api/customers/search` - Search customers
- ✅ GET `/api/customers/{customer_id}` - Get customer
- ✅ POST `/api/customers/vehicles` - Create vehicle
- ✅ PUT `/api/customers/vehicles/{vehicle_id}` - Update vehicle
- ✅ GET `/api/customers/{customer_id}/vehicles` - List vehicles

### Repair Orders (14)
- ✅ GET `/api/ro/list` - List ROs (raw data)
- ✅ GET `/api/ro/{ro_id}` - RO details
- ✅ GET `/api/ro/{ro_id}/estimate` - Get estimate
- ✅ GET `/api/ro/{ro_id}/activity` - Activity feed
- ✅ GET `/api/ro/{ro_id}/job-history` - Job history
- ✅ GET `/api/ro/{ro_id}/inspection-history` - Inspection history
- ✅ GET `/api/ro/{ro_id}/appointments` - RO appointments
- ✅ GET `/api/ro/{ro_id}/purchase-orders` - Purchase orders
- ✅ POST `/api/ro/{ro_id}/share/estimate` - Send estimate
- ✅ POST `/api/ro/{ro_id}/share/invoice` - Send invoice
- ✅ PUT `/api/ro/{ro_id}/complete` - Mark complete
- ✅ PUT `/api/ro/{ro_id}/post` - Post RO
- ✅ PUT `/api/ro/{ro_id}/unpost` - Unpost RO

### Appointments (5)
- ✅ GET `/api/appointments/calendar` - Calendar view
- ✅ GET `/api/appointments/{appointment_id}` - Get appointment
- ✅ POST `/api/appointments` - Create/update appointment
- ✅ GET `/api/appointments/settings` - Calendar settings
- ✅ GET `/api/appointments/colors` - Color labels

### Parts Hub (5)
- ✅ GET `/api/parts/integration-config` - Integration config
- ✅ POST `/api/parts/proxy` - PartsTech proxy
- ✅ GET `/api/parts/vendors` - Vendor search
- ✅ POST `/api/parts/orders` - Create manual order
- ✅ PATCH `/api/parts/orders/{order_id}/receive` - Mark received

### VCDB Lookups (5)
- ✅ GET `/api/vcdb/years` - Get years
- ✅ GET `/api/vcdb/makes/{year}` - Get makes
- ✅ GET `/api/vcdb/models/{year}/{make_id}` - Get models
- ✅ GET `/api/vcdb/submodels/{vehicle_id}` - Get submodels
- ✅ GET `/api/vcdb/vehicle/{vehicle_id}` - Vehicle details

---

## REMAINING ENDPOINTS (By Priority)

### TIER 6: Job Creation & Management (High Priority)

**Job CRUD:**
- POST `/api/jobs` - Create job with parts/labor
- GET `/api/jobs/{job_id}` - Get job details
- DELETE `/api/jobs/{job_id}` - Delete job

**Job Operations:**
- POST `/api/jobs/{job_id}/parts` - Add parts to job
- POST `/api/jobs/{job_id}/labor` - Add labor to job
- PUT `/api/jobs/{job_id}/technician` - Assign technician

**Why:** Core functionality for creating estimates

---

### TIER 7: Inspection & Media (High Priority)

**Inspection Management:**
- GET `/api/inspections/{ro_id}` - Get inspections
- POST `/api/inspections` - Create inspection
- PUT `/api/inspections/{inspection_id}` - Update inspection
- GET `/api/inspections/{inspection_id}/tasks` - Get tasks

**Media Upload:**
- POST `/api/media/create-video-upload-url` - Get S3 presigned URL
- POST `/api/media/create-photo-upload-url` - Get S3 presigned URL
- POST `/api/inspections/{inspection_id}/media/confirm` - Confirm upload

**Why:** Complete inspection workflow (documented in Nov 19 session)

---

### TIER 8: Employee Management (Medium Priority)

**Employee Operations:**
- GET `/api/employees` - List employees
- GET `/api/employees/{employee_id}` - Get employee
- POST `/api/employees` - Create employee
- PUT `/api/employees/{employee_id}` - Update employee
- DELETE `/api/employees/{employee_id}` - Deactivate employee

**Time Clock:**
- GET `/api/employees/{employee_id}/time-card-active` - Current clock status
- POST `/api/employees/{employee_id}/clock-in` - Clock in
- POST `/api/employees/{employee_id}/clock-out` - Clock out
- GET `/api/employees/{employee_id}/time-cards` - Time card history

**Tech Board:**
- GET `/api/tech-board` - Tech board view
- GET `/api/tech-board/config` - Tech board config

**Why:** Workforce management, time tracking (already documented)

---

### TIER 9: Inventory Management (Medium Priority)

**Inventory:**
- GET `/api/inventory` - List inventory parts
- GET `/api/inventory/search` - Search parts
- POST `/api/inventory` - Add part to inventory
- PUT `/api/inventory/{part_id}` - Update inventory part
- GET `/api/inventory/statistics` - Inventory stats

**Why:** Parts stock tracking, reorder management

---

### TIER 10: Advanced Authorization (Low Priority)

**Transparency Settings:**
- GET `/api/ro/{ro_id}/transparency-settings` - Get settings
- PUT `/api/ro/{ro_id}/transparency-settings` - Update settings

**Digital Inspection Sharing:**
- GET `/api/public/inspection/{nonce}` - Public inspection view
- GET `/api/public/estimate/{nonce}` - Public estimate view

**Why:** Print customization, public sharing

---

### TIER 11: Carfax Integration (Low Priority)

**Carfax:**
- GET `/api/carfax/vehicle/{vin}` - Vehicle history
- GET `/api/carfax/vehicle/{vin}/maintenance` - Maintenance schedule
- GET `/api/carfax/vehicle/{vin}/recalls` - Recall data

**Why:** Vehicle history, maintenance tracking (already documented)

---

### TIER 12: Shop Configuration (Low Priority)

**Shop Settings:**
- GET `/api/shop/{shop_id}/config` - Shop configuration
- GET `/api/shop/{shop_id}/lead-sources` - Lead sources
- GET `/api/shop/{shop_id}/ro-custom-labels` - Custom RO labels
- GET `/api/shop/{shop_id}/profitability-goal` - GP goals

**Labor/Pricing Matrices:**
- GET `/api/shop/{shop_id}/labor-matrices` - Labor rate matrices
- GET `/api/shop/{shop_id}/pricing-matrices` - Parts pricing matrices

**Why:** Configuration management, pricing rules

---

### TIER 13: Reports & Analytics (Low Priority)

**Financial Reports:**
- GET `/api/reports/sales-summary` - Sales report
- GET `/api/reports/ar-aging` - AR aging
- GET `/api/reports/parts-purchased` - Parts spending

**Employee Reports:**
- GET `/api/reports/employee-productivity` - Tech productivity
- GET `/api/reports/employee-sales` - Sales by employee

**Why:** Already documented (27 report types), but could expose via API

---

### TIER 14: Advanced Operations (Very Low Priority)

**Sublets:**
- GET `/api/sublets/{ro_id}` - Get sublets
- POST `/api/sublets` - Create sublet

**Fees & Discounts:**
- POST `/api/jobs/{job_id}/fees` - Add fees
- POST `/api/jobs/{job_id}/discounts` - Add discounts

**Notes:**
- POST `/api/ro/{ro_id}/notes` - Add note
- GET `/api/ro/{ro_id}/notes` - Get notes

**Customer Concerns:**
- GET `/api/ro/{ro_id}/customer-concerns` - Get concerns
- POST `/api/ro/{ro_id}/customer-concerns` - Add concern

**Why:** Edge cases, less frequently used

---

### TIER 15: Fleet & Advanced Features (Future)

**Fleet Management:**
- GET `/api/fleet/{fleet_id}` - Fleet details
- GET `/api/fleet/{fleet_id}/vehicles` - Fleet vehicles

**Rewards/Loyalty:**
- GET `/api/customers/{customer_id}/rewards` - Rewards balance
- POST `/api/customers/{customer_id}/rewards/redeem` - Redeem points

**Recalls:**
- GET `/api/recalls/{vin}` - Check recalls
- POST `/api/recalls/{ro_id}/add` - Add recall to RO

**Why:** Advanced features, not commonly used

---

## SUMMARY BY TIER

| Tier | Category | Status | Endpoints | Priority |
|------|----------|--------|-----------|----------|
| 1 | RO Summary Tabs | ✅ Complete | 5 | Critical |
| 2 | RO Lifecycle | ✅ Complete | 4 | Critical |
| 3 | Calendar/Scheduling | ✅ Complete | 5 | High |
| 4 | Parts Hub | ✅ Complete | 5 | High |
| 5 | Customer/Vehicle Updates + VCDB | ✅ Complete | 7 | High |
| 6 | Job Creation & Management | ⏳ Not Started | 6 | High |
| 7 | Inspection & Media | ⏳ Not Started | 7 | High |
| 8 | Employee Management | ⏳ Not Started | 11 | Medium |
| 9 | Inventory Management | ⏳ Not Started | 5 | Medium |
| 10 | Advanced Authorization | ⏳ Not Started | 4 | Low |
| 11 | Carfax Integration | ⏳ Not Started | 3 | Low |
| 12 | Shop Configuration | ⏳ Not Started | 6 | Low |
| 13 | Reports & Analytics | ⏳ Not Started | 5+ | Low |
| 14 | Advanced Operations | ⏳ Not Started | 8+ | Very Low |
| 15 | Fleet & Advanced | ⏳ Not Started | 5+ | Future |

---

## TOTAL ENDPOINT COVERAGE

**Implemented:** 46 endpoints
**Remaining:** ~80+ endpoints
**Total Documented:** 170+ TM APIs

**Coverage:** ~35% of documented APIs

---

## RECOMMENDED NEXT STEPS

### Phase 2 (Next Build Session)
**Add Tier 6 & 7 (Job Creation + Inspections):**
- Critical for full RO creation workflow
- Enables automated estimate generation
- ~13 endpoints, ~2 hours work

### Phase 3 (Future)
**Add Tier 8 & 9 (Employees + Inventory):**
- Workforce management
- Parts inventory tracking
- ~16 endpoints, ~2 hours work

### Phase 4 (Future)
**Remaining tiers as needed**
- Add on demand based on use cases

---

## WHAT YOU CAN BUILD NOW (With 46 Endpoints)

### ✅ Live Dashboard
- Accurate sales tracking
- Authorization monitoring
- Real-time metrics

### ✅ Customer Portal
- Create customers/vehicles
- Schedule appointments
- View history

### ✅ Payment Processing
- Record payments
- Void payments
- Track AR

### ✅ RO Management
- List/search ROs
- Complete work
- Post ROs
- Send estimates/invoices

### ✅ Calendar Management
- View schedule
- Create/update appointments
- Manage bookings

### ✅ Parts Ordering
- Create manual orders
- Receive orders
- Vendor management

### ❌ NOT YET (Need Tier 6-7)
- Create jobs programmatically
- Upload inspection photos/videos
- Auto-populate estimates

---

## ESTIMATION FOR FULL COVERAGE

**To reach 100% (all 170+ APIs):**
- Remaining tiers: 6-15
- Total endpoints: ~80+
- Estimated time: ~10-15 hours
- Phased approach: 2-3 hour sessions

**Realistic goal: 70-80% coverage** (skip edge cases in Tier 14-15)

---

## CURRENT CAPABILITIES

**You can NOW:**
1. ✅ Pull all RO data for custom dashboard
2. ✅ Record payments and track AR
3. ✅ Manage customers and vehicles
4. ✅ Automate RO lifecycle (complete/post)
5. ✅ Schedule appointments
6. ✅ Order and receive parts
7. ✅ Send estimates/invoices
8. ✅ Track authorizations

**Next priority:** Add job creation (Tier 6) to enable full estimate automation.
