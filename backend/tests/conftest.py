"""
conftest.py -- Shared fixtures for FinAI security & error-path tests.

Uses an in-memory SQLite database so every test session starts fresh.
Patches heavyweight startup code (vector store, agents, etc.) so the
FastAPI app boots in milliseconds.
"""

import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Force test-safe env vars BEFORE any app import
# ---------------------------------------------------------------------------
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET"] = "test-jwt-secret-for-unit-tests-only"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"
os.environ["REQUIRE_AUTH"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["ALLOW_DUPLICATE_UPLOADS"] = "false"
os.environ["DEBUG"] = "true"

# ---------------------------------------------------------------------------
# In-memory async engine + session factory (StaticPool = single shared DB)
# ---------------------------------------------------------------------------
_test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Patch heavy startup dependencies before importing the app
# ---------------------------------------------------------------------------
_vector_store_mock = MagicMock()
_vector_store_mock.initialize = AsyncMock()
_vector_store_mock.is_initialized = False
_vector_store_mock.index_knowledge_graph = AsyncMock(return_value={"graph_entities": 0, "indexed": 0, "source": "test"})
_vector_store_mock.index_agent_memories = AsyncMock(return_value={"indexed": 0})

_cache_mock = MagicMock()
_cache_mock.initialize = AsyncMock()
_cache_mock.close = AsyncMock()

_realtime_mock = MagicMock()
_realtime_mock.connect = AsyncMock()
_realtime_mock.disconnect = MagicMock()
_realtime_mock.handle_message = AsyncMock()

# Patch before importing the app
sys.modules.setdefault("chromadb", MagicMock())


# ---------------------------------------------------------------------------
# Database dependency override
# ---------------------------------------------------------------------------
async def _override_get_db():
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _create_tables():
    """Create all tables once per session."""
    from app.database import Base
    import app.models.all_models  # noqa: F401
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the rate limiter store before each test to prevent 429 cross-contamination."""
    try:
        from app.middleware.rate_limiter import _store
        _store._requests.clear()
        _store._total_checks = 0
    except Exception:
        pass


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _seed_users(_create_tables):
    """Seed test users into the DB once. Persisted for the whole session."""
    from app.models.all_models import User
    from app.auth import hash_password

    users_data = [
        {"email": "testuser@finai.test", "username": "testuser", "full_name": "Test User",
         "password": "SecurePass123!", "role": "analyst"},
        {"email": "admin@finai.test", "username": "adminuser", "full_name": "Admin User",
         "password": "AdminPass456!", "role": "admin"},
        {"email": "viewer@finai.test", "username": "vieweruser", "full_name": "Viewer User",
         "password": "ViewerPass789!", "role": "viewer"},
    ]

    created = {}
    async with _TestSessionLocal() as session:
        for data in users_data:
            user = User(
                email=data["email"],
                username=data["username"],
                full_name=data["full_name"],
                hashed_password=hash_password(data["password"]),
                role=data["role"],
                company="TestCo",
                is_active=True,
                is_verified=True,
            )
            session.add(user)
        await session.commit()

        # Refresh to get IDs
        for data in users_data:
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == data["email"])
            )
            user = result.scalar_one()
            created[data["role"]] = {
                "id": user.id,
                "email": data["email"],
                "password": data["password"],
                "role": data["role"],
                "username": data["username"],
            }

    yield created


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app(_seed_users):
    """Return the FastAPI application with DB dependency overridden."""
    with patch("app.services.vector_store.vector_store", _vector_store_mock), \
         patch("app.services.cache.cache_service", _cache_mock), \
         patch("app.services.realtime.realtime_manager", _realtime_mock), \
         patch("app.database.AsyncSessionLocal", _TestSessionLocal), \
         patch("app.database.engine", _test_engine):
        from app.database import get_db
        from main import app as fastapi_app
        fastapi_app.dependency_overrides[get_db] = _override_get_db
        yield fastapi_app
        fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(app):
    """Async HTTP test client (no real server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_session(_create_tables) -> AsyncSession:
    """Provide a long-lived DB session for direct DB queries in tests."""
    async with _TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_user(_seed_users) -> dict:
    return _seed_users["analyst"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_user(_seed_users) -> dict:
    return _seed_users["admin"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def viewer_user(_seed_users) -> dict:
    return _seed_users["viewer"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def auth_token(test_user) -> str:
    """Return a valid JWT for the test_user."""
    from app.auth import create_access_token
    return create_access_token(test_user["id"], test_user["email"], test_user["role"])


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_token(admin_user) -> str:
    """Return a valid JWT for the admin user."""
    from app.auth import create_access_token
    return create_access_token(admin_user["id"], admin_user["email"], admin_user["role"])


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def viewer_token(viewer_user) -> str:
    """Return a valid JWT for the viewer user."""
    from app.auth import create_access_token
    return create_access_token(viewer_user["id"], viewer_user["email"], viewer_user["role"])


def auth_headers(token: str) -> dict:
    """Convenience: build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}
