"""Step 18 — Razorpay DTO Schemas for RecoverAI.

Defines Data Transfer Objects for Razorpay REST API interactions
(e.g., POST /v1/payment_links) and Webhook payloads.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class PaymentLinkCustomer(BaseModel):
    """Customer contact details for payment link generation."""

    name: Optional[str] = Field(default=None, description="Customer full name")
    email: Optional[str] = Field(default=None, description="Customer email address")
    contact: Optional[str] = Field(default=None, description="Customer phone contact number")


class PaymentLinkNotify(BaseModel):
    """Notification dispatch settings for payment link."""

    sms: bool = Field(default=True, description="Send SMS notification")
    email: bool = Field(default=True, description="Send Email notification")


class PaymentLinkCreateRequest(BaseModel):
    """Request payload DTO for creating a Razorpay Payment Link (POST /v1/payment_links)."""

    amount: int = Field(..., gt=0, description="Amount in smallest currency unit (paise for INR)")
    currency: str = Field(default="INR", description="3-letter ISO currency code")
    accept_partial: bool = Field(default=False, description="Allow partial payments")
    first_min_partial_amount: Optional[int] = Field(default=None, description="First minimum partial amount in paise")
    description: Optional[str] = Field(default=None, description="Payment description")
    customer: Optional[PaymentLinkCustomer] = Field(default=None, description="Customer details")
    notify: Optional[PaymentLinkNotify] = Field(default_factory=PaymentLinkNotify, description="Notification channels")
    reminder_enable: bool = Field(default=True, description="Enable automatic payment reminders")
    notes: Dict[str, Any] = Field(default_factory=dict, description="Key-value key metadata for tracking")
    callback_url: Optional[str] = Field(default=None, description="Redirect URL upon payment completion")
    callback_method: Optional[str] = Field(default=None, description="Callback HTTP method (e.g., 'get')")
    reference_id: str = Field(..., description="Unique reference ID formatted as RAI-{short_tx_id}-{recovery_cycle}")

    model_config = ConfigDict(extra="ignore")


class PaymentLinkCreateResponse(BaseModel):
    """Response payload DTO from Razorpay Payment Link creation (POST /v1/payment_links)."""

    id: str = Field(..., description="Razorpay Payment Link ID (e.g. plink_1234567890)")
    entity: str = Field(default="payment_link", description="Entity type")
    short_url: str = Field(..., description="Shortened URL for checkout payment link")
    status: str = Field(..., description="Payment link status (e.g. created, paid, expired)")
    amount: int = Field(..., description="Target amount in paise")
    amount_paid: int = Field(default=0, description="Amount paid in paise")
    currency: str = Field(default="INR", description="Currency code")
    customer: Optional[Any] = Field(default=None, description="Customer details or empty array")
    reference_id: Optional[str] = Field(default=None, description="Unique reference ID")
    created_at: int = Field(..., description="Unix timestamp of creation")
    notes: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata notes")

    model_config = ConfigDict(extra="ignore")


class RazorpayErrorDetail(BaseModel):
    """Structured error object returned by Razorpay API on HTTP errors."""

    code: str = Field(..., description="Error code")
    description: str = Field(..., description="Human readable description")
    source: Optional[str] = Field(default=None, description="Error source")
    step: Optional[str] = Field(default=None, description="Error step")
    reason: Optional[str] = Field(default=None, description="Error reason")
    field: Optional[str] = Field(default=None, description="Field causing error")


class RazorpayErrorResponse(BaseModel):
    """Top-level error response payload from Razorpay REST API."""

    error: RazorpayErrorDetail

    model_config = ConfigDict(extra="ignore")
