# True GP Calculation System - Master Guide

## Overview

The True GP system provides **accurate gross profit calculations** that fix known issues with Tekmetric's built-in aggregates. It's built in 3 tiers:

| Tier | Purpose |
|------|---------|
| **Tier 1** | Core GP fixes (quantity handling, tech rates, fees, discounts) |
| **Tier 2** | Structured responses (tax/fee attribution, caching) |
| **Tier 3** | Advanced analytics (tech performance, parts margin, variance) |

---

## Quick Start: Which Endpoint Do I Use?

| I want to... | Use this endpoint |
|--------------|-------------------|
| Show today's GP metrics on dashboard | `GET /api/dashboard/true-metrics` |
| Compare my numbers vs TM's numbers | `GET /api/analytics/variance-analysis` |
| See profit per technician | `GET /api/analytics/tech-performance` |
| Analyze parts margins | `GET /api/analytics/parts-margin` |
| Check labor efficiency | `GET /api/analytics/labor-efficiency` |
| Get everything in one call | `GET /api/analytics/full-analysis` |

---

## Endpoint Reference

### 1. True Metrics (Main Dashboard Endpoint)

**`GET /api/dashboard/true-metrics?start=2025-11-01&end=2025-11-26`**

This is your **primary dashboard endpoint**. Use it for KPI cards.

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "metrics": {
    "sales": 45230.50,
    "cost": 18540.25,
    "gross_profit": 26690.25,
    "gp_percentage": 59.02,
    "aro": 1507.68,
    "car_count": 30,
    "fee_profit": 892.50,
    "discount_total": 450.00
  },
  "parts_summary": {
    "retail": 22500.00,
    "cost": 11250.00,
    "profit": 11250.00,
    "margin_pct": 50.0
  },
  "labor_summary": {
    "retail": 18500.00,
    "cost": 5400.00,
    "profit": 13100.00,
    "margin_pct": 70.81
  },
  "sublet_summary": {
    "retail": 3500.00,
    "cost": 1890.25,
    "profit": 1609.75,
    "margin_pct": 46.0
  },
  "tax_breakdown": {
    "parts_tax": 1687.50,
    "labor_tax": 1387.50,
    "fees_tax": 66.94,
    "sublet_tax": 262.50,
    "total_tax": 3404.44
  },
  "fee_breakdown": {
    "total_fees": 892.50,
    "by_category": {
      "shop_supplies": 675.00,
      "environmental": 217.50
    }
  },
  "source": "TRUE_GP_TIER2",
  "calculated_at": "2025-11-26T14:30:00"
}
```

#### Dashboard Usage Example (JavaScript)

```javascript
// Fetch true metrics for date range
async function loadDashboard(startDate, endDate) {
  const response = await fetch(
    `/api/dashboard/true-metrics?start=${startDate}&end=${endDate}`
  );
  const data = await response.json();

  // Update KPI cards
  document.getElementById('sales').textContent = `$${data.metrics.sales.toLocaleString()}`;
  document.getElementById('gp-dollars').textContent = `$${data.metrics.gross_profit.toLocaleString()}`;
  document.getElementById('gp-percent').textContent = `${data.metrics.gp_percentage}%`;
  document.getElementById('aro').textContent = `$${data.metrics.aro.toLocaleString()}`;
  document.getElementById('car-count').textContent = data.metrics.car_count;

  // Update category breakdown chart
  updatePieChart({
    parts: data.parts_summary.profit,
    labor: data.labor_summary.profit,
    sublet: data.sublet_summary.profit,
    fees: data.metrics.fee_profit
  });
}
```

---

### 2. Tech Performance

**`GET /api/analytics/tech-performance?start=2025-11-01&end=2025-11-26`**

Shows profit metrics **per technician**.

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "technicians": [
    {
      "tech_id": 12345,
      "tech_name": "John Smith",
      "hourly_rate": 35.00,
      "hours_billed": 45.5,
      "labor_revenue": 8167.50,
      "labor_cost": 1592.50,
      "labor_profit": 6575.00,
      "labor_margin_pct": 80.5,
      "gp_per_hour": 144.51,
      "jobs_worked": 28,
      "ros_worked": 18
    },
    {
      "tech_id": 0,
      "tech_name": "Shop Average (shop_average)",
      "hourly_rate": 32.50,
      "hours_billed": 12.0,
      "labor_revenue": 2154.00,
      "labor_cost": 390.00,
      "labor_profit": 1764.00,
      "labor_margin_pct": 81.89,
      "gp_per_hour": 147.00,
      "jobs_worked": 8,
      "ros_worked": 5
    }
  ],
  "summary": {
    "tech_count": 2,
    "total_hours": 57.5,
    "total_labor_revenue": 10321.50,
    "total_labor_profit": 8339.00,
    "ros_analyzed": 23
  }
}
```

#### Dashboard Usage: Tech Leaderboard

```javascript
async function loadTechLeaderboard(start, end) {
  const response = await fetch(`/api/analytics/tech-performance?start=${start}&end=${end}`);
  const data = await response.json();

  // Sort by profit and display
  const techs = data.technicians.sort((a, b) => b.labor_profit - a.labor_profit);

  techs.forEach(tech => {
    addLeaderboardRow({
      name: tech.tech_name,
      hours: tech.hours_billed,
      profit: `$${tech.labor_profit.toLocaleString()}`,
      gpPerHour: `$${tech.gp_per_hour.toFixed(2)}/hr`,
      margin: `${tech.labor_margin_pct}%`
    });
  });
}
```

---

### 3. Parts Margin Analysis

**`GET /api/analytics/parts-margin?start=2025-11-01&end=2025-11-26`**

Analyzes parts margins with **high/low performers**.

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "summary": {
    "total_retail": 22500.00,
    "total_cost": 11250.00,
    "total_profit": 11250.00,
    "overall_margin_pct": 50.0,
    "total_line_items": 145,
    "avg_quantity": 1.35
  },
  "by_quantity": {
    "single_items": {
      "count": 120,
      "retail": 18000.00,
      "cost": 8800.00,
      "profit": 9200.00,
      "margin_pct": 51.11
    },
    "multi_items": {
      "count": 25,
      "retail": 4500.00,
      "cost": 2450.00,
      "profit": 2050.00,
      "margin_pct": 45.56
    }
  },
  "highest_margin_parts": [
    { "name": "Oil Filter", "quantity": 1, "cost": 4.50, "retail": 12.00, "profit": 7.50, "margin_pct": 62.5 }
  ],
  "lowest_margin_parts": [
    { "name": "Brake Rotor", "quantity": 2, "cost": 85.00, "retail": 95.00, "profit": 10.00, "margin_pct": 10.53 }
  ]
}
```

---

### 4. Labor Efficiency

**`GET /api/analytics/labor-efficiency?start=2025-11-01&end=2025-11-26`**

Shows labor metrics **by rate source** (helps identify where tech rates are missing).

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "summary": {
    "total_hours_billed": 57.5,
    "total_revenue": 10321.50,
    "total_cost": 1982.50,
    "total_profit": 8339.00,
    "overall_margin_pct": 80.79,
    "total_labor_items": 36
  },
  "rates": {
    "avg_retail_rate": 179.50,
    "avg_tech_cost_rate": 34.48,
    "effective_spread": 145.02,
    "gp_per_hour": 145.03
  },
  "by_rate_source": {
    "assigned": {
      "hours": 45.5,
      "revenue": 8167.50,
      "cost": 1592.50,
      "profit": 6575.00,
      "margin_pct": 80.5,
      "count": 28
    },
    "shop_average": {
      "hours": 12.0,
      "revenue": 2154.00,
      "cost": 390.00,
      "profit": 1764.00,
      "margin_pct": 81.89,
      "count": 8
    },
    "default": {
      "hours": 0,
      "revenue": 0,
      "cost": 0,
      "profit": 0,
      "margin_pct": 0,
      "count": 0
    }
  },
  "rate_source_note": {
    "assigned": "Tech rate from labor assignment",
    "shop_average": "Fallback to shop average tech rate",
    "default": "Fallback to $25/hr default"
  }
}
```

---

### 5. Variance Analysis

**`GET /api/analytics/variance-analysis?start=2025-11-01&end=2025-11-26`**

**Explains WHY your numbers differ from TM's dashboard.**

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "tm_aggregates": {
    "sales": 46500.00,
    "car_count": 32,
    "average_ro": 1453.13,
    "source": "TM Dashboard API"
  },
  "true_calculations": {
    "sales": 45230.50,
    "cost": 18540.25,
    "gross_profit": 26690.25,
    "gp_percentage": 59.02,
    "car_count": 30,
    "average_ro": 1507.68,
    "source": "TRUE_GP_TIER3"
  },
  "variance": {
    "sales_delta": -1269.50,
    "sales_delta_pct": -2.73,
    "car_count_delta": -2,
    "aro_delta": 54.55
  },
  "variance_reasons": [
    "Car count differs by -2: TM uses postedDate, we use authorizedDate",
    "Sales differ by $1269.50: Check date filtering and RO inclusion criteria",
    "Tech rate fallback used for 8/36 labor items - affects GP calculation",
    "25 parts with qty > 1 - potential TM quantity handling issues",
    "Fee profit of $892.50 included (100% margin) - may not match TM GP"
  ]
}
```

---

### 6. Full Analysis (Everything in One Call)

**`GET /api/analytics/full-analysis?start=2025-11-01&end=2025-11-26`**

Best for **comprehensive reports** - combines all metrics.

```json
{
  "date_range": { "start": "2025-11-01", "end": "2025-11-26" },
  "summary": {
    "total_sales": 45230.50,
    "total_cost": 18540.25,
    "gross_profit": 26690.25,
    "gp_percentage": 59.02,
    "car_count": 30,
    "aro": 1507.68
  },
  "category_breakdown": {
    "parts": { "revenue": 22500.00, "cost": 11250.00, "profit": 11250.00, "margin_pct": 50.0 },
    "labor": { "revenue": 18500.00, "cost": 5400.00, "profit": 13100.00, "margin_pct": 70.81, "hours": 57.5 },
    "fees": { "revenue": 892.50, "cost": 0, "profit": 892.50, "margin_pct": 100.0 }
  },
  "top_technicians": [
    { "name": "John Smith", "profit": 6575.00, "hours": 45.5 },
    { "name": "Mike Jones", "profit": 4200.00, "hours": 32.0 }
  ],
  "labor_rate_effectiveness": {
    "avg_retail_rate": 179.50,
    "avg_cost_rate": 34.48,
    "spread": 145.02,
    "gp_per_hour": 145.03
  },
  "parts_insights": {
    "total_line_items": 145,
    "avg_quantity": 1.35,
    "multi_qty_items": 25
  }
}
```

---

## How the Calculations Work

### What We Fix vs TM

| Issue | TM Behavior | Our Fix |
|-------|-------------|---------|
| **Parts qty > 1** | Sometimes cost is per-unit, sometimes total | Detect format, always calculate correctly |
| **Missing tech rate** | Uses $0 or unknown | Fallback: assigned → shop avg → $25 default |
| **Fees** | Not always in GP | Include at 100% margin |
| **Discounts** | Sometimes missed | Handle job-level and RO-level |
| **Date filtering** | Uses postedDate | Uses authorizedDate (when work was sold) |

### GP Formula

```
Gross Profit = Total Retail - Total Cost

Where:
- Total Retail = Parts + Labor + Sublet + Fees - Discounts
- Total Cost = Parts Cost + Labor Cost (tech rate × hours) + Sublet Cost
- Fees have 0 cost (100% margin)

GP% = (Gross Profit / Total Retail) × 100
ARO = Total Retail / Car Count
```

### Tech Rate Fallback Chain

```
1. Check labor.technician.hourlyRate (assigned tech)
   ↓ if missing
2. Use shop average tech rate (from /employees-lite)
   ↓ if missing
3. Use $25/hr default
```

---

## Dashboard Integration Examples

### Example 1: KPI Cards

```html
<div class="kpi-grid">
  <div class="kpi-card">
    <span class="label">Sales</span>
    <span class="value" id="sales">$0</span>
  </div>
  <div class="kpi-card">
    <span class="label">Gross Profit</span>
    <span class="value" id="gp-dollars">$0</span>
  </div>
  <div class="kpi-card">
    <span class="label">GP%</span>
    <span class="value" id="gp-percent">0%</span>
  </div>
  <div class="kpi-card">
    <span class="label">ARO</span>
    <span class="value" id="aro">$0</span>
  </div>
  <div class="kpi-card">
    <span class="label">Car Count</span>
    <span class="value" id="car-count">0</span>
  </div>
</div>

<script>
async function refreshDashboard() {
  const today = new Date().toISOString().split('T')[0];
  const res = await fetch(`/api/dashboard/true-metrics?start=${today}&end=${today}`);
  const data = await res.json();

  document.getElementById('sales').textContent = `$${data.metrics.sales.toLocaleString()}`;
  document.getElementById('gp-dollars').textContent = `$${data.metrics.gross_profit.toLocaleString()}`;
  document.getElementById('gp-percent').textContent = `${data.metrics.gp_percentage}%`;
  document.getElementById('aro').textContent = `$${data.metrics.aro.toLocaleString()}`;
  document.getElementById('car-count').textContent = data.metrics.car_count;
}
</script>
```

### Example 2: Category Breakdown Chart

```javascript
// Using Chart.js
async function loadCategoryChart(start, end) {
  const res = await fetch(`/api/dashboard/true-metrics?start=${start}&end=${end}`);
  const data = await res.json();

  new Chart(document.getElementById('category-chart'), {
    type: 'doughnut',
    data: {
      labels: ['Parts', 'Labor', 'Sublet', 'Fees'],
      datasets: [{
        data: [
          data.parts_summary.profit,
          data.labor_summary.profit,
          data.sublet_summary.profit,
          data.metrics.fee_profit
        ],
        backgroundColor: ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0']
      }]
    }
  });
}
```

### Example 3: TM vs True Comparison

```javascript
async function showVariance(start, end) {
  const res = await fetch(`/api/analytics/variance-analysis?start=${start}&end=${end}`);
  const data = await res.json();

  // Show variance alert if significant
  if (Math.abs(data.variance.sales_delta_pct) > 5) {
    showAlert(`Sales differ from TM by ${data.variance.sales_delta_pct}%`);
  }

  // Display reasons
  data.variance_reasons.forEach(reason => {
    addVarianceNote(reason);
  });
}
```

---

## API Base URL

```
Development: http://localhost:8000
Production:  https://your-deployed-url.com
```

## Authentication

All endpoints require the TM auth token to be configured in environment variables:

```bash
TM_AUTH_TOKEN=your-jwt-token
TM_SHOP_ID=6212
```

---

## Summary

| Endpoint | Use For |
|----------|---------|
| `/api/dashboard/true-metrics` | Main KPI dashboard |
| `/api/analytics/tech-performance` | Tech leaderboard |
| `/api/analytics/parts-margin` | Parts profitability analysis |
| `/api/analytics/labor-efficiency` | Labor rate analysis |
| `/api/analytics/variance-analysis` | Debug TM vs True differences |
| `/api/analytics/full-analysis` | Comprehensive reports |

**All values are in dollars (not cents).** The system handles conversion internally.
