"""
PostgreSQL Setup Script
========================
Creates the database, runs migrations, and verifies connectivity.

Usage:
    1. Install PostgreSQL and create database:
       CREATE DATABASE finai_db;
       CREATE USER finai WITH PASSWORD 'finai_secure_password';
       GRANT ALL PRIVILEGES ON DATABASE finai_db TO finai;

    2. Install async driver:
       pip install asyncpg psycopg2-binary

    3. Update .env:
       DATABASE_URL=postgresql+asyncpg://finai:finai_secure_password@localhost:5432/finai_db

    4. Run migrations:
       alembic upgrade head

    5. Run this script to verify:
       python scripts/setup_postgres.py
"""

import asyncio
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def check_connection():
    """Test database connectivity and report status."""
    from app.config import settings

    db_url = settings.DATABASE_URL
    is_postgres = "postgresql" in db_url
    is_sqlite = "sqlite" in db_url

    print("=" * 60)
    print("  FinAI Database Setup Verification")
    print("=" * 60)
    print()
    print(f"  DATABASE_URL: {db_url[:40]}...")
    print(f"  Driver:       {'PostgreSQL (asyncpg)' if is_postgres else 'SQLite (aiosqlite)' if is_sqlite else 'Unknown'}")
    print()

    if not is_postgres:
        print("  [WARN] Not using PostgreSQL. For production, set:")
        print("    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/finai_db")
        print()

    # Test actual connection
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(db_url, echo=False)
    try:
        async with engine.connect() as conn:
            # Basic connectivity
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
            print("  [OK] Database connection successful")

            # Check tables exist
            if is_postgres:
                result = await conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
                ))
            else:
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ))
            tables = [row[0] for row in result.fetchall()]
            print(f"  [OK] Found {len(tables)} tables")

            # Check critical tables
            critical_tables = [
                "datasets", "transactions", "revenue_items", "cogs_items",
                "balance_sheet_items", "trial_balance_items", "journal_entries",
                "posting_lines", "users", "knowledge_entities",
            ]
            missing = [t for t in critical_tables if t not in tables]
            if missing:
                print(f"  [WARN] Missing tables: {', '.join(missing)}")
                print("         Run: alembic upgrade head")
            else:
                print("  [OK] All critical tables present")

            # Check record counts for key tables
            for table in ["datasets", "journal_entries", "posting_lines", "users"]:
                if table in tables:
                    count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    print(f"  [INFO] {table}: {count} records")

            # Check alembic version
            if "alembic_version" in tables:
                ver_result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                ver = ver_result.scalar()
                print(f"  [OK] Alembic version: {ver}")
            else:
                print("  [WARN] No alembic_version table. Run: alembic upgrade head")

        print()
        print("  Verification complete.")
        print("=" * 60)

    except Exception as e:
        print(f"  [FAIL] Connection failed: {e}")
        print()
        if is_postgres:
            print("  Troubleshooting:")
            print("    1. Is PostgreSQL running? (pg_isready)")
            print("    2. Does the database exist? (createdb finai_db)")
            print("    3. Check credentials in .env DATABASE_URL")
            print("    4. Install driver: pip install asyncpg psycopg2-binary")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_connection())
