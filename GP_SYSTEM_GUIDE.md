# True GP Calculation System - Master Guide

## Overview

The True GP system provides **accurate gross profit calculations** that fix known issues with Tekmetric's built-in aggregates. It's built in 7 tiers:

| Tier | Purpose |
|------|---------|
| **Tier 1** | Core GP fixes (quantity handling, tech rates, fees, discounts) |
| **Tier 2** | Structured responses (tax/fee attribution, caching) |
| **Tier 3** | Advanced analytics (tech performance, parts margin, variance) |
| **Tier 4** | Database persistence (historical tracking, trend analysis) |
| **Tier 5** | Real-time dashboard (WebSocket streaming, live updates) |
| **Tier 6** | Service advisor tracking (sales, GP, goals) |
| **Tier 7** | Trend analysis & forecasting (WoW, MoM, rolling averages, linear regression) |

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
| **Save today's metrics to database** | `POST /api/history/snapshot/daily` |
| **View GP trends over time** | `GET /api/history/trends` |
| **Get historical daily snapshots** | `GET /api/history/snapshots/daily` |
| **Track specific RO over time** | `GET /api/history/ro/{ro_id}` |
| **Compare two time periods** | `GET /api/history/compare/periods` |
| **View tech performance history** | `GET /api/history/tech-performance` |
| **Connect to live dashboard** | `WS /api/realtime/ws` |
| **Start auto-refresh** | `POST /api/realtime/start` |
| **Send GP alert** | `POST /api/realtime/alert` |
| **Get advisor performance** | `GET /api/advisors/performance` |
| **Get advisor leaderboard** | `GET /api/advisors/leaderboard` |
| **Check advisor vs goals** | `GET /api/advisors/goals` |
| **Week-over-week comparison** | `GET /api/trends/wow` |
| **Month-over-month comparison** | `GET /api/trends/mom` |
| **Rolling averages** | `GET /api/trends/rolling-averages` |
| **GP forecasting** | `GET /api/trends/forecast` |
| **Day-of-week patterns** | `GET /api/trends/day-patterns` |
| **Best/worst days** | `GET /api/trends/extremes` |
| **Category trends** | `GET /api/trends/category-trends` |
| **Trend summary dashboard** | `GET /api/trends/summary` |

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

---

## Tier 4: Historical Persistence & Trends

Tier 4 adds **database storage** for GP calculations, enabling:
- Track GP trends over time
- Period-over-period comparisons
- Audit trail for calculations
- Tech performance history

### Database Setup (Supabase)

Create these tables in your Supabase dashboard:

```sql
-- Daily GP Snapshots
CREATE TABLE gp_daily_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    total_revenue INTEGER NOT NULL,
    total_cost INTEGER NOT NULL,
    total_gp_dollars INTEGER NOT NULL,
    gp_percentage DECIMAL(5,2) NOT NULL,
    ro_count INTEGER NOT NULL,
    aro_cents INTEGER NOT NULL,
    parts_revenue INTEGER DEFAULT 0,
    parts_cost INTEGER DEFAULT 0,
    parts_profit INTEGER DEFAULT 0,
    labor_revenue INTEGER DEFAULT 0,
    labor_cost INTEGER DEFAULT 0,
    labor_profit INTEGER DEFAULT 0,
    sublet_revenue INTEGER DEFAULT 0,
    sublet_cost INTEGER DEFAULT 0,
    sublet_profit INTEGER DEFAULT 0,
    fees_total INTEGER DEFAULT 0,
    taxes_total INTEGER DEFAULT 0,
    tech_hours_billed DECIMAL(10,2) DEFAULT 0,
    avg_tech_rate INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    calculation_method TEXT DEFAULT 'TRUE_GP_TIER4',
    UNIQUE(shop_id, snapshot_date)
);

-- RO History Records
CREATE TABLE gp_ro_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    ro_id INTEGER NOT NULL,
    ro_number TEXT,
    snapshot_date DATE NOT NULL,
    customer_name TEXT,
    vehicle_description TEXT,
    ro_status TEXT,
    total_revenue INTEGER NOT NULL,
    total_cost INTEGER NOT NULL,
    gp_dollars INTEGER NOT NULL,
    gp_percentage DECIMAL(5,2) NOT NULL,
    tm_reported_gp_pct DECIMAL(5,2),
    variance_pct DECIMAL(5,2),
    variance_reason TEXT,
    parts_breakdown JSONB,
    labor_breakdown JSONB,
    sublet_breakdown JSONB,
    fee_breakdown JSONB,
    tax_breakdown JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(shop_id, ro_id, snapshot_date)
);

-- Tech Performance History
CREATE TABLE gp_tech_performance (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    shop_id INTEGER NOT NULL,
    tech_id INTEGER NOT NULL,
    tech_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    hours_billed DECIMAL(10,2) NOT NULL,
    hourly_rate INTEGER NOT NULL,
    labor_revenue INTEGER NOT NULL,
    labor_cost INTEGER NOT NULL,
    labor_profit INTEGER NOT NULL,
    labor_margin_pct DECIMAL(5,2) NOT NULL,
    gp_per_hour INTEGER NOT NULL,
    jobs_worked INTEGER DEFAULT 0,
    ros_worked INTEGER DEFAULT 0,
    rate_source_counts JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(shop_id, tech_id, snapshot_date)
);

-- Indexes
CREATE INDEX idx_daily_snapshots_shop_date ON gp_daily_snapshots(shop_id, snapshot_date DESC);
CREATE INDEX idx_ro_history_shop_date ON gp_ro_history(shop_id, snapshot_date DESC);
CREATE INDEX idx_tech_performance_shop_date ON gp_tech_performance(shop_id, snapshot_date DESC);
```

### Environment Variables

```bash
# Add to your .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Optional: Custom table names
GP_DAILY_TABLE=gp_daily_snapshots
GP_RO_TABLE=gp_ro_history
GP_TECH_TABLE=gp_tech_performance
```

---

### 7. Create Daily Snapshot

**`POST /api/history/snapshot/daily?start_date=2025-11-26&end_date=2025-11-26`**

Creates a historical snapshot from current RO data. **Run this daily via cron.**

```json
{
  "success": true,
  "message": "Daily snapshot created successfully",
  "period": {
    "start": "2025-11-26",
    "end": "2025-11-26"
  },
  "summary": {
    "ros_processed": 30,
    "ro_records_stored": 30,
    "tech_records_stored": 5,
    "total_revenue": 45230.50,
    "gp_percentage": 59.02
  }
}
```

#### Cron Setup (Daily Snapshots)

```bash
# Add to crontab (run at 11:59 PM daily)
59 23 * * * curl -X POST "http://localhost:8000/api/history/snapshot/daily"
```

---

### 8. Get Daily Snapshots History

**`GET /api/history/snapshots/daily?days=30`**

Retrieves stored daily snapshots for trend analysis.

```json
{
  "period": {
    "start": "2025-10-27",
    "end": "2025-11-26",
    "days": 30
  },
  "count": 22,
  "snapshots": [
    {
      "snapshot_date": "2025-11-26",
      "total_revenue": 45230.50,
      "total_cost": 18540.25,
      "total_gp_dollars": 26690.25,
      "gp_percentage": 59.02,
      "ro_count": 30,
      "aro": 1507.68,
      "parts_profit": 11250.00,
      "labor_profit": 13100.00
    },
    {
      "snapshot_date": "2025-11-25",
      "total_revenue": 38750.00,
      "gp_percentage": 57.45
    }
  ]
}
```

---

### 9. Get GP Trends

**`GET /api/history/trends?days=30`**

Returns trend analysis with direction indicator.

```json
{
  "success": true,
  "analysis": {
    "period_days": 30,
    "data_points": 22,
    "start_date": "2025-10-27",
    "end_date": "2025-11-26",
    "average_gp_percentage": 56.78,
    "average_daily_revenue": 42500.00,
    "average_aro": 1425.50,
    "total_ros": 660,
    "gp_trend": 2.15,
    "trend_direction": "up"
  },
  "recommendations": [
    "Strong GP% - Maintain current pricing strategy",
    "Positive trend - Document recent changes for best practices"
  ]
}
```

---

### 10. Get RO History

**`GET /api/history/ro/24715?limit=10`**

Track GP calculations for a specific RO over time.

```json
{
  "ro_id": 24715,
  "ro_number": "24715",
  "history_count": 5,
  "history": [
    {
      "snapshot_date": "2025-11-26",
      "gp_percentage": 62.5,
      "gp_dollars": 1875.50,
      "variance_pct": 3.2,
      "variance_reason": "labor_cost_included"
    },
    {
      "snapshot_date": "2025-11-25",
      "gp_percentage": 61.8,
      "gp_dollars": 1850.00
    }
  ]
}
```

---

### 11. Compare Time Periods

**`GET /api/history/compare/periods?period1_start=2025-10-01&period1_end=2025-10-31&period2_start=2025-11-01&period2_end=2025-11-26`**

Compare GP metrics between two periods (month-over-month, year-over-year).

```json
{
  "period_1": {
    "start": "2025-10-01",
    "end": "2025-10-31",
    "summary": {
      "days": 23,
      "total_revenue": 125000.00,
      "total_gp": 68750.00,
      "avg_gp_pct": 55.0,
      "total_ros": 85,
      "avg_aro": 1470.59
    }
  },
  "period_2": {
    "start": "2025-11-01",
    "end": "2025-11-26",
    "summary": {
      "days": 19,
      "total_revenue": 145000.00,
      "total_gp": 85550.00,
      "avg_gp_pct": 59.0,
      "total_ros": 92,
      "avg_aro": 1576.09
    }
  },
  "comparison": {
    "gp_pct_change": 4.0,
    "revenue_change_pct": 16.0,
    "aro_change_pct": 7.17
  }
}
```

---

### 12. Tech Performance History

**`GET /api/history/tech-performance?days=30&tech_id=12345`**

Track how technician metrics change over time.

```json
{
  "period": {
    "start": "2025-10-27",
    "end": "2025-11-26"
  },
  "tech_id": 12345,
  "record_count": 18,
  "records": [
    {
      "snapshot_date": "2025-11-26",
      "tech_name": "John Smith",
      "hours_billed": 8.5,
      "hourly_rate": 35.00,
      "labor_profit": 1275.50,
      "labor_margin_pct": 82.3,
      "gp_per_hour": 150.06
    },
    {
      "snapshot_date": "2025-11-25",
      "tech_name": "John Smith",
      "hours_billed": 7.0,
      "labor_profit": 1050.00,
      "gp_per_hour": 150.00
    }
  ]
}
```

---

## Dashboard Integration: Trend Chart

```javascript
// Fetch 30-day trend data
async function loadTrendChart() {
  const res = await fetch('/api/history/snapshots/daily?days=30');
  const data = await res.json();

  // Reverse for chronological order
  const snapshots = data.snapshots.reverse();

  new Chart(document.getElementById('trend-chart'), {
    type: 'line',
    data: {
      labels: snapshots.map(s => s.snapshot_date),
      datasets: [
        {
          label: 'GP%',
          data: snapshots.map(s => s.gp_percentage),
          borderColor: '#4CAF50',
          yAxisID: 'y-gp'
        },
        {
          label: 'Revenue',
          data: snapshots.map(s => s.total_revenue),
          borderColor: '#2196F3',
          yAxisID: 'y-revenue'
        }
      ]
    },
    options: {
      scales: {
        'y-gp': { position: 'left', min: 40, max: 70 },
        'y-revenue': { position: 'right' }
      }
    }
  });
}

// Show trend indicator
async function showTrendIndicator() {
  const res = await fetch('/api/history/trends?days=30');
  const data = await res.json();

  const indicator = document.getElementById('trend-indicator');
  const trend = data.analysis.trend_direction;

  if (trend === 'up') {
    indicator.innerHTML = '&#x2191; Trending Up';
    indicator.className = 'trend-up';
  } else if (trend === 'down') {
    indicator.innerHTML = '&#x2193; Trending Down';
    indicator.className = 'trend-down';
  } else {
    indicator.innerHTML = '&#x2194; Stable';
    indicator.className = 'trend-stable';
  }
}
```

---

## Updated Summary

| Endpoint | Use For | Tier |
|----------|---------|------|
| `/api/dashboard/true-metrics` | Main KPI dashboard | 1-2 |
| `/api/analytics/tech-performance` | Tech leaderboard | 3 |
| `/api/analytics/parts-margin` | Parts profitability analysis | 3 |
| `/api/analytics/labor-efficiency` | Labor rate analysis | 3 |
| `/api/analytics/variance-analysis` | Debug TM vs True differences | 3 |
| `/api/analytics/full-analysis` | Comprehensive reports | 3 |
| `POST /api/history/snapshot/daily` | Store daily snapshot | 4 |
| `/api/history/snapshots/daily` | Get historical snapshots | 4 |
| `/api/history/trends` | Trend analysis | 4 |
| `/api/history/ro/{ro_id}` | RO history tracking | 4 |
| `/api/history/compare/periods` | Period comparison | 4 |
| `/api/history/tech-performance` | Tech performance history | 4 |
| `WS /api/realtime/ws` | Live dashboard WebSocket | 5 |
| `WS /api/realtime/ws/tech` | Live tech leaderboard | 5 |
| `POST /api/realtime/start` | Start auto-refresh | 5 |
| `POST /api/realtime/stop` | Stop auto-refresh | 5 |
| `POST /api/realtime/alert` | Send GP alert | 5 |

---

## Tier 5: Real-time Dashboard (WebSocket)

Tier 5 adds **live streaming** of GP metrics via WebSocket:
- No polling required - instant updates
- Channel-based subscriptions
- Auto-refresh with configurable interval
- GP threshold alerts

### WebSocket Channels

| Channel | Content |
|---------|---------|
| `dashboard` | Main KPI metrics (sales, GP%, ARO, car count) |
| `tech_performance` | Technician leaderboard updates |
| `ro_feed` | Live RO create/update feed |
| `alerts` | GP threshold warnings |

### 13. Connect to Live Dashboard

**`WS /api/realtime/ws`**

Main WebSocket endpoint. Receives automatic updates when auto-refresh is running.

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/api/realtime/ws');

ws.onopen = () => {
  console.log('Connected to live dashboard');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'initial_data':
      // First data on connect
      updateDashboard(message.data);
      break;

    case 'dashboard_update':
      // Live updates
      updateDashboard(message.data);
      break;

    case 'alert':
      // GP alerts
      showAlert(message.data.message, message.severity);
      break;

    case 'heartbeat':
      // Connection health (every 30s)
      console.log('Heartbeat:', message.timestamp);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected - will attempt reconnect');
  setTimeout(connectWebSocket, 5000);
};

function updateDashboard(data) {
  document.getElementById('sales').textContent = `$${data.sales.toLocaleString()}`;
  document.getElementById('gp-percent').textContent = `${data.gp_percentage}%`;
  document.getElementById('aro').textContent = `$${data.aro.toLocaleString()}`;
  document.getElementById('car-count').textContent = data.car_count;
  document.getElementById('last-update').textContent = data.updated_at;
}
```

### Message Formats

**dashboard_update:**
```json
{
  "type": "dashboard_update",
  "channel": "dashboard",
  "timestamp": "2025-11-26T14:30:00",
  "data": {
    "date": "2025-11-26",
    "sales": 45230.50,
    "cost": 18540.25,
    "gross_profit": 26690.25,
    "gp_percentage": 59.02,
    "car_count": 30,
    "aro": 1507.68,
    "updated_at": "2025-11-26T14:30:00"
  }
}
```

**tech_update:**
```json
{
  "type": "tech_update",
  "channel": "tech_performance",
  "timestamp": "2025-11-26T14:30:00",
  "data": [
    {
      "tech_id": 12345,
      "tech_name": "John Smith",
      "hours_billed": 8.5,
      "labor_profit": 1275.50,
      "gp_per_hour": 150.06
    }
  ]
}
```

**alert:**
```json
{
  "type": "alert",
  "channel": "alerts",
  "severity": "warning",
  "data": {
    "message": "GP% at 48.5% - approaching 50% threshold",
    "metric": "gp_percentage",
    "value": 48.5,
    "timestamp": "2025-11-26T14:30:00"
  }
}
```

---

### 14. Start Auto-Refresh

**`POST /api/realtime/start?interval=60`**

Starts background task that broadcasts metrics at regular intervals.

```json
{
  "status": "started",
  "interval": 60,
  "message": "Real-time updates started. Broadcasting every 60s"
}
```

---

### 15. Stop Auto-Refresh

**`POST /api/realtime/stop`**

Stops the background refresh task.

```json
{
  "status": "stopped"
}
```

---

### 16. Send Alert

**`POST /api/realtime/alert?message=GP%20below%20target&severity=warning`**

Manually send alert to all connected clients.

```json
{
  "status": "alert_sent",
  "message": "GP below target",
  "severity": "warning",
  "recipients": 3
}
```

---

### 17. Get Real-time Status

**`GET /api/realtime/status`**

Check service status and connected clients.

```json
{
  "service": "realtime",
  "status": "active",
  "refresh_interval_seconds": 60,
  "connections": {
    "total_connections": 3,
    "channels": {
      "dashboard": 3,
      "tech_performance": 1,
      "ro_feed": 0,
      "alerts": 3
    }
  }
}
```

---

## Complete Real-time Dashboard Example

```html
<!DOCTYPE html>
<html>
<head>
  <title>Live GP Dashboard</title>
  <style>
    .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 20px; }
    .kpi-card { background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; }
    .kpi-value { font-size: 2em; font-weight: bold; color: #333; }
    .kpi-label { color: #666; margin-top: 5px; }
    .connected { color: green; }
    .disconnected { color: red; }
    .alert { padding: 10px; margin: 10px 0; border-radius: 4px; }
    .alert-warning { background: #fff3cd; border: 1px solid #ffc107; }
    .alert-critical { background: #f8d7da; border: 1px solid #dc3545; }
  </style>
</head>
<body>
  <h1>Live GP Dashboard</h1>
  <p>Status: <span id="status" class="disconnected">Disconnected</span></p>
  <p>Last Update: <span id="last-update">-</span></p>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-value" id="sales">$0</div>
      <div class="kpi-label">Sales</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="gp-dollars">$0</div>
      <div class="kpi-label">Gross Profit</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="gp-percent">0%</div>
      <div class="kpi-label">GP%</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="aro">$0</div>
      <div class="kpi-label">ARO</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" id="car-count">0</div>
      <div class="kpi-label">Car Count</div>
    </div>
  </div>

  <div id="alerts"></div>

  <h2>Tech Leaderboard</h2>
  <table id="tech-table">
    <thead>
      <tr><th>Technician</th><th>Hours</th><th>Profit</th><th>$/Hour</th></tr>
    </thead>
    <tbody></tbody>
  </table>

  <script>
    let ws;

    function connect() {
      ws = new WebSocket('ws://localhost:8000/api/realtime/ws');

      ws.onopen = () => {
        document.getElementById('status').textContent = 'Connected';
        document.getElementById('status').className = 'connected';

        // Start auto-refresh on server
        fetch('/api/realtime/start?interval=30', { method: 'POST' });
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'initial_data' || msg.type === 'dashboard_update') {
          updateKPIs(msg.data);
        }

        if (msg.type === 'tech_update') {
          updateTechTable(msg.data);
        }

        if (msg.type === 'alert') {
          showAlert(msg.data.message, msg.severity);
        }
      };

      ws.onclose = () => {
        document.getElementById('status').textContent = 'Disconnected';
        document.getElementById('status').className = 'disconnected';
        setTimeout(connect, 5000);
      };
    }

    function updateKPIs(data) {
      document.getElementById('sales').textContent = '$' + data.sales.toLocaleString();
      document.getElementById('gp-dollars').textContent = '$' + data.gross_profit.toLocaleString();
      document.getElementById('gp-percent').textContent = data.gp_percentage + '%';
      document.getElementById('aro').textContent = '$' + data.aro.toLocaleString();
      document.getElementById('car-count').textContent = data.car_count;
      document.getElementById('last-update').textContent = new Date(data.updated_at).toLocaleTimeString();
    }

    function updateTechTable(techs) {
      const tbody = document.querySelector('#tech-table tbody');
      tbody.innerHTML = '';
      techs.forEach(t => {
        tbody.innerHTML += `<tr>
          <td>${t.tech_name}</td>
          <td>${t.hours_billed}</td>
          <td>$${t.labor_profit.toLocaleString()}</td>
          <td>$${t.gp_per_hour.toFixed(2)}</td>
        </tr>`;
      });
    }

    function showAlert(message, severity) {
      const div = document.createElement('div');
      div.className = 'alert alert-' + severity;
      div.textContent = message;
      document.getElementById('alerts').prepend(div);
      setTimeout(() => div.remove(), 30000);
    }

    connect();
  </script>
</body>
</html>
```

---

## Tier 6: Service Advisor Tracking

Tier 6 adds **advisor-level metrics** for tracking sales performance:
- Sales, GP, and volume per advisor
- Leaderboards with customizable sorting
- Goal tracking and progress
- Advisor comparison tools

### 18. Advisor Performance

**`GET /api/advisors/performance?days=30`**

Get all advisor metrics for the period.

```json
{
  "date_range": {
    "start": "2025-10-27",
    "end": "2025-11-26"
  },
  "advisors": [
    {
      "advisor_id": 12345,
      "advisor_name": "Sarah Johnson",
      "total_sales": 125000.00,
      "total_cost": 52500.00,
      "gross_profit": 72500.00,
      "gp_percentage": 58.0,
      "ro_count": 85,
      "job_count": 142,
      "aro": 1470.59,
      "avg_job_value": 880.28,
      "category_breakdown": {
        "parts": 62500.00,
        "labor": 50000.00,
        "sublet": 10000.00,
        "fees": 2500.00
      }
    }
  ],
  "summary": {
    "advisor_count": 3,
    "total_sales": 350000.00,
    "total_gp": 203000.00,
    "avg_gp_pct": 58.0,
    "ros_analyzed": 240
  }
}
```

---

### 19. Advisor Leaderboard

**`GET /api/advisors/leaderboard?days=7&sort_by=sales`**

Ranked advisor list. Sort options: `sales`, `gp`, `gp_pct`, `aro`, `ro_count`

```json
{
  "date_range": {
    "start": "2025-11-19",
    "end": "2025-11-26"
  },
  "leaderboard": [
    {
      "rank": 1,
      "advisor_id": 12345,
      "advisor_name": "Sarah Johnson",
      "total_sales": 45000.00,
      "gross_profit": 26100.00,
      "gp_percentage": 58.0,
      "aro": 1500.00,
      "ro_count": 30,
      "job_count": 48
    },
    {
      "rank": 2,
      "advisor_id": 67890,
      "advisor_name": "Mike Davis",
      "total_sales": 38000.00,
      "gross_profit": 21280.00,
      "gp_percentage": 56.0,
      "aro": 1357.14,
      "ro_count": 28,
      "job_count": 42
    }
  ],
  "sort_by": "sales"
}
```

---

### 20. Single Advisor Detail

**`GET /api/advisors/advisor/12345?days=30`**

Detailed performance with RO breakdown for one advisor.

```json
{
  "advisor_id": 12345,
  "advisor_name": "Sarah Johnson",
  "date_range": {
    "start": "2025-10-27",
    "end": "2025-11-26"
  },
  "summary": {
    "total_sales": 125000.00,
    "gross_profit": 72500.00,
    "gp_percentage": 58.0,
    "ro_count": 85,
    "job_count": 142,
    "aro": 1470.59
  },
  "category_breakdown": {
    "parts": 62500.00,
    "labor": 50000.00,
    "sublet": 10000.00,
    "fees": 2500.00
  },
  "ros": [
    {
      "ro_id": 24750,
      "ro_number": 24750,
      "customer": "John Smith",
      "vehicle": "2022 Toyota Camry",
      "total": 1850.00,
      "gp": 1073.00,
      "gp_pct": 58.0,
      "jobs": 3
    }
  ]
}
```

---

### 21. Compare Advisors

**`GET /api/advisors/compare?advisor_ids=12345,67890&days=30`**

Side-by-side advisor comparison.

```json
{
  "date_range": {
    "start": "2025-10-27",
    "end": "2025-11-26"
  },
  "comparison": [
    {
      "advisor_id": 12345,
      "advisor_name": "Sarah Johnson",
      "total_sales": 125000.00,
      "gross_profit": 72500.00,
      "gp_percentage": 58.0,
      "ro_count": 85,
      "aro": 1470.59,
      "avg_job_value": 880.28
    },
    {
      "advisor_id": 67890,
      "advisor_name": "Mike Davis",
      "total_sales": 98000.00,
      "gross_profit": 54880.00,
      "gp_percentage": 56.0,
      "ro_count": 72,
      "aro": 1361.11,
      "avg_job_value": 816.67
    }
  ]
}
```

---

### 22. Goal Tracking

**`GET /api/advisors/goals?sales_goal=50000&gp_pct_goal=55&days=30`**

Check advisor progress against goals.

```json
{
  "date_range": {
    "start": "2025-10-27",
    "end": "2025-11-26"
  },
  "goals": {
    "sales": 50000.0,
    "gp": null,
    "gp_pct": 55.0,
    "ro_count": null
  },
  "advisors": [
    {
      "advisor_id": 12345,
      "advisor_name": "Sarah Johnson",
      "current": {
        "sales": 125000.00,
        "gp": 72500.00,
        "gp_pct": 58.0,
        "ro_count": 85
      },
      "progress": {
        "sales": {
          "goal": 50000.0,
          "current": 125000.00,
          "percent": 250.0,
          "met": true
        },
        "gp_pct": {
          "goal": 55.0,
          "current": 58.0,
          "met": true
        }
      }
    }
  ]
}
```

---

## Dashboard Integration: Advisor Cards

```html
<div id="advisor-cards"></div>

<script>
async function loadAdvisorCards() {
  const res = await fetch('/api/advisors/performance?days=7');
  const data = await res.json();

  const container = document.getElementById('advisor-cards');
  container.innerHTML = '';

  data.advisors.forEach(adv => {
    container.innerHTML += `
      <div class="advisor-card">
        <h3>${adv.advisor_name}</h3>
        <div class="metric">
          <span class="label">Sales</span>
          <span class="value">$${adv.total_sales.toLocaleString()}</span>
        </div>
        <div class="metric">
          <span class="label">GP%</span>
          <span class="value">${adv.gp_percentage}%</span>
        </div>
        <div class="metric">
          <span class="label">ROs</span>
          <span class="value">${adv.ro_count}</span>
        </div>
        <div class="metric">
          <span class="label">ARO</span>
          <span class="value">$${adv.aro.toLocaleString()}</span>
        </div>
      </div>
    `;
  });
}
</script>
```

---

## Final Summary (All Tiers)

| Endpoint | Use For | Tier |
|----------|---------|------|
| `/api/dashboard/true-metrics` | Main KPI dashboard | 1-2 |
| `/api/analytics/tech-performance` | Tech leaderboard | 3 |
| `/api/analytics/parts-margin` | Parts profitability | 3 |
| `/api/analytics/labor-efficiency` | Labor rate analysis | 3 |
| `/api/analytics/variance-analysis` | TM vs True differences | 3 |
| `/api/analytics/full-analysis` | Comprehensive reports | 3 |
| `POST /api/history/snapshot/daily` | Store daily snapshot | 4 |
| `/api/history/snapshots/daily` | Historical snapshots | 4 |
| `/api/history/trends` | Trend analysis | 4 |
| `/api/history/ro/{ro_id}` | RO history | 4 |
| `/api/history/compare/periods` | Period comparison | 4 |
| `WS /api/realtime/ws` | Live WebSocket | 5 |
| `POST /api/realtime/start` | Start auto-refresh | 5 |
| `POST /api/realtime/alert` | Send GP alert | 5 |
| `/api/advisors/performance` | Advisor metrics | 6 |
| `/api/advisors/leaderboard` | Advisor rankings | 6 |
| `/api/advisors/advisor/{id}` | Single advisor detail | 6 |
| `/api/advisors/compare` | Advisor comparison | 6 |
| `/api/advisors/goals` | Goal tracking | 6 |
| `/api/trends/wow` | Week-over-week | 7 |
| `/api/trends/mom` | Month-over-month | 7 |
| `/api/trends/rolling-averages` | Rolling averages | 7 |
| `/api/trends/forecast` | Linear regression forecast | 7 |
| `/api/trends/day-patterns` | Day-of-week analysis | 7 |
| `/api/trends/extremes` | Best/worst days | 7 |
| `/api/trends/category-trends` | Category trend analysis | 7 |
| `/api/trends/summary` | Trend summary dashboard | 7 |

---

## Tier 7: Trend Analysis & Forecasting

Tier 7 adds **advanced trend analysis** and **forecasting** using historical data from Tier 4:
- Week-over-week (WoW) and month-over-month (MoM) comparisons
- Rolling averages with configurable windows
- Linear regression forecasting with confidence indicators
- Day-of-week pattern analysis
- Best/worst performing days identification
- Category-specific trend tracking

### 23. Week-over-Week Comparison

**`GET /api/trends/wow?weeks_back=4`**

Compares GP metrics across recent weeks with change calculations.

```json
{
  "analysis_type": "week_over_week",
  "weeks_analyzed": 4,
  "weeks": [
    {
      "week_number": 0,
      "week_label": "Week of 2025-11-25",
      "start_date": "2025-11-25",
      "end_date": "2025-11-26",
      "days_with_data": 2,
      "metrics": {
        "total_revenue": 12500.00,
        "total_gp": 7375.00,
        "avg_gp_pct": 59.0,
        "ro_count": 8,
        "aro": 1562.50
      }
    },
    {
      "week_number": 1,
      "week_label": "Week of 2025-11-18",
      "metrics": {
        "total_revenue": 45000.00,
        "total_gp": 25650.00,
        "avg_gp_pct": 57.0,
        "ro_count": 30,
        "aro": 1500.00
      }
    }
  ],
  "wow_changes": [
    {
      "period": "Week of 2025-11-25 vs Week of 2025-11-18",
      "revenue_change": -32500.00,
      "revenue_change_pct": -72.22,
      "gp_pct_change": 2.0,
      "ro_count_change": -22,
      "aro_change": 62.50
    }
  ],
  "insights": [
    "GP% improved from 55.5% to 59.0% over 4 weeks"
  ]
}
```

---

### 24. Month-over-Month Comparison

**`GET /api/trends/mom?months_back=3`**

Compares GP metrics across recent months.

```json
{
  "analysis_type": "month_over_month",
  "months_analyzed": 3,
  "months": [
    {
      "month_number": 0,
      "month_label": "November 2025",
      "start_date": "2025-11-01",
      "end_date": "2025-11-26",
      "days_with_data": 19,
      "metrics": {
        "total_revenue": 145000.00,
        "total_gp": 85550.00,
        "avg_gp_pct": 59.0,
        "ro_count": 95,
        "aro": 1526.32,
        "daily_avg_revenue": 7631.58,
        "parts_profit": 42775.00,
        "labor_profit": 38500.00
      }
    },
    {
      "month_number": 1,
      "month_label": "October 2025",
      "metrics": {
        "total_revenue": 125000.00,
        "total_gp": 68750.00,
        "avg_gp_pct": 55.0,
        "ro_count": 85,
        "aro": 1470.59
      }
    }
  ],
  "mom_changes": [
    {
      "period": "November 2025 vs October 2025",
      "revenue_change_pct": 16.0,
      "gp_pct_change": 4.0,
      "ro_count_change_pct": 11.76,
      "aro_change_pct": 3.79
    }
  ]
}
```

---

### 25. Rolling Averages

**`GET /api/trends/rolling-averages?days=30&short_window=7&long_window=14`**

Calculates rolling averages for GP%, revenue, and ARO with configurable windows.

```json
{
  "analysis_type": "rolling_averages",
  "period": {
    "start": "2025-10-27",
    "end": "2025-11-26",
    "data_points": 22
  },
  "windows": {
    "short_term": 7,
    "long_term": 14
  },
  "current_values": {
    "gp_pct_actual": 59.02,
    "gp_pct_short_ma": 58.25,
    "gp_pct_long_ma": 56.80,
    "trend": "up"
  },
  "signals": [
    "BULLISH: Short-term GP% crossed above long-term - positive momentum"
  ],
  "time_series": [
    {
      "date": "2025-11-26",
      "gp_pct": 59.02,
      "gp_ma_short": 58.25,
      "gp_ma_long": 56.80,
      "revenue": 6500.00,
      "revenue_ma_short": 6200.00,
      "revenue_ma_long": 5800.00,
      "aro": 1625.00
    }
  ]
}
```

#### Dashboard Usage: Trend Crossover Alerts

```javascript
async function checkTrendCrossover() {
  const res = await fetch('/api/trends/rolling-averages?days=30');
  const data = await res.json();

  if (data.signals.some(s => s.includes('BULLISH'))) {
    showNotification('GP trend turning positive! 📈', 'success');
  } else if (data.signals.some(s => s.includes('BEARISH'))) {
    showNotification('GP trend turning negative! 📉', 'warning');
  }
}
```

---

### 26. GP Forecasting

**`GET /api/trends/forecast?days_history=30&days_forecast=7`**

Uses linear regression to forecast GP metrics with confidence indicators.

```json
{
  "analysis_type": "forecast",
  "model": "linear_regression",
  "training_period": {
    "start": "2025-10-27",
    "end": "2025-11-26",
    "data_points": 22
  },
  "forecast_period": {
    "start": "2025-11-27",
    "end": "2025-12-03",
    "days": 7
  },
  "model_metrics": {
    "gp_pct": {
      "slope_per_day": 0.12,
      "r_squared": 0.65,
      "confidence": "medium",
      "trend": "increasing"
    },
    "revenue": {
      "slope_per_day": 125.50,
      "r_squared": 0.45,
      "confidence": "medium"
    },
    "aro": {
      "slope_per_day": 8.25,
      "r_squared": 0.55,
      "confidence": "medium"
    }
  },
  "forecasts": [
    {
      "date": "2025-11-27",
      "day_number": 1,
      "gp_pct_forecast": 59.14,
      "revenue_forecast": 6625.50,
      "aro_forecast": 1633.25
    },
    {
      "date": "2025-11-28",
      "day_number": 2,
      "gp_pct_forecast": 59.26,
      "revenue_forecast": 6751.00,
      "aro_forecast": 1641.50
    }
  ],
  "disclaimer": "Forecasts are based on historical trends and should be used as guidance only"
}
```

#### Confidence Levels

| R-squared | Confidence | Interpretation |
|-----------|------------|----------------|
| ≥ 0.70 | High | Strong linear relationship, forecast reliable |
| 0.40 - 0.69 | Medium | Moderate relationship, use with caution |
| < 0.40 | Low | Weak relationship, forecast less reliable |

---

### 27. Day-of-Week Patterns

**`GET /api/trends/day-patterns?weeks=8`**

Analyzes GP patterns by day of week to identify best/worst performing days.

```json
{
  "analysis_type": "day_of_week_patterns",
  "period": {
    "start": "2025-09-30",
    "end": "2025-11-26",
    "weeks_analyzed": 8
  },
  "by_day": [
    {
      "day_number": 0,
      "day_name": "Monday",
      "sample_count": 8,
      "gp_pct": {
        "avg": 56.5,
        "min": 52.0,
        "max": 61.0,
        "std_dev": 2.85
      },
      "revenue": {
        "avg": 5800.00,
        "min": 4200.00,
        "max": 7500.00
      },
      "ro_count": {
        "avg": 4.2,
        "total": 34
      }
    },
    {
      "day_number": 1,
      "day_name": "Tuesday",
      "sample_count": 8,
      "gp_pct": {
        "avg": 58.2,
        "min": 54.0,
        "max": 62.0,
        "std_dev": 2.45
      }
    }
  ],
  "highlights": {
    "best_gp_day": "Thursday",
    "best_gp_avg": 60.5,
    "worst_gp_day": "Monday",
    "worst_gp_avg": 56.5,
    "busiest_day": "Wednesday",
    "busiest_revenue_avg": 8200.00
  },
  "insights": [
    "GP% varies by 4.0% between Thursday and Monday",
    "Wednesday is typically the busiest day",
    "Sunday is typically the slowest day"
  ]
}
```

#### Dashboard Usage: Day Pattern Chart

```javascript
async function loadDayPatternChart() {
  const res = await fetch('/api/trends/day-patterns?weeks=8');
  const data = await res.json();

  new Chart(document.getElementById('day-chart'), {
    type: 'bar',
    data: {
      labels: data.by_day.map(d => d.day_name),
      datasets: [{
        label: 'Avg GP%',
        data: data.by_day.map(d => d.gp_pct?.avg || 0),
        backgroundColor: data.by_day.map(d =>
          d.day_name === data.highlights.best_gp_day ? '#4CAF50' : '#2196F3'
        )
      }]
    }
  });
}
```

---

### 28. Best/Worst Days

**`GET /api/trends/extremes?days=90&top_n=5`**

Finds the best and worst performing days by GP%, revenue, and ARO.

```json
{
  "analysis_type": "extreme_days",
  "period": {
    "start": "2025-08-28",
    "end": "2025-11-26",
    "total_days_analyzed": 65
  },
  "by_gp_percentage": {
    "best": [
      {
        "date": "2025-11-15",
        "gp_pct": 68.5,
        "revenue": 8500.00,
        "gross_profit": 5822.50,
        "ro_count": 5,
        "aro": 1700.00
      }
    ],
    "worst": [
      {
        "date": "2025-09-12",
        "gp_pct": 42.0,
        "revenue": 3200.00,
        "gross_profit": 1344.00,
        "ro_count": 2,
        "aro": 1600.00
      }
    ]
  },
  "by_revenue": {
    "best": [
      {
        "date": "2025-10-23",
        "gp_pct": 58.0,
        "revenue": 12500.00,
        "ro_count": 8,
        "aro": 1562.50
      }
    ],
    "worst": [
      {
        "date": "2025-09-08",
        "gp_pct": 55.0,
        "revenue": 1800.00,
        "ro_count": 1
      }
    ]
  },
  "by_aro": {
    "best": [...],
    "worst": [...]
  }
}
```

---

### 29. Category Trends

**`GET /api/trends/category-trends?days=30`**

Analyzes trends by revenue category (parts, labor) over time.

```json
{
  "analysis_type": "category_trends",
  "period": {
    "start": "2025-10-27",
    "end": "2025-11-26",
    "data_points": 22
  },
  "category_trends": {
    "parts": {
      "first_half_margin_avg": 48.5,
      "second_half_margin_avg": 51.2,
      "trend": "improving"
    },
    "labor": {
      "first_half_margin_avg": 78.5,
      "second_half_margin_avg": 80.1,
      "trend": "improving"
    }
  },
  "gp_contribution_pct": {
    "parts": 45.5,
    "labor": 48.2,
    "sublet": 4.8,
    "fees": 1.5
  },
  "time_series": [
    {
      "date": "2025-11-26",
      "parts_margin_pct": 52.0,
      "labor_margin_pct": 81.5,
      "parts_profit": 2600.00,
      "labor_profit": 3200.00,
      "total_gp": 6300.00
    }
  ],
  "insights": [
    "Parts contribute 45.5% of total GP",
    "Labor contributes 48.2% of total GP",
    "Parts margin is improving",
    "Labor margin is improving"
  ]
}
```

---

### 30. Trend Summary Dashboard

**`GET /api/trends/summary?days=30`**

Comprehensive trend summary combining key metrics from all analyses.

```json
{
  "analysis_type": "trend_summary",
  "period": {
    "start": "2025-10-27",
    "end": "2025-11-26",
    "days": 30,
    "data_points": 22
  },
  "current_metrics": {
    "total_revenue": 145000.00,
    "total_gross_profit": 85550.00,
    "avg_gp_pct": 59.0,
    "total_ros": 95,
    "avg_daily_revenue": 6590.91,
    "aro": 1526.32
  },
  "trend_indicators": {
    "gp_trend": "up",
    "gp_slope_per_day": 0.12,
    "trend_confidence": "medium",
    "r_squared": 0.55
  },
  "week_over_week": {
    "this_week_gp_pct": 59.5,
    "last_week_gp_pct": 57.0,
    "change": 2.5
  },
  "alerts": [
    {
      "level": "info",
      "message": "WoW GP improved 2.5% - document what's working"
    },
    {
      "level": "info",
      "message": "All metrics within normal range"
    }
  ]
}
```

#### Alert Levels

| Level | Trigger |
|-------|---------|
| `critical` | GP% < 45% |
| `warning` | GP% < 50% OR downward trend OR WoW drop > 2% |
| `info` | WoW improvement > 2% OR all normal |

---

## Dashboard Integration: Trend Dashboard

```html
<!DOCTYPE html>
<html>
<head>
  <title>GP Trend Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h1>GP Trend Analysis</h1>

  <!-- Summary Cards -->
  <div class="summary-grid">
    <div class="card">
      <h3>30-Day GP%</h3>
      <span id="avg-gp">0%</span>
      <span id="gp-trend" class="trend-indicator">→</span>
    </div>
    <div class="card">
      <h3>WoW Change</h3>
      <span id="wow-change">0%</span>
    </div>
    <div class="card">
      <h3>7-Day Forecast</h3>
      <span id="forecast-gp">0%</span>
      <span class="confidence" id="forecast-confidence">Low</span>
    </div>
  </div>

  <!-- Rolling Average Chart -->
  <canvas id="rolling-chart"></canvas>

  <!-- Day Pattern Chart -->
  <canvas id="day-pattern-chart"></canvas>

  <!-- Alerts -->
  <div id="alerts"></div>

  <script>
    async function loadTrendDashboard() {
      // Load summary
      const summary = await fetch('/api/trends/summary?days=30').then(r => r.json());

      document.getElementById('avg-gp').textContent = summary.current_metrics.avg_gp_pct + '%';
      document.getElementById('gp-trend').textContent =
        summary.trend_indicators.gp_trend === 'up' ? '↑' :
        summary.trend_indicators.gp_trend === 'down' ? '↓' : '→';
      document.getElementById('wow-change').textContent =
        (summary.week_over_week.change > 0 ? '+' : '') + summary.week_over_week.change + '%';

      // Display alerts
      summary.alerts.forEach(alert => {
        document.getElementById('alerts').innerHTML +=
          `<div class="alert alert-${alert.level}">${alert.message}</div>`;
      });

      // Load forecast
      const forecast = await fetch('/api/trends/forecast?days_history=30&days_forecast=7')
        .then(r => r.json());

      if (forecast.forecasts && forecast.forecasts.length > 0) {
        const lastForecast = forecast.forecasts[forecast.forecasts.length - 1];
        document.getElementById('forecast-gp').textContent = lastForecast.gp_pct_forecast + '%';
        document.getElementById('forecast-confidence').textContent =
          forecast.model_metrics.gp_pct.confidence;
      }

      // Load rolling averages for chart
      const rolling = await fetch('/api/trends/rolling-averages?days=30').then(r => r.json());

      new Chart(document.getElementById('rolling-chart'), {
        type: 'line',
        data: {
          labels: rolling.time_series.map(d => d.date),
          datasets: [
            {
              label: 'GP%',
              data: rolling.time_series.map(d => d.gp_pct),
              borderColor: '#333',
              borderDash: [5, 5]
            },
            {
              label: '7-Day MA',
              data: rolling.time_series.map(d => d.gp_ma_short),
              borderColor: '#2196F3'
            },
            {
              label: '14-Day MA',
              data: rolling.time_series.map(d => d.gp_ma_long),
              borderColor: '#4CAF50'
            }
          ]
        },
        options: {
          scales: { y: { min: 40, max: 70 } }
        }
      });

      // Load day patterns
      const patterns = await fetch('/api/trends/day-patterns?weeks=8').then(r => r.json());

      new Chart(document.getElementById('day-pattern-chart'), {
        type: 'bar',
        data: {
          labels: patterns.by_day.filter(d => d.gp_pct).map(d => d.day_name),
          datasets: [{
            label: 'Avg GP%',
            data: patterns.by_day.filter(d => d.gp_pct).map(d => d.gp_pct.avg),
            backgroundColor: patterns.by_day.filter(d => d.gp_pct).map(d =>
              d.day_name === patterns.highlights.best_gp_day ? '#4CAF50' :
              d.day_name === patterns.highlights.worst_gp_day ? '#f44336' : '#2196F3'
            )
          }]
        }
      });
    }

    loadTrendDashboard();
  </script>
</body>
</html>
```

---

## Complete API Summary (All 7 Tiers)

| Endpoint | Use For | Tier |
|----------|---------|------|
| `/api/dashboard/true-metrics` | Main KPI dashboard | 1-2 |
| `/api/analytics/tech-performance` | Tech leaderboard | 3 |
| `/api/analytics/parts-margin` | Parts profitability | 3 |
| `/api/analytics/labor-efficiency` | Labor rate analysis | 3 |
| `/api/analytics/variance-analysis` | TM vs True differences | 3 |
| `/api/analytics/full-analysis` | Comprehensive reports | 3 |
| `POST /api/history/snapshot/daily` | Store daily snapshot | 4 |
| `/api/history/snapshots/daily` | Historical snapshots | 4 |
| `/api/history/trends` | Basic trend analysis | 4 |
| `/api/history/ro/{ro_id}` | RO history | 4 |
| `/api/history/compare/periods` | Period comparison | 4 |
| `WS /api/realtime/ws` | Live WebSocket | 5 |
| `POST /api/realtime/start` | Start auto-refresh | 5 |
| `POST /api/realtime/alert` | Send GP alert | 5 |
| `/api/advisors/performance` | Advisor metrics | 6 |
| `/api/advisors/leaderboard` | Advisor rankings | 6 |
| `/api/advisors/goals` | Goal tracking | 6 |
| `/api/trends/wow` | Week-over-week | 7 |
| `/api/trends/mom` | Month-over-month | 7 |
| `/api/trends/rolling-averages` | Rolling averages | 7 |
| `/api/trends/forecast` | Linear regression forecast | 7 |
| `/api/trends/day-patterns` | Day-of-week analysis | 7 |
| `/api/trends/extremes` | Best/worst days | 7 |
| `/api/trends/category-trends` | Category trend analysis | 7 |
| `/api/trends/summary` | Trend summary dashboard | 7 |
