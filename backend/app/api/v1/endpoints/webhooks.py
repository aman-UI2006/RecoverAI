"""
RecoverAI - Webhooks Ingestion Router (Step 5)

FastAPI router handling Razorpay webhooks with raw-body signature verification,
Application events, and Simulator events.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.events import (
    AppEventPayload,
    SimulatorEventPayload,
    IngestionResponse,
)
from backend.app.services.event_ingestion import EventIngestionService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/razorpay",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive and ingest Razorpay webhook events",
    description="Validates HMAC-SHA256 signature using raw request body bytes and ingests event idempotently.",
)
async def razorpay_webhook_endpoint(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(None, alias="X-Razorpay-Event-Id"),
    db: AsyncSession = Depends(get_db),
) -> IngestionResponse:
    """FastAPI endpoint processing Razorpay HTTP POST webhooks."""
    raw_body = await request.body()

    event, is_duplicate = await EventIngestionService.ingest_razorpay_webhook(
        session=db,
        raw_body=raw_body,
        signature_header=x_razorpay_signature,
        razorpay_event_id=x_razorpay_event_id,
    )

    status_str = "DUPLICATE_SKIPPED" if is_duplicate else "SUCCESS"
    message_str = "Event already ingested (idempotent skip)" if is_duplicate else "Razorpay webhook event successfully ingested"

    return IngestionResponse(
        status=status_str,
        event_id=event.id,
        event_source=event.event_source,
        event_type=event.event_type,
        idempotency_key=event.idempotency_key,
        message=message_str,
    )


@router.post(
    "/app-event",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive and ingest application events",
    description="Ingests application lifecycle events (e.g. checkout abandonment) idempotently.",
)
async def app_event_endpoint(
    payload: AppEventPayload,
    db: AsyncSession = Depends(get_db),
) -> IngestionResponse:
    """FastAPI endpoint processing Application events."""
    event, is_duplicate = await EventIngestionService.ingest_app_event(
        session=db,
        app_event=payload,
    )

    status_str = "DUPLICATE_SKIPPED" if is_duplicate else "SUCCESS"
    message_str = "App event already ingested (idempotent skip)" if is_duplicate else "Application event successfully ingested"

    return IngestionResponse(
        status=status_str,
        event_id=event.id,
        event_source=event.event_source,
        event_type=event.event_type,
        idempotency_key=event.idempotency_key,
        message=message_str,
    )


@router.post(
    "/simulator-event",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive and ingest simulator events",
    description="Ingests synthetic 50,000+ simulation events idempotently.",
)
async def simulator_event_endpoint(
    payload: SimulatorEventPayload,
    db: AsyncSession = Depends(get_db),
) -> IngestionResponse:
    """FastAPI endpoint processing Simulator events."""
    event, is_duplicate = await EventIngestionService.ingest_simulator_event(
        session=db,
        sim_event=payload,
    )

    status_str = "DUPLICATE_SKIPPED" if is_duplicate else "SUCCESS"
    message_str = "Simulator event already ingested (idempotent skip)" if is_duplicate else "Simulator event successfully ingested"

    return IngestionResponse(
        status=status_str,
        event_id=event.id,
        event_source=event.event_source,
        event_type=event.event_type,
        idempotency_key=event.idempotency_key,
        message=message_str,
    )
