# FinAI Platform -- Demo Data Requirements

Complete guide to the data needed to showcase every feature of the FinAI
financial intelligence platform.

---

## Table of Contents

1. [Primary Data Upload (Excel File)](#1-primary-data-upload)
2. [GL Pipeline / Trial Balance](#2-gl-pipeline)
3. [P&L / Income Statement](#3-pl-income-statement)
4. [Balance Sheet](#4-balance-sheet)
5. [Cash Flow Statement](#5-cash-flow-statement)
6. [1C Chart of Accounts](#6-1c-chart-of-accounts)
7. [Benchmark Engine](#7-benchmark-engine)
8. [Forecast Ensemble](#8-forecast-ensemble)
9. [Diagnosis Engine](#9-diagnosis-engine)
10. [Decision Engine](#10-decision-engine)
11. [Sensitivity Analysis](#11-sensitivity-analysis)
12. [Strategy Engine](#12-strategy-engine)
13. [Orchestrator (Full Pipeline)](#13-orchestrator)
14. [Monitoring / Alerts](#14-monitoring-alerts)
15. [ESG Engine](#15-esg-engine)
16. [AI Chat](#16-ai-chat)
17. [PDF Report](#17-pdf-report)
18. [Existing Seed Data Inventory](#18-existing-seed-data)
19. [Gap Analysis: What Is Missing](#19-gap-analysis)
20. [Recommended Demo Dataset](#20-recommended-demo-dataset)

---

## 1. Primary Data Upload

**Endpoint:** `POST /api/datasets/upload`
**Accepted formats:** `.xlsx`, `.xls`, `.csv`
**Max size:** Configurable via `MAX_UPLOAD_SIZE_MB`

### What the parser expects

The file parser (`app/services/file_parser.py`) auto-detects sheet types by
scanning column headers. It recognizes these sheet types:

#### Sheet 1: "Base" (Transaction Ledger)

The core accounting journal. Each row is one double-entry transaction.

| Column       | Type   | Description                              | Example              |
|-------------|--------|------------------------------------------|----------------------|
| date        | String | Transaction date                         | "15.01.2025"         |
| recorder    | String | Document that created the entry          | "Invoice #1234"      |
| acct_dr     | String | Debit account code (Georgian COA 4-digit)| "7310"               |
| acct_cr     | String | Credit account code                      | "3110"               |
| dept        | String | Department / cost center                 | "Head Office"        |
| counterparty| String | Vendor/customer name                     | "NYX Core Thinker"      |
| cost_class  | String | Cost classification                      | "Admin"              |
| type        | String | "Expense", "Income", or "Transfer"       | "Expense"            |
| amount      | Float  | Transaction amount (positive)            | 15000.50             |
| vat         | Float  | VAT amount                               | 2700.09              |

**Account code ranges (Georgian IFRS COA):**
- 1xxx = Current Assets (cash, receivables, inventory)
- 2xxx = Non-Current Assets (PPE, intangibles)
- 3xxx = Current Liabilities (payables, tax)
- 4xxx = Non-Current Liabilities (long-term debt)
- 5xxx = Equity (share capital, retained earnings)
- 6xxx = Revenue
- 7xxx = Expenses (71xx=COGS, 72xx=Labour, 73xx=Selling, 74xx=Distribution)
- 8xxx = Other Operating Income / Finance Income/Cost
- 9xxx = Tax / Deferred

**Minimum for meaningful demo:** 30-50 transactions covering at least
5 different account codes across both P&L (6xxx-9xxx) and BS (1xxx-5xxx).

**Ideal:** 100-300 transactions across 20+ accounts, spanning multiple
departments and counterparties. This enables the full GL pipeline, trial
balance, and all three financial statements to be generated.

#### Sheet 2: "Revenue Breakdown"

Product-level revenue detail (typically from 1C report).

| Column    | Type   | Description              | Example                         |
|-----------|--------|--------------------------|---------------------------------|
| product   | String | Product name (Georgian)  | "Euro Regular (Import)"         |
| gross     | Float  | Gross revenue            | 2500000                         |
| vat       | Float  | VAT amount               | 450000                          |
| net       | Float  | Net revenue (gross - VAT)| 2050000                         |
| segment   | String | Wholesale/Retail/Other   | "Revenue Wholesale"             |

The parser classifies Georgian product names into categories like
"Revenue Whsale Petrol (Lari)", "Revenue Retial Diesel (Lari)", etc.

**Minimum:** 5-10 product lines covering wholesale and retail segments.

#### Sheet 3: "COGS Breakdown"

Cost of Goods Sold by product, mirrors the revenue breakdown.

| Column        | Type   | Description                       | Example          |
|---------------|--------|-----------------------------------|------------------|
| product       | String | Product name (matches revenue)    | "Euro Regular"   |
| col6_amount   | Float  | Account 6 cost column             | 1800000          |
| col7310_amount| Float  | Account 7310 cost column          | 25000            |
| col8230_amount| Float  | Account 8230 cost column          | 12000            |
| total_cogs    | Float  | Sum of cost columns               | 1837000          |
| segment       | String | "COGS Wholesale" / "COGS Retail"  | "COGS Wholesale" |

**Minimum:** 5-10 product lines with matching revenue products.

#### Sheet 4: "TDSheet" (Trial Balance / Oborotno-Saldovaya Vedomost)

Standard 1C trial balance export.

| Column          | Type   | Description                        | Example    |
|-----------------|--------|------------------------------------|------------|
| account_code    | String | Account code                       | "6110"     |
| account_name    | String | Account name (Georgian/Russian)    | "Revenue"  |
| sub_account     | String | Sub-account detail (Subkonto)      | "Diesel"   |
| opening_debit   | Float  | Opening balance debit              | 0          |
| opening_credit  | Float  | Opening balance credit             | 0          |
| turnover_debit  | Float  | Period debit turnover              | 5000000    |
| turnover_credit | Float  | Period credit turnover             | 0          |
| closing_debit   | Float  | Closing balance debit              | 5000000    |
| closing_credit  | Float  | Closing balance credit             | 0          |

**Minimum:** 15-20 accounts covering all 9 account classes (1xxx through 9xxx).

#### Sheet 5 (optional): "Balance Sheet"

Pre-formatted balance sheet with IFRS mapping.

| Column              | Type   | Description                          |
|---------------------|--------|--------------------------------------|
| account_code        | String | Account code                         |
| account_name        | String | Account name                         |
| ifrs_line_item      | String | IFRS mapping group                   |
| opening_balance     | Float  | Opening balance                      |
| turnover_debit      | Float  | Debit turnover                       |
| turnover_credit     | Float  | Credit turnover                      |
| closing_balance     | Float  | Closing balance                      |

---

## 2. GL Pipeline

**Service:** `app/services/v2/gl_pipeline.py`
**Endpoint:** `POST /api/agent/agents/gl/full-pipeline`

### Input format

The GL Pipeline processes transactions from the database (uploaded via the
dataset upload). Each transaction needs:

```json
{
    "acct_dr": "7310",
    "acct_cr": "3110",
    "amount": 15000.50
}
```

The `TransactionAdapter.expand()` method converts each transaction into two
entries:
1. `{account_code: "7310", debit: 15000.50, credit: 0}`
2. `{account_code: "3110", debit: 0, credit: 15000.50}`

### Output

Trial Balance -> Income Statement -> Balance Sheet -> Cash Flow, plus
reconciliation checks (TB balanced, BS equation holds, net income matches).

### Data volume

- **Minimum:** 20 transactions hitting at least 10 distinct account codes
- **Ideal:** 100+ transactions, 30+ accounts, to produce a rich TB and
  all three financial statements with multiple line items per section

### Existing seed data

YES -- the seed data (`app/services/seed_data.py`) contains ~100 transactions
for "NYX Core Thinker LLC" (January 2025), plus revenue items and budget
lines. This is enough for GL pipeline demo.

---

## 3. P&L / Income Statement

**Service:** `app/services/socar_pl_engine.py` + `app/services/account_hierarchy.py`

### What it needs

The P&L is built from TWO sources:

**Source A -- Revenue + COGS items** (from Revenue Breakdown and COGS Breakdown
sheets): Product-level detail with Wholesale/Retail segmentation.

**Source B -- GL transactions** with 6xxx-9xxx account codes mapped to P&L lines:
- 6xxx -> Revenue
- 71xx -> Cost of Sales
- 72xx -> Admin Expenses (Labour)
- 73xx -> Selling Expenses
- 74xx -> Distribution Expenses
- 8xxx -> Other Operating Income, Finance Income/Cost
- 9xxx -> Income Tax

### P&L waterfall structure

```
Revenue
- Cost of Sales
= Gross Profit
- Selling Expenses
- Admin Expenses
- Distribution Expenses
+ Other Operating Income
= EBITDA
- Depreciation & Amortisation
= EBIT
+ Finance Income
- Finance Costs
= EBT (Earnings Before Tax)
- Income Tax
= Net Income
```

### Minimum data

At minimum: revenue (6xxx), COGS (71xx), and G&A (73xx/72xx) transactions.
This produces Gross Profit, EBITDA, and Net Income.

### Existing seed data

YES -- seed data includes revenue items, COGS breakdown, and G&A expenses
extracted from transaction account codes. Sufficient for P&L demo.

---

## 4. Balance Sheet

**Service:** `app/services/account_hierarchy.py`

### Account code to BS mapping

```
1xxx -> Current Assets (Cash, Receivables, Inventory, Prepayments)
2xxx -> Non-Current Assets (PPE, Intangibles, Investments)
3xxx -> Current Liabilities (Payables, Tax, VAT, Payroll)
4xxx -> Non-Current Liabilities (Long-term Debt, Provisions)
5xxx -> Equity (Share Capital, Retained Earnings, Reserves)
```

### Balance Sheet structure

```json
{
    "current_assets": {
        "Cash & Cash Equivalents": 500000,
        "Trade Receivables": 1200000,
        "Inventory": 800000
    },
    "noncurrent_assets": {
        "Property, Plant & Equipment": 5000000,
        "Accumulated Depreciation": -1500000
    },
    "current_liabilities": {
        "Trade Payables": 900000,
        "Tax Payable": 200000
    },
    "noncurrent_liabilities": {
        "Long-term Debt": 2000000
    },
    "equity": {
        "Share Capital": 1000000,
        "Retained Earnings": 1900000
    }
}
```

The system automatically injects Net Income into equity as "Retained Earnings
(Net Income)" so the BS equation (Assets = Liabilities + Equity) holds.

### Minimum data

Transactions hitting accounts in classes 1-5 (at least one account per BS
section). Without 1xxx-5xxx transactions, the BS will be empty.

### Existing seed data

PARTIAL -- The seed data focuses on P&L accounts (6xxx-7xxx). BS account
transactions (1xxx-5xxx) are limited. A separate Balance Sheet sheet upload
or additional transactions with BS accounts would improve this.

---

## 5. Cash Flow Statement

**Service:** `app/services/account_hierarchy.py` (integrated with BS builder)

### How it works

Cash Flow is derived from BS account movements (indirect method):
- Operating: Accounts 6-8xxx (P&L), 13xx-15xx, 31xx-36xx (working capital)
- Investing: Accounts 21xx, 23xx, 24xx, 25xx (long-term assets)
- Financing: Accounts 41xx, 51xx-53xx (debt, equity)

Each BS transaction generates a "movement" line in the appropriate CF section.

### Minimum data

Same as Balance Sheet -- need transactions across all account classes,
especially:
- 11xx (cash) for opening/closing cash
- 1xxx/3xxx for working capital changes (operating activities)
- 2xxx for capital expenditure (investing)
- 4xxx/5xxx for debt/equity changes (financing)

### Existing seed data

LIMITED -- Cash flow will be sparse with current seed data.

---

## 6. 1C Chart of Accounts

**Service:** `app/services/onec_interpreter.py`
**Referenced file:** `C:\Users\Nino\OneDrive\Desktop\1c AccountN.xlsx`
**Also in uploads:** `uploads/1c AccountN.xlsx`

### File format

Standard 1C "Plan of Accounts" (ПланСчетов) Excel export with columns:

| Column        | Description                                     |
|---------------|------------------------------------------------|
| Code          | Account code: "6110", "50.01", "01"            |
| Name          | Bilingual name "Georgian // Russian"            |
| Type          | "A" (Active/Debit), "P" (Passive/Credit), "AP" |
| Off-balance   | "Yes"/"No" (Georgian: "დიახ"/"არა")             |
| Currency      | Tracks foreign currency flag                    |
| Quantity      | Tracks quantity flag                             |
| Subkonto 1-3  | Analytical dimensions (up to 3)                 |
| Quick Select  | Shortcut alias                                   |

The interpreter handles:
- Georgian boolean values (დიახ/არა)
- Bilingual name splitting (Georgian // Russian)
- Russian 1C 2-digit codes (01, 02, 10, 50, 51, 60, etc.)
- Georgian IFRS 4-digit codes (1110, 6110, 7310, etc.)
- Automatic IFRS classification by first digit
- Parent-child hierarchy inference

### Existing data

YES -- `1c AccountN.xlsx` exists in uploads with 406 accounts (378 postable,
28 group headers). This is fully functional.

---

## 7. Benchmark Engine

**Service:** `app/services/benchmark_engine.py`
**Endpoint:** `POST /api/agent/agents/benchmarks/compare`

### Input format

```json
{
    "metrics": {
        "gross_margin_pct": 12.5,
        "net_margin_pct": 2.1,
        "current_ratio": 1.8,
        "debt_to_equity": 1.2,
        "ebitda_margin_pct": 5.3,
        "roe": 15.0,
        "roa": 6.0,
        "inventory_turnover": 28.0,
        "days_sales_outstanding": 35,
        "asset_turnover": 2.5,
        "operating_margin_pct": 3.5,
        "ga_to_revenue_pct": 2.8
    },
    "industry_id": "fuel_distribution"
}
```

### Available metrics (15 per industry)

`gross_margin_pct`, `wholesale_margin_pct`, `retail_margin_pct`,
`net_margin_pct`, `current_ratio`, `quick_ratio`, `debt_to_equity`,
`inventory_turnover`, `days_sales_outstanding`, `ebitda_margin_pct`,
`roe`, `roa`, `ga_to_revenue_pct`, `asset_turnover`, `operating_margin_pct`

### Available industries (6)

`fuel_distribution`, `retail_general`, `manufacturing`, `services`,
`construction`, `agriculture`

### Minimum data

At least 3-5 metrics to produce a meaningful comparison. The engine auto-
enriches metrics from stored company history if available.

### Existing seed data

NO explicit benchmark input -- but the system can compute metrics from
uploaded P&L and BS data automatically. The benchmark thresholds themselves
are hardcoded per industry (no user data needed for those).

---

## 8. Forecast Ensemble

**Service:** `app/services/forecast_ensemble.py`
**Endpoint:** `POST /api/agent/agents/forecast/ensemble`

### Input format

```json
{
    "historical_values": [5000000, 5200000, 5100000, 5500000, 5800000, 6000000,
                          5900000, 6200000, 6500000, 6300000, 6800000, 7000000],
    "historical_periods": ["Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24",
                           "Jun-24", "Jul-24", "Aug-24", "Sep-24", "Oct-24",
                           "Nov-24", "Dec-24"],
    "forecast_periods": 6,
    "confidence_level": 0.95
}
```

### Methods used

5 methods: `moving_avg`, `exp_smoothing`, `linear_regression`, `growth_rate`,
`seasonal`

### Minimum data

- **Absolute minimum:** 2 data points (but results will be trivial)
- **For backtest:** 6+ data points (backtest requires holdout validation)
- **For seasonal:** 8+ data points (uses last half as seasonal pattern)
- **Recommended:** 12-24 monthly data points for meaningful ensemble with
  confidence intervals and backtest accuracy metrics

### Existing seed data

NO -- seed data is single-period (January 2025). Multi-period historical
data is needed. This is a critical gap for forecast demo.

---

## 9. Diagnosis Engine

**Service:** `app/services/diagnosis_engine.py`

### Input format

```json
{
    "current_financials": {
        "revenue": 18500000,
        "cogs": 15000000,
        "gross_profit": 3500000,
        "ga_expenses": 800000,
        "selling_expenses": 200000,
        "ebitda": 2500000,
        "depreciation": 300000,
        "net_profit": 1800000,
        "finance_income": 50000,
        "finance_costs": 150000,
        "tax_expense": 300000
    },
    "previous_financials": {
        "revenue": 17000000,
        "cogs": 13500000,
        "gross_profit": 3500000,
        "ga_expenses": 750000,
        "ebitda": 2750000,
        "net_profit": 2100000
    },
    "balance_sheet": {
        "total_current_assets": 8000000,
        "total_noncurrent_assets": 12000000,
        "total_current_liabilities": 5000000,
        "total_noncurrent_liabilities": 4000000,
        "total_equity": 11000000,
        "cash": 2000000,
        "inventory": 3000000,
        "trade_receivables": 2500000,
        "trade_payables": 3000000
    },
    "industry_id": "fuel_distribution"
}
```

### What it produces

- Health score (0-100) and grade (A+/A/B+/B/C+/C/D/F)
- Signal detection (critical/high/medium/low changes)
- Root cause analysis via causal chains
- Benchmark comparison against industry
- Accounting issue detection
- Liquidity analysis
- Prioritized recommendations

### Minimum data

- `current_financials` with at least `revenue`, `cogs`, and `net_profit`
- For signal detection: `previous_financials` (enables period-over-period changes)
- For liquidity analysis: `balance_sheet` with at least `cash` and `total_current_assets`/`total_current_liabilities`

### Existing seed data

PARTIAL -- single-period P&L data exists. No previous period for comparison.
No balance sheet data in seed. This limits diagnosis to single-period threshold
checks only.

---

## 10. Decision Engine

**Service:** `app/services/v2/decision_engine.py`
**Endpoint:** `POST /api/agent/agents/decisions/generate`

### Input

The Decision Engine consumes a `DiagnosticReport` (output of diagnosis engine)
plus current financials. It is not called directly with raw data -- the
orchestrator chains diagnosis -> decision automatically.

For the standalone endpoint, you pass financials and the engine runs diagnosis
internally:

```json
{
    "financials": {
        "revenue": 18500000,
        "cogs": 15000000,
        "gross_profit": 3500000,
        "ga_expenses": 800000,
        "ebitda": 2500000,
        "net_profit": 1800000
    }
}
```

### What it produces

- Ranked business actions (cost_reduction, revenue_growth, risk_mitigation, etc.)
- CFO Verdict with conviction score and grade
- Monte Carlo sensitivity per action
- Risk matrix (low/medium/high/critical)
- Do-nothing cost estimate

### Minimum data

Same as Diagnosis Engine. Richer data produces more meaningful actions.

---

## 11. Sensitivity Analysis

**Service:** `app/services/v2/sensitivity_analyzer.py`
**Endpoint:** `POST /api/agent/agents/sensitivity/analyze`

### Input format

```json
{
    "financials": {
        "revenue": 18500000,
        "cogs": 15000000,
        "ga_expenses": 800000,
        "selling_expenses": 200000,
        "depreciation": 300000,
        "finance_costs": 150000,
        "tax_expense": 300000
    },
    "steps": 5
}
```

### What it produces

- Tornado chart bands: each variable varied +/-10% to +/-50%
- Most/least sensitive variable identification
- For each variable: min/max net profit, swing, elasticity

### Multi-Variable endpoint

```json
{
    "financials": { ... },
    "changes": {
        "revenue": -0.10,
        "cogs": 0.05,
        "ga_expenses": 0.15
    }
}
```

### Monte Carlo endpoint

```json
{
    "financials": { ... },
    "ranges": {
        "revenue": [0.85, 1.15],
        "cogs": [0.90, 1.10],
        "ga_expenses": [0.95, 1.20]
    },
    "iterations": 5000,
    "seed": 42
}
```

### Minimum data

At least `revenue` and `cogs`. More P&L line items = richer sensitivity
analysis. The engine varies each variable independently and measures
net profit impact.

---

## 12. Strategy Engine

**Service:** `app/services/v2/strategy_engine.py`
**Endpoint:** `POST /api/agent/agents/strategy/generate`

### Input

Consumes output from Decision Engine (ranked actions) plus health score
and current financials. Called automatically by the orchestrator.

For standalone:

```json
{
    "financials": {
        "revenue": 18500000,
        "cogs": 15000000,
        "ga_expenses": 800000,
        "ebitda": 2500000,
        "net_profit": 1800000
    },
    "health_score": 65.0,
    "months": 12
}
```

### What it produces

- Phased strategy (stabilization -> optimization -> growth)
- Phase templates based on health level (critical/moderate/healthy)
- Monthly time projections with revenue, COGS, gross profit, EBITDA, net profit
- Cumulative cash flow projections
- Strategy ROI and risk level

### Minimum data

Same as Decision Engine financials.

---

## 13. Orchestrator (Full 7-Stage Pipeline)

**Service:** `app/services/orchestrator.py`
**Endpoint:** Invoked from dashboard and PDF report generation

### Input format (the master data structure)

```json
{
    "current_financials": {
        "revenue": 18500000,
        "cogs": 15000000,
        "gross_profit": 3500000,
        "ga_expenses": 800000,
        "selling_expenses": 200000,
        "admin_expenses": 300000,
        "ebitda": 2500000,
        "depreciation": 300000,
        "ebit": 2200000,
        "net_profit": 1800000,
        "finance_income": 50000,
        "finance_costs": 150000,
        "tax_expense": 300000
    },
    "previous_financials": {
        "revenue": 17000000,
        "cogs": 13500000,
        "gross_profit": 3500000,
        "ga_expenses": 750000,
        "selling_expenses": 180000,
        "ebitda": 2750000,
        "net_profit": 2100000
    },
    "balance_sheet": {
        "cash": 2000000,
        "total_current_assets": 8000000,
        "total_noncurrent_assets": 12000000,
        "total_current_liabilities": 5000000,
        "total_noncurrent_liabilities": 4000000,
        "total_equity": 11000000,
        "inventory": 3000000,
        "trade_receivables": 2500000,
        "trade_payables": 3000000
    },
    "industry_id": "fuel_distribution",
    "project_months": 12,
    "monte_carlo_iterations": 500
}
```

### The 7 stages

1. **Diagnosis** -> health score, signals, root causes, benchmarks
2. **Decision Intelligence** -> ranked actions, CFO verdict
3. **Strategy** -> phased plan, time projection
4. **Simulation** -> sensitivity tornado chart, Monte Carlo VaR
5. **Monitoring** -> alerts, KPIs, cash runway, expense spikes
6. **Learning** -> prediction tracking, calibration
7. **Analogy** -> historical pattern matching

### Auto-enrichment

The orchestrator auto-computes derived metrics if missing:
- `gross_profit` = revenue - cogs
- `gross_margin_pct` = gross_profit / revenue * 100
- `ebitda` = gross_profit - selling_expenses - ga_expenses
- `ebitda_margin_pct` = ebitda / revenue * 100
- `net_margin_pct` = net_profit / revenue * 100
- `ebit` = ebitda - depreciation

### Minimum data

- **Bare minimum:** `current_financials` with `revenue` and `cogs`
  (5 of 7 stages will run)
- **For full demo:** All three inputs (current, previous, balance_sheet)
- **For expense spike detection:** `previous_financials` required

---

## 14. Monitoring / Alerts

**Service:** `app/services/v2/monitoring_engine.py`
**Endpoints:** Multiple under `/api/agent/agents/monitoring/`

### Default monitoring rules (5 built-in)

| Rule                   | Operator | Threshold | Severity  |
|------------------------|----------|-----------|-----------|
| gross_margin_pct       | lt       | 0.0       | emergency |
| net_margin_pct         | lt       | -10.0     | critical  |
| current_ratio          | lt       | 1.0       | critical  |
| debt_to_equity         | gt       | 4.0       | warning   |
| ebitda_margin_pct      | lt       | -5.0      | critical  |

### KPI evaluation input

```json
{
    "financials": {
        "gross_margin_pct": 12.5,
        "net_margin_pct": 2.1,
        "ebitda_margin_pct": 5.3,
        "current_ratio": 1.8,
        "debt_to_equity": 1.2,
        "roe": 15.0
    }
}
```

### Cash runway input

```json
{
    "cash_balance": 2000000,
    "monthly_revenue": 1541667,
    "monthly_expenses": 1375000
}
```

### Expense spike input

```json
{
    "current_expenses": {
        "cogs": 15000000,
        "ga_expenses": 800000,
        "selling_expenses": 200000
    },
    "previous_expenses": {
        "cogs": 13500000,
        "ga_expenses": 750000,
        "selling_expenses": 180000
    }
}
```

### Minimum data

The monitoring engine needs the orchestrator's `current_financials` dict
with percentage metrics. For alerts, the metrics just need to exist -- the
5 default rules will check them automatically.

---

## 15. ESG Engine

**Service:** `app/services/esg_engine.py`
**Status:** PLACEHOLDER -- uses hardcoded demo data, not connected to real inputs

### Seed endpoint

`POST /api/esg/seed` -- populates the engine with realistic demo data
for a fuel distribution company. No user data needed.

### Full input format (if providing real data)

```json
{
    "environmental": {
        "emissions_reduction_pct": 12.5,
        "renewable_energy_pct": 18.0,
        "waste_diversion_pct": 62.0,
        "water_recycled_pct": 45.0,
        "env_incidents": 2,
        "env_investment_pct": 3.5
    },
    "social": {
        "employee_turnover_pct": 14.2,
        "training_hours_per_employee": 24.0,
        "diversity_pct": 28.0,
        "safety_incident_rate": 1.8,
        "community_investment_pct": 1.2,
        "living_wage_compliance": 94.0
    },
    "governance": {
        "board_independence_pct": 55.0,
        "female_board_pct": 22.0,
        "ethics_violations": 1,
        "audit_committee_meetings": 6,
        "whistleblower_reports": 3,
        "anti_corruption_training_pct": 78.0,
        "data_breach_count": 0
    },
    "energy_data": {
        "scope1": {
            "diesel_litre": 2850000,
            "gasoline_litre": 1200000,
            "natural_gas_m3": 450000,
            "lpg_litre": 380000
        },
        "scope2": {
            "electricity_kwh": 8500000,
            "district_heating_kwh": 1200000
        },
        "scope3": {
            "air_travel_km": 350000,
            "road_freight_tkm": 12000000,
            "waste_kg": 280000,
            "water_m3": 95000
        },
        "revenue": 185000000,
        "prior_total": 12800
    }
}
```

### Existing seed data

YES -- `esg_engine.seed_demo_data()` has full demo data built in. The ESG
module is self-contained for demo purposes.

---

## 16. AI Chat

**Service:** `app/services/ai_agent.py` + `app/agents/supervisor.py`
**Endpoint:** `POST /api/agent/chat`

### What it can answer

The multi-agent system routes questions to specialized agents:

| Agent       | Handles                                                    |
|-------------|----------------------------------------------------------|
| CalcAgent   | Financial calculations, ratio analysis, margin queries    |
| DataAgent   | Data questions, report lookups, upload status             |
| InsightAgent| Trend analysis, metric change explanations, scenarios     |
| ReportAgent | Report generation, P&L summaries, financial overviews     |
| DecisionAgent| Business recommendations, strategy questions             |

### Example questions

- "What is our gross margin?" (CalcAgent)
- "Show me the P&L for January 2025" (DataAgent/ReportAgent)
- "Why did net profit decrease?" (InsightAgent)
- "What should we do to improve EBITDA?" (DecisionAgent)
- "Compare our margins to fuel distribution benchmarks" (CalcAgent)
- "Generate a financial report" (ReportAgent)
- "What is the cash runway?" (CalcAgent)

### Data dependency

The chat agents pull data from the active dataset in the database. They need
at least one uploaded/seeded dataset with transactions and revenue items.

### API key requirement

Requires `ANTHROPIC_API_KEY` for Claude-based responses. Falls back to
Ollama local LLM, then to template-based responses if neither is available.

---

## 17. PDF Report

**Service:** `app/services/pdf_report.py`
**Generated from:** Orchestrator output

### What it needs

The PDF report generator takes an `OrchestratorResult.to_dict()` output
and renders it as a professional A4 PDF with:

- Executive summary (health score, conviction grade, strategy)
- Diagnosis section (signals, root causes)
- Decision section (ranked actions, CFO verdict)
- Strategy section (phases, timeline)
- Simulation section (tornado chart data, Monte Carlo)
- Monitoring section (alerts, KPIs, cash runway)

### Minimum data

Run the full orchestrator with all three inputs (current_financials,
previous_financials, balance_sheet) to get maximum PDF content.

---

## 18. Existing Seed Data Inventory

### What exists in `app/services/seed_data.py`

| Data Type        | Count          | Period         | Company              |
|-----------------|----------------|----------------|----------------------|
| Transactions     | ~100           | January 2025   | NYX Core Thinker LLC |
| Revenue Items    | ~20-30         | January 2025   | NYX Core Thinker LLC |
| Budget Lines     | ~30            | January 2025   | NYX Core Thinker LLC |
| COGS Items       | 7              | January 2025   | NYX Core Thinker LLC |
| G&A Expenses     | Auto-extracted | January 2025   | NYX Core Thinker LLC |

### What exists in uploads/

Multiple real Excel files from various periods (January 2025, January 2026)
for SGP (NYX Core Thinker):
- `Reports.xlsx`, `Reports2.xlsx` -- full multi-sheet reports
- `SGP*.xls` -- monthly SGP reports (Jan-Dec)
- `January 2026.xlsx` -- newer period data
- `1c AccountN.xlsx` -- Chart of Accounts
- `P&L_Statement*.xlsx` -- standalone P&L reports
- `TDSheet_Only_Test.xlsx` -- trial balance only

### ESG demo data

Built into `esg_engine.seed_demo_data()` -- no external file needed.

---

## 19. Gap Analysis: What Is Missing

### CRITICAL GAPS (features will not work without this)

| Gap | Impact | Feature Blocked |
|-----|--------|-----------------|
| **No multi-period historical data** | Cannot demonstrate forecasting | Forecast Ensemble (needs 6-24 periods) |
| **No previous_financials in seed** | Cannot show period-over-period changes | Diagnosis signal detection, expense spikes |
| **Limited BS account transactions** | Empty or sparse Balance Sheet | BS display, Cash Flow, liquidity analysis, current_ratio, D/E |

### MODERATE GAPS

| Gap | Impact | Feature Blocked |
|-----|--------|-----------------|
| No balance_sheet dict in seed | Cash runway and liquidity analysis run with defaults | Monitoring cash runway, accounting checks |
| Single company only | Cannot demo multi-company comparison | Benchmark company history comparison |
| No real ESG data from user | ESG module uses hardcoded demo | ESG scoring from actual company data |

### MINOR GAPS

| Gap | Impact | Feature Blocked |
|-----|--------|-----------------|
| No multi-currency transactions | Currency engine has no real conversions to show | Currency conversion demo |
| No anomaly examples | Anomaly detection has nothing to flag | Data quality anomaly display |

---

## 20. Recommended Demo Dataset

To showcase the FULL potential of FinAI, create a comprehensive demo Excel
file with the following structure.

### Recommended file: `Demo_Full_NYX_12M.xlsx`

**5 sheets covering 12 months (January - December 2025)**

#### Sheet 1: "Base" (Transaction Ledger) -- 300-500 rows

Include transactions across ALL account classes:

```
ASSET TRANSACTIONS (1xxx):
- 1110 Cash receipts/payments
- 1310 Trade receivable invoices
- 1510 Inventory purchases

FIXED ASSET TRANSACTIONS (2xxx):
- 2110 PPE acquisitions
- 2210 Depreciation entries

LIABILITY TRANSACTIONS (3xxx):
- 3110 Trade payable invoices
- 3210 Tax payments
- 3510 Payroll entries

EQUITY TRANSACTIONS (5xxx):
- 5310 Retained earnings transfers

REVENUE TRANSACTIONS (6xxx):
- 6110 Product sales (wholesale)
- 6120 Product sales (retail)

EXPENSE TRANSACTIONS (7xxx):
- 7110 COGS -- product cost
- 7210 Administrative salaries
- 7310 Selling expenses
- 7320 Marketing costs

OTHER INCOME/EXPENSE (8xxx):
- 8210 Finance income (interest)
- 8310 Finance costs (loan interest)

TAX (9xxx):
- 9110 Income tax provisions
```

Each transaction should have: date, recorder, acct_dr, acct_cr, dept,
counterparty, cost_class, type, amount, vat.

#### Sheet 2: "Revenue Breakdown" -- 15-25 product rows

Include both Wholesale and Retail segments:
- 5+ wholesale products (petrol, diesel, bitumen, CNG, LPG)
- 5+ retail products (same fuels at retail prices)
- 2-3 service/other revenue items

Each row: product (Georgian name), gross, vat, net

#### Sheet 3: "COGS Breakdown" -- 15-25 product rows

Mirror the revenue breakdown with matching cost data per product.

#### Sheet 4: "TDSheet" (Trial Balance) -- 40-60 accounts

Full trial balance with opening and closing balances for all account
classes. This is the most important sheet for comprehensive demos as it
feeds the GL pipeline, all three financial statements, and the dashboard.

#### Sheet 5: "Balance Sheet" (optional) -- 30-40 rows

Pre-formatted with IFRS line item mapping for BS display.

### Multi-Period Data for Forecasting

To enable the forecast ensemble, provide one of:

**Option A:** 12 separate monthly files (January 2025 - December 2025),
each uploaded sequentially. The system tracks periods.

**Option B:** A JSON/API payload with historical values:

```json
{
    "revenue_history": {
        "values": [15.2, 16.1, 17.5, 18.0, 19.2, 18.5, 17.8, 19.0, 20.1, 19.5, 21.0, 22.3],
        "periods": ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25",
                     "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25"],
        "unit": "millions GEL"
    }
}
```

### Previous Period Financials (for full Orchestrator)

Store or provide manually in the API call:

```json
{
    "previous_financials": {
        "revenue": 17000000,
        "cogs": 13500000,
        "gross_profit": 3500000,
        "ga_expenses": 750000,
        "selling_expenses": 180000,
        "admin_expenses": 280000,
        "ebitda": 2750000,
        "depreciation": 280000,
        "net_profit": 2100000,
        "finance_costs": 130000,
        "tax_expense": 280000
    }
}
```

### Balance Sheet Snapshot (for full Orchestrator)

```json
{
    "balance_sheet": {
        "cash": 2000000,
        "trade_receivables": 2500000,
        "inventory": 3000000,
        "total_current_assets": 8000000,
        "total_noncurrent_assets": 12000000,
        "trade_payables": 3000000,
        "total_current_liabilities": 5000000,
        "total_noncurrent_liabilities": 4000000,
        "total_equity": 11000000
    }
}
```

---

## Quick Reference: Minimum Data Per Feature

| Feature                | Minimum Input                                    | Multi-Period? | Seed Exists? |
|------------------------|--------------------------------------------------|:------------:|:------------:|
| Data Upload            | 1 Excel file with Base sheet                     | No           | YES          |
| GL Pipeline            | 20+ transactions with account codes              | No           | YES          |
| P&L / Income Statement | Revenue (6xxx) + COGS (71xx) transactions        | No           | YES          |
| Balance Sheet          | BS account (1xxx-5xxx) transactions              | No           | PARTIAL      |
| Cash Flow              | BS transactions + cash account movements         | No           | LIMITED      |
| 1C Chart of Accounts   | 1C AccountN.xlsx file                            | No           | YES          |
| Benchmark Engine       | 3-5 financial metrics + industry_id              | No           | Computed     |
| Forecast Ensemble      | 6+ historical values (12+ recommended)           | YES          | NO           |
| Diagnosis Engine       | current_financials dict                           | No           | YES (1 period)|
| Diagnosis (full)       | current + previous financials + balance_sheet     | YES (2)      | NO           |
| Decision Engine        | DiagnosticReport (from diagnosis)                | No           | YES          |
| Sensitivity Analysis   | financials dict with revenue + cogs              | No           | YES          |
| Strategy Engine        | ranked actions + health_score + financials        | No           | YES          |
| Orchestrator (full)    | current + previous + balance_sheet               | YES (2)      | PARTIAL      |
| Monitoring / Alerts    | financials dict with margin %                    | No           | YES          |
| Cash Runway            | cash_balance + monthly revenue/expenses           | No           | NO (computed)|
| Expense Spikes         | current + previous expense dicts                 | YES (2)      | NO           |
| ESG Engine             | company_data dict OR seed_demo_data()            | No           | YES (built-in)|
| AI Chat                | Active dataset in DB + API key                   | No           | YES          |
| PDF Report             | OrchestratorResult output                        | No           | YES          |

---

## Summary of Critical Actions

1. **Add Balance Sheet transactions to seed data** -- Include 1xxx-5xxx account
   transactions to produce a real BS. Currently, the seed data is P&L-heavy.

2. **Add a second period** -- Duplicate the seed data for a "December 2024"
   period with slightly different numbers. This unlocks diagnosis signals,
   expense spike detection, and period-over-period comparison.

3. **Create historical time series** -- For forecast ensemble demo, provide
   12 monthly values for key metrics (revenue, COGS, net profit). This can
   be stored in DataStore or provided via API.

4. **Pre-compute balance_sheet dict** -- Either extract from uploaded BS sheet
   or hardcode a representative BS snapshot to unlock cash runway, liquidity,
   and full orchestrator features.

With these four additions, every feature in the platform will have meaningful
data to operate on.
