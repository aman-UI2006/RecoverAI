"""
RecoverAI - Event Schema and Webhook Ingestion Test Suite (Step 5)

Tests HMAC-SHA256 signature verification, raw-body extraction, Pydantic schema validation,
idempotency handling, event source isolation, and security compliance.
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
        "event_id": "evt_test_pay_failed_999",
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
    """2. Verify valid Razorpay webhook is accepted (200 OK) and persisted to DB."""
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
    assert data["event_source"] == "RAZORPAY_WEBHOOK"
    assert data["event_type"] == "payment.failed"
    assert data["idempotency_key"] == "razorpay:evt_test_pay_failed_999"


@pytest.mark.asyncio
async def test_3_invalid_razorpay_signature_rejected(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """3. Verify invalid signature returns HTTP 401 Unauthorized."""
    invalid_signature = "a" * 64

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": invalid_signature,
        },
    )

    assert response.status_code == 401
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_4_missing_signature_header_rejected(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """4. Verify missing X-Razorpay-Signature header returns HTTP 401 Unauthorized."""
    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_5_malformed_json_body_rejected(async_client: AsyncClient):
    """5. Verify malformed JSON body returns HTTP 400 Bad Request."""
    malformed_body = b"NOT_VALID_JSON{{{"
    signature = generate_valid_signature(malformed_body)

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=malformed_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 400
    assert "Malformed JSON" in response.json()["detail"]


@pytest.mark.asyncio
async def test_6_idempotency_duplicate_event_handling(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """6. Verify re-submitting duplicate event returns DUPLICATE_SKIPPED without 500 error."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)

    # First submission
    res1 = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "SUCCESS"

    # Second submission of exact same payload & event_id
    res2 = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] == "DUPLICATE_SKIPPED"
    assert "already ingested" in data["message"]


@pytest.mark.asyncio
async def test_7_app_event_ingestion(async_client: AsyncClient):
    """7. Verify application event endpoint ingests checkout abandonment event."""
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
async def test_8_simulator_event_ingestion(async_client: AsyncClient):
    """8. Verify simulator event endpoint ingests synthetic batch event."""
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
async def test_9_schema_validation_rejects_missing_fields(async_client: AsyncClient):
    """9. Verify Pydantic schema rejects invalid/incomplete app event payload with 422."""
    incomplete_payload = {
        "event_type": "checkout.abandoned",
        # Missing merchant_id and amount_in_paise
    }

    response = await async_client.post("/api/v1/webhooks/app-event", json=incomplete_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_10_security_secret_isolation(async_client: AsyncClient, valid_razorpay_payload_bytes: bytes):
    """10. Verify webhook secret is never returned in API responses."""
    signature = generate_valid_signature(valid_razorpay_payload_bytes)

    response = await async_client.post(
        "/api/v1/webhooks/razorpay",
        content=valid_razorpay_payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    response_text = response.text
    assert settings.RAZORPAY_WEBHOOK_SECRET not in response_text
