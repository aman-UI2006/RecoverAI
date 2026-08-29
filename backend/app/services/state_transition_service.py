"""Authoritative State Transition Service for RecoverAI Step 7."""

import hashlib
import json
from typing import Any, Dict, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, AuditEvent, current_utc_time, generate_uuid
from backend.app.schemas.state_machine import (
    VALID_TRANSACTION_TRANSITIONS,
    InvalidStateTransitionException,
    StateTransitionResponse,
)


class StateTransitionService:
    """Centralized service enforcing atomic, concurrency-safe lifecycle mutations on transactions."""

    @staticmethod
    async def transition(
        session: AsyncSession,
        transaction_id: str,
        target_state: str,
        actor: str = "SYSTEM",
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Transaction, AuditEvent]:
        """Atomically transition a transaction's lifecycle state with row-locking and SHA-256 audit chaining.

        Args:
            session: Active SQLAlchemy AsyncSession.
            transaction_id: UUID of transaction to transition.
            target_state: Target transaction lifecycle state.
            actor: Actor initiating transition (e.g., SYSTEM, MERCHANT, HUMAN_REVIEW).
            reason: Optional textual reason for state change.
            details: Optional context metadata payload.

        Returns:
            Tuple of (updated Transaction, created AuditEvent).

        Raises:
            ValueError: If transaction ID does not exist.
            InvalidStateTransitionException: If target_state is invalid for the current state.
        """
        # 1. Acquire row lock via SELECT ... FOR UPDATE
        stmt = (
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()

        if not tx:
            raise ValueError(f"Transaction with ID '{transaction_id}' not found.")

        current_state = tx.status

        # 2. Check transition validity against state transition matrix
        allowed_targets = VALID_TRANSACTION_TRANSITIONS.get(current_state, set())
        if target_state not in allowed_targets:
            raise InvalidStateTransitionException(
                state_from=current_state,
                state_to=target_state,
                transaction_id=transaction_id,
            )

        # 3. Mutate transaction state and timestamp
        now = current_utc_time()
        tx.status = target_state
        tx.updated_at = now

        # 4. SHA-256 Audit Trail Chaining
        stmt_last_audit = (
            select(AuditEvent)
            .where(AuditEvent.transaction_id == transaction_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        last_audit = (await session.execute(stmt_last_audit)).scalar_one_or_none()
        previous_hash = last_audit.event_hash if last_audit else "0" * 64

        audit_details = details or ({ "reason": reason } if reason else {})

        payload_dict = {
            "transaction_id": transaction_id,
            "state_from": current_state,
            "state_to": target_state,
            "actor": actor,
            "details": audit_details,
            "previous_hash": previous_hash,
        }
        payload_json = json.dumps(payload_dict, sort_keys=True, default=str)
        event_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        audit_record = AuditEvent(
            id=generate_uuid(),
            transaction_id=transaction_id,
            event_type="STATE_TRANSITION",
            actor=actor,
            state_from=current_state,
            state_to=target_state,
            details=audit_details,
            previous_hash=previous_hash,
            event_hash=event_hash,
            created_at=now,
        )
        session.add(audit_record)

        # 5. Commit transaction atomically
        await session.commit()
        await session.refresh(tx)
        await session.refresh(audit_record)

        return tx, audit_record

    @staticmethod
    def get_valid_transitions(current_state: str) -> Set[str]:
        """Return the set of valid target states from the current state."""
        return VALID_TRANSACTION_TRANSITIONS.get(current_state, set())
