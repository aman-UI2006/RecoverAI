"""
RecoverAI - Attribution Engine Service (Step 20)

Evaluates whether verified transaction recoveries are attributable to RecoverAI interventions,
distinguishing between RecoverAI-driven revenue (DIRECT_REFERENCE / WINDOW_MATCH),
natural recovery (NATURAL_RECOVERY), and unattributable recoveries (UNATTRIBUTED).
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.app.models.domain import Transaction, RecoveryAttempt, RecoveryAttribution
from backend.app.schemas.attribution import (
    AttributionStatus,
    AttributionMethod,
    AttributionRequest,
    AttributionResultResponse,
)
from backend.app.services.result_processor import ResultProcessor

logger = logging.getLogger(__name__)


class AttributionEngine:
    """Deterministic Attribution Engine for RecoverAI recovery evaluation."""

    @staticmethod
    def _current_utc_time() -> datetime:
        """Helper to return naive UTC datetime consistent with database models."""
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @classmethod
    async def evaluate_attribution(
        cls,
        session: AsyncSession,
        request: AttributionRequest,
    ) -> AttributionResultResponse:
        """Evaluate and persist recovery attribution for a verified recovered transaction.

        Args:
            session: Active SQLAlchemy AsyncSession.
            request: AttributionRequest containing transaction_id, recovery_attempt_id, and window settings.

        Returns:
            AttributionResultResponse containing canonical attribution outcome.
        """
        tx_id = request.transaction_id
        attempt_id = request.recovery_attempt_id
        window_minutes = request.attribution_window_minutes or 4320

        # 1. Idempotency Check: Look for existing RecoveryAttribution
        if attempt_id:
            stmt = select(RecoveryAttribution).where(
                RecoveryAttribution.transaction_id == tx_id,
                RecoveryAttribution.recovery_attempt_id == attempt_id,
            )
        else:
            stmt = select(RecoveryAttribution).where(
                RecoveryAttribution.transaction_id == tx_id,
                RecoveryAttribution.recovery_attempt_id.is_(None),
            )

        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            logger.info(
                f"Idempotent attribution replay: Record '{existing.id}' already exists for "
                f"transaction '{tx_id}' and attempt '{attempt_id}'."
            )
            return AttributionResultResponse(
                id=existing.id,
                transaction_id=existing.transaction_id,
                recovery_attempt_id=existing.recovery_attempt_id,
                recovery_source=existing.recovery_source,
                attribution_status=existing.attribution_status,
                attribution_method=existing.attribution_method,
                attribution_window_minutes=existing.attribution_window_minutes,
                recovered_amount=float(existing.recovered_amount),
                refunded_amount=float(existing.refunded_amount),
                intervention_timestamp=existing.intervention_timestamp,
                recovery_timestamp=existing.recovery_timestamp,
                is_duplicate=True,
            )

        # 2. Fetch Transaction with validation
        stmt_tx = select(Transaction).where(Transaction.id == tx_id)
        tx = (await session.execute(stmt_tx)).scalar_one_or_none()
        if not tx:
            raise ValueError(f"Transaction '{tx_id}' not found for attribution evaluation.")

        attempt: Optional[RecoveryAttempt] = None
        if attempt_id:
            stmt_att = select(RecoveryAttempt).where(RecoveryAttempt.id == attempt_id)
            attempt = (await session.execute(stmt_att)).scalar_one_or_none()
            if not attempt:
                raise ValueError(f"RecoveryAttempt '{attempt_id}' not found for transaction '{tx_id}'.")

            # Multi-tenant security check
            if attempt.transaction_id != tx_id:
                raise ValueError(
                    f"RecoveryAttempt '{attempt_id}' transaction ID '{attempt.transaction_id}' "
                    f"does not match request transaction ID '{tx_id}'."
                )

        now = cls._current_utc_time()

        # 3. Attribution Hierarchy Resolution
        if not attempt:
            # Case A: Natural Recovery (No intervention attempt took place)
            attribution_status = AttributionStatus.NATURAL_RECOVERY.value
            attribution_method = AttributionMethod.NATURAL_RECOVERY.value
            recovery_source = "SIMULATION"
            intervention_ts = None

        else:
            # Source mode from execution attempt (REAL_TEST vs SIMULATION)
            recovery_source = attempt.external_resource_type or "SIMULATION"
            intervention_ts = attempt.executed_at or attempt.created_at

            # Case B: Direct Reference check
            has_direct_ref = bool(
                attempt.razorpay_payment_link_id
                or attempt.razorpay_reference_id
                or (attempt.external_resource_id and attempt.external_resource_id.startswith("plink_"))
            )

            if has_direct_ref:
                attribution_status = AttributionStatus.ATTRIBUTED.value
                attribution_method = AttributionMethod.DIRECT_REFERENCE.value

            else:
                # Case C: Attribution Window Evaluation
                if intervention_ts:
                    # Strip tzinfo for naive UTC comparison if needed
                    ts_compare = intervention_ts.replace(tzinfo=None) if intervention_ts.tzinfo else intervention_ts
                    elapsed_seconds = (now - ts_compare).total_seconds()
                    elapsed_mins = elapsed_seconds / 60.0

                    if 0 <= elapsed_mins <= window_minutes:
                        attribution_status = AttributionStatus.ATTRIBUTED.value
                        attribution_method = AttributionMethod.WINDOW_MATCH.value
                    else:
                        attribution_status = AttributionStatus.UNATTRIBUTED.value
                        attribution_method = AttributionMethod.UNATTRIBUTED.value
                else:
                    attribution_status = AttributionStatus.UNATTRIBUTED.value
                    attribution_method = AttributionMethod.UNATTRIBUTED.value

        # 4. Construct and Persist Canonical RecoveryAttribution Record
        attribution = RecoveryAttribution(
            transaction_id=tx.id,
            recovery_attempt_id=attempt.id if attempt else None,
            recovery_source=recovery_source,
            attribution_status=attribution_status,
            attribution_method=attribution_method,
            attribution_window_minutes=window_minutes,
            recovered_amount=tx.amount,
            refunded_amount=0.00,
            intervention_timestamp=intervention_ts,
            recovery_timestamp=now,
        )

        try:
            session.add(attribution)
            await session.commit()
            await session.refresh(attribution)

        except IntegrityError:
            await session.rollback()
            # Handle concurrent duplicate race condition gracefully
            if attempt_id:
                stmt_dup = select(RecoveryAttribution).where(
                    RecoveryAttribution.transaction_id == tx_id,
                    RecoveryAttribution.recovery_attempt_id == attempt_id,
                )
            else:
                stmt_dup = select(RecoveryAttribution).where(
                    RecoveryAttribution.transaction_id == tx_id,
                    RecoveryAttribution.recovery_attempt_id.is_(None),
                )
            existing_dup = (await session.execute(stmt_dup)).scalars().first()
            if existing_dup:
                return AttributionResultResponse(
                    id=existing_dup.id,
                    transaction_id=existing_dup.transaction_id,
                    recovery_attempt_id=existing_dup.recovery_attempt_id,
                    recovery_source=existing_dup.recovery_source,
                    attribution_status=existing_dup.attribution_status,
                    attribution_method=existing_dup.attribution_method,
                    attribution_window_minutes=existing_dup.attribution_window_minutes,
                    recovered_amount=float(existing_dup.recovered_amount),
                    refunded_amount=float(existing_dup.refunded_amount),
                    intervention_timestamp=existing_dup.intervention_timestamp,
                    recovery_timestamp=existing_dup.recovery_timestamp,
                    is_duplicate=True,
                )
            raise

        logger.info(
            f"Persisted RecoveryAttribution '{attribution.id}' for transaction '{tx.id}' "
            f"(status: '{attribution_status}', method: '{attribution_method}', source: '{recovery_source}')"
        )

        return AttributionResultResponse(
            id=attribution.id,
            transaction_id=attribution.transaction_id,
            recovery_attempt_id=attribution.recovery_attempt_id,
            recovery_source=attribution.recovery_source,
            attribution_status=attribution.attribution_status,
            attribution_method=attribution.attribution_method,
            attribution_window_minutes=attribution.attribution_window_minutes,
            recovered_amount=float(attribution.recovered_amount),
            refunded_amount=float(attribution.refunded_amount),
            intervention_timestamp=attribution.intervention_timestamp,
            recovery_timestamp=attribution.recovery_timestamp,
            is_duplicate=False,
        )

    @classmethod
    async def result_processor_hook_handler(
        cls,
        session: AsyncSession,
        transaction_id: str,
        attempt_id: str,
        payment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Callback handler matching ResultProcessor attribution hook signature.

        Args:
            session: Active SQLAlchemy AsyncSession.
            transaction_id: UUID of verified recovered transaction.
            attempt_id: UUID of successful RecoveryAttempt.
            payment_id: Optional Razorpay payment ID.

        Returns:
            Dictionary payload acknowledging trigger invocation.
        """
        request = AttributionRequest(
            transaction_id=transaction_id,
            recovery_attempt_id=attempt_id,
            payment_id=payment_id,
        )
        res = await cls.evaluate_attribution(session, request)
        return res.model_dump()


# Register the AttributionEngine handler with ResultProcessor
ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
