"""
RecoverAI - Step 46: Merchant Intelligence Service Test Suite

Validates merchant-level analytics aggregation, turnaround computation, channel ranking,
industry cohort benchmarking, and multi-tenant isolation endpoint behavior.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.domain import Merchant, Transaction, Customer, RecoveryAttempt
from backend.app.services.merchant_intelligence_service import MerchantIntelligenceService
from backend.app.schemas.analytics import MerchantIntelligenceResponse

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create isolated in-memory SQLite DB for merchant intelligence tests."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.mark.asyncio
async def test_merchant_intelligence_service_cold_start(db_session: AsyncSession):
    """Verify MerchantIntelligenceService provides fallback benchmarks for empty/new merchant."""
    res = await MerchantIntelligenceService.get_merchant_intelligence(
        session=db_session,
        merchant_id=None,
        mode="SIMULATION",
    )

    assert isinstance(res, MerchantIntelligenceResponse)
    assert res.total_transactions_analyzed == 0
    assert res.avg_turnaround_minutes > 0.0
    assert res.top_channel != ""
    assert len(res.industry_benchmarks) >= 4

    industries = [b.industry for b in res.industry_benchmarks]
    assert "SaaS" in industries
    assert "E-commerce" in industries
    assert "EdTech" in industries
    assert "FinTech" in industries


@pytest.mark.asyncio
async def test_merchant_intelligence_service_populated(db_session: AsyncSession):
    """Verify MerchantIntelligenceService accurately aggregates populated transaction history."""
    # 1. Create test merchant
    m = Merchant(
        name="Test Merchant SaaS",
        email="saas@testmerchant.com",
        industry="SaaS",
    )
    db_session.add(m)
    await db_session.flush()

    # 2. Create customer
    c = Customer(
        merchant_id=m.id,
        email="customer@testmerchant.com",
    )
    db_session.add(c)
    await db_session.flush()

    # 3. Create transaction
    tx = Transaction(
        merchant_id=m.id,
        customer_id=c.id,
        amount=5000.0,
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    db_session.add(tx)
    await db_session.flush()

    # 4. Create recovery attempt
    att = RecoveryAttempt(
        transaction_id=tx.id,
        logical_operation_key=f"op_{uuid.uuid4()}",
        recommended_action="PAYMENT_LINK",
        action_payload={"link_type": "instant"},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="EXECUTED",
        external_resource_type="PAYMENT_LINK",
    )
    db_session.add(att)
    await db_session.commit()

    # 5. Retrieve merchant intelligence
    res = await MerchantIntelligenceService.get_merchant_intelligence(
        session=db_session,
        merchant_id=m.id,
        mode="SIMULATION",
    )

    assert res.merchant_id == m.id
    assert res.industry == "SaaS"
    assert res.total_transactions_analyzed == 1
    assert res.top_channel == "PAYMENT_LINK"
    assert res.channel_performance.get("PAYMENT_LINK") == 100.0


@pytest.mark.asyncio
async def test_merchant_analytics_api_endpoint(db_session: AsyncSession):
    """Verify GET /api/v1/analytics/merchant API endpoint delivers structured JSON response."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    headers = {"X-API-Key": "key_admin_secret_999"}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=headers,
        ) as client:
            response = await client.get("/api/v1/analytics/merchant?mode=SIMULATION")

            assert response.status_code == 200
            data = response.json()

            assert "industry" in data
            assert "avg_turnaround_minutes" in data
            assert "top_channel" in data
            assert "channel_performance" in data
            assert "industry_benchmarks" in data
            assert isinstance(data["industry_benchmarks"], list)
    finally:
        app.dependency_overrides.clear()
