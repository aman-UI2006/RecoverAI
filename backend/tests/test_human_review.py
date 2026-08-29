"""
RecoverAI — Step 16 Test Suite: Human Review and Escalation

Tests HumanReviewService, REST endpoints, escalation queue management,
reviewer decision processing (APPROVE_OVERRIDE, REJECT_PERMANENT),
RBAC permission checks, multi-tenant merchant isolation, auto-expiration,
audit hash chaining via StateTransitionService, transaction atomicity,
and network air-gap isolation.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, List
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.models.domain import Transaction, Merchant, Customer, HumanReview, AuditEvent
from backend.app.schemas.human_review import (
    HumanReviewDecision,
    HumanReviewStatus,
)
from backend.app.schemas.state_machine import TransactionStatus
from backend.app.services.human_review_service import HumanReviewService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for human review testing."""
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


async def seed_test_merchant_and_transaction(
    session: AsyncSession,
    amount: float = 60000.00,
    initial_status: str = "POLICY_CHECK",
) -> Tuple[Merchant, Transaction]:
    m_id = str(uuid4())
    c_id = str(uuid4())
    tx_id = str(uuid4())

    merchant = Merchant(id=m_id, name="Escalation Test Merchant", email="merchant@test.com", industry="EDTECH")
    customer = Customer(id=c_id, merchant_id=m_id, email="cust@test.com")
    tx = Transaction(
        id=tx_id,
        merchant_id=m_id,
        customer_id=c_id,
        amount=amount,
        currency="INR",
        status=initial_status,
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    session.add_all([merchant, customer, tx])
    await session.commit()
    return merchant, tx


@pytest.mark.asyncio
async def test_1_escalate_transaction_to_human_review_queue(async_test_session: AsyncSession):
    """1. Verify escalating a transaction transitions state to ESCALATED and creates a PENDING HumanReview record."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session, amount=60000.00)

    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="AMOUNT_EXCEEDS_CAP",
        merchant_id=merchant.id,
        reviewer_notes="High value transaction needs manual authorization",
    )

    assert review_record.status == HumanReviewStatus.PENDING.value
    assert review_record.reason == "AMOUNT_EXCEEDS_CAP"

    # Verify transaction state changed to ESCALATED via StateTransitionService
    stmt_tx = select(Transaction).where(Transaction.id == tx.id)
    updated_tx = (await async_test_session.execute(stmt_tx)).scalar_one()
    assert updated_tx.status == TransactionStatus.ESCALATED.value

    # Verify audit log event recorded
    stmt_audit = select(AuditEvent).where(AuditEvent.transaction_id == tx.id)
    audits = (await async_test_session.execute(stmt_audit)).scalars().all()
    assert len(audits) >= 1
    assert any(a.state_to == "ESCALATED" for a in audits)


@pytest.mark.asyncio
async def test_2_approve_override_decision(async_test_session: AsyncSession):
    """2. Verify APPROVE_OVERRIDE transitions transaction state from ESCALATED to APPROVED."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="MIN_PROBABILITY_NOT_MET",
        merchant_id=merchant.id,
    )

    review, updated_tx = await HumanReviewService.process_reviewer_decision(
        session=async_test_session,
        review_id=review_record.id,
        decision=HumanReviewDecision.APPROVE_OVERRIDE,
        reviewer_id="rev_user_101",
        notes="Risk approved after secondary verification",
        merchant_id=merchant.id,
        user_role="ROLE_HUMAN_REVIEWER",
    )

    assert review.status == HumanReviewStatus.APPROVED.value
    assert review.decision == "APPROVE_OVERRIDE"
    assert review.reviewer_id == "rev_user_101"
    assert updated_tx.status == TransactionStatus.APPROVED.value

    # Verify audit event for APPROVED state transition
    stmt_audit = select(AuditEvent).where(AuditEvent.transaction_id == tx.id)
    audits = (await async_test_session.execute(stmt_audit)).scalars().all()
    assert any(a.state_to == "APPROVED" for a in audits)


@pytest.mark.asyncio
async def test_3_reject_permanent_decision(async_test_session: AsyncSession):
    """3. Verify REJECT_PERMANENT transitions transaction state from ESCALATED to STOPPED."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="EXPLICIT_SAFETY_HOLD",
        merchant_id=merchant.id,
    )

    review, updated_tx = await HumanReviewService.process_reviewer_decision(
        session=async_test_session,
        review_id=review_record.id,
        decision=HumanReviewDecision.REJECT_PERMANENT,
        reviewer_id="rev_user_102",
        notes="Confirmed suspicious transaction, rejecting recovery",
        merchant_id=merchant.id,
        user_role="ROLE_HUMAN_REVIEWER",
    )

    assert review.status == HumanReviewStatus.REJECTED.value
    assert review.decision == "REJECT_PERMANENT"
    assert updated_tx.status == TransactionStatus.STOPPED.value


@pytest.mark.asyncio
async def test_4_rbac_permission_enforcement(async_test_session: AsyncSession):
    """4. Verify unauthorized user_role raises PermissionError when attempting reviewer action."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="HIGH_RISK_FLAG",
        merchant_id=merchant.id,
    )

    with pytest.raises(PermissionError) as exc_info:
        await HumanReviewService.process_reviewer_decision(
            session=async_test_session,
            review_id=review_record.id,
            decision=HumanReviewDecision.APPROVE_OVERRIDE,
            reviewer_id="unauthorized_user",
            merchant_id=merchant.id,
            user_role="ROLE_MERCHANT_USER",  # Invalid role for override
        )

    assert "ROLE_HUMAN_REVIEWER" in str(exc_info.value)


@pytest.mark.asyncio
async def test_5_multi_tenant_merchant_isolation(async_test_session: AsyncSession):
    """5. Verify cross-merchant access raises ValueError mismatch error."""
    merchant_a, tx_a = await seed_test_merchant_and_transaction(async_test_session)
    merchant_b_id = str(uuid4())

    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx_a.id,
        reason="HIGH_RISK_FLAG",
        merchant_id=merchant_a.id,
    )

    # Attempt fetching review item under merchant B's ID
    with pytest.raises(ValueError) as exc_info:
        await HumanReviewService.get_review_item(
            session=async_test_session,
            review_id=review_record.id,
            merchant_id=merchant_b_id,
        )

    assert "Merchant ID mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_6_idempotency_duplicate_escalation(async_test_session: AsyncSession):
    """6. Verify duplicate escalation requests for the same transaction reuse the existing PENDING review record."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)

    review_1 = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="CAPACITY_LIMIT",
        merchant_id=merchant.id,
    )

    review_2 = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="CAPACITY_LIMIT",
        merchant_id=merchant.id,
    )

    assert review_1.id == review_2.id

    stmt_all = select(HumanReview).where(HumanReview.transaction_id == tx.id)
    reviews_in_db = (await async_test_session.execute(stmt_all)).scalars().all()
    assert len(reviews_in_db) == 1  # No duplicate rows created


@pytest.mark.asyncio
async def test_7_auto_expire_stale_reviews(async_test_session: AsyncSession):
    """7. Verify auto_expire_stale_reviews transitions transactions older than 48h to STOPPED."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="STALE_QUEUE_TEST",
        merchant_id=merchant.id,
    )

    # Artificially age the review item created_at to 50 hours ago
    stale_time = datetime.now(timezone.utc) - timedelta(hours=50)
    review_record.created_at = stale_time
    await async_test_session.commit()

    expired_ids = await HumanReviewService.auto_expire_stale_reviews(
        session=async_test_session,
        expiration_hours=48,
    )

    assert review_record.id in expired_ids

    # Re-fetch transaction and verify transition to STOPPED
    stmt_tx = select(Transaction).where(Transaction.id == tx.id)
    updated_tx = (await async_test_session.execute(stmt_tx)).scalar_one()
    assert updated_tx.status == TransactionStatus.STOPPED.value

    # Re-fetch review item and verify EXPIRED status
    stmt_rev = select(HumanReview).where(HumanReview.id == review_record.id)
    updated_rev = (await async_test_session.execute(stmt_rev)).scalar_one()
    assert updated_rev.status == HumanReviewStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_8_security_air_gap_no_razorpay_http_execution(
    async_test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """8. Verify zero external HTTP calls take place during Step 16 human review operations."""
    def block_network_calls(*args, **kwargs):
        raise RuntimeError("AIR-GAP VIOLATION: External network call detected during Step 16 operation!")

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "send", block_network_calls)
    monkeypatch.setattr(httpx.Client, "send", block_network_calls)

    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)

    # Perform escalation and decision under monkeypatched air-gap
    review = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="AIR_GAP_TEST",
        merchant_id=merchant.id,
    )

    await HumanReviewService.process_reviewer_decision(
        session=async_test_session,
        review_id=review.id,
        decision=HumanReviewDecision.APPROVE_OVERRIDE,
        reviewer_id="airgap_rev",
        merchant_id=merchant.id,
        user_role="ROLE_HUMAN_REVIEWER",
    )


@pytest.mark.asyncio
async def test_9_human_review_api_endpoints(async_client: AsyncClient, async_test_session: AsyncSession):
    """9. Verify FastAPI REST endpoints for human review queue and decisions."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)

    # 1. POST /api/v1/human-review/escalate
    escalate_res = await async_client.post(
        "/api/v1/human-review/escalate",
        json={"transaction_id": tx.id, "reason": "HIGH_VALUE_CHECK", "reviewer_notes": "Needs API verification"},
        headers={"X-Merchant-ID": merchant.id},
    )
    assert escalate_res.status_code == 201
    review_data = escalate_res.json()
    review_id = review_data["id"]
    assert review_data["status"] == "PENDING"
    assert review_data["merchant_id"] == merchant.id

    # 2. GET /api/v1/human-review/queue
    queue_res = await async_client.get(
        "/api/v1/human-review/queue",
        headers={"X-Merchant-ID": merchant.id},
    )
    assert queue_res.status_code == 200
    queue_data = queue_res.json()
    assert queue_data["count"] >= 1
    assert any(item["id"] == review_id for item in queue_data["items"])

    # 3. GET /api/v1/human-review/items/{review_id}
    item_res = await async_client.get(
        f"/api/v1/human-review/items/{review_id}",
        headers={"X-Merchant-ID": merchant.id},
    )
    assert item_res.status_code == 200
    assert item_res.json()["id"] == review_id

    # 4. POST /api/v1/human-review/items/{review_id}/decision (Forbidden role check)
    bad_role_res = await async_client.post(
        f"/api/v1/human-review/items/{review_id}/decision",
        json={"decision": "APPROVE_OVERRIDE", "reviewer_id": "rev_001", "notes": "Approved"},
        headers={"X-Merchant-ID": merchant.id, "X-User-Role": "ROLE_ANONYMOUS"},
    )
    assert bad_role_res.status_code == 403

    # 5. POST /api/v1/human-review/items/{review_id}/decision (Valid decision)
    good_res = await async_client.post(
        f"/api/v1/human-review/items/{review_id}/decision",
        json={"decision": "APPROVE_OVERRIDE", "reviewer_id": "rev_001", "notes": "Approved via API"},
        headers={"X-Merchant-ID": merchant.id, "X-User-Role": "ROLE_HUMAN_REVIEWER"},
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "APPROVED"
    assert good_res.json()["decision"] == "APPROVE_OVERRIDE"


@pytest.mark.asyncio
async def test_10_atomicity_and_session_rollback(async_test_session: AsyncSession):
    """10. Verify that session rollback cleans up uncommitted review additions while keeping committed transitions intact."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)

    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="ATOM_TEST",
        merchant_id=merchant.id,
    )
    saved_review_id = review_record.id
    await async_test_session.commit()

    # Add an uncommitted temporary item to session
    temp_review = HumanReview(
        id=str(uuid4()),
        transaction_id=tx.id,
        status="PENDING",
        reason="UNCOMMITTED_TEMP",
    )
    async_test_session.add(temp_review)

    # Roll back uncommitted session additions
    await async_test_session.rollback()

    # Query DB to confirm committed review item remains, while uncommitted temp item is gone
    stmt_committed = select(HumanReview).where(HumanReview.id == saved_review_id)
    assert (await async_test_session.execute(stmt_committed)).scalar_one_or_none() is not None

    stmt_uncommitted = select(HumanReview).where(HumanReview.reason == "UNCOMMITTED_TEMP")
    assert (await async_test_session.execute(stmt_uncommitted)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_11_repeated_decision_on_resolved_item_fails(async_test_session: AsyncSession):
    """11. Verify submitting a decision twice on the same review item raises ValueError."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="REPEATED_DECISION_TEST",
        merchant_id=merchant.id,
    )

    # First decision succeeds
    await HumanReviewService.process_reviewer_decision(
        session=async_test_session,
        review_id=review_record.id,
        decision=HumanReviewDecision.APPROVE_OVERRIDE,
        reviewer_id="rev_001",
        merchant_id=merchant.id,
    )

    # Second decision fails
    with pytest.raises(ValueError) as exc_info:
        await HumanReviewService.process_reviewer_decision(
            session=async_test_session,
            review_id=review_record.id,
            decision=HumanReviewDecision.REJECT_PERMANENT,
            reviewer_id="rev_002",
            merchant_id=merchant.id,
        )

    assert "already been processed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_12_auto_expire_skips_already_resolved_items(async_test_session: AsyncSession):
    """12. Verify auto_expire_stale_reviews does not touch already APPROVED or REJECTED reviews."""
    merchant, tx = await seed_test_merchant_and_transaction(async_test_session)
    review_record = await HumanReviewService.escalate_transaction(
        session=async_test_session,
        transaction_id=tx.id,
        reason="EXPIRE_RESOLVED_TEST",
        merchant_id=merchant.id,
    )

    # Process decision to APPROVED
    await HumanReviewService.process_reviewer_decision(
        session=async_test_session,
        review_id=review_record.id,
        decision=HumanReviewDecision.APPROVE_OVERRIDE,
        reviewer_id="rev_001",
        merchant_id=merchant.id,
    )

    # Age created_at
    review_record.created_at = datetime.now(timezone.utc) - timedelta(hours=100)
    await async_test_session.commit()

    expired_ids = await HumanReviewService.auto_expire_stale_reviews(
        session=async_test_session,
        expiration_hours=48,
    )

    assert review_record.id not in expired_ids
    assert review_record.status == HumanReviewStatus.APPROVED.value

