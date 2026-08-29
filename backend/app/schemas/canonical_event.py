"""
RecoverAI - Canonical Event Schema (Step 6)

Defines standardized Pydantic v2 domain schemas for normalized events
ingested across Razorpay Webhooks, Application Events, and Simulator Events.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class NormalizedEvent(BaseModel):
    """Canonical domain representation of an ingested event."""
    model_config = ConfigDict(extra="ignore")

    raw_event_id: str = Field(..., description="UUID of raw record in events table")
    idempotency_key: str = Field(..., description="Authoritative unique idempotency key")
    razorpay_event_id: Optional[str] = Field(None, description="Unique Razorpay event header ID if source is Razorpay")
    event_source: str = Field(..., description="Canonical source: RAZORPAY_WEBHOOK, APP_EVENT, or SIMULATOR")
    event_type: str = Field(..., description="Standardized event type string (e.g. PAYMENT_FAILED, CHECKOUT_ABANDONED)")
    merchant_id: Optional[str] = Field(None, description="Associated merchant ID")
    customer_id: Optional[str] = Field(None, description="Associated customer ID")
    transaction_id: Optional[str] = Field(None, description="Associated transaction ID")
    amount_in_paise: Optional[int] = Field(None, description="Monetary amount in paise / minor units")
    currency: str = Field("INR", description="Currency code")
    scenario: Optional[str] = Field(None, description="Mapped scenario type (e.g. PAYMENT_FAILURE, CHECKOUT_ABANDONMENT)")
    normalized_payload: Dict[str, Any] = Field(default_factory=dict, description="Normalized context metadata payload")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when event occurred")
    is_duplicate: bool = Field(False, description="Flag indicating if event was identified as a duplicate")
