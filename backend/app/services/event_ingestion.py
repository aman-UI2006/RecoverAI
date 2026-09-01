"""
RecoverAI - Event Ingestion Service (Step 5)

Ingests external events from Razorpay Webhooks, Application Events, and Simulator,
enforces HMAC SHA-256 webhook signature verification, validates Pydantic schemas,
and guarantees DB-level event idempotency and persistence.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Tuple, Optional, Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import settings
from backend.app.models.domain import Event
from backend.app.schemas.events import (
    RazorpayWebhookPayload,
    AppEventPayload,
    SimulatorEventPayload,
)


def verify_razorpay_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """
    Validates Razorpay Webhook HMAC-SHA256 signature against raw HTTP request body bytes.

    Args:
        raw_body: Exact raw HTTP request body bytes.
        signature_header: Received 'X-Razorpay-Signature' header value.
        secret: Optional override secret (defaults to settings.RAZORPAY_WEBHOOK_SECRET).

    Returns:
        bool: True if signature matches, False otherwise.
    """
    if not signature_header or not raw_body:
        return False

    webhook_secret = secret or settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        return False

    computed_hash = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_hash, signature_header)


class EventIngestionService:
    """Service providing event ingestion, signature validation, and idempotent storage."""

    @staticmethod
    async def ingest_razorpay_webhook(
        session: AsyncSession,
        raw_body: bytes,
        signature_header: Optional[str],
        razorpay_event_id: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ) -> Tuple[Event, bool]:
        """
        Ingests a raw Razorpay webhook request.

        Args:
            session: Async DB session.
            raw_body: Raw request body bytes.
            signature_header: 'X-Razorpay-Signature' header.
            razorpay_event_id: Unique event ID from 'X-Razorpay-Event-Id' header.
            webhook_secret: Optional override secret.

        Returns:
            Tuple[Event, bool]: (Event instance, is_duplicate)

        Raises:
            HTTPException: 401 Unauthorized if signature invalid.
            HTTPException: 400 Bad Request if JSON malformed.
        """
        # 1. HMAC SHA-256 signature check
        if not verify_razorpay_signature(raw_body, signature_header, secret=webhook_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Razorpay webhook signature",
            )

        # 2. Raw JSON parsing
        try:
            parsed_json = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON payload in webhook body",
            )

        # 3. Pydantic schema validation
        try:
            webhook_payload = RazorpayWebhookPayload.model_validate(parsed_json)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schema validation error for Razorpay webhook: {str(e)}",
            )

        # Extract event descriptors
        event_type = webhook_payload.event

        # Authoritative Razorpay event ID comes exclusively from X-Razorpay-Event-Id header
        if razorpay_event_id:
            idempotency_key = f"razorpay:{razorpay_event_id}"
        else:
            body_hash = hashlib.sha256(raw_body).hexdigest()[:16]
            idempotency_key = f"razorpay:{event_type}:{body_hash}"

        # 4. Check for duplicate event in database
        stmt = select(Event).where(
            (Event.idempotency_key == idempotency_key)
            | (Event.razorpay_event_id == razorpay_event_id) if razorpay_event_id else (Event.idempotency_key == idempotency_key)
        )
        result = await session.execute(stmt)
        existing_event = result.scalars().first()

        if existing_event:
            return (existing_event, True)

        # 5. Create new Event record
        new_event = Event(
            event_type=event_type,
            event_source="RAZORPAY_WEBHOOK",
            payload=parsed_json,
            idempotency_key=idempotency_key,
            razorpay_event_id=razorpay_event_id,
            created_at=datetime.now(timezone.utc),
        )

        session.add(new_event)
        try:
            await session.commit()
            try:
                await session.refresh(new_event)
            except Exception:
                pass
        except IntegrityError:
            await session.rollback()
            result = await session.execute(stmt)
            existing_event = result.scalars().first()
            if existing_event:
                return (existing_event, True)
            raise

        return (new_event, False)

    @staticmethod
    async def ingest_app_event(
        session: AsyncSession,
        app_event: AppEventPayload,
    ) -> Tuple[Event, bool]:
        """
        Ingests an Application Event (e.g. checkout abandonment, payment failure trigger).

        Args:
            session: Async DB session.
            app_event: Validated AppEventPayload model.

        Returns:
            Tuple[Event, bool]: (Event instance, is_duplicate)
        """
        payload_dict = app_event.model_dump()
        payload_hash = hashlib.sha256(
            json.dumps(payload_dict, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        idempotency_key = (
            f"app:{app_event.merchant_id}:{app_event.customer_id}:"
            f"{app_event.event_type}:{app_event.transaction_id or payload_hash}"
        )

        # Deduplication check
        stmt = select(Event).where(Event.idempotency_key == idempotency_key)
        result = await session.execute(stmt)
        existing_event = result.scalars().first()

        if existing_event:
            return (existing_event, True)

        new_event = Event(
            transaction_id=app_event.transaction_id,
            event_type=app_event.event_type,
            event_source="APP_EVENT",
            payload=payload_dict,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )

        session.add(new_event)
        await session.commit()
        await session.refresh(new_event)

        return (new_event, False)

    @staticmethod
    async def ingest_simulator_event(
        session: AsyncSession,
        sim_event: SimulatorEventPayload,
    ) -> Tuple[Event, bool]:
        """
        Ingests a Simulator Event.

        Args:
            session: Async DB session.
            sim_event: Validated SimulatorEventPayload model.

        Returns:
            Tuple[Event, bool]: (Event instance, is_duplicate)
        """
        payload_dict = sim_event.model_dump()
        idempotency_key = f"sim:{sim_event.transaction_id}:{sim_event.event_type}"

        # Deduplication check
        stmt = select(Event).where(Event.idempotency_key == idempotency_key)
        result = await session.execute(stmt)
        existing_event = result.scalars().first()

        if existing_event:
            return (existing_event, True)

        new_event = Event(
            transaction_id=sim_event.transaction_id,
            event_type=sim_event.event_type,
            event_source="SIMULATOR",
            payload=payload_dict,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )

        session.add(new_event)
        await session.commit()
        await session.refresh(new_event)

        return (new_event, False)
