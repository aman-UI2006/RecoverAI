"""
RecoverAI - Result Processor Service (Step 19)

Processes incoming execution outcomes (e.g., Razorpay payment_link.paid webhooks)
and updates transaction lifecycles atomically via StateTransitionService.
"""

import logging
from typing import Any, Dict, Optional, Tuple, Callable, Awaitable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, RecoveryAttempt, Event
from backend.app.schemas.state_machine import (
    TransactionStatus,
    ExecutionStatus,
)
from backend.app.services.state_transition_service import StateTransitionService

logger = logging.getLogger(__name__)

# Type alias for Step 20 Attribution Engine Hook callback
AttributionHookCallable = Callable[[AsyncSession, str, str, Optional[str]], Awaitable[Dict[str, Any]]]


class ResultProcessor:
    """Service responsible for processing external execution results and mutating transaction lifecycles."""

    _attribution_hook: Optional[AttributionHookCallable] = None

    @classmethod
    def register_attribution_hook(cls, hook_fn: AttributionHookCallable) -> None:
        """Register a custom callback hook for Step 20 AttributionEngine integration.

        Args:
            hook_fn: Async callable taking (session, transaction_id, attempt_id, payment_id).
        """
        cls._attribution_hook = hook_fn
        logger.info("Registered custom AttributionEngine hook callback in ResultProcessor")

    @classmethod
    def reset_attribution_hook(cls) -> None:
        """Reset the registered attribution hook back to default boundary."""
        cls._attribution_hook = None

    @classmethod
    async def _default_attribution_hook(
        cls,
        session: AsyncSession,
        transaction_id: str,
        attempt_id: str,
        payment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Default hook interface boundary for Step 20 AttributionEngine invocation.

        Args:
            session: Active SQLAlchemy AsyncSession.
            transaction_id: UUID of verified recovered transaction.
            attempt_id: UUID of successful RecoveryAttempt.
            payment_id: Optional Razorpay payment ID.

        Returns:
            Dictionary payload acknowledging trigger invocation.
        """
        logger.info(
            f"Step 20 Attribution trigger boundary invoked for transaction '{transaction_id}' "
            f"(attempt_id: '{attempt_id}', payment_id: '{payment_id}')"
        )
        return {
            "triggered": True,
            "transaction_id": transaction_id,
            "attempt_id": attempt_id,
            "payment_id": payment_id,
            "status": "ATTRIBUTION_PENDING_STEP_20",
        }

    @classmethod
    async def trigger_attribution(
        cls,
        session: AsyncSession,
        transaction_id: str,
        attempt_id: str,
        payment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke registered or default Step 20 attribution trigger.

        Args:
            session: Active SQLAlchemy AsyncSession.
            transaction_id: UUID of recovered transaction.
            attempt_id: UUID of successful RecoveryAttempt.
            payment_id: Optional Razorpay payment ID.

        Returns:
            Attribution trigger result dictionary.
        """
        if cls._attribution_hook is not None:
            return await cls._attribution_hook(session, transaction_id, attempt_id, payment_id)
        return await cls._default_attribution_hook(session, transaction_id, attempt_id, payment_id)

    @staticmethod
    def extract_identifiers(event_payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Extract payment_link_id, payment_id, reference_id, merchant_id, and event_type from event payload.

        Args:
            event_payload: Dictionary payload from Event or Webhook payload.

        Returns:
            Tuple of (payment_link_id, payment_id, reference_id, merchant_id, event_type).
        """
        event_type = event_payload.get("event")
        payload = event_payload.get("payload", {})

        payment_link_entity = payload.get("payment_link", {}).get("entity", {})
        payment_entity = payload.get("payment", {}).get("entity", {})

        payment_link_id = payment_link_entity.get("id") or event_payload.get("razorpay_payment_link_id")
        payment_id = payment_entity.get("id") or event_payload.get("razorpay_payment_id")
        reference_id = payment_link_entity.get("reference_id") or event_payload.get("reference_id")

        notes = payment_link_entity.get("notes", {}) or payment_entity.get("notes", {})
        merchant_id = notes.get("merchant_id") or event_payload.get("merchant_id")

        return payment_link_id, payment_id, reference_id, merchant_id, event_type

    @staticmethod
    async def match_recovery_attempt(
        session: AsyncSession,
        payment_link_id: Optional[str],
        payment_id: Optional[str],
        reference_id: Optional[str],
    ) -> Optional[RecoveryAttempt]:
        """Find matching RecoveryAttempt record using authoritative database identifiers.

        Args:
            session: Active AsyncSession.
            payment_link_id: Optional Razorpay Payment Link ID.
            payment_id: Optional Razorpay Payment ID.
            reference_id: Optional Merchant Reference ID.

        Returns:
            Matching RecoveryAttempt instance or None if not found.
        """
        if payment_link_id:
            stmt = select(RecoveryAttempt).where(
                (RecoveryAttempt.razorpay_payment_link_id == payment_link_id)
                | (RecoveryAttempt.external_resource_id == payment_link_id)
            )
            attempt = (await session.execute(stmt)).scalars().first()
            if attempt:
                return attempt

        if payment_id:
            stmt = select(RecoveryAttempt).where(
                RecoveryAttempt.external_resource_id == payment_id
            )
            attempt = (await session.execute(stmt)).scalars().first()
            if attempt:
                return attempt

        if reference_id:
            stmt = select(RecoveryAttempt).where(
                RecoveryAttempt.razorpay_reference_id == reference_id
            )
            attempt = (await session.execute(stmt)).scalars().first()
            if attempt:
                return attempt

        return None

    @classmethod
    async def process_event(
        cls,
        session: AsyncSession,
        event: Event,
    ) -> Dict[str, Any]:
        """Process an ingested Event record and mutate transaction lifecycle atomically.

        Args:
            session: Active AsyncSession.
            event: Ingested Event OR synthetic simulation event model instance.

        Returns:
            Dictionary summary of processing outcome.
        """
        payload = event.payload or {}
        return await cls.process_payload(
            session=session,
            payload=payload,
            event_id=event.id,
        )

    @classmethod
    async def process_payload(
        cls,
        session: AsyncSession,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a raw or structured event payload dictionary.

        Args:
            session: Active AsyncSession.
            payload: Webhook or event payload dictionary.
            event_id: Optional persisted Event UUID.

        Returns:
            Dictionary summary of processing outcome.
        """
        payment_link_id, payment_id, reference_id, notes_merchant_id, event_type = cls.extract_identifiers(payload)

        # 1. Handle Unlinked Events: missing or non-matching identifiers
        attempt = await cls.match_recovery_attempt(session, payment_link_id, payment_id, reference_id)
        if not attempt:
            logger.warning(
                f"Unlinked event detected (event_id: '{event_id}', link_id: '{payment_link_id}', "
                f"ref_id: '{reference_id}'). Flagging for reconciliation check."
            )
            return {
                "status": "UNLINKED_EVENT",
                "matched": False,
                "event_id": event_id,
                "payment_link_id": payment_link_id,
                "reference_id": reference_id,
                "message": "No matching RecoveryAttempt found. Authoritative transaction state unchanged.",
            }

        # 2. Acquire transaction with row locking
        stmt = select(Transaction).where(Transaction.id == attempt.transaction_id).with_for_update()
        tx = (await session.execute(stmt)).scalar_one_or_none()
        if not tx:
            logger.error(f"Transaction '{attempt.transaction_id}' referenced by attempt '{attempt.id}' not found.")
            return {
                "status": "TRANSACTION_NOT_FOUND",
                "matched": True,
                "attempt_id": attempt.id,
                "message": f"Transaction '{attempt.transaction_id}' not found.",
            }

        # 3. Multi-Tenant Security Verification
        if notes_merchant_id and notes_merchant_id != tx.merchant_id:
            logger.error(
                f"Multi-tenant isolation breach attempt! Webhook notes merchant '{notes_merchant_id}' "
                f"does not match Transaction merchant '{tx.merchant_id}'."
            )
            return {
                "status": "MERCHANT_MISMATCH_REJECTED",
                "matched": True,
                "transaction_id": tx.id,
                "message": "Merchant isolation mismatch between payload notes and transaction.",
            }

        # 4. Idempotency Check: If RecoveryAttempt is already SUCCESS or FAILURE, skip duplicate processing
        if attempt.execution_status in (ExecutionStatus.SUCCESS.value, ExecutionStatus.FAILURE.value):
            logger.info(
                f"Idempotent skip: RecoveryAttempt '{attempt.id}' for transaction '{tx.id}' "
                f"already has execution_status '{attempt.execution_status}'."
            )
            return {
                "status": "IDEMPOTENT_SKIPPED",
                "matched": True,
                "transaction_id": tx.id,
                "attempt_id": attempt.id,
                "execution_status": attempt.execution_status,
                "transaction_status": tx.status,
                "message": "Result already processed previously. Zero duplicate action or transition performed.",
            }

        # 5. Inspect payment & link state from payload
        payload_entities = payload.get("payload", {})
        link_entity = payload_entities.get("payment_link", {}).get("entity", {})
        payment_entity = payload_entities.get("payment", {}).get("entity", {})

        link_status = link_entity.get("status") or payload.get("payment_link_status") or payload.get("status")
        payment_status = payment_entity.get("status") or payload.get("payment_status")

        is_captured = (payment_status == "captured") or payment_entity.get("captured") is True
        is_paid_link = (link_status == "paid")

        # 6. Branch execution outcomes
        attribution_result = None

        if is_paid_link or is_captured or event_type in ("payment_link.paid", "payment.captured"):
            # SUCCESS PATH: Payment link paid / payment captured
            attempt.execution_status = ExecutionStatus.SUCCESS.value
            if payment_id and not attempt.external_resource_id:
                attempt.external_resource_id = payment_id

            # Transition transaction to RECOVERED via StateTransitionService
            updated_tx, audit_event = await StateTransitionService.transition(
                session=session,
                transaction_id=tx.id,
                target_state=TransactionStatus.RECOVERED.value,
                actor="RESULT_PROCESSOR",
                reason=f"Verified payment completion (event: '{event_type}', status: '{link_status or payment_status}')",
                details={
                    "event_id": event_id,
                    "payment_link_id": payment_link_id,
                    "payment_id": payment_id,
                    "attempt_id": attempt.id,
                    "logical_operation_key": attempt.logical_operation_key,
                },
            )

            # Trigger Step 20 Attribution hook ONLY for verified successful payments
            attribution_result = await cls.trigger_attribution(
                session=session,
                transaction_id=tx.id,
                attempt_id=attempt.id,
                payment_id=payment_id,
            )

            result_status = "SUCCESS_RECOVERED"

        elif link_status == "cancelled" or event_type == "payment_link.cancelled":
            # CANCELLED PATH: Payment link cancelled by merchant or customer
            attempt.execution_status = ExecutionStatus.FAILURE.value

            updated_tx, audit_event = await StateTransitionService.transition(
                session=session,
                transaction_id=tx.id,
                target_state=TransactionStatus.FAILED.value,
                actor="RESULT_PROCESSOR",
                reason="Payment link cancelled",
                details={"event_id": event_id, "attempt_id": attempt.id},
            )
            result_status = "FAILED_CANCELLED"

        elif link_status == "expired" or event_type == "payment_link.expired":
            # EXPIRED PATH: Payment link expired
            attempt.execution_status = ExecutionStatus.FAILURE.value

            updated_tx, audit_event = await StateTransitionService.transition(
                session=session,
                transaction_id=tx.id,
                target_state=TransactionStatus.EXPIRED.value,
                actor="RESULT_PROCESSOR",
                reason="Payment link expired",
                details={"event_id": event_id, "attempt_id": attempt.id},
            )
            result_status = "EXPIRED"

        elif payment_status == "failed" or event_type == "payment.failed":
            # FAILED PAYMENT PATH: Individual payment attempt failed
            attempt.execution_status = ExecutionStatus.FAILURE.value

            updated_tx, audit_event = await StateTransitionService.transition(
                session=session,
                transaction_id=tx.id,
                target_state=TransactionStatus.FAILED.value,
                actor="RESULT_PROCESSOR",
                reason=f"Payment failed: {payment_entity.get('error_description', 'Payment failure')}",
                details={"event_id": event_id, "attempt_id": attempt.id},
            )
            result_status = "FAILED_PAYMENT"

        else:
            # AMBIGUOUS / UNKNOWN PATH: Keep transaction state EXECUTING, mark attempt for reconciliation
            logger.warning(
                f"Ambiguous event payload for transaction '{tx.id}' (event_type: '{event_type}', "
                f"link_status: '{link_status}', payment_status: '{payment_status}'). State unchanged."
            )
            return {
                "status": "AMBIGUOUS_UNPROCESSED",
                "matched": True,
                "transaction_id": tx.id,
                "attempt_id": attempt.id,
                "transaction_status": tx.status,
                "message": "Payment outcome ambiguous. Transaction lifecycle unchanged.",
            }

        await session.commit()

        return {
            "status": result_status,
            "matched": True,
            "transaction_id": tx.id,
            "attempt_id": attempt.id,
            "execution_status": attempt.execution_status,
            "transaction_status": updated_tx.status,
            "attribution_hook": attribution_result,
        }
