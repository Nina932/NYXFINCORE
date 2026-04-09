"""
sanitize_neon.py -- Wipes the public schema of the Neon PostgreSQL database.
Used to ensure a clean slate for Alembic migrations.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path so 'app' can be imported
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sanitize_neon")

async def sanitize_neon():
    # Robust URL normalization
    raw_url = settings.DATABASE_URL.strip()
    
    # Ensure postgresql+asyncpg protocol
    if raw_url.startswith("postgresql://"):
        db_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif "postgresql" in raw_url and "+asyncpg" not in raw_url:
        db_url = raw_url.replace("postgresql", "postgresql+asyncpg", 1)
    else:
        db_url = raw_url

    # Ensure it ends with postgresql+asyncpg for the engine
    db_url = db_url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    db_url = f"postgresql+asyncpg://{db_url}"
    
    logger.info(f"Connecting to Neon (Target): {db_url.split('@')[-1]}")
    
    engine = create_async_engine(
        db_url, 
        connect_args={"ssl": "require"}, 
        echo=False
    )
    
    try:
        async with engine.begin() as conn:
            # 1. Drop all tables in public schema
            logger.info("Dropping all tables in 'public' schema...")
            
            # This query find all tables in public and generates DROP statements
            query = text("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            await conn.execute(query)
            
            # 2. Drop all sequences
            logger.info("Dropping all sequences...")
            query_seq = text("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'S' AND n.nspname = 'public') LOOP
                        EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.relname) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            await conn.execute(query_seq)
            
            # 3. Drop all types (enums)
            logger.info("Dropping all custom types...")
            query_types = text("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = 'public' AND typtype = 'e') LOOP
                        EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            await conn.execute(query_types)

            logger.info("Neon public schema successfully sanitized.")

    except Exception as e:
        logger.error(f"Sanitization failed: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(sanitize_neon())
