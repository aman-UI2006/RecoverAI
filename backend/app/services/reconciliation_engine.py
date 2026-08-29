"""
RecoverAI - Reconciliation Engine Service (Step 22)

Polls external status for transactions stuck in UNKNOWN execution state (e.g., gateway HTTP timeouts)
without creating duplicate business attempts or incrementing recovery cycles.
Enforces multi-tenant isolation, state machine safety via StateTransitionService,
Step 20 Attribution Engine hook triggers, and Decimal monetary correctness.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, RecoveryAttempt
from backend.app.schemas.state_machine import (
    TransactionStatus,
    ExecutionStatus,
    StateTransitionRequest,
)
from backend.app.services.state_transition_service import StateTransitionService
from backend.app.services.result_processor import ResultProcessor
from backend.app.integrations.razorpay_adapter import RazorpayAdapter

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """Reconciliation Engine resolving ambiguous UNKNOWN execution states."""

    def __init__(self, razorpay_adapter: Optional[RazorpayAdapter] = None) -> None:
        """Initialize ReconciliationEngine with Razorpay adapter dependency.

        Args:
            razorpay_adapter: Instance of RazorpayAdapter (defaults to new RazorpayAdapter()).
        """
        self.razorpay_adapter = razorpay_adapter or RazorpayAdapter()

    @staticmethod
    def _current_utc_time() -> datetime:
        """Helper to return naive UTC datetime consistent with DB models."""
        return datetime.now(timezone.utc).replace(tzinfo=None)

    async def reconcile_pending_attempts(
        self,
        session: AsyncSession,
        min_age_seconds: int = 300,
        merchant_id: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query database for UNKNOWN attempts older than min_age_seconds and reconcile external status.

        Args:
            session: Active AsyncSession instance.
            min_age_seconds: Minimum age threshold in seconds for UNKNOWN attempts (defaults to 300s / 5 mins).
            merchant_id: Optional merchant UUID filter for multi-tenant isolation.
            mode: Operational mode filter ("REAL_TEST" or "SIMULATION").

        Returns:
            Dictionary with reconciliation metrics (scanned, success, failure, pending, errors).
        """
        now = self._current_utc_time()
        cutoff_time = now - timedelta(seconds=min_age_seconds)

        # 1. Fetch pending UNKNOWN attempts older than cutoff_time
        stmt = select(RecoveryAttempt).where(
            RecoveryAttempt.execution_status == ExecutionStatus.UNKNOWN.value,
            RecoveryAttempt.created_at <= cutoff_time,
        )
        attempts = (await session.execute(stmt)).scalars().all()

        scanned = 0
        reconciled_success = 0
        reconciled_failure = 0
        pending = 0
        errors = 0

        for attempt in attempts:
            scanned += 1
            transaction = await session.get(Transaction, attempt.transaction_id)
            if not transaction:
                logger.warning(f"Reconciliation: Transaction '{attempt.transaction_id}' not found for attempt '{attempt.id}'.")
                errors += 1
                continue

            # Multi-tenant isolation check
            if merchant_id and transaction.merchant_id != merchant_id:
                logger.debug(f"Reconciliation: Skipping attempt '{attempt.id}' belonging to merchant '{transaction.merchant_id}' (filtered by '{merchant_id}').")
                continue

            # Operational mode filter check
            effective_mode = mode or transaction.mode or "SIMULATION"
            if mode and transaction.mode != mode:
                continue

            # Obtain Payment Link ID for polling
            payment_link_id = attempt.razorpay_payment_link_id or attempt.external_resource_id
            if not payment_link_id:
                logger.warning(
                    f"Reconciliation: Attempt '{attempt.id}' for transaction '{transaction.id}' has no payment link ID. Cannot poll."
                )
                errors += 1
                continue

            # Poll external Razorpay / SIMULATION status
            try:
                link_data = await self.razorpay_adapter.fetch_payment_link(
                    payment_link_id=payment_link_id,
                    mode=effective_mode,
                )
            except Exception as exc:
                logger.warning(
                    f"Reconciliation: Failed to fetch payment link '{payment_link_id}' for attempt '{attempt.id}': {exc}. "
                    "Keeping state as UNKNOWN."
                )
                errors += 1
                continue

            raw_status = str(link_data.get("status", "")).lower()

            # 2. Process status resolution
            if raw_status in ("paid", "captured"):
                # Update attempt state without incrementing recovery_cycle or creating duplicate attempt
                attempt.execution_status = ExecutionStatus.SUCCESS.value

                # Authoritative state transition if transaction is in EXECUTING state
                if transaction.status == TransactionStatus.EXECUTING.value:
                    await StateTransitionService.transition(
                        session=session,
                        transaction_id=transaction.id,
                        target_state=TransactionStatus.RECOVERED.value,
                        actor="RECONCILIATION_ENGINE",
                        reason="Payment confirmed paid via Razorpay reconciliation",
                        details={
                            "attempt_id": attempt.id,
                            "payment_link_id": payment_link_id,
                            "logical_operation_key": attempt.logical_operation_key,
                        },
                    )

                # Trigger Step 20 Attribution Engine hook if registered
                if ResultProcessor._attribution_hook is not None:
                    try:
                        await ResultProcessor._attribution_hook(
                            session,
                            transaction.id,
                            attempt.id,
                            payment_link_id,
                        )
                    except Exception as attr_exc:
                        logger.error(f"Reconciliation: Attribution hook execution failed for transaction '{transaction.id}': {attr_exc}")

                reconciled_success += 1

            elif raw_status in ("expired",):
                attempt.execution_status = ExecutionStatus.FAILURE.value

                if transaction.status == TransactionStatus.EXECUTING.value:
                    await StateTransitionService.transition(
                        session=session,
                        transaction_id=transaction.id,
                        target_state=TransactionStatus.EXPIRED.value,
                        actor="RECONCILIATION_ENGINE",
                        reason="Payment link expired via Razorpay reconciliation",
                        details={
                            "attempt_id": attempt.id,
                            "payment_link_id": payment_link_id,
                            "logical_operation_key": attempt.logical_operation_key,
                        },
                    )

                reconciled_failure += 1

            elif raw_status in ("cancelled", "failed"):
                attempt.execution_status = ExecutionStatus.FAILURE.value

                if transaction.status == TransactionStatus.EXECUTING.value:
                    await StateTransitionService.transition(
                        session=session,
                        transaction_id=transaction.id,
                        target_state=TransactionStatus.FAILED.value,
                        actor="RECONCILIATION_ENGINE",
                        reason=f"Payment link status '{raw_status}' via Razorpay reconciliation",
                        details={
                            "attempt_id": attempt.id,
                            "payment_link_id": payment_link_id,
                            "logical_operation_key": attempt.logical_operation_key,
                        },
                    )

                reconciled_failure += 1

            else:
                # Status created/issued/pending: Payment still pending
                logger.info(
                    f"Reconciliation: Payment link '{payment_link_id}' status is '{raw_status}'. "
                    "Keeping attempt as UNKNOWN."
                )
                pending += 1

        await session.commit()

        return {
            "total_scanned": scanned,
            "reconciled_success": reconciled_success,
            "reconciled_failure": reconciled_failure,
            "pending": pending,
            "errors": errors,
        }
