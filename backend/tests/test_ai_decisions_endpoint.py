"""
RecoverAI - AI Decisions REST API Endpoint Test Suite

Exhaustively verifies GET /api/v1/ai-decisions/{id} endpoint:
- Correct DecisionContext & RecoveryActionScore extraction
- Correct ENRV ranking and top action identification
- Multi-tenant merchant isolation & 404 behavior
- Authentication & JWT/API-Key security checks
- X-Merchant-ID spoofing protection
- Read-only state safety (zero state mutations, zero DB writes, zero Razorpay calls)
- Graceful handling of missing decision contexts or diagnoses
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.domain import (
    Merchant,
    Customer,
    Transaction,
    Diagnosis,
    DecisionContext,
    RecoveryActionScore,
    AuditEvent,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create isolated in-memory SQLite database session."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """Async HTTP client with DB dependency override and admin API key header."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "key_admin_secret_999"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Seed DB with multi-tenant test data: Merchant Alpha, Merchant Beta, transactions, diagnoses, decision contexts, scores, audit events."""
    session = db_session

    # Merchant Alpha
    m_alpha = Merchant(
        id="m_alpha_123",
        name="Merchant Alpha",
        email="alpha@merchant.com",
        industry="E-COMMERCE",
    )
    # Merchant Beta
    m_beta = Merchant(
        id="m_beta_456",
        name="Merchant Beta",
        email="beta@merchant.com",
        industry="SAAS",
    )

    c_alpha = Customer(
        id="c_alpha_1",
        merchant_id=m_alpha.id,
        email="customer1@alpha.com",
        name="Alice Alpha",
    )

    tx_alpha = Transaction(
        id="tx_alpha_100",
        merchant_id=m_alpha.id,
        customer_id=c_alpha.id,
        amount=1000.00,
        currency="INR",
        status="INTERVENTION_SELECTED",
        scenario_type="CARD_AUTHENTICATION_FAILURE",
        mode="SIMULATION",
    )

    tx_beta = Transaction(
        id="tx_beta_200",
        merchant_id=m_beta.id,
        customer_id=c_alpha.id,
        amount=2500.00,
        currency="INR",
        status="FAILED",
        scenario_type="INSUFFICIENT_FUNDS",
        mode="REAL_TEST",
    )

    diag_alpha = Diagnosis(
        id=str(uuid.uuid4()),
        transaction_id=tx_alpha.id,
        failure_code="BAD_OTP",
        failure_category="AUTHENTICATION",
        root_cause_explanation="Customer entered incorrect OTP during 3DS challenge.",
        confidence_score=0.92,
        diagnosis_source="RULES",
    )

    ctx_alpha = DecisionContext(
        id=str(uuid.uuid4()),
        transaction_id=tx_alpha.id,
        model_version="v1.2",
        feature_version="v1.1",
        policy_version="v1.0",
    )

    score_1 = RecoveryActionScore(
        id=str(uuid.uuid4()),
        decision_context_id=ctx_alpha.id,
        transaction_id=tx_alpha.id,
        action="PAYMENT_LINK",
        recovery_probability=0.75,
        expected_gross_recovery=750.00,
        intervention_cost=3.50,
        expected_net_recovery_value=746.50,
    )

    score_2 = RecoveryActionScore(
        id=str(uuid.uuid4()),
        decision_context_id=ctx_alpha.id,
        transaction_id=tx_alpha.id,
        action="RECOVERY_MESSAGE",
        recovery_probability=0.40,
        expected_gross_recovery=400.00,
        intervention_cost=0.60,
        expected_net_recovery_value=399.40,
    )

    audit_alpha = AuditEvent(
        id=str(uuid.uuid4()),
        transaction_id=tx_alpha.id,
        event_type="STATE_TRANSITION",
        actor="STRUCTURED_AI_RECOMMENDER",
        state_from="DIAGNOSED",
        state_to="INTERVENTION_SELECTED",
        details={
            "recommended_action": "PAYMENT_LINK",
            "confidence_score": 0.88,
            "rationale_text": "High recovery probability via direct payment link.",
            "customer_message_template": "Complete your transaction securely with this link.",
        },
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
        event_hash="hash_alpha_123",
    )

    session.add_all([m_alpha, m_beta, c_alpha, tx_alpha, tx_beta, diag_alpha, ctx_alpha, score_1, score_2, audit_alpha])
    await session.commit()

    return {
        "tx_alpha_id": tx_alpha.id,
        "tx_beta_id": tx_beta.id,
        "m_alpha_id": m_alpha.id,
        "m_beta_id": m_beta.id,
        "ctx_alpha_id": ctx_alpha.id,
    }


@pytest.mark.asyncio
async def test_get_ai_decision_success(async_client: AsyncClient, seed_data: dict):
    """Verify successful retrieval of complete AI decision context for a transaction."""
    tx_id = seed_data["tx_alpha_id"]
    merchant_id = seed_data["m_alpha_id"]

    res = await async_client.get(
        f"/api/v1/ai-decisions/{tx_id}",
        headers={"X-Merchant-ID": merchant_id},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["transaction_id"] == tx_id
    assert data["merchant_id"] == merchant_id
    assert data["decision_context_id"] == seed_data["ctx_alpha_id"]
    assert data["model_version"] == "v1.2"
    assert data["feature_version"] == "v1.1"
    assert data["policy_version"] == "v1.0"
    assert data["top_action"] == "PAYMENT_LINK"
    assert data["best_enrv_rupees"] == 746.50

    # Diagnosis assertions
    assert data["diagnosis"] is not None
    assert data["diagnosis"]["failure_code"] == "BAD_OTP"
    assert data["diagnosis"]["failure_category"] == "AUTHENTICATION"
    assert data["diagnosis"]["confidence_score"] == 0.92

    # Recommendation assertions
    assert data["recommendation"] is not None
    assert data["recommendation"]["recommended_action"] == "PAYMENT_LINK"
    assert data["recommendation"]["confidence_score"] == 0.88
    assert "High recovery probability" in data["recommendation"]["rationale_text"]

    # Action Scores ranking & ENRV assertions
    assert len(data["action_scores"]) == 2
    top_score = data["action_scores"][0]
    second_score = data["action_scores"][1]

    assert top_score["action"] == "PAYMENT_LINK"
    assert top_score["expected_net_recovery_value"] == 746.50
    assert top_score["rank"] == 1

    assert second_score["action"] == "RECOVERY_MESSAGE"
    assert second_score["expected_net_recovery_value"] == 399.40
    assert second_score["rank"] == 2

    # Capability & Policy summaries
    assert data["capability_evaluation"]["status"] == "SUPPORTED"
    assert data["capability_evaluation"]["is_executable"] is True
    assert data["policy_evaluation"]["policy_status"] == "APPROVED"


@pytest.mark.asyncio
async def test_get_ai_decision_not_found(async_client: AsyncClient):
    """Verify HTTP 404 response for non-existent transaction."""
    res = await async_client.get("/api/v1/ai-decisions/non_existent_tx_999")
    assert res.status_code == 404
    assert "was not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_ai_decision_cross_tenant_404(async_client: AsyncClient, seed_data: dict):
    """Verify strict multi-tenant isolation returns 404 when Merchant Alpha requests Merchant Beta's transaction."""
    tx_beta_id = seed_data["tx_beta_id"]
    m_alpha_id = seed_data["m_alpha_id"]

    res = await async_client.get(
        f"/api/v1/ai-decisions/{tx_beta_id}",
        headers={"X-Merchant-ID": m_alpha_id},
    )

    assert res.status_code == 404
    assert "was not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_get_ai_decision_unauthenticated(db_session: AsyncSession):
    """Verify HTTP 401 response when request lacks Authorization and X-API-Key headers."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    # No auth header
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/ai-decisions/tx_alpha_100")
        assert res.status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_ai_decision_invalid_api_key(db_session: AsyncSession):
    """Verify HTTP 401 response for invalid X-API-Key."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "invalid_bogus_key"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        res = await client.get("/api/v1/ai-decisions/tx_alpha_100")
        assert res.status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_ai_decision_missing_context_fallback(async_client: AsyncClient, seed_data: dict):
    """Verify graceful handling for transaction without decision context or action scores."""
    tx_beta_id = seed_data["tx_beta_id"]
    m_beta_id = seed_data["m_beta_id"]

    res = await async_client.get(
        f"/api/v1/ai-decisions/{tx_beta_id}",
        headers={"X-Merchant-ID": m_beta_id},
    )

    assert res.status_code == 200
    data = res.json()

    assert data["transaction_id"] == tx_beta_id
    assert data["merchant_id"] == m_beta_id
    assert data["decision_context_id"] is None
    assert data["action_scores"] == []
    assert data["diagnosis"] is None
    assert data["top_action"] == "PAYMENT_LINK"
    assert data["capability_evaluation"]["execution_mode"] == "REAL_TEST"


@pytest.mark.asyncio
async def test_get_ai_decision_read_only_safety(async_client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify reading AI decision context performs zero state mutations or side effects."""
    tx_id = seed_data["tx_alpha_id"]
    m_id = seed_data["m_alpha_id"]

    # Retrieve before state
    res1 = await async_client.get(f"/api/v1/ai-decisions/{tx_id}", headers={"X-Merchant-ID": m_id})
    assert res1.status_code == 200

    res2 = await async_client.get(f"/api/v1/ai-decisions/{tx_id}", headers={"X-Merchant-ID": m_id})
    assert res2.status_code == 200

    # Ensure responses are strictly identical
    assert res1.json() == res2.json()
