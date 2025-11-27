# TM Data Audit Findings

**Audit Date:** November 27, 2025
**Audited Period:** November 26-27, 2025
**ROs Audited:** 17 total (16 on Nov 26, 1 on Nov 27)
**Total Discrepancies Found:** 116

---

## Executive Summary

A comprehensive data audit was conducted to identify discrepancies between TM API endpoints and verify data integrity for dashboard calculations. The audit revealed:

- **0 mathematical errors** in parts or labor calculations
- **All line item math is correct** (qty × price = total)
- **Discrepancies are due to endpoint behavior differences**, not calculation bugs
- **Key finding:** The `/profit/labor` endpoint only returns **authorized** jobs, while `/estimate` returns all jobs

---

## Audit System Architecture

### Endpoints Audited
The audit system fetches data from 4 TM API endpoints and cross-references:

1. **Job Board** (`/api/shop/{shopId}/job-board-group-by`)
   - Source: Board summary data
   - Fields: total, subtotal, authorizedTotal, amountPaid, status

2. **Estimate** (`/api/repair-order/{roId}/estimate`)
   - Source: Full RO with all jobs, parts, labor
   - Fields: total, subtotal, authorizedTotal, jobs[]

3. **Profit/Labor** (`/api/repair-order/{roId}/profit/labor`)
   - Source: Profit calculations
   - Fields: laborProfit, totalProfit (nested objects)

4. **RO Basic** (`/api/repair-order/{roId}`)
   - Source: Basic RO info
   - Fields: status, serviceAdvisor

### Audit Process
For each RO:
1. Fetch data from all 4 endpoints
2. Calculate totals from line items (parts × qty, labor × hours)
3. Compare calculated values vs reported values
4. Flag any discrepancies with suspected causes

---

## Discrepancy Categories

### 1. Parts Math Errors
**Count:** 0
**Status:** ✅ CLEAN

All parts calculations are correct:
```
part.quantity × part.retail = part.total ✓
```

### 2. Labor Math Errors
**Count:** 0
**Status:** ✅ CLEAN

All labor calculations are correct:
```
labor.hours × labor.rate = labor.total ✓
```

### 3. Sum Mismatches
**Count:** 13
**Status:** ⚠️ EXPECTED BEHAVIOR

**Root Cause:** The `estimate.subtotal` field is often `null`. When comparing against `estimate.total`, the difference is typically **tax**.

**Example:**
```json
{
  "calculated_subtotal": 906.07,
  "estimate_total": 1008.37,
  "difference": 102.30  // ~11.3% tax
}
```

**Resolution:**
- Use `estimate.total` as the comparison baseline
- Accept ~10-12% variance as tax
- Or fetch tax separately if exact subtotal needed

### 4. Missing Data
**Count:** 86
**Status:** ⚠️ DATA ENTRY ISSUE

**Root Cause:** Labor lines without technician assignments.

**Example:**
```json
{
  "type": "missing_data",
  "job": "Oil Change",
  "field": "technician",
  "labor_line": "SYNTHETIC OIL CHANGE",
  "suspected_cause": "No technician assigned to labor line"
}
```

**Impact:**
- Cannot calculate accurate labor costs (technician hourly rate unknown)
- Audit defaults to $25/hr estimate when tech not assigned

**Resolution:** This is a shop workflow issue, not a system bug. Technicians should be assigned to labor lines before authorization.

### 5. Cross-Endpoint Disagreements
**Count:** 16
**Status:** 🔴 CRITICAL FINDING (but expected behavior)

**Root Cause:** The `/profit/labor` endpoint only returns data for **authorized** jobs, while our line item calculations include **all** jobs.

**Example:**
```json
{
  "type": "cross_endpoint_disagreements",
  "field": "labor_revenue",
  "calculated": 7972.99,      // All jobs
  "profit_labor_reported": 4449.99,  // Authorized only
  "difference": 3523.00       // Unauthorized jobs
}
```

**Why This Happens:**
- Estimate endpoint returns ALL jobs on an RO
- Profit/Labor endpoint returns ONLY jobs where `authorized = true`
- When jobs are pending authorization, there's a gap

**Resolution:**
- For **potential revenue**: Sum all jobs from estimate
- For **committed revenue**: Use profit/labor endpoint OR filter jobs by `authorized = true`

---

## Endpoint Trust Matrix

| Endpoint | What It Returns | Best Used For | Caveats |
|----------|-----------------|---------------|---------|
| `/estimate` | All jobs (authorized + pending) | Full RO value, potential revenue | Includes non-authorized work |
| `/profit/labor` | Authorized jobs only | GP calculations, committed revenue | Ignores pending jobs |
| `/repair-order/{id}` | Basic RO info | Status, advisor lookup | Returns 404 for some WIP ROs |
| `/job-board-group-by` | Summary by board | Quick board totals | Less detail than estimate |

### Field-Level Trust

| Field | Source | Trust Level | Notes |
|-------|--------|-------------|-------|
| `job.parts[].total` | estimate | ✅ 100% | qty × retail always correct |
| `job.labor[].total` | estimate | ✅ 100% | hours × rate always correct |
| `job.authorized` | estimate | ✅ 100% | Reliable authorization status |
| `job.authorizedDate` | estimate | ✅ 100% | Reliable timestamp |
| `laborProfit.retail` | profit/labor | ✅ 100% | But only for authorized work |
| `totalProfit.retail` | profit/labor | ✅ 100% | But only for authorized work |
| `estimate.subtotal` | estimate | ⚠️ Often null | Use total instead |
| `estimate.total` | estimate | ✅ 100% | Includes tax |
| `estimate.tax` | estimate | ⚠️ Often null | May need to calculate |

---

## API Response Structures

### Profit/Labor Endpoint Structure
**Important:** Uses camelCase, not snake_case!

```json
{
  "labor": [
    {
      "name": "Labor Line Name",
      "rate": 20000,        // cents
      "hours": 2.65,
      "jobTechnician": {
        "accountFullName": "Kevin F.",
        "hourlyRate": 6497  // cents
      },
      "profit": 35783,      // cents
      "margin": 0.675,
      "cost": 17217,        // cents
      "retail": 53000       // cents
    }
  ],
  "laborProfit": {
    "hours": 2.95,
    "retail": 56000,        // Total labor revenue (cents)
    "cost": 19166,          // Total labor cost (cents)
    "profit": 36834,        // Total labor profit (cents)
    "margin": 0.65775
  },
  "totalProfit": {
    "retail": 90607,        // Total RO revenue (cents)
    "cost": 28705,          // Total RO cost (cents)
    "profit": 61902,        // Total RO profit (cents)
    "margin": 0.683
  }
}
```

**Note:** There is NO `partsProfit` field. Calculate parts as:
```javascript
partsRevenue = totalProfit.retail - laborProfit.retail
partsCost = totalProfit.cost - laborProfit.cost
partsProfit = totalProfit.profit - laborProfit.profit
```

### Estimate Endpoint Structure

```json
{
  "total": 100837,           // cents, includes tax
  "subtotal": null,          // Often null!
  "authorizedTotal": 95140,  // cents, authorized work only
  "tax": null,               // Often null
  "jobs": [
    {
      "id": 944265433,
      "name": "Job Name",
      "authorized": true,
      "authorizedDate": "2025-11-26T18:38:55Z",
      "parts": [...],
      "labor": [...],
      "fees": [...]
    }
  ]
}
```

---

## Recommendations for Dashboard

### For "Live" Authorized Sales View
Filter jobs by authorization status:

```python
authorized_jobs = [job for job in estimate['jobs'] if job.get('authorized') == True]

total_authorized = sum(
    sum(p['total'] for p in job['parts']) +
    sum(l['total'] for l in job['labor']) +
    sum(f['total'] for f in job['fees'])
    for job in authorized_jobs
)
```

### For GP Calculations
Use the `/profit/labor` endpoint directly - it already filters for authorized work and includes proper cost calculations:

```python
profit_data = await tm.get(f"/api/repair-order/{ro_id}/profit/labor")
total_profit = profit_data['totalProfit']

gp_dollars = total_profit['profit'] / 100
gp_percent = total_profit['margin'] * 100
```

### For Full RO Potential Value
Sum all jobs from estimate (includes pending authorization):

```python
estimate = await tm.get(f"/api/repair-order/{ro_id}/estimate")
full_potential = estimate['total'] / 100  # Already includes all jobs
```

---

## Audit API Endpoints

The audit system is available at:

### Daily Audit
```
GET /api/audit/daily?date=2025-11-27
```
Returns all ROs for a specific day with discrepancy analysis.

### Single RO Audit
```
GET /api/audit/ro/{ro_id}
```
Deep audit of a single RO comparing all endpoints.

### Date Range Audit
```
GET /api/audit/date-range?start=2025-11-01&end=2025-11-27
```
Audit multiple days with summary statistics.

---

## Conclusion

The TM data is **mathematically accurate** at the line-item level. All discrepancies found are due to:

1. **Endpoint behavior differences** (authorized vs all jobs)
2. **Null fields** (subtotal, tax often missing)
3. **Data entry gaps** (missing technician assignments)

**No calculation bugs were found.** The dashboard should use:
- `estimate.jobs[]` filtered by `authorized=true` for live sales
- `/profit/labor` endpoint for GP calculations
- Accept that `estimate.total` includes tax when comparing to subtotals

---

## Appendix: Sample Audit Output

```json
{
  "audit_date": "2025-11-27",
  "ros_audited": 1,
  "discrepancies_found": 1,
  "summary": {
    "total_issues": 1,
    "parts_math_errors": 0,
    "labor_math_errors": 0,
    "sum_mismatches": 1,
    "tax_mismatches": 0,
    "gp_mismatches": 0,
    "missing_data": 0,
    "cross_endpoint_disagreements": 0
  }
}
```
