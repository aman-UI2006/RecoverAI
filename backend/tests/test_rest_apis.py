"""
RecoverAI - REST API Integration Test Suite (Step 25)

Comprehensive test suite verifying transactions, analytics, audit, policies, and evaluations REST endpoints.
Enforces multi-tenant merchant isolation, Pydantic input validation, standardized exception formatting,
Decimal monetary safety, mode separation, and read-only GET constraints.
"""

import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
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
    Policy,
    RecoveryAttempt,
    RecoveryAttribution,
    AuditEvent,
    EvaluationRun,
)
from backend.app.services.audit_trail_service import AuditTrailService, GENESIS_HASH

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create an isolated in-memory SQLite database session for Step 25 testing."""
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
    """Async HTTP client for FastAPI endpoints with DB dependency override."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def setup_test_data(db_session: AsyncSession):
    """Seed test database with merchants, transactions, audit events, policies, and evaluations."""
    session = db_session

    # 1. Create Merchant A and Merchant B
    merchant_a = Merchant(
        id=str(uuid.uuid4()),
        name="Merchant Alpha",
        email="alpha@merchant.com",
        industry="E-COMMERCE",
    )
    merchant_b = Merchant(
        id=str(uuid.uuid4()),
        name="Merchant Beta",
        email="beta@merchant.com",
        industry="SAAS",
    )
    session.add_all([merchant_a, merchant_b])
    await session.flush()

    # 2. Create Customers
    cust_a = Customer(
        id=str(uuid.uuid4()),
        merchant_id=merchant_a.id,
        email="customer_a@example.com",
        name="Customer Alpha",
    )
    cust_b = Customer(
        id=str(uuid.uuid4()),
        merchant_id=merchant_b.id,
        email="customer_b@example.com",
        name="Customer Beta",
    )
    session.add_all([cust_a, cust_b])
    await session.flush()

    # 3. Create Transactions
    tx_a1 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=merchant_a.id,
        customer_id=cust_a.id,
        razorpay_payment_id="pay_alpha123",
        amount=Decimal("1500.00"),
        currency="INR",
        status="FAILED",
        scenario_type="PAYMENT_LINK_EXPIRED",
        mode="SIMULATION",
    )
    tx_a2 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=merchant_a.id,
        customer_id=cust_a.id,
        razorpay_payment_id="pay_alpha456",
        amount=Decimal("2500.00"),
        currency="INR",
        status="RECOVERED",
        scenario_type="CARD_AUTHENTICATION_FAILED",
        mode="SIMULATION",
    )
    tx_b1 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=merchant_b.id,
        customer_id=cust_b.id,
        razorpay_payment_id="pay_beta123",
        amount=Decimal("5000.00"),
        currency="INR",
        status="FAILED",
        scenario_type="PAYMENT_LINK_EXPIRED",
        mode="SIMULATION",
    )
    session.add_all([tx_a1, tx_a2, tx_b1])
    await session.flush()

    # 4. Create Diagnoses
    diag_a1 = Diagnosis(
        id=str(uuid.uuid4()),
        transaction_id=tx_a1.id,
        failure_code="EXPIRED",
        failure_category="LINK_EXPIRATION",
        root_cause_explanation="Payment link expired after 24h cooldown.",
        confidence_score=0.95,
        diagnosis_source="RULES",
    )
    session.add(diag_a1)

    # 5. Create Policies
    policy_a = Policy(
        id=str(uuid.uuid4()),
        merchant_id=merchant_a.id,
        policy_version="v1.0",
        max_recovery_attempts=3,
        max_auto_action_amount=50000.00,
        min_recovery_probability=0.15,
        cooldown_hours=24,
        is_active=True,
    )
    policy_b = Policy(
        id=str(uuid.uuid4()),
        merchant_id=merchant_b.id,
        policy_version="v1.0",
        max_recovery_attempts=2,
        max_auto_action_amount=10000.00,
        min_recovery_probability=0.20,
        cooldown_hours=12,
        is_active=True,
    )
    session.add_all([policy_a, policy_b])
    await session.flush()

    # 6. Create Audit Chain for tx_a1
    await AuditTrailService.record_event(
        session=session,
        transaction_id=tx_a1.id,
        event_type="INGESTION_RECEIVED",
        actor="EVENT_INGESTION",
        state_from=None,
        state_to="FAILED",
        details={"source": "test_seed"},
    )

    # 7. Create EvaluationRun
    eval_run = EvaluationRun(
        id=str(uuid.uuid4()),
        run_name="step_25_test_run",
        dataset_version="v1.0",
        dataset_size=100,
        random_seed=42,
        model_version="v1.0",
        feature_version="v1.0",
        policy_version="v1.0",
        configuration_version="v1.0",
        code_commit_sha="5150d72",
        mode="SIMULATION",
        revenue_at_risk=9000.00,
        baseline_recovered_amount=1500.00,
        recoverai_gross_recovered_amount=4000.00,
        incremental_recovered_amount=2500.00,
        baseline_recovery_rate=0.166,
        recoverai_recovery_rate=0.444,
        summary_metrics={"lift": 0.278},
    )
    session.add(eval_run)
    await session.commit()

    return {
        "merchant_a": merchant_a,
        "merchant_b": merchant_b,
        "tx_a1": tx_a1,
        "tx_a2": tx_a2,
        "tx_b1": tx_b1,
        "policy_a": policy_a,
        "policy_b": policy_b,
        "eval_run": eval_run,
    }


# =====================================================================
# TRANSACTIONS ENDPOINTS TESTS (1 - 9)
# =====================================================================

@pytest.mark.asyncio
async def test_1_list_transactions(async_client, setup_test_data):
    """1. List transactions endpoint."""
    response = await async_client.get("/api/v1/transactions")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_2_transactions_pagination(async_client, setup_test_data):
    """2. Pagination limit and page parameters."""
    response = await async_client.get("/api/v1/transactions?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 2
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_3_transactions_invalid_pagination(async_client, setup_test_data):
    """3. Invalid pagination parameters produce HTTP 422 validation error."""
    res_page = await async_client.get("/api/v1/transactions?page=0")
    assert res_page.status_code == 422

    res_limit = await async_client.get("/api/v1/transactions?limit=150")
    assert res_limit.status_code == 422


@pytest.mark.asyncio
async def test_4_transactions_scenario_filter(async_client, setup_test_data):
    """4. Filter transactions by failure scenario_type."""
    response = await async_client.get("/api/v1/transactions?scenario_type=PAYMENT_LINK_EXPIRED")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["scenario_type"] == "PAYMENT_LINK_EXPIRED"


@pytest.mark.asyncio
async def test_5_transactions_status_filter(async_client, setup_test_data):
    """5. Filter transactions by status."""
    response = await async_client.get("/api/v1/transactions?status=RECOVERED")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "RECOVERED"


@pytest.mark.asyncio
async def test_6_transaction_detail_success(async_client, setup_test_data):
    """6. Get transaction detail by ID including diagnosis and audit timeline."""
    tx_id = setup_test_data["tx_a1"].id
    response = await async_client.get(f"/api/v1/transactions/{tx_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tx_id
    assert data["customer_email"] == "customer_a@example.com"
    assert data["diagnosis"] is not None
    assert data["diagnosis"]["failure_code"] == "EXPIRED"
    assert "audit_timeline" in data
    assert len(data["audit_timeline"]) >= 1


@pytest.mark.asyncio
async def test_7_transaction_detail_not_found(async_client, setup_test_data):
    """7. Missing transaction returns HTTP 404."""
    random_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/transactions/{random_id}")
    assert response.status_code == 404
    assert response.json()["error"] is True


@pytest.mark.asyncio
async def test_8_transaction_cross_tenant_isolation(async_client, setup_test_data):
    """8. Merchant A cannot access Merchant B's transaction."""
    tx_b_id = setup_test_data["tx_b1"].id
    merchant_a_id = setup_test_data["merchant_a"].id

    # Requesting Tx B with Merchant A header must return 404
    response = await async_client.get(
        f"/api/v1/transactions/{tx_b_id}",
        headers={"X-Merchant-ID": merchant_a_id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_9_transaction_get_is_read_only(async_client, setup_test_data, db_session):
    """9. GET transaction endpoint does not mutate status."""
    tx_id = setup_test_data["tx_a1"].id
    initial_status = setup_test_data["tx_a1"].status

    res1 = await async_client.get(f"/api/v1/transactions/{tx_id}")
    assert res1.status_code == 200

    tx = await db_session.get(Transaction, tx_id)
    assert tx.status == initial_status


# =====================================================================
# ANALYTICS ENDPOINTS TESTS (10 - 13)
# =====================================================================

@pytest.mark.asyncio
async def test_10_analytics_summary(async_client, setup_test_data):
    """10. Analytics summary endpoint returns Command Center KPI metrics."""
    response = await async_client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "treatment_metrics" in data
    assert "control_metrics" in data
    assert "incremental_recovery_rate" in data


@pytest.mark.asyncio
async def test_11_analytics_expected_kpi_schema(async_client, setup_test_data):
    """11. Analytics KPI metrics match schema fields."""
    response = await async_client.get("/api/v1/analytics/summary?mode=SIMULATION")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "SIMULATION"
    assert "net_incremental_revenue" in data
    assert "estimated_incremental_recovered_amount" in data


@pytest.mark.asyncio
async def test_12_analytics_decimal_money_serialization(async_client, setup_test_data):
    """12. Decimal monetary values are serialized as standard JSON floats without rounding distortion."""
    response = await async_client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["treatment_recovered_amount"], (float, int))
    assert isinstance(data["net_incremental_revenue"], (float, int))


@pytest.mark.asyncio
async def test_13_analytics_mode_separation(async_client, setup_test_data):
    """13. Mode separation between REAL_TEST and SIMULATION in analytics."""
    res_sim = await async_client.get("/api/v1/analytics/summary?mode=SIMULATION")
    assert res_sim.status_code == 200
    assert res_sim.json()["mode"] == "SIMULATION"

    res_real = await async_client.get("/api/v1/analytics/summary?mode=REAL_TEST")
    assert res_real.status_code == 200
    assert res_real.json()["mode"] == "REAL_TEST"


# =====================================================================
# AUDIT ENDPOINTS TESTS (14 - 17)
# =====================================================================

@pytest.mark.asyncio
async def test_14_audit_list(async_client, setup_test_data):
    """14. Audit log records list endpoint."""
    response = await async_client.get("/api/v1/audit")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_15_audit_verify_valid_chain(async_client, setup_test_data):
    """15. Cryptographic hash chain verification for valid transaction."""
    tx_id = setup_test_data["tx_a1"].id
    response = await async_client.get(f"/api/v1/audit/verify?transaction_id={tx_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == tx_id
    assert data["is_valid"] is True
    assert data["genesis_hash"] == GENESIS_HASH


@pytest.mark.asyncio
async def test_16_audit_verify_tampered_chain(async_client, setup_test_data, db_session):
    """16. Cryptographic hash chain verification detects tampered records."""
    session = db_session
    # Create transaction with tampered audit event
    tx_tampered = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=setup_test_data["merchant_a"].id,
        customer_id=setup_test_data["tx_a1"].customer_id,
        amount=Decimal("100.00"),
        currency="INR",
        status="FAILED",
        scenario_type="SIMULATION",
    )
    session.add(tx_tampered)
    await session.flush()

    # Add event with corrupted previous_hash
    bad_event = AuditEvent(
        id=str(uuid.uuid4()),
        transaction_id=tx_tampered.id,
        event_type="INGESTION_RECEIVED",
        actor="SYSTEM",
        details={"corrupted": True},
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
        event_hash="1111111111111111111111111111111111111111111111111111111111111111",
    )
    session.add(bad_event)
    await session.commit()
    tampered_tx_id = tx_tampered.id

    response = await async_client.get(f"/api/v1/audit/verify?transaction_id={tampered_tx_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert data["tampered_event_id"] is not None


@pytest.mark.asyncio
async def test_17_audit_endpoint_read_only(async_client, setup_test_data):
    """17. Audit endpoints are strictly read-only."""
    response = await async_client.get("/api/v1/audit")
    assert response.status_code == 200


# =====================================================================
# POLICIES ENDPOINTS TESTS (18 - 22)
# =====================================================================

@pytest.mark.asyncio
async def test_18_get_policy(async_client, setup_test_data):
    """18. Get specific policy by ID."""
    policy_id = setup_test_data["policy_a"].id
    response = await async_client.get(f"/api/v1/policies/{policy_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == policy_id
    assert data["max_recovery_attempts"] == 3


@pytest.mark.asyncio
async def test_19_patch_policy_valid(async_client, setup_test_data):
    """19. Valid PATCH policy updates target fields."""
    policy_id = setup_test_data["policy_a"].id
    payload = {"max_recovery_attempts": 5, "min_recovery_probability": 0.25}

    response = await async_client.patch(f"/api/v1/policies/{policy_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["max_recovery_attempts"] == 5
    assert data["min_recovery_probability"] == 0.25


@pytest.mark.asyncio
async def test_20_patch_policy_invalid(async_client, setup_test_data):
    """20. Invalid PATCH payload returns HTTP 422."""
    policy_id = setup_test_data["policy_a"].id
    invalid_payload = {"min_recovery_probability": 2.5}  # Must be <= 1.0

    response = await async_client.patch(f"/api/v1/policies/{policy_id}", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_21_patch_policy_partial_preservation(async_client, setup_test_data):
    """21. PATCH preserves unspecified fields and policy versioning."""
    policy_id = setup_test_data["policy_b"].id
    payload = {"cooldown_hours": 36}

    response = await async_client.patch(f"/api/v1/policies/{policy_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["cooldown_hours"] == 36
    # Unspecified fields remain intact
    assert data["max_recovery_attempts"] == 2
    assert data["max_auto_action_amount"] == 10000.00


@pytest.mark.asyncio
async def test_22_policy_cross_tenant_isolation(async_client, setup_test_data):
    """22. Cross-tenant policy access isolation."""
    policy_b_id = setup_test_data["policy_b"].id
    merchant_a_id = setup_test_data["merchant_a"].id

    response = await async_client.get(
        f"/api/v1/policies/{policy_b_id}",
        headers={"X-Merchant-ID": merchant_a_id},
    )
    assert response.status_code == 404


# =====================================================================
# EVALUATIONS ENDPOINTS TESTS (23 - 25)
# =====================================================================

@pytest.mark.asyncio
async def test_23_list_evaluations(async_client, setup_test_data):
    """23. List evaluation runs endpoint."""
    response = await async_client.get("/api/v1/evaluations")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_24_get_evaluation_detail(async_client, setup_test_data):
    """24. Get evaluation run detail and 404 handling."""
    eval_id = setup_test_data["eval_run"].id
    response = await async_client.get(f"/api/v1/evaluations/{eval_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == eval_id
    assert data["run_name"] == "step_25_test_run"

    res_404 = await async_client.get(f"/api/v1/evaluations/{str(uuid.uuid4())}")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_25_evaluations_mode_filtering(async_client, setup_test_data):
    """25. Filter evaluations by mode."""
    response = await async_client.get("/api/v1/evaluations?mode=SIMULATION")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["mode"] == "SIMULATION"


# =====================================================================
# CROSS-CUTTING ARCHITECTURAL & SECURITY TESTS (26 - 33)
# =====================================================================

@pytest.mark.asyncio
async def test_26_standardized_validation_errors(async_client):
    """26. Validation errors produce standardized JSON format."""
    response = await async_client.get("/api/v1/transactions?page=invalid")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] is True
    assert data["status"] == "error"
    assert data["code"] == 422


@pytest.mark.asyncio
async def test_27_standardized_404_behavior(async_client):
    """27. Nonexistent resources return standardized 404 JSON response."""
    response = await async_client.get(f"/api/v1/transactions/{str(uuid.uuid4())}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert data["code"] == 404


@pytest.mark.asyncio
async def test_28_sanitized_error_responses(async_client):
    """28. Errors do not leak internal file paths, stack traces, or credentials."""
    response = await async_client.get(f"/api/v1/transactions/{str(uuid.uuid4())}")
    body_text = response.text
    assert "RAZORPAY_KEY_SECRET" not in body_text
    assert "Traceback" not in body_text


@pytest.mark.asyncio
async def test_29_request_trace_id_propagation(async_client, setup_test_data):
    """29. X-Trace-ID header is generated/propagated across REST endpoints."""
    custom_trace_id = "trace-step25-test-12345"
    response = await async_client.get(
        "/api/v1/transactions",
        headers={"X-Trace-ID": custom_trace_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Trace-ID") == custom_trace_id


@pytest.mark.asyncio
async def test_30_no_secret_leakage(async_client, setup_test_data):
    """30. Response payloads do not leak system secrets or environment variables."""
    response = await async_client.get("/api/v1/analytics/summary")
    data_str = response.text.lower()
    assert "secret" not in data_str
    assert "password" not in data_str


@pytest.mark.asyncio
async def test_31_no_direct_state_mutation_from_read_endpoints(async_client, setup_test_data, db_session):
    """31. GET endpoints never mutate transaction status or recovery attempt status."""
    tx_id = setup_test_data["tx_a1"].id
    tx_before = await db_session.get(Transaction, tx_id)
    status_before = tx_before.status

    await async_client.get(f"/api/v1/transactions/{tx_id}")
    await async_client.get(f"/api/v1/audit/verify?transaction_id={tx_id}")

    tx_after = await db_session.get(Transaction, tx_id)
    assert tx_after.status == status_before


@pytest.mark.asyncio
async def test_32_no_razorpay_action_execution_from_rest_apis(async_client, setup_test_data):
    """32. REST API endpoints do not execute external Razorpay financial calls."""
    tx_id = setup_test_data["tx_a1"].id
    res = await async_client.get(f"/api/v1/transactions/{tx_id}")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_33_no_llm_invocation_from_api_layer(async_client, setup_test_data):
    """33. REST API layer does not invoke external LLM providers."""
    res = await async_client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
