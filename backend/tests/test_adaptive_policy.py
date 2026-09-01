"""
RecoverAI - Step 44 Adaptive Policy Unit Tests

Validates reinforcement-style adaptive policy threshold tuning:
1. Tightening threshold when recent ROI drops below target.
2. Expanding threshold when recent ROI exceeds target.
3. Rate of change clamping (<= 0.05 max step per cycle).
4. Strict enforcement of non-negotiable hard safety bounds (0.05 <= P <= 0.50).
5. Database persistence and policy version updates.
"""

import pytest
from sqlalchemy import select
from backend.app.models.domain import Policy
from backend.app.services.adaptive_policy_service import (
    AdaptivePolicyService,
    AdjustmentDirection,
    MIN_HARD_PROBABILITY_BOUND,
    MAX_HARD_PROBABILITY_BOUND,
    MAX_CYCLE_ADJUSTMENT_STEP,
)


def test_adaptive_policy_tighten_on_low_roi():
    """
    Test 1: When recent Net ROI drops below target (e.g. 0.5 vs target 1.5),
    the probability threshold is tightened (min_recovery_probability increases).
    """
    current_threshold = 0.15
    recent_roi = 0.50
    target_roi = 1.50

    new_prob, direction, step, hard_clamped, rate_clamped = AdaptivePolicyService.calculate_threshold_adjustment(
        current_threshold=current_threshold,
        recent_roi=recent_roi,
        target_roi=target_roi,
    )

    assert direction == AdjustmentDirection.TIGHTENED
    assert new_prob > current_threshold
    assert step > 0
    # Step must be clamped by max 0.05
    assert step <= MAX_CYCLE_ADJUSTMENT_STEP
    assert rate_clamped is True


def test_adaptive_policy_expand_on_high_roi():
    """
    Test 2: When recent Net ROI exceeds target (e.g. 2.5 vs target 1.5),
    the probability threshold is expanded (min_recovery_probability decreases).
    """
    current_threshold = 0.20
    recent_roi = 2.50
    target_roi = 1.50

    new_prob, direction, step, hard_clamped, rate_clamped = AdaptivePolicyService.calculate_threshold_adjustment(
        current_threshold=current_threshold,
        recent_roi=recent_roi,
        target_roi=target_roi,
    )

    assert direction == AdjustmentDirection.EXPANDED
    assert new_prob < current_threshold
    assert step < 0
    assert abs(step) <= MAX_CYCLE_ADJUSTMENT_STEP
    assert rate_clamped is True


def test_adaptive_policy_hard_bounds_clamping():
    """
    Test 3: Enforces hard safety bounds (0.05 <= P <= 0.50) even after multiple adjustments.
    """
    # Test lower bound (0.05)
    low_prob, dir_low, _, hard_clamped_low, _ = AdaptivePolicyService.calculate_threshold_adjustment(
        current_threshold=0.06,
        recent_roi=5.00,  # Huge ROI attempting to lower threshold drastically
        target_roi=1.50,
    )
    assert low_prob >= MIN_HARD_PROBABILITY_BOUND
    assert low_prob == 0.05

    # Test upper bound (0.50)
    high_prob, dir_high, _, hard_clamped_high, _ = AdaptivePolicyService.calculate_threshold_adjustment(
        current_threshold=0.48,
        recent_roi=0.10,  # Low ROI attempting to push threshold high
        target_roi=1.50,
    )
    assert high_prob <= MAX_HARD_PROBABILITY_BOUND
    assert high_prob == 0.50


def test_adaptive_policy_unchanged_when_target_met():
    """
    Test 4: When recent ROI equals target ROI, threshold remains unchanged.
    """
    current_threshold = 0.15
    new_prob, direction, step, _, _ = AdaptivePolicyService.calculate_threshold_adjustment(
        current_threshold=current_threshold,
        recent_roi=1.50,
        target_roi=1.50,
    )

    assert direction == AdjustmentDirection.UNCHANGED
    assert new_prob == current_threshold
    assert step == 0.0


import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.core.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for adaptive policy testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_adaptive_policy_db_persistence(async_test_session: AsyncSession):
    """
    Test 5: Integration test verifying Policy model is updated in SQLite/PostgreSQL
    and policy_version tag is incremented.
    """
    merchant_id = "mch_adaptive_test_01"

    # Seed initial merchant policy
    policy = Policy(
        merchant_id=merchant_id,
        policy_version="v1.0",
        max_recovery_attempts=3,
        max_auto_action_amount=50000.0,
        min_recovery_probability=0.15,
        cooldown_hours=24,
        is_active=True,
    )
    async_test_session.add(policy)
    await async_test_session.commit()

    # Trigger adjustment for low ROI (should increase threshold)
    res = await AdaptivePolicyService.adjust_merchant_policy(
        session=async_test_session,
        merchant_id=merchant_id,
        recent_roi=0.80,
        target_roi=1.50,
    )

    assert res.direction == AdjustmentDirection.TIGHTENED
    assert res.updated_min_probability > 0.15
    assert res.policy_version.startswith("v1.1")

    # Query DB to confirm persistence
    stmt = select(Policy).where(Policy.merchant_id == merchant_id)
    db_result = await async_test_session.execute(stmt)
    updated_policy = db_result.scalars().first()

    assert updated_policy is not None
    assert updated_policy.min_recovery_probability == res.updated_min_probability
    assert updated_policy.policy_version == res.policy_version
