"""
RecoverAI - Step 53 Focused Tests (Razorpay Integration & Test Mode Verification)

Validates the full Razorpay integration verification pipeline:
1. Creation of Payment Link via RazorpayAdapter (SIMULATION/REAL_TEST fallback).
2. HMAC SHA-256 signature calculation & verification.
3. Webhook ingestion, ResultProcessor execution, and transition to RECOVERED.
4. Attribution verification under Step 53 test script workflow.
"""

import pytest
import pytest_asyncio
import asyncio
from decimal import Decimal
import hmac
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings
from backend.app.integrations.razorpay_adapter import RazorpayAdapter
from backend.app.models.domain import (
    Merchant,
    Customer,
    Transaction,
    RecoveryAttempt,
    RecoveryAttribution,
)
from backend.app.schemas.events import AppEventPayload
from backend.app.schemas.razorpay_dto import PaymentLinkCreateRequest
from backend.app.services.event_ingestion import EventIngestionService
from backend.app.services.result_processor import ResultProcessor
from backend.app.services.attribution_engine import AttributionEngine
from scripts.verify_razorpay_live_test import execute_razorpay_live_test_verification


@pytest_asyncio.fixture
async def isolated_session():
    """Provides a fresh AsyncSession bound to a NullPool engine to prevent event loop connection pollution."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_step53_hmac_signature_validation():
    """Verify RazorpayAdapter HMAC SHA-256 signature verification helper."""
    secret = "test_webhook_secret_xyz"
    raw_body = b'{"event":"payment_link.paid","entity":"event"}'
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    assert RazorpayAdapter.verify_webhook_signature(raw_body, valid_sig, secret) is True
    assert RazorpayAdapter.verify_webhook_signature(raw_body, "invalid_signature", secret) is False


@pytest.mark.asyncio
async def test_step53_script_execution_success(isolated_session):
    """Verify that execute_razorpay_live_test_verification passes end-to-end with an isolated session."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    success = await execute_razorpay_live_test_verification(mode="SIMULATION", session=isolated_session)
    assert success is True


@pytest.mark.asyncio
async def test_step53_end_to_end_state_mutation_and_attribution(isolated_session):
    """Verify step-by-step state mutation and attribution generation for Razorpay webhook ingestion."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    session = isolated_session
    random_hex = uuid.uuid4().hex[:6]
    merchant_id = f"m53_{random_hex}"
    customer_id = f"c53_{random_hex}"
    tx_id = f"t53_{random_hex}"

    merchant = Merchant(id=merchant_id, name="Test M53", email="m53@test.com", industry="Ecom")
    customer = Customer(id=customer_id, merchant_id=merchant_id, name="C53 Test", email="c53@test.com")
    tx = Transaction(
        id=tx_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=Decimal("2000.00"),
        currency="INR",
        status="EXECUTING",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    session.add_all([merchant, customer, tx])
    await session.commit()

    ref_id = f"RAI-{tx_id}-1"
    adapter = RazorpayAdapter()
    pl_req = PaymentLinkCreateRequest(
        amount=200000,
        currency="INR",
        description="Step 53 Test Link",
        reference_id=ref_id,
        notes={"merchant_id": merchant_id, "transaction_id": tx_id},
    )
    pl_resp = await adapter.create_payment_link(pl_req, mode="SIMULATION")
    pl_id = pl_resp.id

    attempt = RecoveryAttempt(
        id=f"att53_{random_hex}",
        transaction_id=tx_id,
        logical_operation_key=f"{merchant_id}:{tx_id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": 200000, "reference_id": ref_id},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="PENDING",
        external_resource_type="payment_link",
        external_resource_id=pl_id,
        razorpay_payment_link_id=pl_id,
        razorpay_reference_id=ref_id,
    )
    session.add(attempt)
    await session.commit()

    wh_dict = {
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
                    "id": f"pay_{random_hex}",
                    "status": "captured",
                }
            },
        },
    }
    raw_bytes = json.dumps(wh_dict, separators=(",", ":")).encode("utf-8")
    wh_secret = "secret_53"
    sig = hmac.new(wh_secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    wh_event, _ = await EventIngestionService.ingest_razorpay_webhook(
        session=session,
        raw_body=raw_bytes,
        signature_header=sig,
        razorpay_event_id=f"evt_{random_hex}",
        webhook_secret=wh_secret,
    )

    result = await ResultProcessor.process_event(session=session, event=wh_event)
    assert result["status"] == "SUCCESS_RECOVERED"
    assert result["transaction_status"] == "RECOVERED"

    await session.refresh(tx)
    assert tx.status == "RECOVERED"

    attr_stmt = select(RecoveryAttribution).where(RecoveryAttribution.transaction_id == tx_id)
    attr_res = await session.execute(attr_stmt)
    attr_rec = attr_res.scalar_one_or_none()
    assert attr_rec is not None
    assert attr_rec.attribution_status == "ATTRIBUTED"
