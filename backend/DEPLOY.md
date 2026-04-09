# FinAI Financial Intelligence Platform
## Complete Production Deployment Guide
### Version 2.0.0 | FinAI Backend + Claude AI + PostgreSQL + Nginx

---

## 📋 What You Have

**28 Production-Ready Files:**

```
FinAI_Platform_v7.html  ← Complete React frontend (responsive, self-contained)
backend/
├── main.py                               ← FastAPI entry point, all routers
├── requirements.txt                      ← All 20+ dependencies pinned
├── .env.example                          ← Configuration template
├── Dockerfile                            ← Multi-stage production container
├── docker-compose.yml                    ← Complete stack: API + DB + Nginx
├── nginx.conf                            ← TLS, compression, security headers
├── init.sql                              ← PostgreSQL schema init
├── DEPLOY.md                             ← This guide
│
├── app/
│   ├── config.py                         ← Settings & environment vars
│   ├── database.py                       ← SQLAlchemy async engine
│   ├── models/all_models.py              ← 6 models: Dataset, Transaction, Account, Report, Tool, Budget
│   ├── routers/
│   │   ├── datasets.py                   ← Upload, list, activate datasets
│   │   ├── analytics.py                  ← Dashboard KPIs, P&L, BS endpoints  
│   │   ├── agent.py                      ← AI chat + 11 tools
│   │   ├── reports.py                    ← Save/list/export reports
│   │   └── tools.py                      ← Custom tools CRUD
│   └── services/
│       ├── ai_agent.py                   ← Claude integration + tool calls
│       ├── coa_engine.py                 ← P&L & BS computation
│       ├── file_parser.py                ← Excel/CSV → Georgian COA mapping
│       ├── seed_data.py                  ← 335 NYX Core Thinker transactions
│       └── utils/excel_export.py         ← Themed Excel exports
│
├── tests/test_api.py                     ← Full integration test suite
├── uploads/                              ← User upload directory
├── exports/                              ← Generated reports directory
├── logs/                                 ← Application logs
└── static/                               ← Frontend HTML served here
```

**Key Technology Stack:**
- **API:** FastAPI 0.115 + Uvicorn
- **Database:** PostgreSQL 16 (production) / SQLite (dev)
- **AI:** Anthropic Claude Sonnet 4 with tool-calling
- **Server:** Nginx + Gunicorn + Docker
- **ORM:** SQLAlchemy 2.0 async
- **Data:** Pandas + OpenpyXL for Excel parsing

---

## 🚀 QUICK START (5 Minutes)

### Option A: Frontend Only (Browser-Based)
1. Open `FinAI_Platform.html` in any modern browser
2. Add Anthropic API key in the agent panel (right side)
3. Start using—all data saves in your browser's IndexedDB

**Pros:** No server needed | Works offline  
**Cons:** Single-machine only | Data loss if browser cache cleared

---

### Option B: Local Backend (Development)
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: Set ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
python -m uvicorn main:app --reload
# Access: http://localhost:8000
```

**Pros:** Full features | Real database | Team collaboration  
**Cons:** Requires Python 3.12 | Only works on your machine

---

## 🐳 PRODUCTION DEPLOYMENT (Docker)

### Best for: Cloud hosting, team servers, production

---

### Step 1: Get Prerequisites

**Docker & Docker Compose:**
```bash
# Install: https://docs.docker.com/get-docker/
docker --version        # Verify (should be 24+)
docker compose version  # Verify (should be 2.0+)
```

**Anthropic API Key:**
1. Go to https://console.anthropic.com/api/keys
2. Create key (looks like: `sk-ant-ABC123...`)
3. Keep it safe ✓

---

### Step 2: Configure Environment

```bash
cd backend
cp .env.example .env
```

**Edit `.env` with your values:**
```env
# ── AI ──
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# ── Database (choose one) ──
# Local development:
DATABASE_URL=sqlite+aiosqlite:///./finai.db

# OR PostgreSQL (production):
DATABASE_URL=postgresql+asyncpg://finai:STRONG_PASSWORD@db:5432/finai_db

# ── Security ──
SECRET_KEY=generate-32-random-characters-here-xyz123abc
DB_PASSWORD=STRONG_DATABASE_PASSWORD_MIN_16_CHARS

# ── Server ──
APP_ENV=production
DEBUG=false
DOMAIN=yourdomain.com                    # or localhost

# ── CORS (where frontend comes from) ──
CORS_ORIGINS=http://localhost,https://yourdomain.com

# ── Files ──
MAX_UPLOAD_SIZE_MB=50
UPLOAD_DIR=./uploads
EXPORT_DIR=./exports
```

**Generate secure keys:**
```bash
# On Linux/Mac:
openssl rand -base64 32

# On Windows (PowerShell):
[Convert]::ToBase64String((1..32 | ForEach-Object {[byte](Get-Random -Max 256)}))
```

---

### Step 3: Prepare Frontend

```bash
# Copy frontend HTML to static directory
mkdir -p static
cp ../FinAI_Platform_v7.html static/FinAI_Platform.html
```

---

### Step 4: Launch the Stack

```bash
# Build and start all services
docker compose up -d

# Check if everything started
docker compose ps

# Watch logs
docker compose logs -f api

# Stop everything
docker compose down
```

**Expected output:**
```
CONTAINER ID   IMAGE              STATUS              PORTS
abc123...      finai_api          Up 2 seconds        0.0.0.0:8000->8000/tcp
def456...      postgres:16-alpine Up 3 seconds        0.0.0.0:5432->5432/tcp
ghi789...      nginx:alpine       Up 1 second         0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

### Step 5: Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# Test endpoints
curl http://localhost:8000/api/datasets

# Access frontend
open http://localhost   # Mac
start http://localhost  # Windows
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "env": "production",
  "model": "claude-sonnet-4-20250514",
  "api_key": "configured"
}
```

---

## ☁️ CLOUD DEPLOYMENT

### AWS EC2 (Simple Example)

```bash
# 1. Launch t3.small Ubuntu 24.04 instance
# 2. SSH into instance
chmod 400 finai-key.pem
ssh -i finai-key.pem ubuntu@YOUR_EC2_IP

# 3. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 4. Clone/upload backend
git clone <your-repo> backend
cd backend
cp .env.example .env

# 5. Edit .env with your settings
nano .env

# 6. Launch
docker compose up -d

# 7. Set up domain (optional)
# Point yourdomain.com DNS to YOUR_EC2_IP:80
```

### DigitalOcean App Platform (Easiest)

1. Fork backend repo to GitHub
2. Create new DigitalOcean App → Connect GitHub repo
3. Configuration:
   - Language: Python
   - Build: `pip install -r requirements.txt`
   - Run: `gunicorn main:app --worker-class uvicorn.workers.UvicornWorker`
4. Add environment variables (from .env)
5. Deploy

### Heroku

```bash
# Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
heroku login
heroku create finai-backend
heroku addons:create heroku-postgresql:standard-0 -a finai-backend

# Configure environment
heroku config:set ANTHROPIC_API_KEY=sk-ant-... -a finai-backend
heroku config:set SECRET_KEY=... -a finai-backend
# ... set all vars from .env

# Deploy
git push heroku main

# View logs
heroku logs --tail -a finai-backend

# Open app
heroku open -a finai-backend
```

---

## 📊 DATABASE MANAGEMENT

### PostgreSQL Administration

```bash
# Connect to database container
docker compose exec db psql -U finai -d finai_db

# Useful PostgreSQL commands:
\dt                          # List tables
\d transactions              # Describe table
SELECT COUNT(*) FROM transactions;  # Count rows
\q                           # Quit
```

### Backup & Restore

```bash
# Backup
docker compose exec db pg_dump -U finai finai_db > backup.sql

# Restore
docker compose exec -T db psql -U finai finai_db < backup.sql
```

---

## 🔒 SECURITY CHECKLIST

Before going to production:

- [ ] Change all `.env` secrets (ANTHROPIC_API_KEY, SECRET_KEY, DB_PASSWORD)
- [ ] Set `DEBUG=false` in production
- [ ] Set `APP_ENV=production`
- [ ] Configure CORS_ORIGINS to only your domain
- [ ] Enable SSL/TLS certificates (nginx configured)
- [ ] Set strong database password (20+ chars, mixed case+numbers+symbols)
- [ ] Restrict API access by IP if possible
- [ ] Set up database backups (automated daily)
- [ ] Monitor logs for errors: `docker compose logs api`
- [ ] Use environment secrets manager (AWS Secrets Manager, Vault, etc.)

---

## 🐛 TROUBLESHOOTING

### API won't start
```bash
# Check logs
docker compose logs api

# Verify .env is correct
cat .env | grep -i anthropic

# Rebuild container
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Database connection error
```bash
# Check database is running
docker compose ps db

# Verify DATABASE_URL in .env matches docker-compose.yml

# Reset database
docker compose down -v  # Remove volumes
docker compose up -d    # Recreate fresh
```

### Port already in use
```bash
# Check what's using port 8000
lsof -i :8000     # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Or change ports in docker-compose.yml
```

### Out of memory
```bash
# Check docker stats
docker stats

# Increase Docker memory in Settings
```

---

## 📈 MONITORING & MAINTENANCE

### Health checks
```bash
# Auto-running every 30s in docker-compose.yml
curl http://localhost:8000/health
```

### View real-time metrics
```bash
docker stats finai_api finai_db finai_nginx

# Or use Portainer for GUI: https://www.portainer.io/
```

### Regular maintenance
```bash
# Weekly: Update images
docker compose pull
docker compose up -d

# Monthly: Clean unused images/volumes
docker system prune -a

# Quarterly: Review logs
docker compose logs --timestamps api | tail -1000
```

---

## 🚢 PRODUCTION DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] All environment variables configured
- [ ] Database password changed
- [ ] SSL certificates obtained (for HTTPS)
- [ ] Backups automated
- [ ] Monitoring alerts set up
- [ ] API key rate limits checked

### First Deployment
- [ ] Run health check: `curl /health`
- [ ] Test file upload: POST to `/api/datasets/upload`
- [ ] Test AI agent: POST to `/api/agent/chat`
- [ ] Test analytics: GET `/api/analytics/p-and-l`
- [ ] Verify frontend loads at `/`

### Post-Deployment
- [ ] Monitor `docker stats` for 24 hours
- [ ] Check error logs daily for first week
- [ ] Test database backups
- [ ] Document any custom configurations
- [ ] Set up uptime monitoring (StatusPage.io, etc.)

---

## 🔐 SSL/TLS SETUP (HTTPS)

For production, you need SSL certificates. There are several options:

### Option 1: Let's Encrypt (Free)
```bash
# For Docker: certbot will auto-renew in container
# Nginx in docker-compose.yml already configured for SSL

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copy to ssl directory
mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
sudo chown $USER:$USER ssl/*
```

### Option 2: Self-Signed (Development Only)
```bash
# Generate self-signed certificate (valid 365 days)
openssl req -x509 -newkey rsa:4096 -nodes -out ssl/fullchain.pem -keyout ssl/privkey.pem -days 365

# When prompted:
# Country: US
# State: State
# City: City
# Organization: FinAI
# Common Name: localhost
```

---

## 📦 API ENDPOINTS REFERENCE

### Datasets
```bash
GET    /api/datasets                   # List all datasets
POST   /api/datasets/upload            # Upload Excel/CSV file
POST   /api/datasets/{id}/activate     # Set as active dataset
DELETE /api/datasets/{id}              # Delete dataset
```

### Analytics
```bash
GET /api/analytics/dashboard           # KPIs: revenue, expenses, profit
GET /api/analytics/p-and-l             # Profit & Loss statement
GET /api/analytics/balance-sheet       # Balance sheet
GET /api/analytics/cash-flow           # Cash flow statement
```

### AI Agent
```bash
POST /api/agent/chat                   # Send message, get Claude response with tools

# Request body:
{
  "message": "What is our gross profit?",
  "tools": ["calculate_profit", "get_accounts", "analyze_trends"]
}

# Response:
{
  "response": "Your gross profit for January is 50,000 GEL.",
  "confidence": 0.95,
  "sources": ["transactions", "accounts"],
  "tools_used": ["calculate_profit"]
}
```

### Reports
```bash
POST   /api/reports                    # Create report
GET    /api/reports                    # List reports
GET    /api/reports/{id}               # Get report details
PATCH  /api/reports/{id}               # Update report
DELETE /api/reports/{id}               # Delete report
GET    /api/reports/{id}/export        # Export as Excel
```

### Tools (Custom)
```bash
GET    /api/tools                      # List available tools
POST   /api/tools                      # Create custom tool
GET    /api/tools/{id}                 # Get tool details
PATCH  /api/tools/{id}                 # Update tool
DELETE /api/tools/{id}                 # Delete tool
POST   /api/tools/{id}/sync            # Sync tool with Claude
```

### System
```bash
GET  /health                           # Health check
POST /api/datasets/seed                # Load demo data (development only)
```

---

## 🧪 TESTING

### Run Tests Locally
```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py::test_health -v

# With coverage
pytest --cov=app tests/
```

### Curl Examples (No Auth Required)
```bash
# Health check
curl http://localhost:8000/health

# Get datasets
curl http://localhost:8000/api/datasets

# Upload file
curl -X POST http://localhost:8000/api/datasets/upload \
  -F "file=@mydata.xlsx"

# Chat with AI
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is total revenue?"}'

# Get P&L
curl http://localhost:8000/api/analytics/p-and-l
```

---

## 📱 FRONTEND SETUP

### Serve Frontend from Backend
```bash
# Copy HTML to static directory
mkdir -p static
cp FinAI_Platform_v7.html static/FinAI_Platform.html

# Restart backend
docker compose up -d

# Access at: http://localhost or https://yourdomain.com
```

### Frontend Configuration
The frontend (`FinAI_Platform.html`) contains embedded seed data and connects to:
1. Your backend at `/api/*` endpoints
2. Anthropic API directly (for AI chat)
3. Browser's IndexedDB (for caching)

**No additional configuration needed** — it auto-detects the backend URL.

---

## 🎯 ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────┐
│                  FINAI PLATFORM STACK                   │
├─────────────────────────────────────────────────────────┤
│  Frontend Layer (Browser)                               │
│  ├─ React SPA (FinAI_Platform.html)                    │
│  ├─ IndexedDB Cache                                    │
│  └─ Anthropic API (client-side)                        │
├─────────────────────────────────────────────────────────┤
│  Nginx Layer (Reverse Proxy)                            │
│  ├─ TLS/SSL Termination                                │
│  ├─ Static File Serving                                │
│  ├─ Request Compression                                │
│  └─ Security Headers                                   │
├─────────────────────────────────────────────────────────┤
│  API Layer (FastAPI + Uvicorn)                         │
│  ├─ /api/datasets    (Upload & manage datasets)        │
│  ├─ /api/analytics   (KPIs, P&L, BS)                  │
│  ├─ /api/agent       (Claude integration)              │
│  ├─ /api/reports     (Report generation)               │
│  └─ /api/tools       (Custom tools CRUD)               │
├─────────────────────────────────────────────────────────┤
│  Background Services                                    │
│  ├─ File Parser (xlsx/csv → tables)                   │
│  ├─ COA Engine (account computations)                 │
│  ├─ Excel Export (NYX Core Thinker themed)                       │
│  └─ Seed Data (335 transactions)                      │
├─────────────────────────────────────────────────────────┤
│  Data Layer (PostgreSQL / SQLite)                      │
│  ├─ Datasets        (User uploaded files)              │
│  ├─ Transactions    (Financial entries)                │
│  ├─ Accounts        (Chart of Accounts)                │
│  ├─ Reports         (Generated reports)                │
│  ├─ Tools           (Custom tools)                     │
│  └─ Budgets         (Budget lines)                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🤖 AI INTEGRATION DETAILS

### Claude Configuration
The backend uses **Claude Sonnet 4** with tool-calling:

**System Prompt Includes:**
- Georgian language support
- Financial terminology (balance sheet, P&L, cash flow)
- Company context (NYX Core Thinker)
- 11 pre-configured tools:
  1. `get_transactions` — Fetch transaction records
  2. `calculate_profit` — Compute P&L
  3. `get_accounts` — Retrieve COA
  4. `search_data` — Full-text search
  5. `analyze_trends` — Time-series analysis
  6. `create_report` — Generate reports
  7. `export_data` — Export to Excel
  8. `validate_data` — Data quality checks
  9. `update_budget` — Budget operations
  10. `forecast_cashflow` — Predictions
  11. `chat_history` — Conversation context

### Tool Calls
When you ask: *"What is our gross profit?"*

Claude:
1. Identifies relevant tool: `calculate_profit`
2. Gathers context: `get_accounts`
3. Executes backend functions
4. Returns: "Your gross profit is 50,000 GEL (confidence: 95%)"

---

## 🔄 DATA FLOW EXAMPLE

**User uploads Excel file → AI generates report:**

```
1. User: "Upload monthly_data.xlsx"
   ↓
2. Frontend: POST /api/datasets/upload [multipart file]
   ↓
3. Backend file_parser.py:
   - Read Excel file
   - Map Georgian account codes to COA
   - Insert transactions into database
   ↓
4. User: "Create P&L report"
   ↓
5. Backend coa_engine.py:
   - Group transactions by account
   - Calculate totals
   - Generate P&L structure
   ↓
6. Response: JSON P&L document
   ↓
7. Frontend: Render report + charts
```

---

## 💡 BEST PRACTICES

### For Development
```bash
# Use SQLite with dev seed data
DATABASE_URL=sqlite+aiosqlite:///./finai.db

# Enable debug mode
DEBUG=true
APP_ENV=development

# Watch for code changes
python -m uvicorn main:app --reload
```

### For Production
```bash
# Use PostgreSQL with backup
DATABASE_URL=postgresql+asyncpg://...

# Disable debug
DEBUG=false
APP_ENV=production

# Restrict CORS to your domain only
CORS_ORIGINS=https://yourdomain.com

# Use Gunicorn with multiple workers
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Security Recommendations
1. **API Keys**: Rotate quarterly
2. **Secrets**: Use environment manager (AWS Secrets Manager, HashiCorp Vault)
3. **Database**: Enable SSL for PostgreSQL
4. **Backups**: Daily automated backups to S3
5. **Monitoring**: Set up CloudWatch/Datadog alerts
6. **Logging**: Centralize logs (CloudWatch, ELK, Datadog)
7. **Rate Limiting**: Add rate limits to `/api/agent/chat` endpoint
8. **Audit**: Enable PostgreSQL audit logging

---

## 📞 SUPPORT & RESOURCES

- **API Docs:** http://localhost:8000/api/docs (Swagger UI)
- **Anthropic Docs:** https://docs.anthropic.com
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **PostgreSQL Docs:** https://www.postgresql.org/docs
- **Docker Docs:** https://docs.docker.com

---

## 📄 FILE DESCRIPTIONS

### Core Application
- **main.py** - FastAPI app initialization, middleware, routes
- **app/config.py** - Settings, environment parsing, validation
- **app/database.py** - SQLAlchemy engine, session factory, initialization

### Models
- **app/models/all_models.py** - SQLAlchemy ORM models:
  - `Dataset` - User uploaded files
  - `Transaction` - Financial entries
  - `Account` - Chart of Accounts entries
  - `Report` - Generated reports
  - `Tool` - Custom tools
  - `Budget` - Budget lines

### Routers (API Endpoints)
- **app/routers/datasets.py** - File upload, dataset management
- **app/routers/analytics.py** - Dashboard, P&L, BS, cash flow
- **app/routers/agent.py** - Claude AI chat endpoint
- **app/routers/reports.py** - Report CRUD operations
- **app/routers/tools.py** - Custom tools management

### Services (Business Logic)
- **app/services/ai_agent.py** - Claude integration, tool execution
- **app/services/coa_engine.py** - P&L and balance sheet computation
- **app/services/file_parser.py** - Excel/CSV parsing with Georgian COA
- **app/services/seed_data.py** - 335 NYX Core Thinker demo transactions
- **app/utils/excel_export.py** - NYX Core Thinker-themed Excel export

### Infrastructure
- **Dockerfile** - Production container (Python 3.12, Gunicorn)
- **docker-compose.yml** - Full stack orchestration
- **nginx.conf** - Reverse proxy, TLS, compression
- **init.sql** - PostgreSQL schema initialization

### Configuration
- **.env.example** - Environment variables template
- **requirements.txt** - Python dependencies (pinned versions)
- **DEPLOY.md** - This deployment guide

### Testing
- **tests/test_api.py** - Integration tests for all endpoints

Paste this (replace YOUR_USER):
```ini
[Unit]
Description=FinAI Financial Intelligence Backend
After=network.target postgresql.service

[Service]
Type=exec
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/opt/finai
Environment=PATH=/opt/finai/venv/bin
ExecStart=/opt/finai/venv/bin/gunicorn main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile /opt/finai/logs/access.log \
    --error-logfile /opt/finai/logs/error.log
Restart=always
RestartSec=5
StandardOutput=append:/opt/finai/logs/service.log
StandardError=append:/opt/finai/logs/error.log

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
mkdir -p /opt/finai/logs

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable finai
sudo systemctl start finai

# Check it's running
sudo systemctl status finai
curl http://localhost:8000/health
```

### Step 6 — Configure Nginx:
```bash
# Copy nginx config
sudo cp /opt/finai/nginx.conf /etc/nginx/sites-available/finai
sudo ln -s /etc/nginx/sites-available/finai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Edit to set your domain
sudo nano /etc/nginx/sites-available/finai
# Change: server_name yourdomain.com;

# Test config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### Step 7 — SSL Certificate (Free with Certbot):
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is set up automatically
# Test renewal:
sudo certbot renew --dry-run
```

### Step 8 — Deploy Frontend:
```bash
# Put the HTML file in nginx static dir
sudo mkdir -p /opt/finai/static
sudo cp FinAI_Platform.html /opt/finai/static/
```

### Step 9 — Update Nginx to Serve Frontend:
In `/etc/nginx/sites-available/finai`, ensure:
```nginx
location = / {
    root /opt/finai/static;
    try_files /FinAI_Platform.html =404;
}
```

```bash
sudo systemctl reload nginx
```

**Your app is now live at `https://yourdomain.com`**

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/docs` | Interactive API docs (dev only) |
| **Datasets** | | |
| POST | `/api/datasets/upload` | Upload & parse Excel/CSV file |
| GET | `/api/datasets` | List all datasets |
| PUT | `/api/datasets/{id}/activate` | Set active dataset |
| DELETE | `/api/datasets/{id}` | Delete dataset |
| **Analytics** | | |
| GET | `/api/analytics/dashboard` | KPIs + chart data |
| GET | `/api/analytics/transactions` | Filter transactions |
| GET | `/api/analytics/revenue` | Revenue breakdown |
| GET | `/api/analytics/costs` | Cost analysis |
| GET | `/api/analytics/budget` | Budget vs actual |
| GET | `/api/analytics/pl` | P&L statement |
| GET | `/api/analytics/balance-sheet` | Balance sheet |
| **AI Agent** | | |
| GET | `/api/agent/status` | Agent readiness |
| POST | `/api/agent/chat` | Send message to agent |
| GET | `/api/agent/memory` | Agent memory |
| POST | `/api/agent/feedback` | Submit feedback |
| **Reports** | | |
| GET | `/api/reports` | List saved reports |
| POST | `/api/reports` | Save a report |
| GET | `/api/reports/{id}` | Get report details |
| GET | `/api/reports/{id}/export` | Download as Excel |
| DELETE | `/api/reports/{id}` | Delete report |

---

## Troubleshooting

### "No module named 'fastapi'"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Database connection refused"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U finai -d finai_db -h localhost
```

### "ANTHROPIC_API_KEY not set"
```bash
# Check your .env file
cat .env | grep ANTHROPIC

# Make sure there are no spaces around the = sign
ANTHROPIC_API_KEY=sk-ant-xxxxx   ← CORRECT
ANTHROPIC_API_KEY = sk-ant-xxxxx ← WRONG
```

### Port 8000 already in use
```bash
# Find what's using port 8000
lsof -i :8000
# Kill it
kill -9 PID_NUMBER
```

### Frontend can't reach backend (CORS error)
In `.env`, add your frontend's URL to CORS_ORIGINS:
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,https://yourdomain.com
```

### Large file upload fails
```bash
# In .env
MAX_UPLOAD_SIZE_MB=100

# In nginx.conf
client_max_body_size 100M;
```

### SQLite WAL mode warning on startup
Safe to ignore. WAL mode improves concurrent read performance.

---

## Monitoring & Maintenance

### View live logs:
```bash
# Systemd service logs
journalctl -u finai -f

# Application logs
tail -f /opt/finai/logs/finai.log

# Nginx access logs
tail -f /var/log/nginx/access.log
```

### Database backup (PostgreSQL):
```bash
# Backup
pg_dump -U finai finai_db > backup_$(date +%Y%m%d).sql

# Restore
psql -U finai finai_db < backup_20250103.sql
```

### SQLite backup (development):
```bash
cp finai.db finai_backup_$(date +%Y%m%d).db
```

### Update application:
```bash
cd /opt/finai
# Pull new code (if using git)
git pull

# Install any new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart finai
```

---

## Quick Start Checklist

### Frontend Only (5 minutes):
- [ ] Open FinAI_Platform.html in Chrome
- [ ] Get API key from console.anthropic.com
- [ ] Enter API key in agent panel → Save
- [ ] Try: "Generate P&L statement"

### Local Backend (15 minutes):
- [ ] `cd backend`
- [ ] `python3 -m venv venv && source venv/bin/activate`
- [ ] `pip install -r requirements.txt`
- [ ] `cp .env.example .env` and fill in ANTHROPIC_API_KEY
- [ ] `python main.py`
- [ ] Visit http://localhost:8000/health

### Production Server (45 minutes):
- [ ] Provision Ubuntu 22.04 VPS
- [ ] Install Python, PostgreSQL, Nginx
- [ ] Create database user and DB
- [ ] Deploy code to /opt/finai
- [ ] Configure .env with production values
- [ ] Create systemd service
- [ ] Configure nginx with your domain
- [ ] Get SSL cert with certbot
- [ ] Deploy frontend HTML to /opt/finai/static/

---

*FinAI Financial Intelligence Platform — NYX Core Thinker*  
*Built with FastAPI, SQLAlchemy, Anthropic Claude, Chart.js, SheetJS*
