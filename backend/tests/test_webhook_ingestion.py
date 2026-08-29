"""
RecoverAI - Event Schema and Webhook Ingestion Test Suite (Step 5)

Tests HMAC-SHA256 signature verification, raw-body extraction, Pydantic schema validation,
authoritative X-Razorpay-Event-Id header ingestion, idempotency handling, event source isolation,
and security compliance.
"""

import hashlib
import hmac
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.models.domain import Event
from backend.app.services.event_ingestion import EventIngestionService, verify_razorpay_signature

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for testing."""
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
async def async_client(async_test_session: AsyncSession):
    """Async HTTP client for FastAPI endpoints with DB dependency override."""
    async def _override_get_db():
        yield async_test_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


def generate_valid_signature(raw_body: bytes, secret: str = settings.RAZORPAY_WEBHOOK_SECRET) -> str:
    """Helper function to generate valid HMAC-SHA256 signature for test payloads."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()


@pytest.fixture
def valid_razorpay_payload_bytes() -> bytes:
    """Fixture providing a valid Razorpay webhook JSON payload as bytes."""
    payload = {
        "entity": "event",
        "account_id": "acc_test_merchant_123",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_failure_111",
                    "amount": 150000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed due to insufficient funds",
                    "email": "customer@example.com",
                    "contact": "+919876543210",
                }
            }
        },
        "created_at": 1770000000,
    }
    return json.dumps(payload).encode("utf-8")


def test_1_verify_razorpay_signature_helper():
    """1. Verify standalone verify_razorpay_signature function logic."""
    raw_body = b'{"test":"data"}'
    secret = "my_secret_key"
    valid_sig = generate_valid_signature(raw_body, secret)

    assert verify_razorpay_signature(raw_body, valid_sig, secret) is True
    assert verify_razorpay_signature(raw_body, "invalid_sig", secret) is False
    assert verify_razorpay_signature(raw_body, None, secret) is False
    assert verify_razorpay_signature(b"", valid_sig, secret) is False


@pytest.mark.asyncio
async def test_2_valid_razorpay_webhook_ingestion(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """2. Verify valid Razorpay webhook with X-Razorpay-Event-Id is accepted and persisted."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)
    event_id = "evt_hdr_test_99999"

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["event_source"] == "RAZORPAY_WEBHOOK"
    assert data["event_type"] == "payment.failed"
    assert data["idempotency_key"] == f"razorpay:{event_id}"


@pytest.mark.asyncio
async def test_3_conflicting_body_field_cannot_override_header_event_id(async_client: AsyncClient):
    """3. Verify body fields cannot override authoritative X-Razorpay-Event-Id header."""
    body_with_fake_id = {
        "entity": "event",
        "account_id": "acc_123",
        "event": "payment.failed",
        "event_id": "evt_FAKE_BODY_ID_MALICIOUS",
        "payload": {"payment": {"entity": {"id": "pay_1", "amount": 100, "status": "failed"}}},
    }
    raw_bytes = json.dumps(body_with_fake_id).encode("utf-8")
    signature = generate_valid_signature(raw_bytes)
    header_event_id = "evt_AUTHORITATIVE_HEADER_ID_123"

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": header_event_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["idempotency_key"] == f"razorpay:{header_event_id}"
    assert "evt_FAKE_BODY_ID_MALICIOUS" not in data["idempotency_key"]


@pytest.mark.asyncio
async def test_4_invalid_razorpay_signature_rejected(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """4. Verify invalid signature returns HTTP 401 Unauthorized."""
    invalid_signature = "a" * 64

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": invalid_signature,
            "X-Razorpay-Event-Id": "evt_test_123",
        },
    )

    assert response.status_code == 401
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_5_missing_signature_header_rejected(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """5. Verify missing X-Razorpay-Signature header returns HTTP 401 Unauthorized."""
    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_6_missing_event_id_header_fallback(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """6. Verify missing X-Razorpay-Event-Id header falls back safely to body-hash idempotency key."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["idempotency_key"].startswith("razorpay:payment.failed:")


@pytest.mark.asyncio
async def test_7_idempotency_duplicate_event_id_handling(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """7. Verify re-submitting duplicate X-Razorpay-Event-Id returns DUPLICATE_SKIPPED without 500 error."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)
    event_id = "evt_duplicate_header_test_001"

    # First submission
    res1 = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "SUCCESS"

    # Second submission of exact same X-Razorpay-Event-Id
    res2 = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id,
        },
    )

    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] == "DUPLICATE_SKIPPED"
    assert "already ingested" in data["message"]


@pytest.mark.asyncio
async def test_8_app_event_ingestion(async_client: AsyncClient):
    """8. Verify application event endpoint ingests checkout abandonment event."""
    payload = {
        "event_type": "checkout.abandoned",
        "merchant_id": "m_test_merchant_001",
        "customer_id": "c_test_customer_002",
        "amount_in_paise": 250000,
        "currency": "INR",
        "metadata": {"device": "mobile_android"},
    }

    response = await async_client.post("/api/v1/webhooks/app-event", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["event_source"] == "APP_EVENT"
    assert data["event_type"] == "checkout.abandoned"


@pytest.mark.asyncio
async def test_9_simulator_event_ingestion(async_client: AsyncClient):
    """9. Verify simulator event endpoint ingests synthetic batch event."""
    payload = {
        "event_type": "simulator.transaction_event",
        "transaction_id": "tx_sim_test_001",
        "scenario": "SUBSCRIPTION_FAILURE",
        "amount_in_paise": 49900,
        "payload_data": {"test_run_id": "eval_001"},
    }

    response = await async_client.post("/api/v1/webhooks/simulator-event", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["event_source"] == "SIMULATOR"
    assert data["event_type"] == "simulator.transaction_event"


@pytest.mark.asyncio
async def test_10_schema_validation_rejects_missing_fields(async_client: AsyncClient):
    """10. Verify Pydantic schema rejects invalid/incomplete app event payload with 422."""
    incomplete_payload = {
        "event_type": "checkout.abandoned",
        # Missing merchant_id and amount_in_paise
    }

    response = await async_client.post("/api/v1/webhooks/app-event", json=incomplete_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_11_security_secret_isolation(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """11. Verify webhook secret is never returned in API responses."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": "evt_sec_test_001",
        },
    )

    response_text = response.text
    assert settings.RAZORPAY_WEBHOOK_SECRET not in response_text
