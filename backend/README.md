# FinAI Financial Intelligence Platform — Backend

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-20.10+-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

> **AI-Powered Financial Intelligence Software** for NYX Core Thinker  
> Real-time analytics, Chart of Accounts mapping, Claude AI integration, and PostgreSQL persistence

---

## 📌 Overview

FinAI is a **production-ready financial intelligence platform** combining:

- **FastAPI Backend** — Modern async Python API with 5 router groups (18+ endpoints)
- **PostgreSQL Database** — Robust 6-table schema with 335 seed transactions
- **Claude AI Integration** — 11 context-aware tools for financial analysis
- **Excel/CSV Parser** — Georgian Chart of Accounts mapping
- **Report Generation** — P&L, Balance Sheet, Cash Flow in Excel (NYX Core Thinker themed)
- **React Frontend** — FinAI_Platform.html (single HTML file, no build required)

**Key Features:**
✅ Real AI reasoning about financial data  
✅ Account hierarchy with Georgian NYX Core Thinker COA  
✅ Multi-dataset support  
✅ Report automation  
✅ File upload & parsing  
✅ Dashboard with KPIs  
✅ Customizable AI tools  

---

## 🚀 Quick Start (5 Minutes)

### Option 1: Docker (Recommended)
```bash
cd backend

# Setup
cp .env.example .env
# Edit .env with your API key

# Start
docker compose up -d

# Access
firefox http://localhost
```

### Option 2: PowerShell Script (Windows)
```powershell
cd backend
.\deploy.ps1 setup
# Edit .env
.\deploy.ps1 start
```

### Option 3: Bash Script (Mac/Linux)
```bash
cd backend
chmod +x deploy.sh
./deploy.sh setup
# Edit .env
./deploy.sh start
```

### Option 4: Python (Development)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: Set ANTHROPIC_API_KEY and DATABASE_URL
python -m uvicorn main:app --reload
```

---

## 📁 Project Structure

```
backend/
├── 📄 main.py                          — FastAPI application entry point
├── 📄 requirements.txt                 — Python dependencies (20 packages)
├── 📄 .env.example                     — Configuration template
├── 📄 Dockerfile                       — Production container (Python 3.12)
├── 📄 docker-compose.yml               — Full stack (API + DB + Nginx)
├── 📄 nginx.conf                       — Reverse proxy, TLS, compression
├── 📄 init.sql                         — PostgreSQL schema init
├── 📄 DEPLOY.md                        — Complete deployment guide
├── 📄 QUICKSTART.md                    — 5-minute quick start
├── 📄 PRODUCTION_CHECKLIST.md          — Pre-launch checklist
├── 📄 deploy.sh                        — Bash deployment helper
├── 📄 deploy.ps1                       — PowerShell deployment helper
├── 📄 README.md                        — This file
│
├── app/
│   ├── 📄 config.py                    — Settings from environment variables
│   ├── 📄 database.py                  — SQLAlchemy async engine (SQLite/PostgreSQL)
│   │
│   ├── models/
│   │   ├── 📄 __init__.py
│   │   └── 📄 all_models.py            — 6 ORM models (Dataset, Transaction, Account, Report, Tool, Budget)
│   │
│   ├── routers/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 datasets.py              — POST upload, GET list, PUT activate (18 handlers)
│   │   ├── 📄 analytics.py             — Dashboard, P&L, B/S, cashflow endpoints
│   │   ├── 📄 agent.py                 — POST chat (Claude integration)
│   │   ├── 📄 reports.py               — CRUD reports, bulk operations
│   │   └── 📄 tools.py                 — Custom tools management
│   │
│   ├── services/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 ai_agent.py              — Claude API integration + 11 tool definitions
│   │   ├── 📄 coa_engine.py            — P&L & Balance Sheet computation from accounts
│   │   ├── 📄 file_parser.py           — Excel/CSV parser with Georgian COA mapping
│   │   ├── 📄 seed_data.py             — 335 NYX Core Thinker demo transactions
│   │   └── 📄 utils/excel_export.py    — Export to .xlsx (NYX Core Thinker themed)
│
├── tests/
│   ├── 📄 __init__.py
│   └── 📄 test_api.py                  — Integration tests (all endpoints)
│
├── uploads/                             — User uploaded files
├── exports/                             — Generated reports
├── logs/                                — Application logs
├── static/                              — Frontend HTML (served by Nginx)
└── backups/                             — Database backups
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` from `.env.example`:

```env
# ── Application ──
APP_NAME=FinAI Financial Intelligence
APP_VERSION=2.0.0
APP_ENV=production                # or: development, staging
DEBUG=false                        # Disable in production
SECRET_KEY=your-32-char-secret    # Generated with: openssl rand -base64 32

# ── Database ──
# Development (SQLite):
DATABASE_URL=sqlite+aiosqlite:///./finai.db

# Production (PostgreSQL):
DATABASE_URL=postgresql+asyncpg://finai:PASSWORD@localhost:5432/finai_db

# ── AI Integration ──
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_MAX_TOKENS=4096

# ── Files ──
UPLOAD_DIR=./uploads
EXPORT_DIR=./exports
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=xlsx,xls,csv

# ── Security ──
CORS_ORIGINS=http://localhost,https://yourdomain.com
JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# ── Company ──
COMPANY_NAME=NYX Core Thinker LLC
DEFAULT_CURRENCY=GEL
DEFAULT_PERIOD=January 2025

# ── Logging ──
LOG_LEVEL=INFO
LOG_FILE=./logs/finai.log
```

---

## 📊 Database Models

### 1. **Dataset** — Uploaded files
```
id (UUID)
filename
mime_type
size_bytes
is_active
uploaded_at
```

### 2. **Transaction** — Financial entries
```
id (UUID)
transaction_date
account_code (e.g., "5010 Revenue")
amount
currency
description
dataset_id (FK)
```

### 3. **Account** — Chart of Accounts
```
id (UUID)
code (e.g., "1010")
name (Georgian)
account_type (Asset/Liability/Equity/Revenue/Expense)
parent_code (hierarchy)
is_summary
```

### 4. **Report** — Generated reports
```
id (UUID)
report_type (P&L/BalanceSheet/CashFlow)
period
content (JSON)
created_at
created_by
```

### 5. **Tool** — Custom AI tools
```
id (UUID)
name
description
parameters (JSON)
created_at
```

### 6. **Budget** — Budget lines
```
id (UUID)
period
account_code
budgeted_amount
actual_amount
variance
```

---

## 🤖 AI Agent Integration

### Claude Configuration
- **Model**: Claude Sonnet 4 (claude-sonnet-4-20250514)
- **Tools**: 11 pre-configured tools for financial analysis
- **System Prompt**: Financial intelligence, Georgian language, NYX Core Thinker context
- **Max Tokens**: 4096

### Available Tools
1. `get_transactions` — Search transaction database
2. `calculate_profit` — P&L computation
3. `get_accounts` — Chart of Accounts lookup
4. `search_data` — Full-text search
5. `analyze_trends` — Time-series analysis
6. `create_report` — Report generation
7. `export_data` — Excel export
8. `validate_data` — Data quality checks
9. `update_budget` — Budget modifications
10. `forecast_cashflow` — Cash flow predictions
11. `chat_history` — Conversation context

### Example Interaction
**User**: "What is our gross profit?"

**Claude**: Identifies `calculate_profit` tool → Calls `get_accounts` → Computes → Returns: "Your gross profit is 50,000 GEL (confidence: 95%)"

---

## 🔌 API Endpoints

### **Datasets** (`/api/datasets`)
```
GET    /                       # List datasets
POST   /upload                 # Upload file
PUT    /{id}/activate          # Set active
DELETE /{id}                   # Delete
POST   /seed                   # Load demo data (dev only)
```

### **Analytics** (`/api/analytics`)
```
GET /dashboard                 # KPIs (revenue, expenses, profit)
GET /p-and-l                   # Profit & Loss
GET /balance-sheet             # Balance Sheet
GET /cash-flow                 # Cash Flow
GET /accounts                  # Chart of Accounts
```

### **Agent** (`/api/agent`)
```
POST /chat                     # Send message, get response with tool calls
```

### **Reports** (`/api/reports`)
```
GET    /                       # List reports
POST   /                       # Create report
GET    /{id}                   # Get report
DELETE /{id}                   # Delete report
GET    /{id}/export            # Export as Excel
POST   /bulk-create            # Create multiple
```

### **Tools** (`/api/tools`)
```
GET    /                       # List tools
POST   /                       # Create tool
GET    /{id}                   # Get tool
PATCH  /{id}                   # Update tool
DELETE /{id}                   # Delete tool
POST   /{id}/sync              # Sync with Claude
```

### **System**
```
GET  /health                   # Health check
GET  /api/docs                 # Swagger UI
GET  /api/redoc                # ReDoc
```

---

## 🧪 Testing

### Run Tests
```bash
cd backend
pip install pytest pytest-asyncio
pytest tests/ -v
pytest tests/test_api.py::test_health -v
```

### Manual Testing (curl)
```bash
# Health check
curl http://localhost:8000/health

# Get datasets
curl http://localhost:8000/api/datasets

# Chat with AI
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Show me the P&L statement"}'
```

---

## 🐳 Docker

### Build Image
```bash
docker compose build
```

### Start Stack
```bash
docker compose up -d
```

### View Logs
```bash
docker compose logs -f api          # API logs
docker compose logs -f db           # Database logs
docker compose logs -f nginx        # Nginx logs
```

### Stop Stack
```bash
docker compose down
docker compose down -v              # with volume deletion
```

### Access Services
- **API**: http://localhost:8000 (or port from docker-compose.yml)
- **Database**: localhost:5432 (PostgreSQL inside container)
- **Frontend**: http://localhost (via Nginx)
- **API Docs**: http://localhost:8000/api/docs

---

## 📚 Database Management

### PostgreSQL (Docker)
```bash
# Connect
docker compose exec db psql -U finai -d finai_db

# Useful commands
\dt                             # List tables
\d transactions                 # Describe table
SELECT COUNT(*) FROM transactions;

# Exit
\q
```

### Backup & Restore
```bash
# Backup
docker compose exec db pg_dump -U finai finai_db > backup.sql

# Restore
docker compose exec -T db psql -U finai finai_db < backup.sql
```

---

## 🚀 Deployment

### Development
```bash
python -m uvicorn main:app --reload
# or: python main.py
```

### Production (Docker)
```bash
docker compose up -d
# Runs on http://localhost with Nginx proxy
```

### Cloud Hosting

**AWS EC2:**
```bash
# Ubuntu 22.04 instance
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
docker compose up -d
```

**DigitalOcean App Platform:**
- Connect GitHub repo
- Build: `pip install -r requirements.txt`
- Run: `gunicorn main:app --worker-class uvicorn.workers.UvicornWorker`

**Heroku:**
```bash
heroku login
heroku create finai-backend
heroku addons:create heroku-postgresql:standard-0
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
git push heroku main
```

See [DEPLOY.md](DEPLOY.md) for detailed deployment guides.

---

## ⚙️ Performance

| Metric | Dev | Production |
|--------|-----|------------|
| Database | SQLite | PostgreSQL |
| Workers | 1 (reload) | 4+ (Gunicorn) |
| Memory | 256MB+ | 512MB+ |
| Startup | 5s | 10s |
| Requests/sec | 50+ | 500+ |

---

## 🔒 Security

- ✅ HTTPS with SSL/TLS (Nginx)
- ✅ CORS configured
- ✅ Environment variables for secrets
- ✅ Non-root Docker user
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Request validation (Pydantic)
- ✅ Rate limiting ready (add middleware)
- ✅ PostgreSQL user with minimal privileges

---

## 🐛 Troubleshooting

### API won't start
```bash
docker compose logs api
# Check .env configuration
# Verify Anthropic API key is set
```

### Database error
```bash
docker compose ps db
docker compose logs db
docker compose down -v
docker compose up -d
```

### Port conflicts
```bash
# Change ports in docker-compose.yml
# Or kill process using port:
lsof -i :8000
kill -9 <PID>
```

### High memory usage
```bash
docker stats
# Increase Docker memory limit in Desktop settings
```

---

## 📖 Documentation

- [DEPLOY.md](DEPLOY.md) — Complete deployment guide
- [QUICKSTART.md](QUICKSTART.md) — Fast 5-minute setup
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) — Pre-launch checklist
- [API Docs](http://localhost:8000/api/docs) — Interactive Swagger UI

---

## 📦 Dependencies

| Category | Package | Version |
|----------|---------|---------|
| Framework | fastapi | 0.115.5 |
| Server | uvicorn | 0.32.1 |
| Database | sqlalchemy | 2.0.36 |
| Async | aiosqlite | 0.20.0 |
| PostgreSQL | psycopg2-binary | 2.9.10 |
| Data | pandas | 2.2.3 |
| Excel | openpyxl | 3.1.5 |
| AI | anthropic | 0.39.0 |
| Config | python-dotenv | 1.0.1 |
| Security | pydantic | 2.10.3 |

See [requirements.txt](requirements.txt) for all 20+ packages.

---

## 📝 License

Proprietary — NYX Core Thinker LLC

---

## 🤝 Support

- **Issues**: Check [DEPLOY.md](DEPLOY.md) or [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- **API Questions**: See [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Anthropic**: https://support.anthropic.com

---

## 🎯 Next Steps

1. **Setup**: `./deploy.sh setup` or `.\deploy.ps1 setup`
2. **Configure**: Edit `.env` with your API key
3. **Deploy**: `./deploy.sh start` or `.\deploy.ps1 start`
4. **Access**: Open http://localhost in your browser
5. **Test**: Try uploading a file or asking the AI questions

---

**FinAI v2.0.0** | Production Ready ✅
