"""
RecoverAI - Continuous Audit Trail Service (Step 23)

Provides tamper-evident cryptographic SHA-256 hash chaining across all system lifecycle events,
with canonical JSON serialization and chain verification.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.canonical_json import serialize_canonical_json
from backend.app.models.domain import AuditEvent, Transaction, generate_uuid, current_utc_time

logger = logging.getLogger(__name__)

# Frozen Genesis Hash constant for initial transaction audit events
GENESIS_HASH = hashlib.sha256("RECOVERAI-AUDIT-GENESIS-V1".encode("utf-8")).hexdigest()
LEGACY_GENESIS_HASH = "0" * 64


class AuditTrailService:
    """Service providing append-only cryptographic audit logging and chain verification."""

    @staticmethod
    def compute_event_hash(canonical_json: str, previous_hash: str) -> str:
        """Compute SHA-256 hash of canonical JSON string combined with previous event hash."""
        return hashlib.sha256((canonical_json + previous_hash).encode("utf-8")).hexdigest()

    @staticmethod
    async def get_latest_event_hash(session: AsyncSession, transaction_id: str) -> str:
        """Retrieve the latest audit event hash for a given transaction, falling back to GENESIS_HASH.

        Args:
            session: Active database session.
            transaction_id: Transaction UUID.

        Returns:
            SHA-256 hash string (64 characters).
        """
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.transaction_id == transaction_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        last_event = result.scalar_one_or_none()
        if last_event:
            return last_event.event_hash
        return GENESIS_HASH

    @classmethod
    async def record_event(
        cls,
        session: AsyncSession,
        transaction_id: str,
        event_type: str,
        actor: str,
        state_from: Optional[str] = None,
        state_to: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        previous_hash_override: Optional[str] = None,
    ) -> AuditEvent:
        """Record an append-only audit event with continuous SHA-256 hash chaining.

        Args:
            session: Active database session.
            transaction_id: Target transaction ID.
            event_type: Type of audit event (e.g. 'STATE_TRANSITION', 'POLICY_EVALUATION').
            actor: Subsystem or user initiating event.
            state_from: Prior state if state transition.
            state_to: Resulting state if state transition.
            details: Contextual details dictionary.
            created_at: Optional override timestamp.
            previous_hash_override: Optional explicit previous hash override.

        Returns:
            Persisted AuditEvent instance.
        """
        # Acquire row-level FOR UPDATE lock on authoritative Transaction row to serialize audit writes per transaction
        lock_stmt = select(Transaction.id).where(Transaction.id == transaction_id).with_for_update()
        lock_res = await session.execute(lock_stmt)
        if lock_res.scalar_one_or_none() is None:
            raise ValueError(f"Transaction '{transaction_id}' not found for audit recording.")

        previous_hash = previous_hash_override or await cls.get_latest_event_hash(session, transaction_id)
        audit_details = details or {}

        payload_dict = {
            "actor": actor,
            "details": audit_details,
            "event_type": event_type,
            "previous_hash": previous_hash,
            "state_from": state_from,
            "state_to": state_to,
            "transaction_id": transaction_id,
        }

        canonical_json = serialize_canonical_json(payload_dict)
        event_hash = cls.compute_event_hash(canonical_json, previous_hash)

        audit_record = AuditEvent(
            id=generate_uuid(),
            transaction_id=transaction_id,
            event_type=event_type,
            actor=actor,
            state_from=state_from,
            state_to=state_to,
            details=audit_details,
            previous_hash=previous_hash,
            event_hash=event_hash,
            created_at=created_at or current_utc_time(),
        )

        session.add(audit_record)
        return audit_record

    @classmethod
    async def verify_chain(
        cls,
        session: AsyncSession,
        transaction_id: str,
    ) -> Dict[str, Any]:
        """Cryptographically verify the audit hash chain integrity for a transaction.

        Args:
            session: Active database session.
            transaction_id: Target transaction ID to verify.

        Returns:
            Dictionary containing validation status (`valid: bool`), event count, and mismatch diagnostics.
        """
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.transaction_id == transaction_id)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        )
        result = await session.execute(stmt)
        events: List[AuditEvent] = list(result.scalars().all())

        if not events:
            return {
                "valid": True,
                "total_events": 0,
                "transaction_id": transaction_id,
                "latest_hash": GENESIS_HASH,
            }

        for idx, event in enumerate(events):
            # 1. Verify previous hash linkage
            if idx == 0:
                # First event must reference GENESIS_HASH or LEGACY_GENESIS_HASH
                if event.previous_hash not in (GENESIS_HASH, LEGACY_GENESIS_HASH):
                    return {
                        "valid": False,
                        "total_events": len(events),
                        "broken_at_index": idx,
                        "failed_event_id": event.id,
                        "reason": f"Invalid genesis previous_hash '{event.previous_hash}'. Expected '{GENESIS_HASH}'.",
                        "expected_previous_hash": GENESIS_HASH,
                        "actual_previous_hash": event.previous_hash,
                        "event_type": event.event_type,
                    }
            else:
                expected_prev = events[idx - 1].event_hash
                if event.previous_hash != expected_prev:
                    return {
                        "valid": False,
                        "total_events": len(events),
                        "broken_at_index": idx,
                        "failed_event_id": event.id,
                        "reason": f"Chain link broken at event index {idx}. Expected previous_hash '{expected_prev}', got '{event.previous_hash}'.",
                        "expected_previous_hash": expected_prev,
                        "actual_previous_hash": event.previous_hash,
                        "event_type": event.event_type,
                    }

            # 2. Re-verify event_hash calculation
            payload_dict = {
                "actor": event.actor,
                "details": event.details,
                "event_type": event.event_type,
                "previous_hash": event.previous_hash,
                "state_from": event.state_from,
                "state_to": event.state_to,
                "transaction_id": event.transaction_id,
            }
            canonical_json = serialize_canonical_json(payload_dict)
            expected_hash = cls.compute_event_hash(canonical_json, event.previous_hash)

            if event.event_hash != expected_hash:
                # Also check legacy formatting fallback for Step 7 compatibility
                legacy_payload = {
                    "transaction_id": event.transaction_id,
                    "state_from": event.state_from,
                    "state_to": event.state_to,
                    "actor": event.actor,
                    "details": event.details,
                    "previous_hash": event.previous_hash,
                }
                import json
                legacy_json = json.dumps(legacy_payload, sort_keys=True, default=str)
                legacy_hash = hashlib.sha256(legacy_json.encode("utf-8")).hexdigest()

                if event.event_hash != legacy_hash:
                    return {
                        "valid": False,
                        "total_events": len(events),
                        "broken_at_index": idx,
                        "failed_event_id": event.id,
                        "reason": f"Event hash payload tampered or corrupted at index {idx}.",
                        "expected_event_hash": expected_hash,
                        "actual_event_hash": event.event_hash,
                        "event_type": event.event_type,
                    }

        return {
            "valid": True,
            "total_events": len(events),
            "transaction_id": transaction_id,
            "latest_hash": events[-1].event_hash,
        }
