"""
FinAI Backend — Database Layer (SQLAlchemy Async)
Supports SQLite (dev) and PostgreSQL (production)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# ── Engine ──
_raw_url = settings.DATABASE_URL
_is_postgres = "postgresql" in _raw_url
_is_sqlite = "sqlite" in _raw_url

# Normalize DB URL for asyncpg
_db_url = _raw_url
if _is_postgres:
    # Ensure async driver prefix
    if _db_url.startswith("postgresql://"):
        _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Strip query params that asyncpg doesn't support
    if "?" in _db_url:
        _db_url = _db_url.split("?")[0]
    _pool_kwargs = {
        "pool_pre_ping": True,
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # recycle connections every 30 min
        "connect_args": {"ssl": True},
    }
    logger.info("PostgreSQL async engine: %s...%s", _db_url[:40], _db_url[-20:])
else:
    # SQLite doesn't support connection pooling parameters
    _pool_kwargs = {}

engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    **_pool_kwargs,
)

# Enable WAL mode for SQLite (better concurrent performance)
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()

# ── Session Factory ──
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Base Model ──
class Base(DeclarativeBase):
    pass

# ── Dependency ──
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ── Health Check ──
async def check_db_health() -> dict:
    """Test the database connection and return health info."""
    try:
        async with AsyncSessionLocal() as session:
            if _is_postgres:
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                db_type = "postgresql"
            else:
                result = await session.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                db_type = "sqlite"
        return {
            "status": "healthy",
            "database_type": db_type,
            "version": version,
            "pool_size": 20 if _is_postgres else "N/A (SQLite)",
            "max_overflow": 10 if _is_postgres else "N/A",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database_type": "postgresql" if _is_postgres else "sqlite",
            "error": str(e),
        }

# ── Init DB ──
async def init_db():
    """Create all tables on startup.

    Schema changes should be managed via Alembic migrations:
        alembic revision --autogenerate -m "description"
        alembic upgrade head

    For development convenience, create_all() still runs to bootstrap new DBs.
    In production, use 'alembic upgrade head' instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized (type: %s). Use 'alembic upgrade head' for production migrations.",
                "PostgreSQL" if _is_postgres else "SQLite")

async def drop_db():
    """Drop all tables (use only in tests)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
