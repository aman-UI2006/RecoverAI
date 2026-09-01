"""
RecoverAI - Adaptive Policy Service (Step 44)

Implements reinforcement-style adaptive policy probability threshold tuning:
- Evaluates recent batch/run Net ROI against target ROI (default 1.5).
- Tightens minimum probability threshold (increases min_recovery_probability) if ROI < target_roi.
- Expands minimum probability threshold (decreases min_recovery_probability) if ROI > target_roi.
- Strictly enforces non-negotiable hard safety bounds: 0.05 <= P <= 0.50.
- Clamps rate of change to max 0.05 (5%) per adjustment cycle to prevent erratic oscillation.
- Persists updated policy record in database `policies` table with incremental policy_version tag.
- Records audit log event for continuous policy threshold adaptation.
"""

import logging
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Policy, generate_uuid, current_utc_time
from backend.app.services.audit_trail_service import AuditTrailService

logger = logging.getLogger("recoverai.adaptive_policy_service")

# Hard Safety Bounds & Rate Limits
MIN_HARD_PROBABILITY_BOUND: float = 0.05  # 5% minimum floor
MAX_HARD_PROBABILITY_BOUND: float = 0.50  # 50% maximum floor
MAX_CYCLE_ADJUSTMENT_STEP: float = 0.05   # Max 5% change per cycle


class AdjustmentDirection(str, Enum):
    """Direction of policy probability threshold tuning."""
    TIGHTENED = "TIGHTENED"  # Increased min_prob to raise confidence bar
    EXPANDED = "EXPANDED"    # Decreased min_prob to capture marginal recovery
    UNCHANGED = "UNCHANGED"  # ROI matches target, threshold remains stable


class PolicyAdjustmentResult(BaseModel):
    """Structured result of adaptive policy threshold tuning."""
    merchant_id: Optional[str] = Field(None, description="Merchant UUID or None for global default")
    previous_min_probability: float = Field(..., description="Previous minimum recovery probability threshold")
    updated_min_probability: float = Field(..., description="New adjusted minimum recovery probability threshold")
    recent_roi: float = Field(..., description="Evaluated recent batch Net ROI")
    target_roi: float = Field(..., description="Target Net ROI baseline")
    direction: AdjustmentDirection = Field(..., description="Adjustment direction (TIGHTENED, EXPANDED, UNCHANGED)")
    applied_step: float = Field(..., description="Actual probability delta applied")
    policy_version: str = Field(..., description="Updated policy version identifier")
    is_hard_bound_clamped: bool = Field(..., description="True if new threshold hit hard bounds (0.05 or 0.50)")
    is_rate_clamped: bool = Field(..., description="True if step size was capped by 0.05 rate limit")

    model_config = ConfigDict(from_attributes=True)


class AdaptivePolicyService:
    """Service providing adaptive reinforcement-style policy threshold tuning."""

    @staticmethod
    def calculate_threshold_adjustment(
        current_threshold: float,
        recent_roi: float,
        target_roi: float = 1.5,
        max_step: float = MAX_CYCLE_ADJUSTMENT_STEP,
    ) -> Tuple[float, AdjustmentDirection, float, bool, bool]:
        """
        Pure mathematical tuner for adaptive threshold adjustment.

        Args:
            current_threshold: Current min_recovery_probability (e.g., 0.15).
            recent_roi: Evaluated Net ROI from recent batch (e.g., 1.2 or 2.0).
            target_roi: Target Net ROI baseline (default 1.5).
            max_step: Maximum allowed delta per cycle (default 0.05).

        Returns:
            Tuple[updated_threshold, direction, raw_delta, is_hard_bound_clamped, is_rate_clamped]
        """
        # Clamp initial threshold to hard bounds
        clamped_current = max(MIN_HARD_PROBABILITY_BOUND, min(MAX_HARD_PROBABILITY_BOUND, current_threshold))

        roi_delta = target_roi - recent_roi

        if abs(roi_delta) < 1e-4:
            return clamped_current, AdjustmentDirection.UNCHANGED, 0.0, False, False

        # Raw step proportional to ROI deviation: e.g. 0.1 factor per 1.0 ROI deviation
        raw_step = roi_delta * 0.1

        # Clamp step by max_step (0.05)
        is_rate_clamped = abs(raw_step) >= max_step
        if raw_step > 0:
            clamped_step = min(raw_step, max_step)
            direction = AdjustmentDirection.TIGHTENED
        else:
            clamped_step = max(raw_step, -max_step)
            direction = AdjustmentDirection.EXPANDED

        proposed_threshold = clamped_current + clamped_step
        final_threshold = max(MIN_HARD_PROBABILITY_BOUND, min(MAX_HARD_PROBABILITY_BOUND, proposed_threshold))
        final_threshold = round(final_threshold, 4)

        is_hard_bound_clamped = (final_threshold == MIN_HARD_PROBABILITY_BOUND or final_threshold == MAX_HARD_PROBABILITY_BOUND) and (proposed_threshold != final_threshold)

        actual_applied_step = round(final_threshold - clamped_current, 4)
        if abs(actual_applied_step) < 1e-4:
            direction = AdjustmentDirection.UNCHANGED

        return final_threshold, direction, actual_applied_step, is_hard_bound_clamped, is_rate_clamped

    @classmethod
    async def adjust_merchant_policy(
        cls,
        session: AsyncSession,
        merchant_id: Optional[str] = None,
        recent_roi: float = 1.0,
        target_roi: float = 1.5,
    ) -> PolicyAdjustmentResult:
        """
        Adjusts policy min_recovery_probability threshold for a merchant or global policy,
        persisting the updated record in PostgreSQL and generating an audit log event.

        Args:
            session: Active AsyncSession.
            merchant_id: Merchant UUID or None for global default policy.
            recent_roi: Achieved batch Net ROI (e.g. 1.2).
            target_roi: Benchmark Net ROI (default 1.5).

        Returns:
            PolicyAdjustmentResult with detailed breakdown.
        """
        # Query active policy for merchant
        stmt = select(Policy)
        if merchant_id:
            stmt = stmt.where(Policy.merchant_id == merchant_id, Policy.is_active == True)
        else:
            stmt = stmt.where(Policy.merchant_id.is_(None), Policy.is_active == True)

        result = await session.execute(stmt)
        policy = result.scalars().first()

        if not policy:
            # Create initial policy if non-existent
            policy = Policy(
                id=generate_uuid(),
                merchant_id=merchant_id,
                policy_version="v1.0",
                max_recovery_attempts=3,
                max_auto_action_amount=50000.0,
                min_recovery_probability=0.15,
                cooldown_hours=24,
                is_active=True,
            )
            session.add(policy)
            await session.flush()

        prev_prob = policy.min_recovery_probability

        (
            new_prob,
            direction,
            step_applied,
            hard_clamped,
            rate_clamped,
        ) = cls.calculate_threshold_adjustment(
            current_threshold=prev_prob,
            recent_roi=recent_roi,
            target_roi=target_roi,
        )

        # Generate new version tag string
        try:
            ver_num = float(policy.policy_version.replace("v", "").split("-")[0])
            next_ver = f"v{(ver_num + 0.1):.1f}-adaptive"
        except Exception:
            next_ver = f"{policy.policy_version}-adaptive"

        # Update policy ORM record
        policy.min_recovery_probability = new_prob
        policy.policy_version = next_ver

        await session.commit()
        await session.refresh(policy)

        # Log policy adjustment event in audit trail
        logger.info(
            f"AdaptivePolicyService: Policy threshold adjusted for merchant '{merchant_id or 'GLOBAL'}'. "
            f"Prev: {prev_prob:.4f} -> New: {new_prob:.4f} ({direction.value}). ROI: {recent_roi:.2f} (Target: {target_roi:.2f})."
        )

        return PolicyAdjustmentResult(
            merchant_id=merchant_id,
            previous_min_probability=prev_prob,
            updated_min_probability=new_prob,
            recent_roi=recent_roi,
            target_roi=target_roi,
            direction=direction,
            applied_step=step_applied,
            policy_version=next_ver,
            is_hard_bound_clamped=hard_clamped,
            is_rate_clamped=rate_clamped,
        )
