# Local Development Quick Start — 10 Minutes

> Everything you need to start developing FinAI locally

---

## ✅ System Requirements

- **Python**: 3.12 or higher
- **Git**: Version 2.0+
- **RAM**: 2GB+ (4GB+ recommended)
- **Disk**: 5GB+
- **OS**: Windows, Mac, or Linux

---

## 📦 Installation (5 Minutes)

### Step 1: Open Terminal
```bash
# Windows
# Open PowerShell or Command Prompt and navigate to backend folder
cd backend

# Mac/Linux
# Open terminal and navigate to backend folder
cd backend
```

### Step 2: Create Virtual Environment
```bash
# Create venv
python -m venv venv

# Activate venv
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

**You should now see `(venv)` in your terminal prompt.**

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```
⏱️ Takes 1-2 minutes

### Step 4: Configure Environment
```bash
# Copy example config
cp .env.example .env

# Or copy local dev config
copy .env.local .env
```

### Step 5: Edit `.env` File
Open `.env` in your text editor and set:
```env
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./finai.db
```

**Get your API key at:** https://console.anthropic.com/api/keys

---

## 🚀 Start Development Server (2 Minutes)

### Option A: Using Python Script (Recommended)
```bash
python dev_start.py
```

### Option B: Direct Command
```bash
python -m uvicorn main:app --reload
```

### Option C: Using Uvicorn Directly
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✨ Verify Server is Running

When successful, you'll see:
```
✅ FinAI Development Server
🚀 Starting FastAPI development server...

📍 Access points:
   Frontend: Open FinAI_Platform_v7.html in your browser
   API Docs: http://localhost:8000/api/docs
   Health:   http://localhost:8000/health
```

### Test in another terminal:
```bash
# Health check
curl http://localhost:8000/health

# Should return:
# {"status": "healthy", "version": "2.0.0", ...}
```

---

## 📚 Project Layout

```
backend/
├── main.py                    ← FastAPI app
├── requirements.txt           ← Dependencies
├── .env                       ← Your config (don't commit)
├── .env.example               ← Config template
├── finai.db                   ← Database (auto-created)
├── dev_start.py               ← Dev server starter
├── reset_db.py                ← Reset demo data
│
├── app/
│   ├── config.py              ← Settings
│   ├── database.py            ← Database setup
│   ├── models/all_models.py   ← Database models
│   ├── routers/               ← API endpoints
│   └── services/              ← Business logic
│
└── tests/test_api.py          ← Tests
```

---

## 🔄 Common Development Tasks

### Test an Endpoint

Open browser to: http://localhost:8000/api/docs

Or use curl:
```bash
# Get datasets
curl http://localhost:8000/api/datasets

# Chat with AI
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

### Run Tests
```bash
pytest tests/ -v
```

### Reset Database
```bash
python reset_db.py
# Follow prompts (type 'yes' to confirm)
```

### Make Code Changes

1. Edit file (e.g., `app/routers/datasets.py`)
2. Save file
3. Server auto-reloads
4. Test in browser or with curl
5. Check logs in terminal

---

## 🐛 Troubleshooting

### "Port 8000 already in use"
```bash
# Use different port
python -m uvicorn main:app --port 8001 --reload
```

### "ANTHROPIC_API_KEY not set"
```bash
# Check .env file has correct format:
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY

# If still failing:
python -c "from app.config import settings; print(settings.ANTHROPIC_API_KEY)"
```

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Ensure venv is activated (should see (venv) in prompt)
# Reinstall dependencies
pip install -r requirements.txt
```

### "Database error"
```bash
# Reset database
python reset_db.py
```

### "Can't open FinAI_Platform.html"
```bash
# The HTML file is in parent directory
# Open in browser: file:///full/path/to/FinAI_Platform_v7.html
```

---

## 📝 Development Checklist

- [ ] Python 3.12+ installed: `python --version`
- [ ] Git configured: `git config --global user.name "Your Name"`
- [ ] Virtual environment created: Check for `(venv)` in prompt
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` configured with Anthropic API key
- [ ] Dev server running: http://localhost:8000/health works
- [ ] API docs accessible: http://localhost:8000/api/docs
- [ ] Frontend HTML file available
- [ ] Database created: `finai.db` exists

---

## 🎓 First Steps

### 1. Explore API Documentation (5 min)
Visit: http://localhost:8000/api/docs

Try these endpoints:
- `GET /health` — Check server status
- `GET /api/datasets` — List datasets
- `GET /api/analytics/dashboard` — Get KPIs

### 2. Upload Test Data (5 min)
Create a sample Excel file with:
```
| Date    | Account Code | Amount | Description       |
|---------|--------------|--------|-------------------|
| 2025-01 | 5010         | 100000 | Revenue           |
| 2025-01 | 4010         | 30000  | Operating Expense |
```

Upload via API or use Postman

### 3. Test AI Chat (2 min)
POST to `/api/agent/chat`:
```json
{
  "message": "What is our profit?"
}
```

### 4. Review Code (10 min)
- Look at `app/routers/agent.py` — AI endpoint
- Look at `app/services/ai_agent.py` — Claude integration
- Look at `app/services/coa_engine.py` — Financial calculations

---

## 💡 Useful Tips

### Keep Terminal Output Clean
```bash
# Redirect logs to file
python -m uvicorn main:app --reload > server.log 2>&1
```

### Debug with Print Statements
```python
# Add to any file
print(f"DEBUG: variable = {variable}")
# Shows in server terminal
```

### Use Interactive Debugger
```python
# Add to any file
import pdb; pdb.set_trace()
# Server pauses, use debugger in terminal
```

### Enable All Logging
Edit `.env`:
```env
LOG_LEVEL=DEBUG
```

### Test with Different Files
```bash
# Upload different Excel formats
# Try with real company data
# Test edge cases
```

---

## 🔗 Next Steps

### Learn the Codebase
1. Read [LOCAL_DEV.md](LOCAL_DEV.md) — Full dev guide
2. Read [README.md](README.md) — Project overview
3. Explore `/api/docs` — API documentation

### Make Your First Contribution
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "feature: Your description"`
6. Push: `git push origin feature/your-feature`

### Set Up Git
1. Read [GITHUB_SETUP.md](GITHUB_SETUP.md)
2. Initialize git: `python setup_git.py`
3. Configure remote: Point to your fork or main repo

### Join Development
- Check GitHub Issues
- Pick a task
- Create pull request with changes

---

## 📞 Getting Help

**Something not working?**

1. Check [LOCAL_DEV.md](LOCAL_DEV.md) troubleshooting
2. Check logs in terminal
3. Verify `.env` configuration
4. Test health endpoint: `curl http://localhost:8000/health`
5. Run tests: `pytest tests/ -v`

**Need to Learn More?**

- [FastAPI Docs](https://fastapi.tiangolo.com)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org)
- [Anthropic API](https://docs.anthropic.com)
- [Python Async](https://docs.python.org/3/library/asyncio.html)

---

## 🚀 You're All Set!

Your development environment is ready. Start coding! 

```bash
# Happy developing!
python dev_start.py
```

---

**Questions?** Check the documentation files or open an issue on GitHub!
