# FinAI Developer Onboarding Guide

Welcome to the NYX Core FinAI codebase. This guide gets you productive within 5 days.

---

## Part 1 — Architecture Overview (Day 1)

### System Architecture

```
User Upload (.xlsx/.csv)
    │
    ▼
SmartExcelParser (app/services/smart_excel_parser.py)
    │  Fuzzy column matching, Georgian/Russian/English
    │  All values converted to Decimal at boundary
    │
    ▼
LangGraph Pipeline (app/graph/graph.py) ← THE canonical pipeline
    │
    ├─ data_extractor    → Parse file, classify data type
    ├─ calculator         → Decimal math only, never float
    ├─ insight_engine     → Reconstruction, completeness check
    ├─ circuit_breaker    → Halt if BS equation fails or data corrupt
    ├─ memory             → Cross-period comparison
    ├─ orchestrator       → Legacy 7-stage (conditional)
    ├─ anomaly_detector   → Statistical outlier detection
    ├─ whatif_simulator    → Scenario analysis
    ├─ reasoner           → LLM explains (Claude → Ollama → Template)
    ├─ alerts             → Threshold/anomaly alerts
    └─ report_generator   → Excel export
    │
    ▼
API Response (JSON)
```

### Key Design Decisions

1. **Decimal, not float** — All financial math uses Python `Decimal` with `ROUND_HALF_UP`. Float is only used for non-financial values (timestamps, confidence scores). See ADR-002.

2. **Symbolic validation before LLM** — The constraint graph validates BS equation, TB balance, and GAAP rules *before* the LLM sees the data. The LLM explains numbers — it never computes them. See ADR-003.

3. **Circuit breaker** — If data integrity checks fail (BS equation, NaN values, completeness < 30%), the pipeline halts immediately rather than producing unreliable narratives. See `app/orchestrator/circuit_breaker.py`.

4. **Multi-tenancy via SQLAlchemy event listener** — Every SELECT on tenant-scoped models is automatically filtered by `company`. See ADR-004.

---

## Part 2 — Domain Knowledge (Day 2-3)

### Georgian IFRS Account Structure

Georgian Chart of Accounts follows a class-digit system (similar to European):

| Class | Category | BS/IS | Side |
|-------|----------|-------|------|
| 1 | Non-current assets | BS | Asset |
| 2 | Current assets | BS | Asset |
| 3 | Equity | BS | Equity |
| 4 | Non-current liabilities | BS | Liability |
| 5 | Current liabilities | BS | Liability |
| 6 | Revenue | IS | Income |
| 7 | Cost of sales | IS | Expense |
| 8 | Operating expenses | IS | Expense |
| 9 | Other income/expense | IS | Income/Expense |

See `app/services/onec_interpreter.py` line 59-70 for the `_CLASS_IFRS` mapping.

### 1C Accounting System

**1C:Enterprise** is the dominant ERP in the post-Soviet market (Russia, Georgia, CIS). Key facts:

- Exports COA as Excel with bilingual names (Georgian // Russian)
- Account codes are 4-digit with dots (e.g., `1410.01.2`)
- Uses Cyrillic for account type codes: А (Active), П (Passive), АП (Mixed)
- Has "subkonto" dimensions (counterparty, contract, product, etc.)
- Off-balance accounts exist (class 0) — tracked but not in BS

The `OneCInterpreter` (`app/services/onec_interpreter.py`) handles all 1C parsing. It's wrapped by `OneCAdapter` (`app/adapters/onec_adapter.py`) which conforms to the `BaseERPAdapter` interface.

### Financial Statement Cross-Validation Rules

The constraint graph enforces these GAAP integrity rules:

1. **BS Equation**: Total Assets = Total Liabilities + Total Equity (tolerance: 1 unit)
2. **TB Balance**: Total Debits = Total Credits (tolerance: 0.01)
3. **IS-BS Link**: Net Income on IS = Change in Retained Earnings on BS
4. **Revenue Consistency**: Sum of revenue line items = Total Revenue
5. **COGS Consistency**: Sum of COGS line items = Total COGS
6. **Gross Profit**: Revenue - COGS = Gross Profit (exact)

---

## Part 3 — Code Navigation Guide (Day 4-5)

### Common Tasks

| "I want to..." | Go to... |
|----------------|----------|
| Change Excel parsing logic | `app/services/smart_excel_parser.py` |
| Add a financial calculation | `app/services/calculation_engine.py` (use `Decimal`) |
| Modify the pipeline | `app/graph/graph.py` (add node), `app/graph/nodes.py` (implement) |
| Add an API endpoint | Create router in `app/routers/`, register in `main.py` |
| Change auth behavior | `app/middleware/auth_middleware.py`, `app/auth.py` |
| Add a new ERP adapter | Subclass `BaseERPAdapter` in `app/adapters/` |
| Change 1C COA parsing | `app/services/onec_interpreter.py` |
| Modify IFRS mappings | `app/services/onec_interpreter.py` lines 59-96 |
| Add a database model | `app/models/all_models.py`, then create Alembic migration |
| Change LLM behavior | `app/graph/nodes.py` → `reasoner_node` |

### Key Files

```
app/
├── adapters/             # ERP system adapters (1C, QuickBooks, etc.)
│   ├── base_adapter.py   # Abstract base class
│   ├── onec_adapter.py   # 1C adapter
│   └── registry.py       # Auto-detection registry
├── auth.py               # JWT, password hashing, role-based access
├── config.py             # Settings (pydantic-settings)
├── database.py           # SQLAlchemy async engine + tenant filter
├── graph/                # LangGraph pipeline (CANONICAL)
│   ├── graph.py          # Graph builder + circuit breaker integration
│   ├── nodes.py          # Individual node implementations
│   └── state.py          # FinAIState TypedDict
├── middleware/
│   ├── auth_middleware.py # Global JWT enforcement
│   └── tenant.py         # Multi-tenant context injection
├── models/
│   └── all_models.py     # 50 SQLAlchemy models
├── orchestrator/
│   ├── circuit_breaker.py # Pipeline halt on data integrity failure
│   └── orchestrator_v3.py # DEPRECATED — use graph/ instead
├── routers/              # FastAPI API endpoints
└── services/             # Business logic, parsers, AI agents
    ├── smart_excel_parser.py  # Universal Excel/CSV parser
    └── onec_interpreter.py    # 1C COA parser
```

---

## Part 4 — Local Development Setup (Day 1)

### Prerequisites

- Python 3.11+
- Git

### Quick Start

```bash
# Clone and enter
git clone <repo-url>
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env: set your NVIDIA_API_KEY_GEMMA, SECRET_KEY, JWT_SECRET

# Initialize database
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"

# Run the server
python main.py
# → http://localhost:8000/docs
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/ -v -m unit

# Security tests
pytest tests/test_security_sprint.py tests/test_security.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### Database Migrations

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

---

## Part 5 — Architecture Decision Records

See the `docs/adr/` directory for full ADRs:

- **ADR-001**: Why LangGraph over procedural orchestration
- **ADR-002**: Why Python Decimal over float for financial math
- **ADR-003**: Why symbolic constraint validation before LLM reasoning
- **ADR-004**: Why SQLAlchemy event listener for multi-tenancy
- **ADR-005**: Why template narratives as primary, LLM as secondary

---

## Part 6 — "What Not to Touch" List

These components have non-obvious correctness constraints. Changing them without domain expertise can break financial integrity:

1. **Constraint graph tolerance thresholds** — BS equation tolerance of 1 unit and TB tolerance of 0.01 were set with CPA input. Don't change without consulting a CPA.

2. **1C IFRS mapping table** (`_CLASS_IFRS`, `_RUSSIAN_1C_IFRS`) — These map 1C account codes to IFRS line items for the Georgian market. Don't change without consulting a Georgian accountant.

3. **LLM chain fallback order** (Claude → Gemma → Ollama → Template) — The order matters for cost, latency, and quality. Don't reorder without load testing.

4. **Decimal pipeline** — Never introduce `float()` arithmetic in financial calculation paths. All financial values must flow through `Decimal` from ingestion to output. If you see `float()` in a financial path, it's a bug.

5. **Tenant filter event listener** (`database.py`) — The `_inject_tenant_filter` runs on every SELECT. Removing it silently breaks multi-tenant isolation. The `TENANT_SCOPED_MODELS` set must include every model with a `company` column.

6. **Auth middleware ordering** in `main.py` — CORS must be first, then Auth, then Tenant, then Rate Limiter. Reordering breaks preflight or tenant context.
