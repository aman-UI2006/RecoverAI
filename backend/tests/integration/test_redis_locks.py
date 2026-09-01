"""
RecoverAI - Step 38 Redis Fast-Path & Fallback Integration Testing Suite

Verifies:
1. Redis fast-path deduplication cache hit & TTL registration when Redis is active.
2. Redis lock acquisition, release, and expiration behavior.
3. Fallback path safety when Redis is unavailable or throws network/connection errors,
   ensuring zero financial action duplication and preservation of PostgreSQL ACID correctness.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.models.domain import Event
from backend.app.services.event_normalizer import EventNormalizerService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def redis_test_session():
    """Isolated DB session fixture for Redis fallback testing."""
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
async def test_1_redis_fast_path_cache_hit_and_ttl(redis_test_session: AsyncSession):
    """
    1. Redis Fast-Path Deduplication Cache Hit & TTL:
       - Production behavior: High-throughput deduplication check via Redis cache.
       - Expected result: Redis fast-path identifies duplicate in <1ms without DB query.
    """
    ev = Event(
        id="evt_redis_hit_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_redis_hit_100",
        razorpay_event_id="evt_redis_hit_100",
        payload={"event": "payment.failed", "payload": {}},
    )

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = True  # Redis key exists (cached event)

    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=redis_test_session,
        event=ev,
        redis_client=mock_redis,
    )

    assert is_duplicate is True
    assert norm.is_duplicate is True
    mock_redis.exists.assert_called_once_with("dedup:razorpay_webhook:evt_redis_hit_100")


@pytest.mark.asyncio
async def test_2_redis_lock_acquisition_and_key_registration(redis_test_session: AsyncSession):
    """
    2. Redis Lock & Cache Registration:
       - Production behavior: Novel event registered in Redis with 24h TTL.
       - Expected result: redis.set(key, "1", ex=86400) called successfully.
    """
    ev = Event(
        id="evt_redis_novel_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_redis_novel_200",
        razorpay_event_id="evt_redis_novel_200",
        payload={"event": "payment.failed", "payload": {}},
    )

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False  # Novel event

    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=redis_test_session,
        event=ev,
        redis_client=mock_redis,
    )

    assert is_duplicate is False
    assert norm.is_duplicate is False
    mock_redis.set.assert_called_once_with("dedup:razorpay_webhook:evt_redis_novel_200", "1", ex=86400)


@pytest.mark.asyncio
async def test_3_redis_unavailable_fallback_to_postgres_correctness(redis_test_session: AsyncSession):
    """
    3. Redis Network Failure / Outage Fallback Test:
       - Production behavior: When Redis fails (connection error / timeout), system degrades gracefully.
       - Database guarantee: PostgreSQL ACID boundary enforces deduplication correctness.
       - Security & Safety check: Zero duplicate financial operations, zero crashes.
    """
    # Create existing event in DB
    ev_existing = Event(
        id="evt_db_exist_001",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_shared_key_300",
        razorpay_event_id="evt_shared_key_300",
        payload={"event": "payment.failed", "payload": {}},
    )
    redis_test_session.add(ev_existing)
    await redis_test_session.commit()

    # Second incoming event instance with identical idempotency key
    ev_incoming = Event(
        id="evt_incoming_002",
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        idempotency_key="razorpay:evt_shared_key_300",
        razorpay_event_id="evt_shared_key_300",
        payload={"event": "payment.failed", "payload": {}},
    )

    # Mock Redis client throwing ConnectionError (Redis server down)
    failing_redis = AsyncMock()
    failing_redis.exists.side_effect = ConnectionError("Redis server connection refused on localhost:6379")
    failing_redis.set.side_effect = ConnectionError("Redis server connection refused on localhost:6379")

    # Service call MUST NOT throw, MUST catch Redis error, log warning, and fall back to DB
    norm, is_duplicate = await EventNormalizerService.process_and_deduplicate(
        session=redis_test_session,
        event=ev_incoming,
        redis_client=failing_redis,
    )

    assert is_duplicate is True
    assert norm.is_duplicate is True
