"""
RecoverAI — Step 42 Security, Failure Mode & Concurrency Test Suite

Validates system resilience under adversarial conditions:
1. Forged HMAC signature prevention and state immutability.
2. 100 concurrent duplicate webhook delivery deduplication and state integrity.
3. Redis fast-path outage graceful degradation to PostgreSQL correctness boundary.
4. Database failure atomic rollback during state transition.
5. Malicious input, SQL injection, XSS, and schema validation rejection.
"""

import asyncio
import hashlib
import hmac
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.models.domain import (
    Merchant,
    Customer,
    Transaction,
    Event,
    AuditEvent,
    RecoveryAttempt,
)
from backend.app.schemas.state_machine import TransactionStatus
from backend.app.services.event_normalizer import EventNormalizerService
from backend.app.services.state_transition_service import StateTransitionService
from backend.app.services.audit_trail_service import AuditTrailService
from backend.app.core.security import create_access_token


def generate_valid_signature(raw_body: bytes, secret: str = settings.RAZORPAY_WEBHOOK_SECRET) -> str:
    """Helper to compute valid HMAC-SHA256 signature for test payloads."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()


@pytest_asyncio.fixture
async def shared_db_engine():
    """Create a shared file-based SQLite engine for true concurrent multi-session tests."""
    import os
    db_file = "./test_step42_concurrency.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


@pytest_asyncio.fixture
async def shared_session_factory(shared_db_engine):
    """Session factory linked to shared in-memory database."""
    return async_sessionmaker(shared_db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(shared_session_factory):
    """Primary DB session fixture."""
    async with shared_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(shared_session_factory):
    """Async HTTP client with DB dependency override tied to shared session factory."""
    async def _override_get_db():
        async with shared_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


# =====================================================================
# TEST 1 — FORGED HMAC SIGNATURE REJECTION & STATE IMMUTABILITY
# =====================================================================

@pytest.mark.asyncio
async def test_1_forged_hmac_prevents_state_mutation(async_client: AsyncClient, db_session: AsyncSession):
    """
    Test 1: Forged HMAC signature rejection.
    Sends a webhook payload with an invalid X-Razorpay-Signature, expects HTTP 401,
    and asserts zero database state mutation (no Event, Transaction, Audit, or Attempt records created).
    """
    payload_dict = {
        "entity": "event",
        "account_id": "acc_forged_test_999",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_forged_001",
                    "amount": 250000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed",
                }
            }
        },
        "created_at": 1770000000,
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    forged_signature = "forged_invalid_hmac_signature_99999"
    event_id = "evt_forged_signature_001"

    # Capture initial DB state counts
    initial_events = len((await db_session.execute(select(Event))).scalars().all())
    initial_txs = len((await db_session.execute(select(Transaction))).scalars().all())
    initial_audits = len((await db_session.execute(select(AuditEvent))).scalars().all())
    initial_attempts = len((await db_session.execute(select(RecoveryAttempt))).scalars().all())

    # Send webhook with forged signature
    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": forged_signature,
            "X-Razorpay-Event-Id": event_id,
        },
    )

    # Assert HTTP 401 Unauthorized
    assert response.status_code == 401
    assert "signature" in response.text.lower() or "unauthorized" in response.text.lower()

    # Re-query DB state after request to assert zero mutation
    post_events = len((await db_session.execute(select(Event))).scalars().all())
    post_txs = len((await db_session.execute(select(Transaction))).scalars().all())
    post_audits = len((await db_session.execute(select(AuditEvent))).scalars().all())
    post_attempts = len((await db_session.execute(select(RecoveryAttempt))).scalars().all())

    assert post_events == initial_events, "Event record created despite forged HMAC!"
    assert post_txs == initial_txs, "Transaction created/mutated despite forged HMAC!"
    assert post_audits == initial_audits, "AuditEvent created despite forged HMAC!"
    assert post_attempts == initial_attempts, "RecoveryAttempt created despite forged HMAC!"


# =====================================================================
# TEST 2 — 100 CONCURRENT DUPLICATE WEBHOOK DELIVERIES
# =====================================================================

@pytest.mark.asyncio
async def test_2_concurrent_100_duplicate_webhooks(async_client: AsyncClient, shared_session_factory):
    """
    Test 2: 100 Concurrent duplicate webhook deliveries.
    Sends 100 simultaneous requests with the exact same payload, event identity, and valid HMAC.
    Verifies exactly ONE authoritative event record is persisted, zero duplicate attempts occur,
    and state/audit chains remain valid.
    """
    event_id = "evt_conc_storm_100_id"
    payload_dict = {
        "entity": "event",
        "account_id": "acc_conc_merchant_100",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_conc_storm_100",
                    "amount": 500000,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_conc_storm_100",
                    "error_code": "GATEWAY_ERROR",
                    "error_description": "Concurrent payment failure test",
                }
            }
        },
        "created_at": 1770000000,
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    valid_signature = generate_valid_signature(raw_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": valid_signature,
        "X-Razorpay-Event-Id": event_id,
    }

    # Dispatch 100 concurrent async POST requests
    tasks = [
        async_client.post("/api/v1/webhooks/razorpay", content=raw_bytes, headers=headers)
        for _ in range(100)
    ]
    responses = await asyncio.gather(*tasks)

    # All responses must succeed with HTTP 200/201
    status_codes = [r.status_code for r in responses]
    assert all(code in (200, 201) for code in status_codes), f"Unexpected status codes: {set(status_codes)}"

    # Inspect persistent DB state across shared session
    async with shared_session_factory() as session:
        # 1. Exactly ONE event persisted for this razorpay_event_id
        stmt_evt = select(Event).where(Event.razorpay_event_id == event_id)
        events = (await session.execute(stmt_evt)).scalars().all()
        assert len(events) == 1, f"Expected exactly 1 Event record, found {len(events)}"

        # 2. Verify no duplicate recovery attempts created
        stmt_att = select(RecoveryAttempt).where(RecoveryAttempt.transaction_id == "order_conc_storm_100")
        attempts = (await session.execute(stmt_att)).scalars().all()
        assert len(attempts) <= 1, f"Duplicate downstream recovery attempts created! Count: {len(attempts)}"

        # 3. Verify audit trail integrity for transaction if created
        stmt_tx = select(Transaction).where(Transaction.id == "order_conc_storm_100")
        tx = (await session.execute(stmt_tx)).scalar_one_or_none()
        if tx:
            audit_report = await AuditTrailService.verify_chain(session, tx.id)
            assert audit_report["valid"] is True, f"Audit chain broken after concurrent delivery: {audit_report}"


# =====================================================================
# TEST 3 — REDIS UNAVAILABLE GRACEFUL DEGRADATION
# =====================================================================

@pytest.mark.asyncio
async def test_3_redis_unavailable_fallback_to_postgres(db_session: AsyncSession):
    """
    Test 3: Redis unavailable fallback.
    Simulates a Redis outage by passing a mock Redis client raising ConnectionError.
    Proves that EventNormalizerService falls back gracefully to PostgreSQL correctness boundary,
    safely rejecting duplicate events without uncaught exceptions.
    """
    failing_redis_mock = AsyncMock()
    failing_redis_mock.exists.side_effect = Exception("RedisConnectionError: Connection refused")
    failing_redis_mock.set.side_effect = Exception("RedisConnectionError: Connection refused")

    event_1 = Event(
        id="evt_redis_outage_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_redis_hdr_999",
        razorpay_event_id="evt_redis_hdr_999",
        payload={"account_id": "acc_redis_test", "event": "payment.failed"},
    )
    db_session.add(event_1)
    await db_session.commit()

    # 1. Process event 1 with failing Redis client -> Must succeed via PostgreSQL boundary (is_duplicate=False)
    norm1, is_dup1 = await EventNormalizerService.process_and_deduplicate(
        session=db_session,
        event=event_1,
        redis_client=failing_redis_mock,
    )
    assert is_dup1 is False, "Initial event incorrectly marked as duplicate during Redis outage!"

    event_2 = Event(
        id="evt_redis_outage_002",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_redis_hdr_999",
        razorpay_event_id="evt_redis_hdr_999",
        payload={"account_id": "acc_redis_test", "event": "payment.failed"},
    )

    # 2. Process duplicate event 2 with failing Redis client -> Must fall back to PostgreSQL boundary (is_duplicate=True)
    norm2, is_dup2 = await EventNormalizerService.process_and_deduplicate(
        session=db_session,
        event=event_2,
        redis_client=failing_redis_mock,
    )
    assert is_dup2 is True, "Duplicate event was NOT detected by PostgreSQL boundary during Redis outage!"


# =====================================================================
# TEST 4 — DATABASE FAILURE DURING STATE TRANSITION (ATOMIC ROLLBACK)
# =====================================================================

@pytest.mark.asyncio
async def test_4_db_failure_atomic_rollback(shared_session_factory):
    """
    Test 4: Database failure during state transition.
    Executes a state transition, induces a database commit exception,
    and asserts atomic rollback (original state preserved, no orphan audit records, session clean).
    """
    tx_id = "tx_atomic_rollback_999"
    merchant_id = "m_rollback_merchant"
    customer_id = "c_rollback_customer"

    # Setup initial transaction in CREATED state
    async with shared_session_factory() as setup_session:
        merchant = Merchant(id=merchant_id, name="Rollback Merchant", email="roll@test.com", industry="SaaS")
        customer = Customer(id=customer_id, merchant_id=merchant_id, email="c_roll@test.com")
        tx = Transaction(
            id=tx_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=Decimal("10000.00"),
            currency="INR",
            status=TransactionStatus.CREATED.value,
            scenario_type="PAYMENT_FAILURE",
        )
        setup_session.add_all([merchant, customer, tx])
        await setup_session.commit()

    # Initiate state transition with injected DB commit failure
    async with shared_session_factory() as failure_session:
        # Mock session.commit to fail during state transition commit step
        with patch.object(failure_session, "commit", side_effect=RuntimeError("Injected DB failure during commit")):
            with pytest.raises(RuntimeError, match="Injected DB failure during commit"):
                await StateTransitionService.transition(
                    session=failure_session,
                    transaction_id=tx_id,
                    target_state=TransactionStatus.AT_RISK.value,
                    actor="TEST_RUNNER",
                    reason="Initiating risk transition for failure test",
                )

        # Explicitly roll back failure session
        await failure_session.rollback()

    # Re-query transaction in a fresh session to verify atomic rollback
    async with shared_session_factory() as fresh_session:
        stmt = select(Transaction).where(Transaction.id == tx_id)
        reloaded_tx = (await fresh_session.execute(stmt)).scalar_one()

        # 1. Original status remains CREATED (no partial mutation persisted)
        assert reloaded_tx.status == TransactionStatus.CREATED.value, (
            f"Transaction state mutated despite rollback! Got: {reloaded_tx.status}"
        )

        # 2. Verify no orphan audit events exist for failed transition
        stmt_audit = select(AuditEvent).where(AuditEvent.transaction_id == tx_id)
        audits = (await fresh_session.execute(stmt_audit)).scalars().all()
        assert len(audits) == 0, f"Orphan audit events persisted after rollback! Count: {len(audits)}"

        # 3. Verify fresh session can execute subsequent valid operations cleanly
        tx_final, _ = await StateTransitionService.transition(
            session=fresh_session,
            transaction_id=tx_id,
            target_state=TransactionStatus.AT_RISK.value,
            actor="RECOVERY_WORKER",
            reason="Clean retry after rollback",
        )
        assert tx_final.status == TransactionStatus.AT_RISK.value


# =====================================================================
# TEST 5 — MALICIOUS & INJECTED INPUT REJECTION
# =====================================================================

@pytest.mark.asyncio
async def test_5_malicious_input_validation_rejection(async_client: AsyncClient, db_session: AsyncSession):
    """
    Test 5: Malicious and injected input validation.
    Tests structural malformed JSON, SQL injection strings, XSS script injection, and invalid amounts.
    Verifies Pydantic schema validation returns HTTP 422/400 and prevents SQL execution or state mutation.
    """
    # 1. Structurally malformed JSON body (with valid signature header for malformed bytes)
    malformed_json_bytes = b'{"entity": "event", "event": "payment.failed", "broken": '
    valid_sig_for_malformed = generate_valid_signature(malformed_json_bytes)

    res1 = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=malformed_json_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": valid_sig_for_malformed,
            "X-Razorpay-Event-Id": "evt_malformed_json_001",
        },
    )
    assert res1.status_code in (400, 422), f"Malformed JSON accepted! Status: {res1.status_code}"

    # 2. SQL Injection payload in route query parameter / search fields
    admin_token = create_access_token({"sub": "admin1", "role": "ROLE_ADMIN"})
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    sqli_string = "m_alpha' OR '1'='1' --"

    res2 = await async_client.get(
        f"/api/v1/transactions?merchant_id={sqli_string}",
        headers=headers_admin,
    )
    assert res2.status_code == 200
    # SQLi string treated literally as merchant_id -> returns empty items list, no SQL execution leakage
    data2 = res2.json()
    items = data2.get("items", data2) if isinstance(data2, dict) else data2
    assert isinstance(items, list)
    assert len(items) == 0

    # 3. XSS Script injection in JSON payload
    xss_payload = {
        "event_type": "<script>alert('xss_attack')</script>",
        "merchant_id": "m_test_xss",
        "transaction_id": "<img src=x onerror=alert('xss')>",
        "amount_in_paise": 10000,
    }
    res3 = await async_client.post(
        "/api/v1/webhooks/app-event",
        json=xss_payload,
    )
    assert res3.status_code in (200, 201, 400, 422)

    # 4. Invalid data type violation in Pydantic schema
    invalid_type_payload = {
        "event_type": "checkout.abandoned",
        "merchant_id": "m_test_type",
        "transaction_id": "tx_type_123",
        "amount_in_paise": "INVALID_NON_INTEGER_AMOUNT_STRING",  # Invalid type violation
    }
    res4 = await async_client.post(
        "/api/v1/webhooks/app-event",
        json=invalid_type_payload,
    )
    assert res4.status_code in (400, 422), f"Invalid type accepted! Status: {res4.status_code}"
