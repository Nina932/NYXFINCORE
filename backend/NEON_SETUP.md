# NYX Core FinAI — Neon PostgreSQL Setup Guide
# ============================================
# Neon is the free, serverless PostgreSQL chosen as our production DB.
# Why Neon?
#   * Branch-per-feature (show investors a live demo on a feature branch)
#   * Auto-sleep when idle (free tier stays free)
#   * std PostgreSQL — zero app code changes needed
#   * 3GB storage on free tier (more than enough to start)
#   * pgvector extension available (future semantic search upgrade)

# ── STEP 1: Sign up ─────────────────────────────────────────────────────────
# Go to: https://neon.tech
# Sign up with GitHub (free, no credit card needed)
# Create project: "nyx-finai-production"
# Database name: "finai"
# Region: closest to Georgia → europe-west3 (Frankfurt) or us-east-2

# ── STEP 2: Get your connection string ───────────────────────────────────────
# In Neon dashboard → Connection Details → select "asyncpg"
# It will look like:
#   postgresql+asyncpg://nino:<password>@ep-xxx.eu-central-1.aws.neon.tech/finai?sslmode=require

# ── STEP 3: Add to .env ──────────────────────────────────────────────────────
# Open: c:\Users\Nino\Downloads\FinAI_Backend_3\backend\.env
# Change DATABASE_URL to your Neon URL:

DATABASE_URL=postgresql+asyncpg://nino:YOUR_PASSWORD@ep-xxx.eu-central-1.aws.neon.tech/finai?sslmode=require

# ── STEP 4: Run migrations ───────────────────────────────────────────────────
# In your project directory (activate venv first):
#   cd C:\Users\Nino\Downloads\FinAI_Backend_3\backend
#   venv\Scripts\activate
#   alembic upgrade head

# ── STEP 5: Migrate existing SQLite data (optional) ──────────────────────────
# If you want to migrate your existing finai.db data to Neon:
#   pip install pgloader        # best tool for SQLite → PostgreSQL
# Or use the python script:    scripts/migrate_sqlite_to_neon.py  (to be created)

# ── STEP 6: Verify ───────────────────────────────────────────────────────────
# Restart the server:
#   uvicorn main:app --reload
# Check: GET /health — should show database_type: "postgresql"

# ── INVESTOR DEMO SETUP ───────────────────────────────────────────────────────
# Create a demo branch in Neon dashboard:
#   Neon → Branches → "Create Branch" → name: "investor-demo"
# The branch gets its own connection string with a copy of production data.
# Use the branch URL for demo sessions — it can't affect production data.

# ── LOCAL DEV WITH NEON ───────────────────────────────────────────────────────
# .env.local (local SQLite — fast, no network):
#   DATABASE_URL=sqlite+aiosqlite:///./data/finai.db

# .env (production Neon):
#   DATABASE_URL=postgresql+asyncpg://...neon.tech/finai?sslmode=require

# Switch with: copy .env.local .env   (local)
#              copy .env.neon .env     (production)
