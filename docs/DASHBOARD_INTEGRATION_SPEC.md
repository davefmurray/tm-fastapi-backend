# Dashboard Integration Specification

**Version:** 1.0
**Date:** November 27, 2025
**Status:** ACTIVE - All dashboard code should follow this spec

---

## Overview

The `/api/audit/today` endpoint is the **backbone** for the owner dashboard. It provides:
- Pre-calculated totals for KPI cards
- Per-RO breakdown with clear POTENTIAL vs AUTHORIZED separation
- Built-in discrepancy flags
- Data shaped for direct frontend consumption

---

## Endpoint

```
GET /api/audit/today?days_back={n}
```

**Parameters:**
- `days_back` (int, default=0): Days back from today. 0=today, 1=yesterday, etc.

**Example:**
```bash
# Today's data
curl /api/audit/today

# Yesterday's data
curl /api/audit/today?days_back=1

# Last Friday (5 days ago)
curl /api/audit/today?days_back=5
```

---

## Response Structure

```typescript
interface DailyAuditResponse {
  // Metadata
  date: string;           // "2025-11-27" - target date
  generated_at: string;   // ISO timestamp
  days_back: number;      // Echo of request param

  // Summary totals (for KPI cards)
  totals: {
    potential: {
      revenue: number;    // All jobs, dollars
      parts: number;
      labor: number;
      fees: number;
      discount: number;
      ro_count: number;
      job_count: number;
    };
    authorized: {
      revenue: number;    // Authorized jobs only, dollars
      parts: number;
      labor: number;
      profit: number;     // From /profit/labor endpoint
      gp_percent: number; // Gross profit margin %
      ro_count: number;   // ROs with at least 1 authorized job
      job_count: number;
    };
    pending: {
      revenue: number;    // Potential - Authorized
      job_count: number;  // Pending authorization
    };
  };

  // Per-RO details (for drill-down)
  ros: ROAuditRecord[];

  // Issues summary
  issues: {
    total: number;
    ros_with_issues: number;
    by_type: {
      missing_tech: number;
      subtotal_null: number;
      profit_mismatch: number;
      ro_404: number;
    };
  };
}

interface ROAuditRecord {
  ro_id: number;
  ro_number: number;
  status: string;         // "ACTIVE", "POSTED", "COMPLETE"
  customer: string;
  vehicle: string;
  advisor: string;

  potential: {
    revenue: number;
    parts: number;
    labor: number;
    fees: number;
    discount: number;
    job_count: number;
    jobs: JobDetail[];
  };

  authorized: {
    revenue: number;
    parts: number;
    labor: number;
    profit: number;
    gp_percent: number;
    job_count: number;
    jobs: JobDetail[];   // Only authorized jobs
  };

  endpoints: {
    estimate_total: number;           // From /estimate
    estimate_authorized_total: number; // From /estimate (field)
    profit_labor_total: number;       // From /profit/labor
    profit_labor_profit: number;      // From /profit/labor
  };

  issues: Issue[];
}

interface JobDetail {
  job_id: number;
  name: string;
  authorized: boolean;
  authorized_date: string | null;
  parts: number;
  labor: number;
  fees: number;
  discount: number;
  total: number;
  authorized_on_target_date?: boolean;  // In authorized[] only
}

interface Issue {
  type: "missing_tech" | "subtotal_null" | "profit_mismatch" | "ro_404";
  message: string;
  details?: any;
}
```

---

## Dashboard KPI Cards

### Card 1: Potential Sales (Full Estimate)
```typescript
// Data source
const value = response.totals.potential.revenue;
const label = "Potential Sales";
const subtitle = `${response.totals.potential.job_count} jobs on ${response.totals.potential.ro_count} ROs`;

// Formatting
formatCurrency(value); // "$66,116.77"
```

### Card 2: Authorized Sales (Committed)
```typescript
const value = response.totals.authorized.revenue;
const label = "Committed Sales";
const subtitle = `${response.totals.authorized.job_count} jobs authorized`;
```

### Card 3: Pending Authorization
```typescript
const value = response.totals.pending.revenue;
const label = "Pending Auth";
const subtitle = `${response.totals.pending.job_count} jobs waiting`;

// Color: Orange/Yellow to indicate action needed
```

### Card 4: Gross Profit
```typescript
const value = response.totals.authorized.profit;
const label = "Gross Profit";
const subtitle = `${response.totals.authorized.gp_percent.toFixed(1)}% margin`;
```

### Card 5: Authorization Rate
```typescript
const authRate = response.totals.potential.revenue > 0
  ? (response.totals.authorized.revenue / response.totals.potential.revenue) * 100
  : 0;
const label = "Auth Rate";
const subtitle = "% of estimate sold";
```

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [<] Nov 27, 2025 [>]                              [Refresh] [?] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │POTENTIAL │  │COMMITTED │  │ PENDING  │  │   GP%    │        │
│  │$66,116   │  │$20,696   │  │$45,419   │  │ 68.3%    │        │
│  │135 jobs  │  │47 jobs   │  │88 jobs   │  │ $619.02  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                 │
│  AUTH RATE: [=========>          ] 31.3%                        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ TODAY'S ROs (sorted by authorized revenue)                      │
│                                                                 │
│ RO#   Status   Customer    Potential  Authorized  GP%    Issues │
│ ──────────────────────────────────────────────────────────────  │
│ 24921 ACTIVE   Smith       $14,117    $10,213     65%    ⚠️     │
│ 24934 POSTED   Johnson     $8,543     $8,543      72%    ✓      │
│ 24952 ACTIVE   Williams    $5,200     $0          --     📋     │
│ ...                                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Icons:**
- ✓ = No issues
- ⚠️ = Has issues (click to see)
- 📋 = Fully pending authorization

---

## Drill-Down Flow

### Click on KPI Card → Filter RO List
```typescript
// User clicks "Pending Auth" card
const filtered = response.ros.filter(ro =>
  ro.potential.job_count > ro.authorized.job_count
);

// Show only ROs with pending jobs
```

### Click on RO Row → Show RO Detail Modal
```typescript
const ro = response.ros.find(r => r.ro_id === selectedId);

// Modal shows:
// - All jobs (potential.jobs)
// - Authorized jobs highlighted
// - Per-job breakdown
// - Issues list
// - Endpoint raw values for debugging
```

### Click on Job → Link to TM
```typescript
const tmUrl = `https://shop.tekmetric.com/repair-order/${ro.ro_id}`;
window.open(tmUrl, '_blank');
```

---

## Date Navigation

### Day Navigation
```typescript
// Previous day
const prevDay = () => fetchAudit(daysBack + 1);

// Next day (don't allow future)
const nextDay = () => {
  if (daysBack > 0) {
    fetchAudit(daysBack - 1);
  }
};

// Jump to today
const goToday = () => fetchAudit(0);
```

### Week/Month Views (Future)
Aggregate multiple daily calls or create new endpoints:
```
GET /api/audit/week?start_date=2025-11-25
GET /api/audit/month?month=2025-11
```

---

## Error Handling

### Token Expired
```typescript
if (response.status === 401 || response.detail?.includes('token')) {
  // Show token refresh prompt
  showTokenRefreshModal();
}
```

### No Data for Date
```typescript
if (response.ros.length === 0) {
  showMessage("No ROs found for this date");
}
```

### Issues Present
```typescript
if (response.issues.total > 0) {
  showIssuesBanner(`${response.issues.ros_with_issues} ROs have data issues`);
}
```

---

## Caching Strategy

### Client-Side Cache
```typescript
const cache = new Map<string, {data: any, timestamp: number}>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function fetchAudit(daysBack: number) {
  const key = `audit_${daysBack}`;
  const cached = cache.get(key);

  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await api.get(`/api/audit/today?days_back=${daysBack}`);
  cache.set(key, {data, timestamp: Date.now()});
  return data;
}
```

### Manual Refresh
```typescript
function forceRefresh() {
  cache.delete(`audit_${currentDaysBack}`);
  fetchAudit(currentDaysBack);
}
```

---

## Metric Source Alignment

The dashboard MUST use the same rules as defined in `METRIC_CONTRACTS.md`:

| Dashboard Card | Data Source | Contract Tag |
|----------------|-------------|--------------|
| Potential Sales | `totals.potential.revenue` | [POTENTIAL] |
| Committed Sales | `totals.authorized.revenue` | [AUTHORIZED] |
| Gross Profit | `totals.authorized.profit` | [AUTHORIZED] |
| Pending Auth | `totals.pending.revenue` | [DERIVED] |
| Auth Rate | Calculated | [DERIVED] |

**Never mix potential and authorized in the same calculation without explicit labeling.**

---

## Testing Checklist

Before releasing dashboard updates:

1. [ ] KPI cards match `/api/audit/today` totals exactly
2. [ ] RO list count matches `totals.*.ro_count`
3. [ ] Clicking date nav fetches correct `days_back` value
4. [ ] Issues badge shows `issues.ros_with_issues` count
5. [ ] Drill-down modal shows correct jobs per RO
6. [ ] Token expiry handled gracefully
7. [ ] Cache invalidates on manual refresh

---

## Example API Call (JavaScript)

```javascript
async function loadDashboard(daysBack = 0) {
  const response = await fetch(
    `https://tm-fastapi-backend-production.up.railway.app/api/audit/today?days_back=${daysBack}`
  );

  if (!response.ok) {
    throw new Error(`Audit API error: ${response.status}`);
  }

  const data = await response.json();

  // Update KPI cards
  document.getElementById('potential-sales').textContent =
    formatCurrency(data.totals.potential.revenue);
  document.getElementById('authorized-sales').textContent =
    formatCurrency(data.totals.authorized.revenue);
  document.getElementById('gross-profit').textContent =
    formatCurrency(data.totals.authorized.profit);
  document.getElementById('gp-percent').textContent =
    `${data.totals.authorized.gp_percent.toFixed(1)}%`;

  // Update RO list
  renderROList(data.ros);

  // Show issues if any
  if (data.issues.total > 0) {
    showIssuesBanner(data.issues);
  }
}

function formatCurrency(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(cents);
}
```

---

## Known Issues / TODOs

1. **GP% Aggregation**: When summing across multiple ROs, ensure profit/revenue ratio is calculated correctly at the total level, not averaged
2. **Date Filtering**: Jobs authorized on different dates may appear - use `authorized_on_target_date` flag for precise filtering
3. **WIP ROs**: Some ROs return 404 on basic endpoint - this is normal for work-in-progress
