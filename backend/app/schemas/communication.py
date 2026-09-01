"""
RecoverAI - Customer Communication Schemas (Step 48)

Defines request and response payload schemas for tone-conditioned customer
recovery message generation and PII-masked preview generation.
"""

from typing import Optional
from pydantic import BaseModel, Field


class CommunicationRequest(BaseModel):
    """Request payload for generating customer communication template."""
    customer_id: str = Field(..., description="Customer identifier UUID or string.")
    scenario_type: str = Field(..., description="Failure scenario classification (e.g. SUBSCRIPTION_LAPSE, INSUFFICIENT_FUNDS).")
    failure_code: Optional[str] = Field(None, description="Specific failure reason code.")
    recommended_action: str = Field(default="PAYMENT_LINK", description="Recommended action strategy.")
    amount_rupees: float = Field(default=0.0, ge=0.0, description="Transaction amount in INR.")
    payment_link: Optional[str] = Field(None, description="Created Razorpay payment link URL if available.")
    preferred_channel: str = Field(default="SMS", description="Preferred communication channel (SMS, EMAIL, WHATSAPP).")
    preferred_language: str = Field(default="en", description="Target language code.")
    customer_segment: Optional[str] = Field(None, description="Customer segment classification (e.g. SUBSCRIPTION, VIP, RETAIL).")
    mode: str = Field(default="SIMULATION", description="Execution mode (REAL_TEST or SIMULATION).")


class CommunicationResponse(BaseModel):
    """Structured response payload containing tone-conditioned communication copy and PII-masked preview."""
    tone: str = Field(..., description="Selected message tone (Empathetic, Urgent, Informative, Direct).")
    channel: str = Field(..., description="Target communication channel (SMS, EMAIL, WHATSAPP).")
    raw_message_text: str = Field(..., description="Unmasked message text generated for system processing.")
    masked_preview_text: str = Field(..., description="PII-masked preview text for UI display.")
    payment_link_placeholder: str = Field(..., description="Razorpay Payment Link placeholder or short URL.")
    execution_mode: str = Field(..., description="Execution mode (REAL_TEST or SIMULATION).")
    is_sent: bool = Field(default=False, description="Whether message was dispatched externally (Always False in REAL_TEST content-only mode).")
    simulated_delivery_status: Optional[str] = Field(None, description="Simulated message delivery status (DELIVERED, PENDING, FAILED).")
    simulated_open_probability: Optional[float] = Field(None, description="Simulated engagement conversion probability.")
