"""
Alembic environment — async SQLAlchemy migration support.
Loads database URL from app.config and imports all models for autogenerate.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config object
config = context.config

# Set up loggers from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so autogenerate detects them ──
from app.database import Base  # noqa: E402
import app.models.all_models  # noqa: E402, F401

target_metadata = Base.metadata

# ── Load database URL from app settings ──
from app.config import settings  # noqa: E402

_db_url = settings.DATABASE_URL
# For alembic's sync operations, we need the sync driver + sslmode if it's PostgreSQL
_sync_url = _db_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
if "postgresql" in _sync_url and "sslmode=" not in _sync_url:
    _query_sep = "&" if "?" in _sync_url else "?"
    _sync_url = f"{_sync_url}{_query_sep}sslmode=require"

# Pure async URL with driver
_async_url = _db_url.strip()
if _async_url.startswith("postgresql://"):
    _async_url = _async_url.replace("postgresql://", "postgresql+asyncpg://", 1)
# Strip params for connect_args logic
_async_url = _async_url.split("?")[0]


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL scripts."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a connection (used by both sync and async paths)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
        compare_type=True,  # Detect column type changes
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _async_url
    
    # Handle SSL for asyncpg (Neon requires SSL)
    _connect_args = {}
    if "postgresql" in _async_url:
        _connect_args["ssl"] = "require"

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
