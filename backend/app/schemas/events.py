"""
RecoverAI - Event Pydantic Schemas (Step 5)

Defines event payload schemas for Razorpay Webhooks, Application Events,
and Simulator Events with strict Pydantic v2 validation.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class RazorpayPaymentEntity(BaseModel):
    """Pydantic model representing payment entity inside Razorpay webhook payload."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Razorpay payment ID (e.g. pay_12345)")
    entity: str = Field("payment", description="Entity type")
    amount: int = Field(..., description="Monetary amount in paise")
    currency: str = Field("INR", description="Currency code")
    status: str = Field(..., description="Payment status (e.g. failed, captured, authorized)")
    order_id: Optional[str] = Field(None, description="Razorpay order ID")
    invoice_id: Optional[str] = Field(None, description="Razorpay invoice ID")
    international: Optional[bool] = Field(False, description="International transaction flag")
    method: Optional[str] = Field(None, description="Payment method (e.g. card, netbanking, upi)")
    amount_refunded: Optional[int] = Field(0, description="Amount refunded in paise")
    refund_status: Optional[str] = Field(None, description="Refund status")
    captured: Optional[bool] = Field(False, description="Capture status")
    description: Optional[str] = Field(None, description="Payment description")
    card_id: Optional[str] = Field(None, description="Card ID")
    bank: Optional[str] = Field(None, description="Bank code")
    wallet: Optional[str] = Field(None, description="Wallet name")
    vpa: Optional[str] = Field(None, description="UPI Virtual Payment Address")
    email: Optional[str] = Field(None, description="Customer email")
    contact: Optional[str] = Field(None, description="Customer phone number")
    error_code: Optional[str] = Field(None, description="Razorpay failure error code")
    error_description: Optional[str] = Field(None, description="Failure description")
    error_source: Optional[str] = Field(None, description="Failure source")
    error_step: Optional[str] = Field(None, description="Failure step")
    error_reason: Optional[str] = Field(None, description="Failure reason")
    created_at: Optional[int] = Field(None, description="Unix timestamp")


class RazorpayPaymentLinkEntity(BaseModel):
    """Pydantic model representing payment link entity inside Razorpay webhook payload."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Razorpay payment link ID (e.g. plink_12345)")
    entity: str = Field("payment_link", description="Entity type")
    amount: int = Field(..., description="Link amount in paise")
    amount_paid: Optional[int] = Field(0, description="Amount paid in paise")
    currency: str = Field("INR", description="Currency code")
    status: str = Field(..., description="Link status (e.g. paid, active, expired)")
    reference_id: Optional[str] = Field(None, description="Merchant reference ID")
    short_url: Optional[str] = Field(None, description="Payment short link URL")
    created_at: Optional[int] = Field(None, description="Unix timestamp")


class RazorpayWebhookPayload(BaseModel):
    """Outer envelope for raw Razorpay Webhook requests."""
    model_config = ConfigDict(extra="ignore")

    entity: str = Field("event", description="Outer entity descriptor")
    account_id: Optional[str] = Field(None, description="Razorpay merchant account ID")
    event: str = Field(..., description="Razorpay event type (e.g. payment.failed, payment_link.paid)")
    event_id: Optional[str] = Field(None, description="Unique Razorpay webhook event ID")
    contains: Optional[List[str]] = Field(default_factory=list, description="Entity list contained in payload")
    payload: Dict[str, Any] = Field(..., description="Nested payload object containing payment/link entity")
    created_at: Optional[int] = Field(None, description="Unix timestamp of event generation")


class AppEventPayload(BaseModel):
    """Payload model for application-driven failure events (e.g. checkout abandonment)."""
    model_config = ConfigDict(extra="ignore")

    event_type: str = Field(..., description="Event type (e.g. checkout.abandoned, receivable.overdue)")
    merchant_id: str = Field(..., description="Merchant identifier")
    customer_id: str = Field(..., description="Customer identifier")
    amount_in_paise: int = Field(..., description="Monetary amount in minor units / paise")
    currency: str = Field("INR", description="Currency code")
    transaction_id: Optional[str] = Field(None, description="Associated transaction ID if known")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context metadata")


class SimulatorEventPayload(BaseModel):
    """Payload model for 50,000+ simulation engine events."""
    model_config = ConfigDict(extra="ignore")

    event_type: str = Field(..., description="Simulator event type (e.g. simulator.transaction_event)")
    transaction_id: str = Field(..., description="Transaction identifier")
    scenario: str = Field(..., description="Scenario type (PAYMENT_FAILURE, CHECKOUT_ABANDONMENT, etc.)")
    amount_in_paise: int = Field(..., description="Monetary amount in paise")
    payload_data: Dict[str, Any] = Field(default_factory=dict, description="Full synthetic transaction record")


class IngestionResponse(BaseModel):
    """Standardized API response payload for event ingestion endpoints."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Ingestion status (e.g. SUCCESS, DUPLICATE_SKIPPED, REJECTED)")
    event_id: str = Field(..., description="Persisted Event UUID")
    event_source: str = Field(..., description="Event source descriptor")
    event_type: str = Field(..., description="Event type descriptor")
    idempotency_key: str = Field(..., description="Computed idempotency key")
    message: str = Field(..., description="Status summary message")
