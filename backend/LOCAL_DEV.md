# FinAI Backend - Local Development Setup

## Quick Start (5 Minutes)

### Prerequisites
- Python 3.12+ installed
- pip (Python package manager)
- Git (for version control)
- Anthropic API key from https://console.anthropic.com/api/keys

### Step 1: Clone/Navigate to Project
```bash
cd backend
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Copy local dev config
cp .env.example .env
```

**Edit `.env` and set:**
```env
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE  # Get from https://console.anthropic.com/api/keys
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./finai.db
```

### Step 5: Run Application
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Output should show:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 6: Access Application
- **Frontend**: Open `FinAI_Platform_v7.html` in your browser
- **API Docs**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/health

---

## Development Workflow

### Running the Development Server
```bash
# With auto-reload (recommended for development)
python -m uvicorn main:app --reload

# Specify host and port
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or use the convenience script
python dev_start.py
```

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_api.py::test_health -v

# Run with coverage
pytest --cov=app tests/
```

### Manual API Testing
```bash
# Health check
curl http://localhost:8000/health

# List datasets
curl http://localhost:8000/api/datasets

# Get API documentation
# Visit: http://localhost:8000/api/docs
```

---

## Database Setup

### SQLite (Default for Development)
The database is automatically created on first run in `./finai.db`

**View SQLite database:**
```bash
# Install SQLite browser (optional)
# Windows: choco install sqlitebrowser
# Mac: brew install sqlitebrowser
# Linux: sudo apt-get install sqlitebrowser

# Or use command line
sqlite3 finai.db
# .tables         # List tables
# .schema         # View schema
# SELECT * FROM transactions;  # Query data
```

### Reset Database
```bash
# Delete the database file
rm finai.db  # Mac/Linux
del finai.db  # Windows

# Or use Python script
python reset_db.py
```

### Load Seed Data
Seed data (335 NYX Core Thinker transactions) automatically loads on app startup.

To reload seed data:
```bash
# Upload test Excel file or POST to seed endpoint
curl -X POST http://localhost:8000/api/datasets/seed
```

---

## Project Structure
```
backend/
├── main.py                          ← FastAPI entry point
├── requirements.txt                 ← Python dependencies
├── .env.example                     ← Config template
├── .env.local                       ← Local dev config (keep private)
├── finai.db                         ← SQLite database (auto-created)
├── 
├── app/
│   ├── config.py                    ← Settings from .env
│   ├── database.py                  ← Database setup
│   ├── models/all_models.py         ← ORM models (6 tables)
│   ├── routers/
│   │   ├── datasets.py              ← File management endpoints
│   │   ├── analytics.py             ← Analytics & reporting
│   │   ├── agent.py                 ← AI chat endpoint
│   │   ├── reports.py               ← Report CRUD
│   │   └── tools.py                 ← Custom tools
│   └── services/
│       ├── ai_agent.py              ← Claude integration
│       ├── coa_engine.py            ← Financial calculations
│       ├── file_parser.py           ← Excel/CSV parsing
│       ├── seed_data.py             ← Demo data
│       └── utils/excel_export.py    ← Export utilities
│
├── tests/
│   └── test_api.py                  ← Integration tests
│
├── uploads/                          ← User uploaded files
├── exports/                          ← Generated reports
└── logs/                             ← Application logs
```

---

## IDE Setup

### VS Code
1. Install "Python" extension (Microsoft)
2. Install "FastAPI" extension (Damien)
3. Open workspace in VS Code

**Create `.vscode/launch.json`:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "jinja": true,
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      }
    }
  ]
}
```

Then press F5 to start debugging.

### PyCharm
1. Open project folder
2. Set Python interpreter: Settings → Project → Python Interpreter
3. Mark `app/` as Sources Root
4. Run configuration: Edit Configurations → Module name: `uvicorn` → Parameters: `main:app --reload`

---

## Common Development Tasks

### Create New Endpoint
1. Create router file in `app/routers/`
2. Define FastAPI router with endpoints
3. Import and include in `main.py`:
   ```python
   from app.routers import my_router
   app.include_router(my_router.router)
   ```

### Add New Database Model
1. Add model to `app/models/all_models.py`
2. Import in `app/database.py` if needed
3. Run app (SQLAlchemy auto-creates tables)

### Create New Service
1. Create file in `app/services/`
2. Implement business logic
3. Use in routers

### Test API Endpoint
```bash
# Using curl
curl -X POST http://localhost:8000/api/agents/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'

# Using httpx (Python)
python
>>> import httpx
>>> resp = httpx.post("http://localhost:8000/api/agent/chat", json={"message":"Hello"})
>>> print(resp.json())

# Using Postman or Thunder Client (GUI)
```

---

## Environment Variables

**Key variables for development:**

| Variable | Value | Notes |
|----------|-------|-------|
| APP_ENV | `development` | Enables debug mode |
| DEBUG | `true` | Shows detailed error pages |
| DATABASE_URL | `sqlite+aiosqlite:///./finai.db` | Lightweight local DB |
| ANTHROPIC_API_KEY | `sk-ant-...` | Get from https://console.anthropic.com |
| LOG_LEVEL | `DEBUG` | Show detailed logs |
| RELOAD | `true` | Auto-reload on code changes |

---

## Debugging

### Enable Detailed Logging
```python
# In main.py or any module
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Inspect Database
```bash
# SQLite command line
sqlite3 finai.db

# List all tables
.tables

# Describe table
.schema transactions

# Query data
SELECT * FROM datasets;
SELECT COUNT(*) FROM transactions;

# Exit
.quit
```

### Check API Health
```bash
curl http://localhost:8000/health
```

### View Application Logs
```bash
# From app logs
tail -f logs/finai.log

# From console output (if running uvicorn directly)
# Logs appear in terminal
```

---

## File Upload Testing

### Using curl
```bash
# Upload Excel file
curl -X POST http://localhost:8000/api/datasets/upload \
  -F "file=@/path/to/file.xlsx"

# Response includes dataset_id
```

### Using Python
```python
import httpx

with open("data.xlsx", "rb") as f:
    resp = httpx.post(
        "http://localhost:8000/api/datasets/upload",
        files={"file": f}
    )
    print(resp.json())
```

### Using Postman
1. New → Request → POST
2. URL: `http://localhost:8000/api/datasets/upload`
3. Body → form-data
4. Key: `file`, Type: File, Select your Excel file
5. Send

---

## Performance Testing

### Load Testing (using Apache Bench)
```bash
# Install: brew install httpd (Mac)
ab -n 100 -c 10 http://localhost:8000/health
```

### Using locust
```bash
# Install: pip install locust
locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089
```

---

## Troubleshooting

### "Port 8000 already in use"
```bash
# Find process using port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Mac/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn main:app --port 8001
```

### "ModuleNotFoundError"
```bash
# Make sure venv is activated
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install missing packages
pip install -r requirements.txt
```

### "ANTHROPIC_API_KEY not set"
```bash
# Edit .env file
# Set: ANTHROPIC_API_KEY=sk-ant-YOUR_KEY

# Verify it's set
python -c "from app.config import settings; print(settings.ANTHROPIC_API_KEY)"
```

### "Database locked"
```bash
# SQLite sometimes locks
# Solution: Restart the server or delete finai.db
rm finai.db
python -m uvicorn main:app --reload
```

---

## Development Best Practices

### 1. Virtual Environment
Always use a virtual environment to isolate dependencies.
```bash
source venv/bin/activate  # Activate before working
```

### 2. Commit Often
```bash
git add .
git commit -m "Feature: Add new endpoint"
```

### 3. Test Before Sharing
```bash
pytest tests/ -v
```

### 4. Keep .env Private
Never commit `.env` files to git. Use `.env.example` as template.

### 5. Use Type Hints
```python
def get_user(user_id: int) -> User:
    ...
```

### 6. Document Functions
```python
def calculate_profit(transactions: List[Transaction]) -> float:
    """
    Calculate total profit from transactions.
    
    Args:
        transactions: List of transaction objects
        
    Returns:
        Total profit as float
    """
    ...
```

---

## Useful Commands

```bash
# Start development server
python -m uvicorn main:app --reload

# Run tests
pytest tests/ -v

# Check code style (if installed)
flake8 app/
black app/
mypy app/

# Database operations
sqlite3 finai.db
python reset_db.py

# View API docs
# http://localhost:8000/api/docs

# Health check
curl http://localhost:8000/health

# Create requirements.txt
pip freeze > requirements.txt

# Update all packages
pip install --upgrade -r requirements.txt
```

---

## Next Steps

1. ✅ Activate virtual environment: `source venv/bin/activate`
2. ✅ Install dependencies: `pip install -r requirements.txt`
3. ✅ Configure `.env`: Copy `.env.example` and add API key
4. ✅ Start server: `python -m uvicorn main:app --reload`
5. ✅ Open http://localhost:8000/api/docs
6. ✅ Test endpoints in Swagger UI
7. ✅ Upload test Excel file via API
8. ✅ Chat with AI agent
9. ✅ Review generated reports

---

## 📚 Additional Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **SQLAlchemy Async**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Anthropic API**: https://docs.anthropic.com
- **Python Virtual Environments**: https://docs.python.org/3/tutorial/venv.html
- **Pytest Guide**: https://docs.pytest.org

---

**Happy coding! 🚀**
