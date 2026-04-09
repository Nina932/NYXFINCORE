"""
FinAI Backend — API Tests
Run: pytest tests/ -v
"""
import pytest
import asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base, get_db
from main import app

# ── Test Database (in-memory SQLite) ──
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

async def override_db():
    async with TestSession() as session:
        yield session

app.dependency_overrides[get_db] = override_db

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

# ── Tests ──
@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_list_datasets_empty(client):
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

@pytest.mark.asyncio
async def test_list_reports_empty(client):
    r = await client.get("/api/reports")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

@pytest.mark.asyncio
async def test_create_report(client):
    payload = {"title": "Test P&L", "report_type": "pl", "period": "Jan 2025", "currency": "GEL"}
    r = await client.post("/api/reports", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["title"] == "Test P&L"

@pytest.mark.asyncio
async def test_get_analytics_dashboard(client):
    r = await client.get("/api/analytics/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "kpis" in data
    assert "charts" in data

@pytest.mark.asyncio
async def test_get_transactions_empty(client):
    r = await client.get("/api/analytics/transactions")
    assert r.status_code == 200
    data = r.json()
    assert "transactions" in data

@pytest.mark.asyncio
async def test_agent_status(client):
    r = await client.get("/api/agent/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "model" in data

@pytest.mark.asyncio
async def test_feedback_submit(client):
    payload = {"feedback_type": "up", "message_content": "Great analysis!", "user_question": "What is revenue?"}
    r = await client.post("/api/agent/feedback", json=payload)
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_feedback_stats(client):
    r = await client.get("/api/agent/feedback/stats")
    assert r.status_code == 200
    data = r.json()
    assert "accuracy_pct" in data

@pytest.mark.asyncio
async def test_add_memory(client):
    payload = {"content": "Revenue target is ₾226M for Jan 2025", "memory_type": "fact", "importance": 7}
    r = await client.post("/api/agent/memory", json=payload)
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_list_memory(client):
    r = await client.get("/api/agent/memory")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

@pytest.mark.asyncio
async def test_pl_statement(client):
    r = await client.get("/api/analytics/pl")
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert "kpis" in data

@pytest.mark.asyncio
async def test_balance_sheet(client):
    r = await client.get("/api/analytics/balance-sheet")
    assert r.status_code == 200
    data = r.json()
    assert "totals" in data
    assert "assets" in data

@pytest.mark.asyncio
async def test_revenue_analysis(client):
    r = await client.get("/api/analytics/revenue")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_404_on_unknown_report(client):
    r = await client.get("/api/reports/99999")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_delete_report(client):
    # Create then delete
    payload = {"title": "Delete Me", "report_type": "custom", "period": "Jan 2025"}
    r = await client.post("/api/reports", json=payload)
    report_id = r.json()["id"]
    
    r2 = await client.delete(f"/api/reports/{report_id}")
    assert r2.status_code == 200

    r3 = await client.get(f"/api/reports/{report_id}")
    assert r3.status_code == 404
