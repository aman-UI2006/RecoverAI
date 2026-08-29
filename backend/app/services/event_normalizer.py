"""
RecoverAI - Event Normalization and Deduplication Service (Step 6)

Normalizes multi-source raw ingested events into canonical NormalizedEvent representations
and enforces dual-layer deduplication (PostgreSQL ACID boundary + optional Redis fast-path).
"""

import logging
from datetime import datetime, timezone
from typing import Tuple, Optional, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Event
from backend.app.schemas.canonical_event import NormalizedEvent

logger = logging.getLogger("recoverai.event_normalizer")


class EventNormalizerService:
    """Service for canonical event normalization and database/Redis deduplication."""

    @staticmethod
    def normalize(event: Event) -> NormalizedEvent:
        """
        Normalizes a raw database Event into a canonical NormalizedEvent.

        Args:
            event: Raw SQLAlchemy Event model record.

        Returns:
            NormalizedEvent: Standardized canonical domain event object.
        """
        payload = event.payload or {}
        event_source = event.event_source
        raw_type = event.event_type

        merchant_id: Optional[str] = None
        customer_id: Optional[str] = None
        transaction_id: Optional[str] = None
        amount_in_paise: Optional[int] = None
        currency: str = "INR"
        scenario: Optional[str] = None
        normalized_type: str = raw_type.upper().replace(".", "_")

        if event_source == "RAZORPAY_WEBHOOK":
            account_id = payload.get("account_id")
            merchant_id = account_id if account_id else None

            # Handle payload contents (payment entity or payment_link entity)
            payload_body = payload.get("payload", {})
            if "payment" in payload_body:
                payment_entity = payload_body["payment"].get("entity", {})
                amount_in_paise = payment_entity.get("amount")
                currency = payment_entity.get("currency", "INR")
                transaction_id = payment_entity.get("order_id") or payment_entity.get("id")
                
                if raw_type == "payment.failed":
                    scenario = "PAYMENT_FAILURE"
                elif raw_type == "payment.captured":
                    scenario = "PAYMENT_CAPTURED"
                    
            elif "payment_link" in payload_body:
                plink_entity = payload_body["payment_link"].get("entity", {})
                amount_in_paise = plink_entity.get("amount")
                currency = plink_entity.get("currency", "INR")
                transaction_id = plink_entity.get("reference_id") or plink_entity.get("id")
                
                if raw_type == "payment_link.paid":
                    scenario = "PAYMENT_LINK_PAID"

        elif event_source == "APP_EVENT":
            merchant_id = payload.get("merchant_id")
            customer_id = payload.get("customer_id")
            transaction_id = payload.get("transaction_id")
            amount_in_paise = payload.get("amount_in_paise")
            currency = payload.get("currency", "INR")
            
            if raw_type in ("checkout.abandoned", "CHECKOUT_ABANDONED"):
                scenario = "CHECKOUT_ABANDONMENT"
            elif raw_type in ("receivable.overdue", "OVERDUE_RECEIVABLE"):
                scenario = "OVERDUE_RECEIVABLE"
            else:
                scenario = raw_type.upper()

        elif event_source == "SIMULATOR":
            transaction_id = payload.get("transaction_id")
            scenario = payload.get("scenario")
            amount_in_paise = payload.get("amount_in_paise")

        occurred_at = event.created_at if event.created_at is not None else datetime.now(timezone.utc)

        return NormalizedEvent(
            raw_event_id=event.id,
            idempotency_key=event.idempotency_key,
            razorpay_event_id=event.razorpay_event_id,
            event_source=event_source,
            event_type=normalized_type,
            merchant_id=merchant_id,
            customer_id=customer_id,
            transaction_id=transaction_id,
            amount_in_paise=amount_in_paise,
            currency=currency,
            scenario=scenario,
            normalized_payload=payload,
            occurred_at=occurred_at,
            is_duplicate=False,
        )

    @classmethod
    async def process_and_deduplicate(
        cls,
        session: AsyncSession,
        event: Event,
        redis_client: Optional[Any] = None,
    ) -> Tuple[NormalizedEvent, bool]:
        """
        Normalizes an event and enforces hard deduplication via Redis fast-path and PostgreSQL fallback.

        Args:
            session: Async DB session.
            event: Event record.
            redis_client: Optional Redis client instance.

        Returns:
            Tuple[NormalizedEvent, bool]: (NormalizedEvent instance, is_duplicate flag)
        """
        dedup_identifier = event.razorpay_event_id or event.idempotency_key
        redis_key = f"dedup:{event.event_source.lower()}:{dedup_identifier}"
        is_duplicate = False

        # 1. Fast-Path Redis Deduplication (if redis_client provided & connected)
        if redis_client is not None:
            try:
                already_seen = await redis_client.exists(redis_key)
                if already_seen:
                    logger.info(f"Deduplication skip via Redis fast-path for key: {redis_key}")
                    is_duplicate = True
            except Exception as e:
                logger.warning(f"Redis fast-path error (falling back to PostgreSQL correctness boundary): {str(e)}")

        # 2. PostgreSQL Correctness Boundary Deduplication
        if not is_duplicate:
            stmt = select(Event).where(
                (Event.idempotency_key == event.idempotency_key)
                & (Event.id != event.id)
            )
            result = await session.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                logger.info(f"Deduplication skip via PostgreSQL boundary for idempotency_key: {event.idempotency_key}")
                is_duplicate = True

        # 3. If novel and Redis available, register in Redis cache (24h TTL)
        if not is_duplicate and redis_client is not None:
            try:
                await redis_client.set(redis_key, "1", ex=86400)
            except Exception as e:
                logger.warning(f"Failed to populate Redis dedup cache key {redis_key}: {str(e)}")

        normalized_event = cls.normalize(event)
        normalized_event.is_duplicate = is_duplicate

        return normalized_event, is_duplicate
