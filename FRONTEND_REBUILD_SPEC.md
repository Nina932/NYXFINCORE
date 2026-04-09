# FinAI Frontend Rebuild Specification
## Complete Blueprint for Next Session
### Date: March 22, 2026

---

## SYSTEM OVERVIEW

### What Exists (Backend — KEEP ALL)
- **113 Python files, 70,369 lines of code**
- **74 service modules**, 79 API endpoints
- **Phases A-S implemented** (18 phases)
- **LangGraph 10-node pipeline**
- **Knowledge Graph: 710 entities**
- **Accounting Knowledge Base: 26,426 chars (647 lines, 12 sections)**
- **LLM: qwen2.5:3b via Ollama on D: drive (free, local)**
- **SQLite DataStore (PostgreSQL-ready)**
- **Electron desktop app wrapper**

### What's Broken (Frontend — REBUILD)
- `static/FinAI_Platform_v8.html` — 5,815 lines of monolithic HTML+JS
- Client-side SheetJS parsing overrides backend results
- IndexedDB stores duplicate/stale data
- Pages render from client-side variables, NOT from backend API
- Dataset switching only changes client-side variable
- Sidebar chat uses WebSocket (legacy agent), not `/api/agent/command`
- State management: NONE (scattered global variables)

---

## ARCHITECTURE DECISION

### DO NOT: Patch the v8 monolith
It has been patched 50+ times and every fix breaks something else.

### DO: Build a new React frontend
- React 19 + TypeScript + Vite + Tailwind CSS v4
- Zustand for state management (single store)
- React Query for all API calls
- Recharts for charts
- Zero IndexedDB, zero SheetJS, zero client-side financial computation

### OR: Build a clean single-file HTML (v12)
- If React is too complex, build a clean 2,000-line HTML that ONLY reads from backend
- Every render function reads from `window.STATE.getState()`
- Every user action calls a backend endpoint
- NO client-side parsing

---

## SINGLE SOURCE OF TRUTH

### The ONLY State:
```javascript
{
  dataset_id: number | null,
  company: string,
  period: string,
  pnl: { revenue, cogs, gross_profit, selling_expenses, admin_expenses,
         ebitda, depreciation, net_profit, gross_margin_pct, ... },
  balance_sheet: { total_assets, total_liabilities, total_equity, cash,
                   fixed_assets_net, current_ratio, debt_to_equity, ... },
  revenue_breakdown: [{ product, net_revenue, category }],
  cogs_breakdown: [{ product, amount }],
  pl_line_items: [{ code, label, amount, type, level }],
  revenue_by_category: { "Revenue Retail": N, "Revenue Wholesale": N, ... },
  orchestrator: { health_score, health_grade, strategy_name, ... },
  alerts: [{ severity, message }],
  llm_insights: [{ severity, title, explanation, action }],
  llm_summary: string,
}
```

### Rules:
1. ALL state comes from backend API responses
2. NO client-side computation of financial numbers
3. NO IndexedDB
4. NO SheetJS
5. State updates ONLY via API responses
6. Every page re-renders when state changes

---

## API ENDPOINTS (for each page)

### 1. UPLOAD (triggers everything)
```
POST /api/agent/agents/smart-upload
  Input: FormData with file
  Returns: { success, company, period, pnl, balance_sheet,
             revenue_breakdown, cogs_breakdown, pl_line_items,
             revenue_by_category, orchestrator, health_score, health_grade,
             llm_insights, llm_summary }
  Time: ~10-40 seconds (includes LLM reasoning)
```
**On upload response: setState(response) → ALL pages re-render**

### 2. DASHBOARD
```
GET /api/agent/agents/dashboard
  Returns: { company, period, pnl, balance_sheet, revenue_breakdown,
             cogs_breakdown, revenue_by_category, orchestrator }
```
**Renders:** 6 KPI cards (Revenue, COGS, Margin, EBITDA, Net Profit, Cash Runway) + charts

### 3. P&L STATEMENT
```
Data from: state.pnl + state.pl_line_items + state.revenue_by_category
```
**Renders:** Hierarchical P&L table with:
- Revenue (Wholesale/Retail/Other breakdown)
- COGS (matching breakdown)
- Gross Margin (per product category)
- G&A Expenses
- EBITDA
- Net Profit
- Waterfall chart

### 4. BALANCE SHEET
```
Data from: state.balance_sheet
```
**Renders:** Assets/Liabilities/Equity sections with BS equation check

### 5. REVENUE ANALYSIS
```
Data from: state.revenue_breakdown + state.revenue_by_category
```
**Renders:** Product-level table + category pie chart + trend

### 6. COST ANALYSIS
```
Data from: state.cogs_breakdown + state.pnl (selling/admin expenses)
```
**Renders:** Cost breakdown table + charts

### 7. ORCHESTRATOR
```
POST /api/agent/agents/orchestrator/run
  Input: { current: state.pnl, balance_sheet: state.balance_sheet }
  Returns: Full orchestrator result (7 stages)
```
**Renders:** Health gauge, 7-stage pipeline, executive summary

### 8. STRATEGY
```
POST /api/agent/agents/strategy/generate
  Input: { financials: state.pnl, balance_sheet: state.balance_sheet }
  Returns: { name, phases, total_duration, overall_roi, actions }
```

### 9. SENSITIVITY
```
POST /api/agent/agents/sensitivity/analyze
  Input: { financials: state.pnl }
  Returns: { tornado_data, most_sensitive }

POST /api/agent/agents/sensitivity/monte-carlo
  Input: { financials: state.pnl, iterations: 500 }
  Returns: { p10, p50, p90, var_95 }
```

### 10. DECISIONS
```
POST /api/agent/agents/decisions/generate
  Input: { financials: state.pnl, balance_sheet: state.balance_sheet }
  Returns: { actions, cfo_verdict }
```

### 11. ANALOGIES
```
POST /api/agent/agents/analogy/search
  Input: { financials: state.pnl }
  Returns: { matches, dominant_strategy, confidence }
```

### 12. ALERTS
```
GET /api/agent/alerts
  Returns: [{ severity, message, metric, created_at }]
```

### 13. KPI MONITOR
```
POST /api/agent/agents/monitoring/kpi/evaluate
  Input: { financials: state.pnl }
  Returns: [{ metric, target, actual, status }]
```

### 14. CASH RUNWAY
```
POST /api/agent/agents/monitoring/cash-runway
  Input: { cash, revenue, expenses }
  Returns: { months, risk_level, burn_rate }
```

### 15. PREDICTIONS
```
POST /api/agent/agents/predictions/record
GET /api/agent/agents/predictions/accuracy
```

### 16. SIDEBAR CHAT (ALL messages)
```
POST /api/agent/command
  Input: { command: "user text" }
  Returns: { command_type, response, data, navigate, insights, llm_summary }
```
**NEVER use WebSocket /ws/chat. ALWAYS use /api/agent/command.**
The command endpoint routes to the correct agent based on intent.

### 17. BENCHMARKS
```
GET /api/agent/agents/benchmarks/industries
POST /api/agent/agents/benchmarks/compare
  Input: { financials: state.pnl, industry_id: "fuel_distribution" }
```

### 18. FORECASTS
```
POST /api/agent/agents/forecast/ensemble
  Input: { values: [...], periods: [...], forecast_periods: 6 }
```

### 19. GL PIPELINE
```
POST /api/agent/agents/gl/full-pipeline
  Input: { transactions: [...] }
```

### 20. REPORTS
```
POST /api/agent/agents/orchestrator/pdf → returns PDF blob
POST /api/agent/agents/orchestrator/brief → returns 1-page PDF blob
GET /api/agent/agents/orchestrator/last → returns last orchestrator result
```

### 21. SYSTEM STATUS
```
GET /api/agent/agents/status → agent registry
GET /api/agent/agents/health → backend health
GET /api/agent/agents/telemetry → performance metrics
```

---

## COMPONENT LIST (React)

### Layout
- `Layout.tsx` — Sidebar + Topbar + Content + ChatPanel
- `Sidebar.tsx` — Navigation (27 items, grouped)
- `Topbar.tsx` — Company name, period, buttons
- `ChatPanel.tsx` — Right sidebar, uses `/api/agent/command`

### Pages (each reads from Zustand store ONLY)
1. `DashboardPage.tsx` — KPI cards + charts
2. `UploadPage.tsx` — Drag & drop → smart-upload → setState
3. `PnLPage.tsx` — Hierarchical P&L from `pl_line_items`
4. `BalanceSheetPage.tsx` — Assets/Liabilities/Equity
5. `RevenuePage.tsx` — Product breakdown + category charts
6. `CostsPage.tsx` — Expense breakdown
7. `BudgetPage.tsx` — Budget vs Actual
8. `OrchestratorPage.tsx` — 7-stage pipeline
9. `StrategyPage.tsx` — Phase timeline + actions
10. `SensitivityPage.tsx` — Tornado + Monte Carlo
11. `DecisionsPage.tsx` — Ranked actions + CFO verdict
12. `AnalogiesPage.tsx` — Historical matches
13. `AlertsPage.tsx` — Active alerts + rules
14. `KPIMonitorPage.tsx` — KPI vs targets
15. `CashRunwayPage.tsx` — Runway projection
16. `PredictionsPage.tsx` — Record + accuracy
17. `TransactionsPage.tsx` — Transaction table
18. `BenchmarksPage.tsx` — Industry comparison
19. `ForecastsPage.tsx` — Ensemble forecast
20. `GLPipelinePage.tsx` — GL → TB → statements
21. `ReportsPage.tsx` — PDF/Excel download
22. `SystemPage.tsx` — Agent status + health
23. `SettingsPage.tsx` — Company info, alert rules

### Shared Components
- `KPICard.tsx` — Large number + trend + sparkline
- `HealthGauge.tsx` — Circular SVG gauge (0-100)
- `FinTable.tsx` — Financial table with indentation + coloring
- `LoadingSkeleton.tsx` — Pulsing placeholder
- `EmptyState.tsx` — "Upload a file to begin"
- `AlertBanner.tsx` — Critical alerts at top

### State (Zustand)
```typescript
// store.ts
interface FinAIState {
  company: string | null;
  period: string | null;
  pnl: Record<string, number> | null;
  balance_sheet: Record<string, number> | null;
  revenue_breakdown: Array<{product: string, net_revenue: number, category: string}>;
  cogs_breakdown: Array<{product: string, amount: number}>;
  pl_line_items: Array<{code: string, label: string, amount: number, type: string, level: number}>;
  revenue_by_category: Record<string, number>;
  orchestrator: any | null;
  alerts: any[];
  llm_insights: any[];
  llm_summary: string;
  isLoading: boolean;
  error: string | null;

  // Actions
  setFromUpload: (response: any) => void;
  setFromDashboard: (response: any) => void;
  clear: () => void;
}
```

### API Client
```typescript
// api.ts
const BASE = '/api/agent';
export const api = {
  upload: (file: File) => postFile(`${BASE}/agents/smart-upload`, file),
  dashboard: () => get(`${BASE}/agents/dashboard`),
  command: (cmd: string) => post(`${BASE}/command`, { command: cmd }),
  orchestrate: (fin: any, bs: any) => post(`${BASE}/agents/orchestrator/run`, { current: fin, balance_sheet: bs }),
  strategy: (fin: any) => post(`${BASE}/agents/strategy/generate`, { financials: fin }),
  sensitivity: (fin: any) => post(`${BASE}/agents/sensitivity/analyze`, { financials: fin }),
  monteCarlo: (fin: any, iters: number) => post(`${BASE}/agents/sensitivity/monte-carlo`, { financials: fin, iterations: iters }),
  decisions: (fin: any, bs: any) => post(`${BASE}/agents/decisions/generate`, { financials: fin, balance_sheet: bs }),
  analogies: (fin: any) => post(`${BASE}/agents/analogy/search`, { financials: fin }),
  alerts: () => get(`${BASE}/alerts`),
  kpi: (fin: any) => post(`${BASE}/agents/monitoring/kpi/evaluate`, { financials: fin }),
  runway: (cash: number, rev: number, exp: number) => post(`${BASE}/agents/monitoring/cash-runway`, { cash, revenue: rev, expenses: exp }),
  benchmarks: (fin: any) => post(`${BASE}/agents/benchmarks/compare`, { financials: fin, industry_id: 'fuel_distribution' }),
  forecast: (values: number[]) => post(`${BASE}/agents/forecast/ensemble`, { values, periods: values.length, forecast_periods: 6 }),
  pdfReport: (fin: any) => postBlob(`${BASE}/agents/orchestrator/pdf`, { current: fin }),
  briefReport: (fin: any) => postBlob(`${BASE}/agents/orchestrator/brief`, { current: fin }),
  status: () => get(`${BASE}/agents/status`),
  health: () => get(`${BASE}/agents/health`),
};
```

---

## WHAT TO DELETE

1. ❌ `static/FinAI_Platform_v8.html` — do NOT use as frontend (keep as legacy reference)
2. ❌ `static/FinAI_Platform_v9.html` — skeleton, incomplete
3. ❌ Any IndexedDB usage in frontend
4. ❌ Any SheetJS/XLSX.js usage in frontend
5. ❌ Any client-side financial computation
6. ❌ WebSocket `/ws/chat` usage (use `/api/agent/command` instead)

## WHAT TO KEEP

1. ✅ ALL backend Python code (app/, services/, routers/, agents/, etc.)
2. ✅ `main.py` — just change root route to serve React build
3. ✅ `desktop/main.js` — Electron wrapper (unchanged)
4. ✅ `static/FinAI_Platform_v7.html` — legacy reference
5. ✅ All API endpoints
6. ✅ SQLite database (`data/finai_store.db`)
7. ✅ Ollama with qwen2.5:3b on D: drive
8. ✅ `frontend/` React project (rebuild contents)

---

## CRITICAL RULES FOR NEW FRONTEND

1. **EVERY number on screen comes from a backend API response**
2. **Upload triggers: smart-upload → setState → ALL pages re-render**
3. **NO parseFile(), NO SheetJS, NO IndexedDB**
4. **Chat ALWAYS uses POST /api/agent/command, NEVER WebSocket**
5. **State is Zustand store — single source of truth**
6. **Pages are React components that read from useStore()**
7. **Loading states on every page (skeleton while fetching)**
8. **Error states with retry button**
9. **Empty states with "Upload a file to begin"**
10. **Dark theme: bg-slate-950, cards bg-slate-900, accent amber-500**

---

## BACKEND ISSUES TO FIX (in parallel)

1. **SOCAR P&L Engine COGS** — currently uses COGS Breakdown (1610 turnovers = wrong). Should use Mapping sheet account 7110 ONLY. The `socar_pl_engine.py` needs to match COGS products to P&L line from Mapping, not from COGS Breakdown sheet.

2. **Revenue double-counting** — when both Budget sheet AND Revenue Breakdown exist, Budget total overrides Revenue Breakdown total (this is fixed). But Revenue Breakdown products still get added to SOCAR P&L line_items alongside Budget products = double count in line items.

3. **Company name detection** — LLM sometimes returns short codes ("SGP") that override the correct "SOCAR Georgia Petroleum LLC". Fixed with length check but needs proper company registry.

4. **Period detection** — works from filename regex. Should also detect from sheet content (e.g., "Период: Январь 2026 г." → "2026-01").

5. **Balance Sheet data in DataStore** — BS fields are saved with `bs_` prefix AND without. Dashboard endpoint tries both. Should be consistent.

6. **Upload creates duplicate companies** — partially fixed but needs proper upsert logic.

---

## EXECUTION PLAN (for next session)

### Phase 1 (30 min): Setup + Store + API Client
- `npm create vite@latest frontend -- --template react-ts`
- Install: tailwindcss, react-router-dom, recharts, zustand, @tanstack/react-query, lucide-react
- Create: `store.ts`, `api.ts`, `Layout.tsx`, `Sidebar.tsx`

### Phase 2 (30 min): Core Pages
- `DashboardPage.tsx` — KPI cards + charts from `useStore()`
- `UploadPage.tsx` — drag & drop → api.upload() → store.setFromUpload()
- `PnLPage.tsx` — hierarchical table from `store.pl_line_items`
- `BalanceSheetPage.tsx` — from `store.balance_sheet`

### Phase 3 (20 min): Analytics Pages
- `RevenuePage.tsx`, `CostsPage.tsx`, `TransactionsPage.tsx`
- `BudgetPage.tsx`, `BenchmarksPage.tsx`, `ForecastsPage.tsx`

### Phase 4 (20 min): Intelligence Pages
- `OrchestratorPage.tsx`, `StrategyPage.tsx`, `SensitivityPage.tsx`
- `DecisionsPage.tsx`, `AnalogiesPage.tsx`

### Phase 5 (15 min): Monitoring Pages
- `AlertsPage.tsx`, `KPIMonitorPage.tsx`, `CashRunwayPage.tsx`, `PredictionsPage.tsx`

### Phase 6 (15 min): Chat + Reports + System
- `ChatPanel.tsx` (uses /api/agent/command)
- `ReportsPage.tsx` (PDF/Excel download)
- `SystemPage.tsx`, `SettingsPage.tsx`

### Phase 7 (10 min): Build + Deploy
- `npm run build`
- Copy `dist/` to `backend/static/app/`
- Update `main.py` to serve React app at `/`
- Test with Electron desktop app

### Total: ~2.5 hours for a clean, working frontend

---

## VERIFICATION CHECKLIST

After rebuild, test these exact steps:

1. ☐ Open app — shows "Upload a file to begin"
2. ☐ Upload `January 2026.xlsx` — takes <15 seconds
3. ☐ Dashboard shows: Revenue ₾51.2M, COGS ₾44.8M, Margin 12.5%
4. ☐ P&L page shows hierarchical breakdown (Revenue Wholesale/Retail, COGS, GM)
5. ☐ Balance Sheet shows: Assets ₾167.6M, Liabilities ₾105.9M, Equity ₾61.7M
6. ☐ Revenue page shows 37 products with categories
7. ☐ Upload `Report- January 2025.xlsx` — period shows 2025-01
8. ☐ Dashboard updates to: Revenue ₾111.5M, COGS ₾102.0M, Margin 8.5%
9. ☐ P&L updates with January 2025 data
10. ☐ Chat: type "what is our margin?" → structured response with real number
11. ☐ Chat: type "generate revenue report" → navigates to Revenue page
12. ☐ Orchestrator page: click "Run" → shows health score, strategy, verdict
13. ☐ All pages have loading state (skeleton while fetching)
14. ☐ All pages have error state (retry button)
15. ☐ Export PDF button works (downloads real PDF)
16. ☐ Export Excel button works

---

## FILES IN PROJECT

```
C:\Users\Nino\Downloads\FinAI_Backend_3\
├── backend/                          ← KEEP ALL (70,369 lines Python)
│   ├── app/
│   │   ├── agents/                   ← 7 agent files
│   │   ├── graph/                    ← LangGraph (state, nodes, graph)
│   │   ├── memory/                   ← Company memory
│   │   ├── models/                   ← SQLAlchemy models
│   │   ├── orchestrator/             ← Orchestrator v3
│   │   ├── routers/                  ← FastAPI routes (79 endpoints)
│   │   ├── services/                 ← 74 service modules
│   │   └── main.py                   ← FastAPI app entry
│   ├── data/finai_store.db           ← SQLite database
│   ├── uploads/                      ← Uploaded Excel files
│   ├── exports/                      ← Generated PDF/Excel reports
│   ├── training_data/                ← Training data for LLM
│   ├── static/                       ← Frontend files
│   │   ├── FinAI_Platform_v7.html    ← Legacy (original)
│   │   ├── FinAI_Platform_v8.html    ← Legacy (patched, broken)
│   │   └── app/                      ← React build output (deploy here)
│   ├── verify_all.py                 ← 580+ tests
│   ├── e2e_test.py                   ← 43 E2E tests
│   └── audit_all_layers.py           ← 84 architecture checks
├── frontend/                         ← REBUILD THIS (React + TypeScript)
│   ├── src/
│   │   ├── api/client.ts             ← API functions
│   │   ├── store/store.ts            ← Zustand state
│   │   ├── components/               ← Shared components
│   │   ├── pages/                    ← 23 page components
│   │   ├── App.tsx                   ← Router
│   │   └── main.tsx                  ← Entry
│   ├── vite.config.ts
│   └── package.json
├── desktop/                          ← KEEP (Electron wrapper)
│   ├── main.js
│   └── package.json
├── docker-compose.yml                ← KEEP
└── FRONTEND_REBUILD_SPEC.md          ← THIS FILE
```

---

## PROMPT FOR NEXT SESSION

Copy-paste this to start the next Claude Code session:

```
Read C:\Users\Nino\Downloads\FinAI_Backend_3\FRONTEND_REBUILD_SPEC.md

This is the complete specification for rebuilding the FinAI frontend.
The backend is fully functional (70,369 lines, 79 API endpoints, 580+ tests passing).
The frontend needs to be rebuilt from scratch as a React + TypeScript app.

Rules:
1. EVERY number on screen comes from backend API
2. NO client-side financial computation
3. State: Zustand store (single source of truth)
4. API calls: React Query
5. Chat: POST /api/agent/command (never WebSocket)

Follow the execution plan in the spec. Build all 23 pages.
Start with Phase 1 (setup + store + API client), then proceed through all phases.
After building, deploy: npm run build → copy dist/ to backend/static/app/ → test.
```
