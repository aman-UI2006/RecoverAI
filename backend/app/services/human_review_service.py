"""
RecoverAI - Step 16: Human Review and Escalation Service

Routes policy-rejected, low-confidence, or high-value transactions to review queues,
processes reviewer overrides/rejections, and enforces RBAC permission checks,
multi-tenant isolation, and SHA-256 audit log integrity via StateTransitionService.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, HumanReview, current_utc_time, generate_uuid
from backend.app.schemas.human_review import (
    HumanReviewDecision,
    HumanReviewStatus,
)
from backend.app.schemas.state_machine import TransactionStatus
from backend.app.services.state_transition_service import StateTransitionService


class HumanReviewService:
    """Service orchestrating human review queue management and reviewer resolution."""

    @staticmethod
    async def escalate_transaction(
        session: AsyncSession,
        transaction_id: str,
        reason: str,
        merchant_id: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
    ) -> HumanReview:
        """
        Escalate a transaction to the Human Review Queue.
        Transitions state to ESCALATED via StateTransitionService and persists HumanReview record.
        Idempotency: Reuses existing PENDING review item for the same transaction if present.
        """
        # 1. Fetch transaction and verify merchant boundary
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()

        if not tx:
            raise ValueError(f"Transaction with ID '{transaction_id}' not found.")

        if merchant_id and tx.merchant_id != merchant_id:
            raise ValueError(f"Merchant ID mismatch for transaction '{transaction_id}'. Access denied.")

        # 2. Check for existing PENDING review record (Idempotency)
        stmt_existing = select(HumanReview).where(
            and_(
                HumanReview.transaction_id == transaction_id,
                HumanReview.status == HumanReviewStatus.PENDING.value,
            )
        )
        existing_review = (await session.execute(stmt_existing)).scalar_one_or_none()
        if existing_review:
            return existing_review

        # 3. Transition transaction state to ESCALATED via StateTransitionService
        if tx.status != TransactionStatus.ESCALATED.value:
            await StateTransitionService.transition(
                session=session,
                transaction_id=transaction_id,
                target_state=TransactionStatus.ESCALATED.value,
                actor="POLICY_ENGINE",
                reason=reason,
                details={"escalation_reason": reason, "reviewer_notes": reviewer_notes},
            )

        # 4. Create and persist HumanReview record
        review_record = HumanReview(
            id=generate_uuid(),
            transaction_id=transaction_id,
            status=HumanReviewStatus.PENDING.value,
            reason=reason,
            notes=reviewer_notes,
            created_at=current_utc_time(),
        )
        session.add(review_record)
        await session.flush()

        return review_record

    @staticmethod
    async def get_pending_reviews(
        session: AsyncSession,
        merchant_id: Optional[str] = None,
    ) -> List[Tuple[HumanReview, Transaction]]:
        """
        Fetch pending review items, scoped by merchant_id for multi-tenant isolation.
        """
        stmt = (
            select(HumanReview, Transaction)
            .join(Transaction, HumanReview.transaction_id == Transaction.id)
            .where(HumanReview.status == HumanReviewStatus.PENDING.value)
        )
        if merchant_id:
            stmt = stmt.where(Transaction.merchant_id == merchant_id)

        stmt = stmt.order_by(HumanReview.created_at.asc())
        result = await session.execute(stmt)
        return list(result.all())

    @staticmethod
    async def get_review_item(
        session: AsyncSession,
        review_id: str,
        merchant_id: Optional[str] = None,
    ) -> Tuple[HumanReview, Transaction]:
        """
        Fetch a specific human review item by ID with merchant ownership validation.
        """
        stmt = (
            select(HumanReview, Transaction)
            .join(Transaction, HumanReview.transaction_id == Transaction.id)
            .where(HumanReview.id == review_id)
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise ValueError(f"HumanReview item with ID '{review_id}' not found.")

        review, tx = row
        if merchant_id and tx.merchant_id != merchant_id:
            raise ValueError(f"Merchant ID mismatch for review item '{review_id}'. Access denied.")

        return review, tx

    @staticmethod
    async def process_reviewer_decision(
        session: AsyncSession,
        review_id: str,
        decision: HumanReviewDecision,
        reviewer_id: str,
        notes: Optional[str] = None,
        merchant_id: Optional[str] = None,
        user_role: str = "ROLE_HUMAN_REVIEWER",
    ) -> Tuple[HumanReview, Transaction]:
        """
        Process reviewer decision (APPROVE_OVERRIDE or REJECT_PERMANENT).
        Requires ROLE_HUMAN_REVIEWER permission.
        Mutates transaction state via StateTransitionService and records resolution metadata.
        """
        # 1. RBAC Security Check
        if user_role != "ROLE_HUMAN_REVIEWER":
            raise PermissionError("Access denied: Action requires 'ROLE_HUMAN_REVIEWER' role permission.")

        # 2. Fetch review item and verify merchant isolation
        review, tx = await HumanReviewService.get_review_item(session, review_id, merchant_id)

        if review.status != HumanReviewStatus.PENDING.value:
            raise ValueError(f"Review item '{review_id}' has already been processed (Status: {review.status}).")

        # 3. Process Decision & Perform State Transition via StateTransitionService
        now = current_utc_time()
        if decision == HumanReviewDecision.APPROVE_OVERRIDE:
            target_state = TransactionStatus.APPROVED.value
            review_status = HumanReviewStatus.APPROVED.value
        elif decision == HumanReviewDecision.REJECT_PERMANENT:
            target_state = TransactionStatus.STOPPED.value
            review_status = HumanReviewStatus.REJECTED.value
        else:
            raise ValueError(f"Invalid human review decision: '{decision}'")

        # Transition transaction state using StateTransitionService (handles SHA-256 audit chaining)
        updated_tx, _ = await StateTransitionService.transition(
            session=session,
            transaction_id=tx.id,
            target_state=target_state,
            actor=f"HUMAN_REVIEWER:{reviewer_id}",
            reason=notes or f"Human Review decision: {decision.value}",
            details={
                "decision": decision.value,
                "reviewer_id": reviewer_id,
                "review_id": review_id,
                "notes": notes,
            },
        )

        # 4. Update HumanReview record
        review.status = review_status
        review.decision = decision.value
        review.reviewer_id = reviewer_id
        review.notes = notes
        review.reviewed_at = now

        await session.flush()
        return review, updated_tx

    @staticmethod
    async def auto_expire_stale_reviews(
        session: AsyncSession,
        expiration_hours: int = 48,
    ) -> List[str]:
        """
        Auto-expire pending review items older than expiration_hours (default 48h).
        Transitions transaction state to STOPPED and marks review item EXPIRED.
        """
        cutoff_time = current_utc_time() - timedelta(hours=expiration_hours)

        stmt = (
            select(HumanReview, Transaction)
            .join(Transaction, HumanReview.transaction_id == Transaction.id)
            .where(
                and_(
                    HumanReview.status == HumanReviewStatus.PENDING.value,
                    HumanReview.created_at <= cutoff_time,
                )
            )
        )
        result = await session.execute(stmt)
        stale_items = result.all()

        expired_ids = []
        now = current_utc_time()

        for review, tx in stale_items:
            # Transition transaction to STOPPED via StateTransitionService
            await StateTransitionService.transition(
                session=session,
                transaction_id=tx.id,
                target_state=TransactionStatus.STOPPED.value,
                actor="SYSTEM_AUTO_EXPIRE",
                reason=f"Human review item expired after {expiration_hours} hours queue timeout",
                details={"review_id": review.id, "expiration_hours": expiration_hours},
            )

            review.status = HumanReviewStatus.EXPIRED.value
            review.decision = "EXPIRED"
            review.reviewed_at = now
            expired_ids.append(review.id)

        await session.flush()
        return expired_ids
