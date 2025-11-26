# TM FastAPI Backend - Comprehensive Examples

**Complete request/response examples for all 110 endpoints.**

**CRITICAL:** Reference the [tm-api-docs](https://github.com/davefmurray/tm-api-docs) repository for full TM API documentation with all captured data.

---

## ⚠️ CRITICAL: Money Format

**ALL monetary values in Tekmetric are in CENTS.**

```javascript
// WRONG
{
  "cost": 45.00,      // Will be treated as $0.45!
  "retail": 179.50    // Will be treated as $1.80!
}

// CORRECT
{
  "cost": 4500,       // $45.00
  "retail": 17950     // $179.50
}
```

**Always multiply by 100 when sending to TM, divide by 100 when displaying.**

---

## Complete RO Workflow Example

### End-to-End: Customer → Authorization → Payment → Posted

```python
import httpx

BASE_URL = "https://tm-fastapi-backend-production.up.railway.app"

async def complete_ro_workflow():
    """Complete RO workflow from customer creation to posting"""

    # 1. Create Customer
    customer = await httpx.post(f"{BASE_URL}/api/customers", json={
        "first_name": "John",
        "last_name": "Smith",
        "email": ["john@email.com"],
        "phone": [{"number": "5551234567", "type": "Mobile", "primary": True}],
        "customer_type_id": 1,  # PERSON
        "address": {
            "address1": "123 Main St",
            "city": "Jacksonville",
            "state": "FL",
            "zip": "32256"
        },
        "ok_for_marketing": True,
        "lead_source": "Google"
    })
    customer_id = customer.json()["data"]["id"]

    # 2. Create Vehicle (with VCDB lookup)
    # First get VCDB data
    makes = await httpx.get(f"{BASE_URL}/api/vcdb/makes/2020")
    ford = next(m for m in makes.json() if m["name"] == "Ford")

    models = await httpx.get(f"{BASE_URL}/api/vcdb/models/2020/{ford['id']}")
    f150 = next(m for m in models.json() if m["name"] == "F-150")

    vehicle = await httpx.post(f"{BASE_URL}/api/customers/vehicles", json={
        "customer_id": customer_id,
        "year": 2020,
        "make": "Ford",
        "make_id": ford["id"],
        "model": "F-150",
        "model_id": f150["id"],
        "vehicle_id": f150["vehicleId"],
        "base_vehicle_id": f150["baseVehicleId"],
        "vin": "1FTFW1E84LKE12345",
        "license_plate": "ABC123",
        "color": "Black"
    })
    vehicle_id = vehicle.json()["data"]["id"]

    # 3. Create Repair Order
    ro = await httpx.post(f"{BASE_URL}/api/ro/create", json={
        "customerId": customer_id,
        "vehicleId": vehicle_id,
        "milesIn": 75000,
        "customerTimeIn": "2025-11-26T09:00:00Z",
        "leadSource": "Google"
    })
    ro_id = ro.json()["data"]["id"]

    # 4. Create Job with Parts and Labor
    job = await httpx.post(f"{BASE_URL}/api/jobs", json={
        "name": "Oil Change Service",
        "repairOrderId": ro_id,
        "syncPartsAttachedToNonQuotedOrders": False,
        "parts": [
            {
                "tempId": 0.123456,  # Random for new parts
                "partType": {"id": 1, "code": "PART"},
                "name": "Oil Filter",
                "partNumber": "PF48",
                "brand": "Fram",
                "quantity": 1,
                "cost": 450,    # $4.50 in cents!
                "retail": 1200  # $12.00 in cents!
            },
            {
                "tempId": 0.789012,
                "partType": {"id": 1, "code": "PART"},
                "name": "Synthetic Oil 5W-30",
                "partNumber": "SYN-5W30",
                "brand": "Mobil 1",
                "quantity": 5,
                "cost": 250,    # $2.50 per quart
                "retail": 850   # $8.50 per quart
            }
        ],
        "labor": [
            {
                "tempId": 0.345678,  # Random for new labor
                "name": "Oil Change Labor",
                "hours": 0.5,
                "rate": 17950,  # $179.50/hr in cents!
                "technician": {
                    "id": 220020,
                    "firstName": "John",
                    "lastName": "Tech",
                    "fullName": "John Tech",
                    "employeeRole": {"id": 3, "code": "3", "name": "Technician"}
                }
            }
        ],
        "taxParts": True,
        "taxLabor": True
    })

    job_id = job.json()["data"]["id"]
    print(f"Job created: {job_id}")
    print(f"Total: ${job.json()['data']['total'] / 100}")

    # 5. Get RO Nonce (needed for authorization)
    ro_details = await httpx.get(f"{BASE_URL}/api/ro/{ro_id}")
    nonce = ro_details.json()["nonce"]

    # 6. Send Estimate to Customer
    await httpx.post(f"{BASE_URL}/api/ro/{ro_id}/share/estimate", json={
        "email": ["john@email.com"]
    })

    # 7. Customer Authorizes (or shop-side verbal approval)
    auth = await httpx.post(f"{BASE_URL}/api/auth/authorize/{nonce}", json={
        "authorization": {
            "method": "VERBAL_IN_PERSON",
            "authorizer": "John Smith",
            "date": "2025-11-26T10:00:00Z",
            "timezone": "America/New_York"
        },
        "jobs": [
            {
                "id": job_id,
                "authorized": True,
                "selected": True
            }
        ]
    })

    # RO status is now WORKINPROGRESS

    # 8. Complete Work
    await httpx.put(
        f"{BASE_URL}/api/ro/{ro_id}/complete",
        params={
            "completed_date": "2025-11-26T15:00:00Z",
            "miles_in": 75000,
            "miles_out": 75010
        }
    )

    # 9. Record Payment
    payment = await httpx.post(f"{BASE_URL}/api/payments/{ro_id}", json={
        "customer_name": "John Smith",
        "customer_id": customer_id,
        "amount": 9730,  # Total in cents
        "payment_type_id": 2,  # Cash
        "payment_date": "2025-11-26T15:30:00Z",
        "should_post": False
    })

    # 10. Post RO
    await httpx.put(
        f"{BASE_URL}/api/ro/{ro_id}/post",
        params={
            "posted_date": "2025-11-26T16:00:00Z",
            "miles_in": 75000,
            "miles_out": 75010
        }
    )

    # 11. Send Invoice
    await httpx.post(f"{BASE_URL}/api/ro/{ro_id}/share/invoice", json={
        "email": ["john@email.com"]
    })

    print("Complete RO workflow finished!")
    return ro_id

# Run workflow
import asyncio
asyncio.run(complete_ro_workflow())
```

---

## Job Creation - Detailed Examples

### Create Simple Job
```bash
curl -X POST "https://tm-fastapi-backend-production.up.railway.app/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Brake Inspection",
    "repairOrderId": 273790021,
    "syncPartsAttachedToNonQuotedOrders": false
  }'
```

**Response:**
```json
{
  "type": "SUCCESS",
  "message": "Job(s) added",
  "data": {
    "id": 936821344,
    "repairOrderId": 273790021,
    "name": "Brake Inspection",
    "status": "Pending",
    "parts": [],
    "labor": []
  }
}
```

---

### Create Job with Parts
```python
job_with_parts = {
    "name": "Brake Service",
    "repairOrderId": 273790021,
    "syncPartsAttachedToNonQuotedOrders": False,
    "parts": [
        {
            "tempId": 0.923456,  # Math.random() equivalent
            "partType": {"id": 1, "code": "PART"},
            "name": "Brake Pads - Front",
            "partNumber": "D1234",
            "brand": "Raybestos",
            "description": "Premium ceramic pads",
            "quantity": 1,
            "cost": 4500,     # $45.00 in CENTS
            "retail": 12000   # $120.00 in CENTS
        },
        {
            "tempId": 0.456789,
            "partType": {"id": 1, "code": "PART"},
            "name": "Brake Rotors - Front",
            "partNumber": "R5678",
            "brand": "Centric",
            "quantity": 2,
            "cost": 8000,     # $80.00 each = $160 total
            "retail": 18000   # $180.00 each = $360 total
        }
    ],
    "taxParts": True,
    "taxLabor": True
}

response = await httpx.post(f"{BASE_URL}/api/jobs", json=job_with_parts)
```

**Response includes calculated totals:**
```json
{
  "data": {
    "id": 937411345,
    "parts": [
      {
        "id": 861127500,  // Server assigns real IDs
        "name": "Brake Pads - Front",
        "cost": 4500,
        "retail": 12000,
        "total": 12000
      },
      {
        "id": 861127501,
        "name": "Brake Rotors - Front",
        "cost": 8000,
        "retail": 18000,
        "quantity": 2,
        "total": 36000  // Automatically calculated (18000 * 2)
      }
    ],
    "partsPrice": 48000,  // $480.00 total
    "grossProfitAmount": 24000,  // $240.00 profit
    "grossProfitPercentage": 0.5000  // 50% margin
  }
}
```

---

### Create Job with Parts AND Labor
```python
complete_job = {
    "name": "Brake Service - Complete",
    "repairOrderId": 273790021,
    "syncPartsAttachedToNonQuotedOrders": False,
    "parts": [
        {
            "tempId": 0.111111,
            "partType": {"id": 1, "code": "PART"},
            "name": "Brake Pads",
            "partNumber": "BP-1234",
            "brand": "Raybestos",
            "quantity": 1,
            "cost": 4500,
            "retail": 12000
        }
    ],
    "labor": [
        {
            "tempId": 0.222222,  # Random for new labor
            "name": "Replace Brake Pads",
            "hours": 1.5,
            "rate": 17950,  # $179.50/hr in CENTS
            "technician": {
                "id": 220020,  # Get from GET /api/employees
                "firstName": "Conner",
                "lastName": "C.",
                "fullName": "Conner C.",
                "employeeRole": {
                    "id": 3,
                    "code": "3",
                    "name": "Technician"
                }
            }
        }
    ],
    "discounts": [],
    "fees": [],
    "taxParts": True,
    "taxLabor": True,
    "taxFees": True
}

response = await httpx.post(f"{BASE_URL}/api/jobs", json=complete_job)
```

**Server calculates everything:**
```json
{
  "data": {
    "id": 937411350,
    "partsPrice": 12000,      // $120.00
    "laborPrice": 26925,      // $269.25 (1.5 hrs * $179.50)
    "subtotal": 38925,        // $389.25
    "laborTime": 1.5,
    "grossProfitAmount": 19425,  // $194.25 profit
    "grossProfitPercentage": 0.6364,  // 63.64% margin
    "grossProfitPerHour": 12950  // $129.50 profit per hour
  }
}
```

---

### Update Existing Job (Add More Parts)
```python
# CRITICAL: Must send COMPLETE job object
# Get existing job first, then add to it

existing_job = await httpx.get(f"{BASE_URL}/api/ro/{ro_id}/estimate")
job_to_update = existing_job.json()["jobs"][0]  # Get first job

# Add new part to existing parts array
job_to_update["parts"].append({
    "tempId": 0.999999,
    "partType": {"id": 1, "code": "PART"},
    "name": "Brake Fluid",
    "partNumber": "BF-DOT3",
    "brand": "Prestone",
    "quantity": 1,
    "cost": 1500,
    "retail": 8999
})

# POST with complete object (includes id for update)
response = await httpx.post(f"{BASE_URL}/api/jobs", json=job_to_update)
```

**Key Pattern:**
- Include `"id": 937411350` = UPDATE
- Omit `"id"` = CREATE
- Always send COMPLETE parts/labor arrays (server replaces, not merges)

---

## Authorization Examples

### Customer Digital Signature Authorization
```python
auth_response = await httpx.post(
    f"{BASE_URL}/api/auth/authorize/{nonce}",
    json={
        "authorization": {
            "method": "DIGITAL_SIGNATURE",
            "authorizer": "John Smith",
            "date": "2025-11-26T13:01:34.563Z",
            "timeZone": "America/New_York",
            "signature": "iVBORw0KGgoAAAANSUhEUgAAA..."  # Base64 PNG
        },
        "jobs": [
            {"id": 937411332, "authorized": True, "selected": True},   # Approved
            {"id": 933843233, "authorized": False, "selected": True}   # Declined
        ]
    }
)
```

**Response shows status change:**
```json
{
  "data": {
    "repairOrder": {
      "repairOrderStatus": {
        "id": 2,
        "code": "WORKINPROGRESS"  // Auto-changed from ESTIMATE!
      }
    },
    "estimate": {
      "jobs": [
        {
          "id": 937411332,
          "authorized": true,
          "status": "Approved",
          "authorizedDate": "2025-11-26T13:01:52.364767646Z"
        },
        {
          "id": 933843233,
          "authorized": false,
          "status": "Declined"
        }
      ]
    }
  }
}
```

---

### Shop-Side Verbal Approval
```python
# Service advisor approves on behalf of customer
await httpx.post(f"{BASE_URL}/api/auth/authorize/{nonce}", json={
    "authorization": {
        "method": "VERBAL_IN_PERSON",  # Not DIGITAL_SIGNATURE
        "authorizer": "John Smith",
        "date": "2025-11-26T15:27:55.848Z",
        "timeZone": "America/New_York"
        # NO signature field
    },
    "jobs": [
        {"id": 937411323, "authorized": True, "selected": True}
    ]
})
```

---

## Payment Examples

### Record Cash Payment
```python
payment = await httpx.post(f"{BASE_URL}/api/payments/{ro_id}", json={
    "customer_name": "John Smith",
    "customer_id": 38655198,
    "amount": 96318,  # $963.18 in CENTS
    "payment_type_id": 2,  # 2 = Cash (get types from /api/payments/types)
    "payment_date": "2025-11-26T16:32:02.083Z",
    "should_post": False  # Set True to auto-post RO after payment
})
```

**Response:**
```json
{
  "attempt_id": "b319a3a5-ed9c-4283-8571-76d280424c5b",
  "status": "FINALIZED",
  "payment_id": 48183289,
  "details": {...}
}
```

---

### Get Payment Types
```bash
curl "https://tm-fastapi-backend-production.up.railway.app/api/payments/types"
```

**Response:**
```json
[
  {"id": 74666, "name": "Credit Card", "sortOrder": 1},
  {"id": 74667, "name": "Debit Card", "sortOrder": 2},
  {"id": 74668, "name": "Cash", "sortOrder": 3},
  {"id": 75375, "name": "Affirm", "sortOrder": 7},
  {"id": 68478, "name": "Write-Off", "sortOrder": 12, "uncollectible": true}
]
```

---

### Void Payment
```python
await httpx.put(f"{BASE_URL}/api/payments/{payment_id}/void")
```

---

## Dashboard Examples

### Get Today's Metrics (TM Aggregates - Fast)
```bash
curl "https://tm-fastapi-backend-production.up.railway.app/api/dashboard/summary"
```

**Response:**
```json
{
  "sold_amount": 16538247,      // $165,382.47
  "posted_amount": 763292,      // $7,632.92
  "pending_amount": 6790136,    // $67,901.36
  "declined_amount": 9023948,   // $90,239.48
  "sold_job_count": 429,
  "posted_job_count": 45,
  "pending_job_count": 98,
  "declined_job_count": 118,
  "close_ratio": 0.51,          // 51%
  "average_ro": 146356.0,       // $1,463.56
  "car_count": 113
}
```

---

### Get ACCURATE Today's Posted Sales (YOUR Calculations)
```bash
curl "https://tm-fastapi-backend-production.up.railway.app/api/dashboard/accurate-today"
```

**This endpoint:**
1. Gets all posted ROs from job-board
2. Filters to TODAY only
3. Gets estimate for EACH RO
4. Calculates totals from raw data

**Response:**
```json
{
  "posted_count": 23,
  "total_sales": 471028,        // $4,710.28 (from estimates, not TM aggregates)
  "total_paid": 450000,         // $4,500.00
  "total_ar": 21028,            // $210.28
  "average_ticket": 20479,      // $204.79
  "source": "ACCURATE_RAW_DATA",
  "calculated_at": "2025-11-26T18:30:00",
  "ros": [...]  // Full RO list included
}
```

**Use this for accurate tracking!**

---

## Appointment Examples

### Get Week's Appointments
```python
from datetime import datetime, timedelta

today = datetime.now()
week_start = today - timedelta(days=today.weekday())
week_end = week_start + timedelta(days=6)

appointments = await httpx.get(
    f"{BASE_URL}/api/appointments/calendar",
    params={
        "view": "week",
        "start": week_start.isoformat(),
        "end": week_end.isoformat(),
        "size": 10000
    }
)
```

---

### Create Appointment
```python
appointment = await httpx.post(f"{BASE_URL}/api/appointments", json={
    "startTime": "2025-11-28T09:00:00Z",
    "endTime": "2025-11-28T09:30:00Z",
    "dropoffTime": "2025-11-28T09:00:00Z",
    "pickupTime": "2025-11-28T17:00:00Z",
    "description": "Oil change appointment",
    "color": "#0D4A80",
    "appointmentOption": {"id": 2, "code": "DROP"},  # Drop-off
    "rideOption": {"id": 3, "code": "NONE"},         # No ride
    "status": "NONE",
    "customer": {"id": 52258809},
    "vehicle": {"id": 128352955},
    "shopId": 6212,
    "remindersEnabled": True,
    "confirmationsEnabled": True
})
```

---

## Parts Hub Examples

### Create Manual Order
```python
order = await httpx.post(f"{BASE_URL}/api/parts/orders", json={
    "quote": False,
    "orderNumber": "24715-TEST-ORDER",
    "tax": 0,
    "delivery": 0,
    "notes": "Rush order",
    "parts": [
        {
            "brand": "Raybestos",
            "name": "Brake Pads",
            "partNumber": "D1786",
            "cost": 4500,
            "retail": 10227,
            "partType": {"id": 1, "code": "PART"},
            "jobId": 937411316,
            "repairOrderId": 273790021,
            "quantity": 1,
            "roPartId": 861688589,
            "core": 0,
            "needed": 1,
            "ordered": 1
        }
    ],
    "vendor": {
        "id": 858273,
        "name": "SHOP"
    },
    "forceInventoryCostChange": True
})
```

---

### Mark Order as Received
```python
await httpx.patch(
    f"{BASE_URL}/api/parts/orders/{order_id}/receive",
    params={
        "invoice_number": "INV-12345",
        "invoice_date": "2025-11-26T16:14:59.609Z"
    }
)
```

---

## Inspection & Media Upload Examples

### Upload Video to Inspection
```python
# 1. Get upload URL
upload_url_response = await httpx.post(
    f"{BASE_URL}/api/inspections/media/video-upload-url",
    params={
        "file_type": "video/mp4",
        "file_name": "brake_inspection.mp4"
    }
)

presigned_url = upload_url_response.json()["presignedUrl"]
media_id = upload_url_response.json()["media"]["id"]

# 2. Upload to S3 (direct)
with open("brake_inspection.mp4", "rb") as video:
    await httpx.put(presigned_url, content=video.read(), headers={
        "Content-Type": "video/mp4"
    })

# 3. Confirm upload
await httpx.post(
    f"{BASE_URL}/api/inspections/{inspection_id}/tasks/{task_id}/media/{media_id}/confirm",
    params={"ro_id": ro_id}
)
```

---

## Customer & Vehicle Examples

### Create Customer with Full Details
```python
customer = await httpx.post(f"{BASE_URL}/api/customers", json={
    "first_name": "Jane",
    "last_name": "Doe",
    "business_name": "",
    "email": ["jane@example.com", "jane.doe@gmail.com"],
    "phone": [
        {
            "number": "9041234567",
            "type": "Mobile",
            "primary": True
        },
        {
            "number": "9047654321",
            "type": "Work",
            "primary": False
        }
    ],
    "customer_type_id": 1,  // 1 = PERSON, 2 = BUSINESS
    "address": {
        "address1": "456 Oak Street",
        "address2": "Apt 2B",
        "city": "Jacksonville",
        "state": "FL",
        "zip": "32256"
    },
    "tax_exempt": False,
    "ok_for_marketing": True,
    "lead_source": "Google Ads"
})
```

---

### Create Vehicle with VCDB Lookup (Complete Flow)
```python
# Step 1: Get years
years = await httpx.get(f"{BASE_URL}/api/vcdb/years")

# Step 2: Get makes for 2023
makes = await httpx.get(f"{BASE_URL}/api/vcdb/makes/2023")
audi = next(m for m in makes.json() if m["name"] == "Audi")

# Step 3: Get models
models = await httpx.get(f"{BASE_URL}/api/vcdb/models/2023/{audi['id']}")
r8 = next(m for m in models.json() if m["name"] == "R8")

# Step 4: Get submodels
submodels = await httpx.get(f"{BASE_URL}/api/vcdb/submodels/{r8['baseVehicleId']}")
perf_spyder = next(s for s in submodels.json() if "Performance Spyder" in s["name"])

# Step 5: Get vehicle details (ACES data)
vehicle_data = await httpx.get(f"{BASE_URL}/api/vcdb/vehicle/{perf_spyder['vehicleId']}")

# Step 6: Create vehicle with ACES data
vehicle = await httpx.post(f"{BASE_URL}/api/customers/vehicles", json={
    "customer_id": customer_id,
    "year": 2023,
    "make": "Audi",
    "make_id": audi["id"],
    "model": "R8",
    "model_id": r8["id"],
    "sub_model": "Performance Spyder",
    "sub_model_id": perf_spyder["id"],
    "vehicle_id": perf_spyder["vehicleId"],
    "base_vehicle_id": r8["baseVehicleId"],
    "vin": "WUABCDEF123456789",
    "license_plate": "FAST123",
    "color": "Red"
})
```

---

## RO List & Data Sync Examples

### Get All Active ROs (For Custom Dashboard)
```python
active_ros = await httpx.get(
    f"{BASE_URL}/api/ro/list",
    params={
        "board": "ACTIVE",
        "group_by": "NONE",
        "page": 0
    }
)

# Filter to pending authorizations
pending_auth = [
    ro for ro in active_ros.json()
    if ro["repairOrderStatus"]["id"] == 1 and ro["estimateShareDate"] is not None
]

print(f"Pending authorizations: {len(pending_auth)}")
```

---

### Full Data Sync (All ROs with Details)
```python
async def sync_all_ros():
    """Complete RO data sync"""
    all_ros = []

    # Get active ROs
    active = await httpx.get(f"{BASE_URL}/api/ro/list", params={"board": "ACTIVE"})
    all_ros.extend(active.json())

    # Get posted ROs
    posted = await httpx.get(f"{BASE_URL}/api/ro/list", params={"board": "POSTED"})
    all_ros.extend(posted.json())

    # For each RO, get complete data
    complete_data = []
    for ro in all_ros:
        ro_id = ro["id"]

        # Get all details in parallel
        estimate, payments, auth, activity = await asyncio.gather(
            httpx.get(f"{BASE_URL}/api/ro/{ro_id}/estimate"),
            httpx.get(f"{BASE_URL}/api/payments/{ro_id}"),
            httpx.get(f"{BASE_URL}/api/auth/authorizations/{ro_id}"),
            httpx.get(f"{BASE_URL}/api/ro/{ro_id}/activity")
        )

        complete_data.append({
            "ro": ro,
            "estimate": estimate.json(),
            "payments": payments.json(),
            "authorizations": auth.json(),
            "activity": activity.json()
        })

    return complete_data
```

---

## Common Patterns

### TempId Pattern (New Items)
```python
import random

# For NEW parts/labor that don't have server IDs yet
new_part = {
    "tempId": random.random(),  # 0.123456789
    "name": "Oil Filter",
    ...
}

# Server assigns real ID:
# Response: {"id": 861127482, ...}
```

---

### Update Pattern (Existing Items)
```python
# KEEP existing IDs when updating
existing_part = {
    "id": 861127482,  # Real ID from server
    "name": "Oil Filter - Updated",
    ...
}
```

---

### Complete Object Pattern
```python
# TM requires COMPLETE objects for updates
# ❌ WRONG: Send only changed fields
await httpx.post("/api/jobs", {"id": 12345, "name": "New Name"})

# ✅ CORRECT: Send complete object
job = await httpx.get(f"/api/ro/{ro_id}/estimate")
job_to_update = job.json()["jobs"][0]
job_to_update["name"] = "New Name"
await httpx.post("/api/jobs", job_to_update)  # Complete object
```

---

## Status Code Reference

### RO Status
| ID | Code | Name |
|----|------|------|
| 1 | ESTIMATE | Estimate |
| 2 | WORKINPROGRESS | Work-In-Progress |
| 3 | COMPLETE | Complete |
| 5 | POSTED | Posted |

### Employee Roles
| ID | Code | Name |
|----|------|------|
| 1 | 1 | Shop Admin |
| 2 | 2 | Service Advisor |
| 3 | 3 | Technician |
| 4 | 4 | Owner |

### Order Status
| ID | Code | Name |
|----|------|------|
| 1 | ORDERED | Ordered |
| 2 | RECEIVED | Received |

### Payment Types (Standard)
| ID | Name |
|----|------|
| 1 | Credit Card |
| 2 | Cash |
| 3 | Check |

---

## Error Handling

### Common Errors

**400 Bad Request:**
- Missing required fields
- Invalid date format
- Wrong data types

**401 Unauthorized:**
- Invalid or expired JWT token
- Solution: Chrome extension refreshes token in Supabase

**404 Not Found:**
- RO/customer/vehicle doesn't exist
- Check IDs before calling

**500 Internal Server Error:**
- TM API error
- Check request format matches examples

---

## Best Practices

### 1. Always Use Cents for Money
```python
# Convert dollars to cents
def to_cents(dollars):
    return int(dollars * 100)

# Convert cents to dollars
def to_dollars(cents):
    return cents / 100
```

### 2. Get Existing Data Before Updates
```python
# Always fetch current state first
existing = await httpx.get(f"{BASE_URL}/api/customers/{customer_id}")
customer = existing.json()

# Merge your updates
customer["email"] = ["new@email.com"]

# Send complete object
await httpx.put(f"{BASE_URL}/api/customers/{customer_id}", json=customer)
```

### 3. Use Query Parameters Properly
```python
# ✅ CORRECT
await httpx.get(f"{BASE_URL}/api/ro/list", params={"board": "ACTIVE"})

# ❌ WRONG
await httpx.get(f"{BASE_URL}/api/ro/list?board=ACTIVE")  # URL encoding issues
```

### 4. Handle Async Properly
```python
# For multiple independent requests
estimates, payments, auth = await asyncio.gather(
    httpx.get(f"{BASE_URL}/api/ro/{ro_id}/estimate"),
    httpx.get(f"{BASE_URL}/api/payments/{ro_id}"),
    httpx.get(f"{BASE_URL}/api/auth/authorizations/{ro_id}")
)
```

---

## Full API Reference

**Interactive Docs:** https://tm-fastapi-backend-production.up.railway.app/docs

**Complete TM API Documentation:** https://github.com/davefmurray/tm-api-docs

**Specific Guides:**
- Authorization: `docs/api/tm_authorization_api.md`
- Payments: `docs/api/tm_payment_invoice_api.md`
- Jobs: `docs/workflows/tm_job_creation_complete_guide.md`
- Customers: `docs/api/tm_customer_vehicle_crud_api.md`
- Dashboard: `docs/api/tm_dashboard_api.md`
- Calendar: `docs/api/tm_appointments_calendar_api.md`

---

## Support

**Issues:** https://github.com/davefmurray/tm-fastapi-backend/issues
**API Docs:** https://github.com/davefmurray/tm-api-docs
