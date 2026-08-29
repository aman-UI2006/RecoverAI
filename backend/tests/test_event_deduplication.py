"""
RecoverAI - Step 6 Event Normalization and Deduplication Test Suite

Tests canonical event mapping across Razorpay, App, and Simulator events,
PostgreSQL ACID boundary deduplication, and Redis fast-path caching fallback behavior.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.models.domain import Event
from backend.app.schemas.canonical_event import NormalizedEvent
from backend.app.services.event_normalizer import EventNormalizerService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Isolated in-memory DB session for deduplication testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def test_1_normalize_razorpay_webhook_event():
    """1. Test normalization of Razorpay payment.failed webhook event."""
    raw_event = Event(
        id="evt_uuid_101",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_hdr_999",
        razorpay_event_id="evt_hdr_999",
        payload={
            "account_id": "acc_merchant_888",
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_001",
                        "amount": 150000,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": "order_test_777",
                    }
                }
            },
        },
        created_at=datetime.now(timezone.utc),
    )

    norm: NormalizedEvent = EventNormalizerService.normalize(raw_event)

    assert norm.raw_event_id == "evt_uuid_101"
    assert norm.event_source == "RAZORPAY_WEBHOOK"
    assert norm.event_type == "PAYMENT_FAILED"
    assert norm.merchant_id == "acc_merchant_888"
    assert norm.transaction_id == "order_test_777"
    assert norm.amount_in_paise == 150000
    assert norm.scenario == "PAYMENT_FAILURE"
    assert norm.is_duplicate is False


def test_2_normalize_app_event():
    """2. Test normalization of application checkout abandonment event."""
    raw_event = Event(
        id="evt_uuid_102",
        event_type="checkout.abandoned",
        event_source="APP_EVENT",
        idempotency_key="app:c_cust_001:1770000000",
        payload={
            "event_type": "checkout.abandoned",
            "merchant_id": "m_merchant_001",
            "customer_id": "c_cust_001",
            "transaction_id": "tx_checkout_999",
            "amount_in_paise": 250000,
            "currency": "INR",
        },
        created_at=datetime.now(timezone.utc),
    )

    norm = EventNormalizerService.normalize(raw_event)

    assert norm.event_source == "APP_EVENT"
    assert norm.event_type == "CHECKOUT_ABANDONED"
    assert norm.merchant_id == "m_merchant_001"
    assert norm.customer_id == "c_cust_001"
    assert norm.transaction_id == "tx_checkout_999"
    assert norm.amount_in_paise == 250000
    assert norm.scenario == "CHECKOUT_ABANDONMENT"


def test_3_normalize_simulator_event():
    """3. Test normalization of simulator batch event."""
    raw_event = Event(
        id="evt_uuid_103",
        event_type="simulator.transaction_event",
        event_source="SIMULATOR",
        idempotency_key="sim:tx_sim_111",
        payload={
            "event_type": "simulator.transaction_event",
            "transaction_id": "tx_sim_111",
            "scenario": "SUBSCRIPTION_FAILURE",
            "amount_in_paise": 49900,
        },
        created_at=datetime.now(timezone.utc),
    )

    norm = EventNormalizerService.normalize(raw_event)

    assert norm.event_source == "SIMULATOR"
    assert norm.event_type == "SIMULATOR_TRANSACTION_EVENT"
    assert norm.transaction_id == "tx_sim_111"
    assert norm.scenario == "SUBSCRIPTION_FAILURE"
    assert norm.amount_in_paise == 49900


@pytest.mark.asyncio
async def test_4_postgresql_boundary_deduplication(db_session: AsyncSession):
    """4. Test PostgreSQL ACID boundary correctly flags duplicate idempotency key."""
    ev1 = Event(
        id="evt_first_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_dup_100",
        razorpay_event_id="evt_dup_100",
        payload={"event": "payment.failed", "payload": {}},
    )
    db_session.add(ev1)
    await db_session.commit()

    # Second event instance in memory with same idempotency key
    ev2 = Event(
        id="evt_second_002",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_dup_100",
        razorpay_event_id="evt_dup_100",
        payload={"event": "payment.failed", "payload": {}},
    )

    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=db_session,
        event=ev2,
        redis_client=None,
    )

    assert is_duplicate is True
    assert norm.is_duplicate is True


@pytest.mark.asyncio
async def test_5_redis_fast_path_deduplication(db_session: AsyncSession):
    """5. Test Redis fast-path deduplication when redis_client returns already_seen=True."""
    ev = Event(
        id="evt_redis_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_redis_key_555",
        razorpay_event_id="evt_redis_key_555",
        payload={"event": "payment.failed", "payload": {}},
    )

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = True

    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=db_session,
        event=ev,
        redis_client=mock_redis,
    )

    assert is_duplicate is True
    assert norm.is_duplicate is True
    mock_redis.exists.assert_called_once_with("dedup:razorpay_webhook:evt_redis_key_555")


@pytest.mark.asyncio
async def test_6_redis_failure_falls_back_to_postgresql(db_session: AsyncSession):
    """6. Test Redis connection exception safely falls back to PostgreSQL correctness boundary without crashing."""
    ev = Event(
        id="evt_fallback_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_fallback_key_777",
        razorpay_event_id="evt_fallback_key_777",
        payload={"event": "payment.failed", "payload": {}},
    )

    mock_redis = AsyncMock()
    mock_redis.exists.side_effect = Exception("Redis connection refused")

    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=db_session,
        event=ev,
        redis_client=mock_redis,
    )

    # Should fall back to PostgreSQL check (which finds no duplicate) and succeed safely
    assert is_duplicate is False
    assert norm.is_duplicate is False
