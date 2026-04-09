# FinAI - Complete Technical Architecture Document

**Date**: March 24, 2026
**Version**: 2.0
**Codebase**: 78,323 lines Python (127 files) + 7,343 lines TypeScript (47 files)

---

## 1. SYSTEM OVERVIEW

FinAI is a financial intelligence platform for SOCAR Georgia Petroleum LLC that:
- Parses 1C accounting Excel exports into structured financial data
- Generates IFRS-compliant P&L, Balance Sheet, and MR Reports
- Provides AI-powered analysis via multi-agent system with Claude
- Supports bilingual UI (English/Georgian)

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async) |
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind CSS 4 |
| **State** | Zustand 5 (client), TanStack React Query 5 (server) |
| **AI — Primary** | Anthropic Claude Sonnet 4 (claude-sonnet-4-20250514) |
| **AI — Reasoning** | NVIDIA Nemotron 3 Super 120B (nvidia/nemotron-3-super-120b-a12b) |
| **AI — Fast** | xAI Grok 4.1 Fast (grok-4-1-fast-non-reasoning) |
| **AI — Backup** | Mistral Large (mistral-large-latest) |
| **AI — Local** | Ollama (llama3.2:3b, qwen2.5:3b, mistral:7b) |
| **RAG** | ChromaDB + LlamaIndex 0.12 |
| **Database** | SQLite (dev) / PostgreSQL 16 (prod) |
| **Cache** | Redis 7 or in-memory |
| **Deploy** | Docker Compose (API + PostgreSQL + Redis + Nginx) |

### LLM Architecture — 5-Tier Fallback Chain

FinAI uses a **multi-provider LLM stack** with automatic fallback. No LLM ever generates financial numbers — they only explain, reason, and provide insights. All numbers come from deterministic computation.

```
                           PRIMARY AGENT INTERFACE
                           (ai_agent.py — tool-based)
                                    |
                    ┌───────────────┼───────────────┐
                    v               v               v
            CLAUDE SONNET 4    LLM CHAIN       LOCAL LLM SERVICE
            (Tool calling,     (Reasoning)     (local_llm.py)
             WebSocket chat)                        |
                                    |          ┌────┴────┐
                              ┌─────┼─────┐    v         v
                              v     v     v  NVIDIA    OLLAMA
                           Claude Grok Mistral Nemotron  Local
                              |     |     |    120B     Models
                              v     v     v    |         |
                           TEMPLATE FALLBACK   |    llama3.2:3b
                           (deterministic)     |    qwen2.5:3b
                                               |    mistral:7b
                                               v
                                          Chain-of-Thought
                                          Reasoning Mode
```

#### Tier 1: Claude Sonnet 4 (Primary — Agent Interface)
- **Model**: `claude-sonnet-4-20250514`
- **Provider**: Anthropic API (`api.anthropic.com`)
- **Used for**: Tool-based agent chat, WebSocket streaming, multi-turn conversation
- **File**: `ai_agent.py` (2,219 lines)
- **Features**: Tool calling, streaming, system prompts with accounting knowledge
- **API Key**: `ANTHROPIC_API_KEY`

#### Tier 2: NVIDIA Nemotron 3 Super 120B (Reasoning — Preferred)
- **Model**: `nvidia/nemotron-3-super-120b-a12b`
- **Provider**: NVIDIA build.nvidia.com API (`integrate.api.nvidia.com`)
- **Used for**: Deep financial reasoning, chain-of-thought analysis, structured reports
- **File**: `local_llm.py` (_try_nvidia method), `structured_report_engine.py`
- **Features**:
  - `enable_thinking: true` — chain-of-thought reasoning mode
  - `reasoning_budget: 4096` — up to 4K tokens of internal reasoning
  - Separate `content` (final answer) and `reasoning_content` (CoT trace) fields
  - 90-second timeout for complex reasoning
- **API Key**: `NVIDIA_API_KEY` (`nvapi-...`)
- **Priority**: Preferred over Ollama in `local_llm.chat()` — tried first

#### Tier 3: xAI Grok 4.1 Fast (Fast Reasoning Backup)
- **Model**: `grok-4-1-fast-non-reasoning`
- **Provider**: xAI API (`api.x.ai`)
- **Used for**: Fast LLM reasoning when Claude is rate-limited
- **File**: `llm_chain.py`
- **API Key**: `XAI_GROK_API_KEY`

#### Tier 4: Mistral Large (Cost-Effective Backup)
- **Model**: `mistral-large-latest`
- **Provider**: Mistral AI API (`api.mistral.ai`)
- **Used for**: Backup reasoning when Claude + Grok unavailable
- **File**: `llm_chain.py`
- **API Key**: `MISTRAL_API_KEY`

#### Tier 5: Ollama Local (Offline Fallback)
- **Models**: `llama3.2:3b` (2GB), `qwen2.5:3b` (2GB), `mistral:7b` (4GB)
- **Provider**: Local Ollama server (`localhost:11434`)
- **Used for**: Offline operation, zero-cost inference, development
- **File**: `local_llm.py`
- **Complexity routing**:
  - `fast` → llama3.2:3b (classification, short answers)
  - `balanced` → llama3.2:3b (reasoning, commentary)
  - `capable` → llama3.2:3b (complex reasoning, multi-turn)
- **Endpoints**: `/api/chat` (preferred) → `/api/generate` (fallback)

#### Tier 6: Template Fallback (Always Works)
- **Provider**: Deterministic templates in code
- **Used for**: When ALL LLMs are unavailable
- **File**: `llm_chain.py` (template_fallback)
- **Features**: Structured JSON response, no AI needed

#### Strict Rule
> LLMs NEVER generate financial numbers. They ONLY explain, reason, and provide insights. All numbers come from deterministic computation (CalculationEngine with Python Decimal).

#### Where Each Model is Used

| Use Case | Primary Model | Fallback |
|----------|---------------|----------|
| Agent chat (tool-based) | Claude Sonnet 4 | Template |
| WebSocket streaming | Claude Sonnet 4 | N/A |
| CFO reasoning & insights | Claude → Grok → Mistral → Ollama → Template | Chain |
| Deep financial reasoning | NVIDIA Nemotron 120B (CoT) | Ollama |
| Structured report generation | NVIDIA Nemotron 120B | Claude |
| Sheet classification | Ollama local | Rule-based |
| Account classification | Claude (tool-based) | COA rules |
| Knowledge graph queries | Claude | Template |

---

## 2. BACKEND ARCHITECTURE

### 2.1 Application Entry (main.py)

**Startup sequence:**
1. Database init (async SQLAlchemy, table creation, migrations)
2. Vector store init (ChromaDB)
3. Cache init (Redis or in-memory)
4. Report scheduler start
5. Multi-agent system init (5 agents + supervisor)
6. Agent memories indexed into RAG
7. Ollama availability check

**Middleware:**
- CORS (configurable origins)
- Request timing (logs >2000ms)
- Global exception handler

**WebSocket:** `/ws/chat` - Token-by-token streaming AI responses

### 2.2 API Routers (11 routers, 150+ endpoints)

#### `/api/datasets` - Dataset Management (30+ endpoints)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /upload | Upload & parse Excel/CSV |
| GET | / | List datasets |
| GET | /{id} | Dataset details |
| PUT | /{id}/activate | Activate dataset |
| POST | /{id}/reparse | Re-parse file |
| DELETE | /{id} | Delete dataset |
| GET | /{id}/snapshots | Version history |
| GET | /{id}/etl-events | ETL audit trail |
| GET/POST/DELETE | /product-mappings | Product classification |
| GET/POST/DELETE | /coa-mappings | COA overrides |
| GET/POST/PUT/DELETE | /coa-master | Master chart of accounts (406 accounts) |
| POST | /{id}/regenerate-bs | Regenerate balance sheet |
| POST | /{id}/regenerate-pl | Regenerate P&L |

#### `/api/analytics` - Financial Analytics
| Method | Path | Purpose |
|--------|------|---------|
| GET | /dashboard | Dashboard KPIs |
| GET | /pl | P&L statement |
| GET | /income-statement | Full structured income statement |
| GET | /pl/compare | Multi-period comparison |
| GET | /balance-sheet | Balance sheet |
| GET | /revenue | Revenue analysis |
| GET | /transactions | Transaction listing |
| GET | /kpis | KPI evaluation |

#### `/api/agent` - AI Agent System (28 endpoints)
| Method | Path | Purpose |
|--------|------|---------|
| POST | /chat | Chat request |
| POST | /command | Command execution |
| GET/POST/DELETE | /memory | Agent memory CRUD |
| POST | /feedback | User feedback (up/down) |
| POST | /agents/smart-upload | Upload + full analysis |
| POST | /agents/smart-analyze | Analyze existing file |
| POST | /agents/orchestrator/run | 7-stage analysis pipeline |
| POST | /agents/strategy/generate | Strategy generation |
| POST | /agents/sensitivity/analyze | Sensitivity analysis |
| POST | /agents/sensitivity/monte-carlo | Monte Carlo simulation |
| POST | /agents/decisions/generate | Decision support |
| POST | /agents/analogy/search | Pattern matching |
| POST | /agents/forecast/ensemble | Ensemble forecasting |
| POST | /agents/reasoning/explain | Causal reasoning |
| POST | /agents/reasoning/collaborative | Multi-agent reasoning |
| POST | /agents/gl/full-pipeline | GL pipeline |
| GET | /agents/status | Agent health |
| GET | /agents/knowledge-graph | Knowledge graph data |
| POST | /agents/orchestrator/pdf | PDF report generation |

#### `/api/mr` - Management Reporting
| Method | Path | Purpose |
|--------|------|---------|
| POST | /exchange-rates | Create/update FX rate |
| GET | /exchange-rates | List rates |
| POST | /generate | Generate MR report (DB-based) |
| POST | /generate-excel | Generate MR Excel from template **[NEW]** |
| GET | /snapshots | Report version history |
| GET | /snapshots/{id}/excel | Export as Excel |

#### `/api/auth` - Authentication
| Method | Path | Purpose |
|--------|------|---------|
| POST | /register | User registration |
| POST | /login | JWT login |
| GET | /me | Current user info |

#### `/api/advanced` - Advanced Features (24 endpoints)
Forecasting, Scenarios, Anomalies, Currency, Scheduling, Lineage, Trends

#### `/api/reports` - Report CRUD & Export
#### `/api/schemas` - Schema Profile Management
#### `/api/documents` - Document RAG Pipeline
#### `/api/external-data` - Live Market Data (NBG rates, commodities)
#### `/api/tools` - Custom Tool Sync

### 2.3 Database Models (27 tables)

#### Core Financial
| Model | Table | Key Columns |
|-------|-------|-------------|
| Dataset | datasets | name, is_active, period, currency, status, parse_metadata |
| Transaction | transactions | date, acct_dr, acct_cr, dept, type, amount, vat |
| RevenueItem | revenue_items | product, gross, vat, net, segment, category |
| COGSItem | cogs_items | product, col6/col7310/col8230_amount, total_cogs |
| GAExpenseItem | ga_expense_items | account_code, account_name, amount |
| BalanceSheetItem | balance_sheet_items | account_code, ifrs_line_item, opening/closing balances |
| TrialBalanceItem | trial_balance_items | account_code, debit/credit turnovers, mr_mapping |
| BudgetLine | budget_lines | line_item, budget_amount, actual_amount |
| Report | reports | title, type, period, rows (JSON), kpis |

#### Mapping & Config
| Model | Table | Purpose |
|-------|-------|---------|
| COAMasterAccount | coa_master_accounts | 406 Georgian COA accounts with IFRS mapping |
| COAMappingOverride | coa_mapping_overrides | User-editable account mappings |
| ProductMapping | product_mappings | Product classification (fuel types, segments) |

#### Audit & Versioning
| Model | Table | Purpose |
|-------|-------|---------|
| DatasetSnapshot | dataset_snapshots | Immutable version + fingerprint |
| ETLAuditEvent | etl_audit_events | Step-by-step ETL audit |
| DataLineage | data_lineage | Origin tracking per figure |

#### Advanced
| Model | Table | Purpose |
|-------|-------|---------|
| Forecast | forecasts | Revenue/expense forecasts |
| Scenario | scenarios | What-if scenarios |
| Anomaly | anomalies | Statistical anomaly detections |
| ExchangeRate | exchange_rates | Historical FX rates |
| MRReportSnapshot | mr_report_snapshots | MR report versions (USD) |
| ScheduledReport | scheduled_reports | Email delivery scheduling |

#### Agent & Auth
| Model | Table | Purpose |
|-------|-------|---------|
| User | users | Roles: admin, analyst, viewer |
| AgentMemory | agent_memory | Persistent agent memories |
| AgentAuditLog | agent_audit_log | Multi-agent audit trail |
| Feedback | feedback | User feedback (up/down/correction) |
| LearningRecord | learning_records | Classification improvement |

### 2.4 Services (60+ modules)

#### Data Parsing Pipeline
| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| FileParser | file_parser.py | 3,284 | Main Excel/CSV parser, Georgian COA, product classification |
| MultiSheetAnalyzer | multi_sheet_analyzer.py | 824 | Sheet type detection + extraction |
| SOCARUniversalParser | socar_universal_parser.py | ~500 | **[NEW]** Clean parser for both file formats |
| SOCARPLEngine | socar_pl_engine.py | 448 | SOCAR-specific P&L builder |
| SmartExcelParser | smart_excel_parser.py | 672 | Universal fuzzy parser |
| UploadIntelligence | upload_intelligence.py | ~300 | **[NEW]** Upload assessment (sheets, capabilities, missing data) |

#### Financial Computation
| Service | File | Purpose |
|---------|------|---------|
| IncomeStatement | income_statement.py | P&L building from DB records |
| COAEngine | coa_engine.py | Structured P&L row builder |
| CalculationEngine | calculation_engine.py | Deterministic Decimal math |
| CashFlow | cash_flow.py | Cash flow analysis |
| CurrencyService | currency_service.py | FX conversion |

#### MR Reporting
| Service | File | Purpose |
|---------|------|---------|
| MREngine | mr_engine.py | 1,408 lines, IFRS/Baku mapping engine |
| MRTemplate | mr_template.py | 1,153 lines, 13-sheet template definition |
| MRReportGenerator | mr_report_generator.py | **[NEW]** Excel template filler (GEL to USD) |
| MRMapping | mr_mapping.py | COA to Baku MR code mapping |

#### AI, LLM & Reasoning
| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| AIAgent | ai_agent.py | 2,219 | Tool-based Claude Sonnet 4 interface |
| LocalLLMService | local_llm.py | ~300 | NVIDIA Nemotron (preferred) + Ollama (fallback) |
| LLMChain | llm_chain.py | ~200 | 4-tier chain: Claude → Grok → Mistral → Ollama → Template |
| StructuredReportEngine | structured_report_engine.py | ~300 | Nemotron-powered multi-section reports |
| KnowledgeGraph | knowledge_graph.py | 2,579 | Financial domain knowledge graph |
| DeepReasoning | deep_reasoning_engine.py | ~800 | Complex financial reasoning |
| ReasoningSession | reasoning_session.py | 1,873 | Deep reasoning with hypothesis |
| FinancialReasoning | financial_reasoning.py | 1,022 | Causal financial reasoning |
| HypothesisParser | hypothesis_parser.py | 1,386 | Hypothesis analysis |
| DebateEngine | debate_engine.py | ~600 | Multi-perspective analysis |
| DecisionEngine | decision_engine.py | 1,065 | Decision support |
| StrategyEngine | strategy_engine.py | ~800 | Strategic recommendations |
| NarrativeEngine | narrative_engine.py | ~500 | Natural language reporting |
| FinancialOntology | financial_ontology.py | 1,020 | **[NEW]** Domain knowledge for LLM |
| AccountingKnowledge | accounting_knowledge.py | ~500 | Georgian COA knowledge for LLM prompts |

#### RAG & Knowledge
| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| VectorStore | vector_store.py | 1,408 | ChromaDB + LlamaIndex RAG |
| DocumentIngestion | document_ingestion.py | ~400 | PDF/Word/Excel chunking |
| Cache | cache.py | ~300 | Redis/in-memory caching |

#### Analytics
| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| ForecastEngine | forecasting.py | 1,146 | Moving avg, exp smoothing, regression |
| AnomalyDetector | anomaly_detector.py | ~500 | Z-score, IQR, Benford |
| ScenarioEngine | scenario_engine.py | ~400 | What-if modeling |
| BenchmarkEngine | benchmark_engine.py | ~300 | Industry comparison |
| TrendAnalyzer | trend_analyzer.py | ~200 | Period-over-period trends |

### 2.5 Multi-Agent System

**5 Specialized Agents + Supervisor:**

| Agent | Purpose | Tools |
|-------|---------|-------|
| **Supervisor** | Routes requests, monitors health, fallback | All tools |
| **CalcAgent** | Deterministic financial calculations | Calculator |
| **DataAgent** | Data ingestion & transformation | Parser, COA |
| **InsightAgent** | Financial analysis & insights | KG, Reasoning |
| **ReportAgent** | Report generation | Templates, Export |
| **LegacyAgent** | Monolithic fallback | All (original) |

**Health Monitoring:** Circuit breaker pattern - disable agent after N failures, exponential backoff recovery.

### 2.6 Environment Configuration (LLM Keys)

| Variable | Provider | Usage |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | Anthropic | Claude Sonnet 4 (primary agent, chat) |
| `NVIDIA_API_KEY` | NVIDIA build.nvidia.com | Nemotron 3 Super 120B (reasoning, reports) |
| `XAI_GROK_API_KEY` | xAI | Grok 4.1 Fast (fast reasoning backup) |
| `MISTRAL_API_KEY` | Mistral AI | Mistral Large (cost-effective backup) |
| `ANTHROPIC_MODEL` | Config | Model ID override (default: claude-sonnet-4-20250514) |
| `OLLAMA_BASE_URL` | Local | Ollama server (default: http://localhost:11434) |

### 2.7 LangGraph Pipeline (10 nodes)

```
data_extractor → calculator → insight_engine → memory → orchestrator
                                                         ↓
                                            reasoner → alert → anomaly_detector
                                                                    ↓
                                                            whatif_simulator → report_generator
```

---

## 3. FRONTEND ARCHITECTURE

### 3.1 Technology

| Library | Version | Purpose |
|---------|---------|---------|
| React | 19.2 | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 8.x | Build tool (port 3000, proxy to :9200) |
| Zustand | 5.0 | Global state management |
| TanStack React Query | 5.91 | Server state + caching |
| Recharts | 3.8 | Charts (line, bar, pie) |
| XyFlow | 12.10 | Node graphs (workflow visualization) |
| Radix UI | latest | Accessible UI primitives |
| Tailwind CSS | 4.2 | Utility-first styling |
| Framer Motion | 12.38 | Animations |
| Lucide React | latest | 600+ icons |
| i18next | 25.10 | EN/KA translations |
| Sonner | 2.0 | Toast notifications |

### 3.2 Routing (35 pages)

| Route | Page | Data Source |
|-------|------|-------------|
| `/` | DashboardPage | store.pnl, store.balance_sheet |
| `/library` | UploadPage | api.upload(), api.listDatasets() |
| `/pnl` | PnLPage | store.pnl, store.pl_line_items |
| `/balance-sheet` | BalanceSheetPage | store.balance_sheet |
| `/revenue` | RevenuePage | store.revenue_breakdown |
| `/costs` | CostsPage | store.cogs_breakdown |
| `/budget` | BudgetPage | (placeholder - needs Budget sheet) |
| `/mr-reports` | ReportsPage | api.pdfReport(), api.excelReport() |
| `/cash-runway` | CashRunwayPage | api.runway() |
| `/kpi-monitor` | KPIMonitorPage | api.kpi() |
| `/ai-intelligence` | ChatPage | api.command() |
| `/benchmarks` | BenchmarksPage | api.benchmarkCompare() |
| `/forecasts` | ForecastsPage | api.forecast() |
| `/gl-pipeline` | GLPipelinePage | (placeholder) |
| `/reasoning` | ReasoningPage | api.explain(), api.scenario() |
| `/orchestrator` | OrchestratorPage | api.orchestrate() |
| `/strategy` | StrategyPage | api.strategy() |
| `/sensitivity` | SensitivityPage | api.sensitivity(), api.monteCarlo() |
| `/decisions` | DecisionsPage | api.decisions() |
| `/analogies` | AnalogiesPage | api.analogies() |
| `/alerts` | AlertsPage | api.alerts() (15s polling) |
| `/predictions` | PredictionsPage | api.recordPrediction() |
| `/transactions` | TransactionsPage | store.pl_line_items |
| `/market` | MarketDataPage | (static/estimated) |
| `/system` | SystemPage | api.status(), api.health() |
| `/workflow` | WorkflowPage | ReactFlow graph |
| `/ai-report` | StructuredReportPage | AI-generated sections |
| `/eval` | EvalPage | api.evalCases() |
| `/login` | LoginPage | api.login() |

### 3.3 State Management (Zustand Store)

```typescript
interface FinAIState {
  // Auth
  user: { email, role, token } | null;

  // Core financial data
  dataset_id: number | null;
  company: string | null;
  period: string | null;
  pnl: {
    revenue, cogs, gross_profit,
    selling_expenses, admin_expenses, ga_expenses,   // [NEW]
    ebitda, depreciation, ebit,                       // [NEW]
    non_operating_income, non_operating_expense,      // [NEW]
    interest_income, interest_expense, fx_gain_loss,  // [NEW]
    profit_before_tax, net_profit,                    // [NEW]
    revenue_wholesale, revenue_retail, revenue_other,
    cogs_wholesale, cogs_retail,
  } | null;
  balance_sheet: Record<string, number> | null;
  revenue_breakdown: { product, net_revenue, category }[];
  cogs_breakdown: { product, amount }[];
  pl_line_items: { code, label, amount, type, level }[];
  revenue_by_category: Record<string, number>;

  // Quality & Assessment
  data_quality_score: number | null;      // [NEW]
  upload_assessment: object | null;       // [NEW]

  // Intelligence
  orchestrator: object | null;
  alerts: { severity, message }[];
  llm_insights: { severity, title, explanation, action }[];
  llm_summary: string;

  // UI
  lang: 'en' | 'ka';
  theme: 'dark' | 'light';
  isLoading: boolean;
  error: string | null;
}
```

### 3.4 API Client (174 lines)

Base URL: `/api/agent` with Bearer token auth.

**40+ API functions** organized by domain:
- Upload & Data: upload, dashboard, listDatasets
- Analytics: orchestrate, strategy, sensitivity, monteCarlo, decisions, analogies
- Monitoring: alerts, kpi, runway, expenseSpikes
- Predictions: recordPrediction, resolvePrediction, predictionAccuracy
- Benchmarks: industries, benchmarkCompare
- Forecasts: forecast, backtest
- GL: glPipeline, trialBalance
- Reports: pdfReport, briefReport, excelReport
- Reasoning: explain, scenario
- System: status, health, telemetry

### 3.5 Components (8 reusable)

| Component | Purpose |
|-----------|---------|
| Layout | Main app shell: sidebar nav (8 groups), embedded chat, theme/lang toggle |
| ActionBar | Page header with export/filter controls |
| AlertBanner | Dismissible severity-coded notifications |
| CausalGraph | ReactFlow causal relationship visualization |
| HealthGauge | Animated SVG circular score gauge |
| KPICard | Animated metric card with sparkline |
| PeriodSelector | **[NEW]** Global month/year picker with available periods |
| OperationChain | **[NEW]** Process step visualization (pending/running/done/error) |

### 3.6 Styling

**Dark theme** (default) with glassmorphism:
- Background: `#030508` to `#181c29`
- Accent: `#38bdf8` (cyan), `#60a5fa` (blue), `#a78bfa` (violet)
- Status: `#34d399` (success), `#fbbf24` (warning), `#f87171` (danger)
- Fonts: Inter (text), JetBrains Mono (numbers/code)
- `.glass` class: `backdrop-filter: blur(16px)` cards

---

## 4. DATA FLOW

### 4.1 Upload Flow (Primary)

```
User drops Excel → UploadPage
    ↓
POST /api/agent/agents/smart-upload
    ↓
[1] Save file to uploads/
[2] MultiSheetAnalyzer.analyze_file() → detect sheets, extract financials
[3] SOCARUniversalParser.parse_socar_excel() → complete P&L with G&A, D&A, BS  [NEW]
[4] Merge universal parser results (selling_expenses, admin_expenses, depreciation...)
[5] UploadIntelligence.assess_upload() → what's available, what's missing  [NEW]
[6] DataStore.save_financials()
[7] SOCAR P&L Engine → product-level breakdown
[8] Orchestrator → health score, strategy
    ↓
Response → useStore.setFromUpload()
    ↓
All pages re-render with new data
```

### 4.2 Standard Upload Flow (datasets/upload)

```
POST /api/datasets/upload
    ↓
[1] Schema validation (deterministic)
[2] Load COA master + overrides + product mappings
[3] file_parser.parse_file()
    ├─ Name-based priority: Mapping → BS → Budget
    ├─ Content-based detection: TDSheet, Balance, COGS, Revenue
    ├─ GA/DA ALWAYS from Mapping (primary source)  [FIXED]
    ├─ Depreciation from sub-accounts + column F  [FIXED]
    ├─ BS preformatted → balance_sheet_items  [FIXED]
    ├─ Period detection from Russian text  [NEW]
    └─ Data quality flags + score  [NEW]
[4] Fingerprint + duplicate detection
[5] Create Dataset + Snapshot
[6] Insert: Transactions, Revenue, COGS, GA, DA, TB, BS items
[7] Synthesize GL entries from TB/BS if no raw transactions
[8] Auto-populate MR mappings
[9] Auto-index for RAG search
    ↓
Response: { id, name, file_type, record_count, status, parse_metadata }
```

### 4.3 MR Report Generation Flow

```
POST /api/mr/generate-excel
    ↓
[1] Find MR template (ANNUAL_MR_REPORT_2023.xlsx)
[2] Get parsed data (from latest upload or re-parse)
[3] mr_report_generator.generate_mr_report()
    ├─ PL_MAPPING: 38 P&L codes → GEL values → /rate/1000 → thsd USD
    ├─ BS_MAPPING: 23 BS codes → GEL values → /rate_eop/1000 → thsd USD
    ├─ Fill Currency sheet with avg/eop/boy rates
    └─ Clean Azerbaijani text (keep English only)
    ↓
Return: downloadable .xlsx file
```

### 4.4 P&L Computation Flow

```
Revenue Breakdown sheet → RevenueItem records
    ↓ SUM by category
Revenue (Wholesale + Retail + Other)
    ↓ MINUS
COGS Breakdown sheet → COGSItem records → COGS total
    ↓ EQUALS
Gross Profit
    ↓ MINUS
Mapping sheet → GAExpenseItem records
    ├─ Account 7310 → Selling Expenses
    ├─ Account 7410 → Admin Expenses
    ├─ Account 7310.*/7410.* (col F = Depreciation) → D&A
    ├─ Account 8110 (NOI:) → Non-operating Income
    ├─ Account 8220/8230 → Non-operating Expenses
    └─ Account 9210 → Tax
    ↓ COMPUTES
EBITDA = GP - Selling - Admin
EBIT = EBITDA - Depreciation
EBT = EBIT + NonOp Income - NonOp Expense + Finance Net
Net Profit = EBT - Tax
```

---

## 5. INTEGRATION STATUS

### 5.1 Fully Integrated (Working End-to-End)

| Feature | Backend | Frontend | Status |
|---------|---------|----------|--------|
| Excel upload + parsing | file_parser.py | UploadPage.tsx | WORKING |
| Revenue/COGS extraction | file_parser.py | RevenuePage, CostsPage | WORKING |
| G&A + Depreciation extraction | file_parser.py [FIXED] | PnLPage.tsx [NEW] | WORKING |
| BS sheet parsing | file_parser.py [FIXED] | BalanceSheetPage.tsx | WORKING |
| Complete P&L waterfall | income_statement.py + universal parser | PnLPage.tsx [NEW] | WORKING |
| Dashboard KPIs | analytics.py | DashboardPage.tsx [NEW] | WORKING |
| Smart-upload (agent) | agent.py (smart-upload) | UploadPage.tsx | WORKING |
| MR Report Excel export | mr_report_generator.py [NEW] | (endpoint ready) | WORKING |
| Upload Intelligence | upload_intelligence.py [NEW] | (data in store) | WORKING |
| Data quality flags | file_parser.py [NEW] | (in parse_metadata) | WORKING |
| Period detection (RU) | file_parser.py [NEW] | (auto-detected) | WORKING |
| Product classification | file_parser.py | RevenuePage.tsx | WORKING |
| COA mapping (406 accts) | file_parser.py + coa_engine.py | SettingsPage.tsx | WORKING |
| Multi-sheet detection | multi_sheet_analyzer.py | UploadPage.tsx | WORKING |
| AI Chat | ai_agent.py + Claude API | ChatPage.tsx | WORKING |
| JWT Auth | auth.py + auth_router.py | LoginPage.tsx | WORKING |
| Report export (PDF/Excel) | reports.py + excel_export.py | ReportsPage.tsx | WORKING |
| Alerts monitoring | agent.py (/alerts) | AlertsPage.tsx | WORKING |
| System health | agent.py (/status, /health) | SystemPage.tsx | WORKING |
| Theme toggle | N/A | Layout.tsx | WORKING |
| Language toggle (EN/KA) | N/A | Layout.tsx + translations.ts | WORKING |

### 5.2 Integrated But Needs Data/Activation

| Feature | Backend | Frontend | What's Missing |
|---------|---------|----------|----------------|
| Orchestrator pipeline | orchestrator_v3.py | OrchestratorPage.tsx | Needs upload first, then click "Run" |
| Strategy generation | strategy_engine.py | StrategyPage.tsx | Needs orchestrator results |
| Sensitivity analysis | agent.py (/sensitivity) | SensitivityPage.tsx | Needs P&L data |
| Monte Carlo simulation | agent.py (/monte-carlo) | SensitivityPage.tsx | Needs P&L data |
| Decision engine | decision_engine.py | DecisionsPage.tsx | Needs P&L + BS data |
| Analogies/patterns | agent.py (/analogy) | AnalogiesPage.tsx | Needs P&L data |
| Benchmarks | benchmark_engine.py | BenchmarksPage.tsx | Needs P&L data |
| Forecasting | forecasting.py | ForecastsPage.tsx | Needs multi-period data |
| KPI Monitor | agent.py (/kpi) | KPIMonitorPage.tsx | Needs P&L data |
| Cash Runway | agent.py (/cash-runway) | CashRunwayPage.tsx | Needs BS cash + P&L |
| Predictions | agent.py (/predictions) | PredictionsPage.tsx | Manual input |
| Causal reasoning | reasoning_session.py | ReasoningPage.tsx | Needs metric + change |
| MR Report (DB-based) | mr_engine.py + mr_template.py | ReportsPage.tsx | Needs TB items + rates |
| Anomaly detection | anomaly_detector.py | AlertsPage.tsx | Needs historical data |
| Data lineage | advanced.py (/lineage) | (no dedicated page) | Accessible via API |
| RAG search | vector_store.py | ChatPage (implicit) | Active in chat context |

### 5.3 Backend Exists, Frontend Placeholder/Missing

| Feature | Backend | Frontend Status |
|---------|---------|-----------------|
| Budget analysis | Budget sheet parsing | BudgetPage.tsx = placeholder |
| GL Pipeline | agent.py (/gl) | GLPipelinePage.tsx = placeholder |
| Custom tools | tools.py router | PlaceholderPage ("Coming Soon") |
| Document RAG | documents_router.py | No dedicated page (API only) |
| Scheduled reports | scheduler.py | No UI (API only) |
| Schema management | schemas.py | No UI (API only) |
| Exchange rate CRUD | mr_reports.py | No UI (API only) |
| Expense spikes | agent.py (/expense-spikes) | No UI (API only) |
| Multi-variable sensitivity | agent.py (/multi-variable) | No UI (API only) |
| Collaborative reasoning | agent.py (/collaborative) | No UI (API only) |
| Account classification AI | agent.py (/classify-account) | No UI (API only) |

### 5.4 Frontend Exists, Backend Partially Ready

| Page | What It Shows | What Backend Provides |
|------|---------------|----------------------|
| MarketDataPage | FX rates, fuel prices, macro | external_data.py (estimated/cached) |
| WorkflowPage | Agent node graph | Static visualization |
| StructuredReportPage | AI-generated report sections | Needs full orchestrator run |
| EvalPage | AI evaluation cases | evaluation_cases.json |

---

## 6. FILE STRUCTURE

### Backend (78,323 lines, 127 files)
```
backend/
  main.py                          # FastAPI entry, 250+ lines
  app/
    config.py                      # Settings (env vars)
    database.py                    # Async SQLAlchemy
    auth.py                        # JWT + bcrypt
    models/
      all_models.py                # 27 SQLAlchemy models
    routers/
      advanced.py                  # 24 endpoints
      agent.py                     # 28 endpoints (2,782 lines)
      analytics.py                 # P&L, BS, KPIs (2,738 lines)
      auth_router.py               # Login/register
      datasets.py                  # Upload/CRUD (1,719 lines)
      documents_router.py          # RAG ingestion
      external_data_router.py      # Market data
      mr_reports.py                # MR reporting (1,510 lines)
      reports.py                   # Report CRUD
      schemas.py                   # Schema profiles
      tools.py                     # Custom tools
    services/
      file_parser.py               # Main parser (3,284 lines)
      socar_universal_parser.py    # [NEW] Clean dual-format parser
      multi_sheet_analyzer.py      # Sheet detection
      socar_pl_engine.py           # SOCAR P&L builder
      smart_excel_parser.py        # Universal fuzzy parser
      upload_intelligence.py       # [NEW] Upload assessment
      upload_integration.py        # [NEW] Smart-upload handler
      mr_report_generator.py       # [NEW] Excel template filler
      financial_ontology.py        # [NEW] Domain knowledge
      parent_child_segmentation.py # [NEW] Product hierarchy
      income_statement.py          # P&L from DB records
      coa_engine.py                # Structured P&L rows
      mr_engine.py                 # MR reporting engine (1,408 lines)
      mr_template.py               # 13-sheet template (1,153 lines)
      mr_mapping.py                # COA to MR code mapping
      ai_agent.py                  # Claude tool interface (2,219 lines)
      knowledge_graph.py           # Financial KG (2,579 lines)
      vector_store.py              # ChromaDB RAG (1,408 lines)
      forecasting.py               # Forecast engine (1,146 lines)
      anomaly_detector.py          # Anomaly detection
      scenario_engine.py           # What-if modeling
      decision_engine.py           # Decision support (1,065 lines)
      strategy_engine.py           # Strategy generation
      financial_intelligence.py    # Smart resolver (1,128 lines)
      financial_reasoning.py       # Reasoning (1,022 lines)
      reasoning_session.py         # Deep reasoning (1,873 lines)
      hypothesis_parser.py         # Hypothesis analysis (1,386 lines)
      deep_reasoning_engine.py     # Complex reasoning
      debate_engine.py             # Multi-perspective
      narrative_engine.py          # NL reporting
      calculation_engine.py        # Decimal math
      cash_flow.py                 # Cash flow
      benchmark_engine.py          # Industry benchmarks
      currency_service.py          # FX conversion
      document_ingestion.py        # PDF/Word chunking
      external_data.py             # Market API integration
      scheduler.py                 # Report scheduling (1,105 lines)
      job_manager.py               # Async jobs
      cache.py                     # Redis/in-memory
      data_store.py                # Legacy data store
      data_validator.py            # Financial validation
      local_llm.py                 # Ollama fallback
      schema_registry_db.py        # Schema validation
      llm_chain.py                 # LLM chain
      file_intelligence.py         # LLM sheet classification
      knowledge/
        llm_reasoning_prompt.md    # [NEW] LLM reasoning template
    agents/
      base.py                      # AgentTask, AgentResult, AgentHealth
      registry.py                  # Agent registry
      supervisor.py                # Orchestrating supervisor (1,204 lines)
      calc_agent.py                # Financial calculations
      data_agent.py                # Data ingestion
      insight_agent.py             # Analysis (1,297 lines)
      report_agent.py              # Report generation
      legacy_agent.py              # Monolithic fallback
    graph/
      graph.py                     # LangGraph pipeline
      state.py                     # FinAIState TypedDict
      nodes.py                     # 10 pipeline nodes
    memory/
      company_memory.py            # Company context memory
    orchestrator/
      orchestrator_v3.py           # 7-stage analysis pipeline
    utils/
      excel_export.py              # Excel formatting
  data/
    finai_store.db                 # SQLite database
    chromadb/                      # Vector store
    MR_Report_January_2026.xlsx    # [NEW] Sample MR export
  tests/
    test_api.py, test_decimal.py, test_export.py
  Dockerfile, docker-compose.yml
  requirements.txt
```

### Frontend (7,343 lines, 47 files)
```
frontend/
  package.json                     # React 19, Vite, Zustand, Recharts, etc.
  vite.config.ts                   # Port 3000, proxy to :9200
  tsconfig.app.json                # Strict TypeScript
  src/
    main.tsx                       # React root
    App.tsx                        # BrowserRouter + QueryClient + Routes
    index.css                      # Tailwind + CSS variables (dark/light theme)
    store/
      useStore.ts                  # Zustand global state (244 lines)
    api/
      client.ts                    # 40+ API functions (174 lines)
    pages/                         # 35 pages
      DashboardPage.tsx            # [NEW] KPIs + P&L summary + BS
      PnLPage.tsx                  # [NEW] Full P&L waterfall
      UploadPage.tsx               # Drag-drop + dataset management
      BalanceSheetPage.tsx         # BS hierarchical table
      RevenuePage.tsx              # Revenue pie + table
      CostsPage.tsx                # COGS breakdown
      ChatPage.tsx                 # AI chat interface
      ReportsPage.tsx              # PDF/Excel export
      OrchestratorPage.tsx         # 7-stage pipeline
      StrategyPage.tsx             # Strategy generation
      SensitivityPage.tsx          # Tornado + Monte Carlo
      DecisionsPage.tsx            # CFO verdict + actions
      ReasoningPage.tsx            # Causal graph
      AlertsPage.tsx               # Real-time alerts
      ForecastsPage.tsx            # Time series forecast
      BenchmarksPage.tsx           # Industry comparison
      KPIMonitorPage.tsx           # KPI tracking
      CashRunwayPage.tsx           # Cash sustainability
      PredictionsPage.tsx          # Prediction tracking
      TransactionsPage.tsx         # GL line items
      MarketDataPage.tsx           # Market data cards
      SystemPage.tsx               # System health
      WorkflowPage.tsx             # Agent graph
      EvalPage.tsx                 # AI evaluation
      SettingsPage.tsx             # Configuration
      LoginPage.tsx                # JWT auth
      AnalysisPage.tsx             # Navigation hub
      StructuredReportPage.tsx     # AI report
      BudgetPage.tsx               # Placeholder
      GLPipelinePage.tsx           # Placeholder
      AnalogiesPage.tsx            # Pattern matching
      PlaceholderPage.tsx          # "Coming Soon"
    components/
      Layout.tsx                   # App shell (692 lines)
      ActionBar.tsx                # Page header
      AlertBanner.tsx              # Notifications
      CausalGraph.tsx              # ReactFlow graph
      HealthGauge.tsx              # SVG gauge
      KPICard.tsx                  # Metric card
      PeriodSelector.tsx           # [NEW] Month picker
      OperationChain.tsx           # [NEW] Process steps
    i18n/
      translations.ts             # EN/KA (170 lines)
    utils/
      format.ts                   # Currency formatting
      exportCsv.ts                # CSV download
```

---

## 7. DEPLOYMENT

### Docker Compose

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://finai:finai@db:5432/finai
      REDIS_URL: redis://redis:6379
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    depends_on: [db, redis]

  db:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7

  nginx:
    ports: ["80:80", "443:443"]
    depends_on: [api]
```

### Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 9200 --reload

# Frontend
cd frontend
npm install
npm run dev   # port 3000, proxies /api to :9200
```
