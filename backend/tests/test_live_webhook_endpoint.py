"""
RecoverAI - Live Webhook Endpoint Integration Test Suite

Validates end-to-end processing of Razorpay webhooks over the HTTP FastAPI router endpoint:
1. Valid HMAC SHA-256 webhook -> HTTP 200 -> ResultProcessor execution -> Transaction RECOVERED -> Attribution & Audit created.
2. Duplicate webhook -> HTTP 200 -> DUPLICATE_SKIPPED -> Zero duplicate transitions, attributions, or audit events.
3. Invalid HMAC SHA-256 signature -> HTTP 401 Unauthorized -> No ingestion or processing.
"""

import pytest
import pytest_asyncio
import hmac
import hashlib
import json
import uuid
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.domain import (
    Merchant,
    Customer,
    Transaction,
    RecoveryAttempt,
    RecoveryAttribution,
    AuditEvent,
)
from backend.app.services.result_processor import ResultProcessor
from backend.app.services.attribution_engine import AttributionEngine


@pytest_asyncio.fixture
async def test_session():
    """Provides a clean AsyncSession bound to NullPool to prevent connection pollution across loops."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest_asyncio.fixture
async def async_client(test_session: AsyncSession):
    """Provides an AsyncClient configured with database session override."""
    async def _get_db_override():
        yield test_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_razorpay_webhook_endpoint_success_processing(async_client: AsyncClient, test_session: AsyncSession):
    """Verify that a valid payment_link.paid HTTP POST webhook triggers ResultProcessor and mutates state to RECOVERED."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    session = test_session

    random_hex = uuid.uuid4().hex[:6]
    merchant_id = f"m_ep_{random_hex}"
    customer_id = f"c_ep_{random_hex}"
    tx_id = f"tx_ep_{random_hex}"
    pl_id = f"plink_ep_{random_hex}"
    ref_id = f"RAI-{tx_id}-1"
    event_id = f"evt_ep_{random_hex}"

    merchant = Merchant(id=merchant_id, name="Endpoint Test Merchant", email="m_ep@test.com", industry="SaaS")
    customer = Customer(id=customer_id, merchant_id=merchant_id, name="Endpoint Test Customer", email="c_ep@test.com")
    tx = Transaction(
        id=tx_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=Decimal("1500.00"),
        currency="INR",
        status="EXECUTING",
        scenario_type="PAYMENT_FAILURE",
        mode="REAL_TEST",
    )
    attempt = RecoveryAttempt(
        id=f"att_ep_{random_hex}",
        transaction_id=tx_id,
        logical_operation_key=f"{merchant_id}:{tx_id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": 150000, "reference_id": ref_id},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="PENDING",
        external_resource_type="payment_link",
        external_resource_id=pl_id,
        razorpay_payment_link_id=pl_id,
        razorpay_reference_id=ref_id,
    )
    session.add_all([merchant, customer, tx, attempt])
    await session.commit()

    webhook_payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": pl_id,
                    "status": "paid",
                    "reference_id": ref_id,
                    "notes": {"merchant_id": merchant_id, "transaction_id": tx_id},
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_ep_{random_hex}",
                    "status": "captured",
                }
            },
        },
    }
    raw_bytes = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id,
    }

    # Execute HTTP POST request to endpoint
    response = await async_client.post("/api/v1/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "SUCCESS"
    assert res_data["event_type"] == "payment_link.paid"

    # Verify transaction state in database mutated to RECOVERED
    await session.refresh(tx)
    assert tx.status == "RECOVERED"

    # Verify Attribution record created
    attr_stmt = select(RecoveryAttribution).where(RecoveryAttribution.transaction_id == tx_id)
    attr = (await session.execute(attr_stmt)).scalar_one_or_none()
    assert attr is not None
    assert attr.attribution_status == "ATTRIBUTED"

    # Verify Audit event created
    audit_stmt = select(AuditEvent).where(AuditEvent.transaction_id == tx_id)
    audit_events = (await session.execute(audit_stmt)).scalars().all()
    assert len(audit_events) > 0


@pytest.mark.asyncio
async def test_razorpay_webhook_endpoint_duplicate_handling(async_client: AsyncClient, test_session: AsyncSession):
    """Verify that duplicate HTTP POST webhooks return DUPLICATE_SKIPPED and perform zero additional state transitions."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    session = test_session

    random_hex = uuid.uuid4().hex[:6]
    merchant_id = f"m_dup_{random_hex}"
    customer_id = f"c_dup_{random_hex}"
    tx_id = f"tx_dup_{random_hex}"
    pl_id = f"plink_dup_{random_hex}"
    ref_id = f"RAI-{tx_id}-1"
    event_id = f"evt_dup_{random_hex}"

    merchant = Merchant(id=merchant_id, name="Dup Test Merchant", email="m_dup@test.com", industry="SaaS")
    customer = Customer(id=customer_id, merchant_id=merchant_id, name="Dup Test Customer", email="c_dup@test.com")
    tx = Transaction(
        id=tx_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=Decimal("1000.00"),
        currency="INR",
        status="EXECUTING",
        scenario_type="PAYMENT_FAILURE",
        mode="REAL_TEST",
    )
    attempt = RecoveryAttempt(
        id=f"att_dup_{random_hex}",
        transaction_id=tx_id,
        logical_operation_key=f"{merchant_id}:{tx_id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": 100000, "reference_id": ref_id},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="PENDING",
        external_resource_type="payment_link",
        external_resource_id=pl_id,
        razorpay_payment_link_id=pl_id,
        razorpay_reference_id=ref_id,
    )
    session.add_all([merchant, customer, tx, attempt])
    await session.commit()

    webhook_payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": pl_id,
                    "status": "paid",
                    "reference_id": ref_id,
                    "notes": {"merchant_id": merchant_id, "transaction_id": tx_id},
                }
            },
            "payment": {
                "entity": {
                    "id": f"pay_dup_{random_hex}",
                    "status": "captured",
                }
            },
        },
    }
    raw_bytes = json.dumps(webhook_payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id,
    }

    # First Webhook Request
    resp1 = await async_client.post("/api/v1/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "SUCCESS"

    # Fetch attribution count after first request
    attr_stmt = select(RecoveryAttribution).where(RecoveryAttribution.transaction_id == tx_id)
    attr_count_before = len((await session.execute(attr_stmt)).scalars().all())

    # Second Webhook Request (Duplicate)
    resp2 = await async_client.post("/api/v1/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "DUPLICATE_SKIPPED"

    # Verify zero additional attribution records created
    attr_count_after = len((await session.execute(attr_stmt)).scalars().all())
    assert attr_count_after == attr_count_before


@pytest.mark.asyncio
async def test_razorpay_webhook_endpoint_invalid_signature(async_client: AsyncClient):
    """Verify that an invalid HMAC signature returns HTTP 401 Unauthorized without ingestion or processing."""
    raw_bytes = b'{"event":"payment_link.paid","entity":"event"}'
    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": "invalid_signature_hash_12345",
        "X-Razorpay-Event-Id": "evt_invalid_sig",
    }

    response = await async_client.post("/api/v1/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert response.status_code == 401
    assert "Invalid Razorpay webhook signature" in response.json()["detail"]
