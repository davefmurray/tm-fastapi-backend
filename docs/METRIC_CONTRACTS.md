# Metric Contracts: Source of Truth Definitions

**Version:** 2.0
**Date:** November 28, 2025
**Status:** ACTIVE - All dashboard code must follow these rules

---

## Warehouse-Backed Metrics (Dashboard Source of Truth)

**The new dashboard reads EXCLUSIVELY from these warehouse tables:**

- `daily_shop_metrics` - Aggregated daily KPIs
- `ro_snapshots` - Individual RO point-in-time records

**Data Flow:**
```
TM API → repair_orders → ro_snapshots → daily_shop_metrics → Dashboard
```

### daily_shop_metrics Fields

| Field | Definition | Unit |
|-------|------------|------|
| `ro_count` | Total ROs for the day (snapshot count) | count |
| `authorized_revenue` | SUM of authorized_revenue from ro_snapshots | cents |
| `authorized_cost` | SUM of authorized_cost from ro_snapshots | cents |
| `authorized_profit` | SUM of authorized_profit from ro_snapshots | cents |
| `authorized_gp_percent` | (authorized_profit / authorized_revenue) * 100 | % |
| `authorized_job_count` | SUM of authorized job counts | count |
| `parts_revenue` | SUM of parts_revenue from authorized jobs | cents |
| `parts_cost` | SUM of parts_cost from authorized jobs | cents |
| `parts_profit` | parts_revenue - parts_cost | cents |
| `labor_revenue` | SUM of labor_revenue from authorized jobs | cents |
| `labor_cost` | SUM of labor_cost from authorized jobs | cents |
| `labor_profit` | labor_revenue - labor_cost | cents |
| `labor_hours` | SUM of billed hours from authorized jobs | decimal |
| `sublet_revenue` | SUM of sublet retail from authorized jobs | cents |
| `sublet_cost` | SUM of sublet cost from authorized jobs | cents |
| `fees_total` | SUM of fees from authorized jobs | cents |
| `tax_total` | SUM of tax amounts | cents |
| `avg_ro_value` | authorized_revenue / ro_count | cents |
| `avg_ro_profit` | authorized_profit / ro_count | cents |
| `avg_labor_rate` | labor_revenue / labor_hours | cents/hour |
| `gp_per_labor_hour` | labor_profit / labor_hours | cents/hour |
| `potential_revenue` | SUM of potential_revenue (all jobs) | cents |
| `authorization_rate` | (authorized_revenue / potential_revenue) * 100 | % |

### Derived Dashboard KPIs

| KPI | Formula | Notes |
|-----|---------|-------|
| **ARO (Avg Repair Order)** | `authorized_revenue / ro_count / 100` | Display as dollars |
| **Car Count** | `ro_count` | Direct field |
| **GP Dollars** | `authorized_profit / 100` | Display as dollars |
| **GP%** | `authorized_gp_percent` | Direct field (already %) |
| **Billed Hours** | `labor_hours` | Direct field |
| **Effective Labor Rate** | `avg_labor_rate / 100` | Display as $/hour |
| **Authorization Rate** | `authorization_rate` | Direct field (already %) |
| **Parts GP%** | `(parts_profit / parts_revenue) * 100` | Calculated |
| **Labor GP%** | `(labor_profit / labor_revenue) * 100` | Calculated |

### Period Aggregation

For date ranges (MTD, last 30 days, etc.):
```sql
SELECT
    SUM(ro_count) as car_count,
    SUM(authorized_revenue) as total_revenue,
    SUM(authorized_profit) as total_profit,
    SUM(authorized_profit) * 100.0 / NULLIF(SUM(authorized_revenue), 0) as gp_percent,
    SUM(authorized_revenue) * 1.0 / NULLIF(SUM(ro_count), 0) as aro,
    SUM(labor_hours) as total_hours
FROM daily_shop_metrics
WHERE shop_id = ?
  AND metric_date BETWEEN ? AND ?
```

---

## Core Principle

**NEVER mix "potential" (all jobs) and "authorized" (approved jobs) in the same metric without explicit labeling.**

Every metric displayed must be tagged as either:
- `[POTENTIAL]` - includes all jobs regardless of authorization
- `[AUTHORIZED]` - includes only jobs where `job.authorized = true`

---

## Revenue Metrics

### Authorized Revenue (Committed Sales)
```
Label: "Authorized Revenue" or "Committed Sales"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: totalProfit.retail (in cents)

Alternative calculation:
  SUM(job.parts[].total + job.labor[].total + job.fees[].total)
  WHERE job.authorized = true
  FROM /api/repair-order/{roId}/estimate
```

### Potential Revenue (Full Estimate)
```
Label: "Potential Revenue" or "Full Estimate"
Tag: [POTENTIAL]

Source: /api/repair-order/{roId}/estimate
Field: estimate.total (in cents, includes tax)

Alternative calculation:
  SUM(job.parts[].total + job.labor[].total + job.fees[].total)
  FOR ALL jobs (no filter)
```

### Pending Revenue (Not Yet Authorized)
```
Label: "Pending Authorization"
Tag: [DERIVED]

Calculation: Potential Revenue - Authorized Revenue
```

---

## Profit Metrics

### Authorized Gross Profit
```
Label: "Gross Profit" or "GP"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: totalProfit.profit (in cents)

This is THE source of truth for GP.
Do NOT calculate GP manually - use this endpoint.
```

### Authorized GP Margin
```
Label: "GP%" or "Margin"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: totalProfit.margin (decimal, multiply by 100 for %)
```

### Potential Gross Profit
```
Label: "Potential GP" (rarely needed)
Tag: [POTENTIAL]

Calculation:
  SUM(job.parts[].total - job.parts[].cost * job.parts[].quantity)
  + SUM(job.labor[].total - (job.labor[].hours * tech.hourlyRate))
  FOR ALL jobs

Warning: Requires technician hourly rates which may be missing.
```

---

## Labor Metrics

### Authorized Labor Revenue
```
Label: "Labor Sales"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: laborProfit.retail (in cents)
```

### Authorized Labor Cost
```
Label: "Labor Cost"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: laborProfit.cost (in cents)

This uses actual technician hourly rates.
```

### Authorized Labor Profit
```
Label: "Labor Profit"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: laborProfit.profit (in cents)
```

### Authorized Labor Hours
```
Label: "Billed Hours"
Tag: [AUTHORIZED]

Source: /api/repair-order/{roId}/profit/labor
Field: laborProfit.hours
```

### Potential Labor (All Jobs)
```
Label: "Potential Labor Hours/Revenue"
Tag: [POTENTIAL]

Calculation:
  SUM(job.labor[].hours) or SUM(job.labor[].total)
  FOR ALL jobs
  FROM /api/repair-order/{roId}/estimate
```

---

## Parts Metrics

### Authorized Parts Revenue
```
Label: "Parts Sales"
Tag: [AUTHORIZED]

Calculation: totalProfit.retail - laborProfit.retail
Source: /api/repair-order/{roId}/profit/labor

Note: No explicit partsProfit field exists.
```

### Authorized Parts Cost
```
Label: "Parts Cost"
Tag: [AUTHORIZED]

Calculation: totalProfit.cost - laborProfit.cost
Source: /api/repair-order/{roId}/profit/labor
```

### Authorized Parts Profit
```
Label: "Parts Profit"
Tag: [AUTHORIZED]

Calculation: totalProfit.profit - laborProfit.profit
Source: /api/repair-order/{roId}/profit/labor
```

### Potential Parts (All Jobs)
```
Label: "Potential Parts Revenue"
Tag: [POTENTIAL]

Calculation:
  SUM(job.parts[].total)
  FOR ALL jobs
  FROM /api/repair-order/{roId}/estimate
```

---

## Tax, Fees, and Discounts

### Tax
```
Source: /api/repair-order/{roId}/estimate
Field: estimate.tax (often NULL)

Fallback calculation:
  estimate.total - (sum of all job line items)

Warning: Tax field is frequently null. Use fallback.
```

### Fees
```
Source: /api/repair-order/{roId}/estimate
Field: job.fees[] array within each job

Always filter by job.authorized if calculating authorized fees.
```

### Discounts
```
Source: /api/repair-order/{roId}/estimate
Field: job.discount within each job (in cents)

Always filter by job.authorized if calculating authorized discounts.
```

---

## Status and Dates

### RO Status
```
Source: /api/shop/{shopId}/job-board-group-by
Field: status or board parameter

Values:
- ACTIVE = Work in Progress (WIP)
- POSTED = Invoiced
- COMPLETE = Completed/Closed
```

### Authorization Date
```
Source: /api/repair-order/{roId}/estimate
Field: job.authorizedDate (ISO 8601 timestamp)

Use this for "when was this job sold" queries.
```

### Posted Date
```
Source: /api/shop/{shopId}/job-board-group-by
Field: postedDate

Use this for "when was this RO invoiced" queries.
This is what TM's Profit Details Report uses.
```

---

## Forbidden Patterns

### DO NOT:

1. **Mix endpoints without filtering**
   ```python
   # WRONG - mixes all jobs with authorized profit
   revenue = estimate['total']
   profit = profit_labor['totalProfit']['profit']
   margin = profit / revenue  # INVALID COMPARISON
   ```

2. **Assume subtotal exists**
   ```python
   # WRONG - subtotal is often null
   subtotal = estimate['subtotal']  # May be None!
   ```

3. **Calculate GP manually when endpoint exists**
   ```python
   # WRONG - manual calculation may miss costs
   gp = sum(parts_retail) - sum(parts_cost)

   # RIGHT - use the endpoint
   gp = profit_labor['totalProfit']['profit']
   ```

4. **Show "total" metrics without specifying authorized vs potential**
   ```python
   # WRONG - ambiguous
   display("Total Sales: $5,000")

   # RIGHT - explicit
   display("Authorized Sales: $5,000")
   display("Potential Sales: $7,500")
   ```

---

## Required Labels for Dashboard

Every metric card on the dashboard MUST use one of these labels:

| Metric Type | Required Label |
|-------------|----------------|
| Authorized Revenue | "Committed Sales" or "Authorized Sales" |
| Potential Revenue | "Potential Sales" or "Full Estimate" |
| Gross Profit | "Gross Profit (Authorized)" |
| Labor Sales | "Labor (Authorized)" |
| Parts Sales | "Parts (Authorized)" |
| Pending | "Pending Authorization" |

---

## Validation Checks

Before displaying any metric, the code should validate:

1. **For authorized metrics:**
   - Source is `/profit/labor` endpoint OR
   - Source is `/estimate` with `job.authorized = true` filter applied

2. **For potential metrics:**
   - Source is `/estimate` with NO authorization filter
   - Label explicitly says "potential" or "full estimate"

3. **For comparisons:**
   - Both values come from same reality (both authorized OR both potential)
   - If comparing across realities, label as "Authorization Rate" or similar

---

## Example: Correct Dashboard Card

```javascript
// Authorized Sales Card
const authorizedSales = profitLabor.totalProfit.retail / 100;
const label = "Committed Sales";  // Clear label
const tag = "[AUTHORIZED]";       // Internal tag for debugging

// Potential Sales Card
const potentialSales = estimate.total / 100;
const label = "Full Estimate Value";
const tag = "[POTENTIAL]";

// Authorization Rate Card
const authRate = (authorizedSales / potentialSales) * 100;
const label = "Authorization Rate";
const tag = "[DERIVED]";
```
