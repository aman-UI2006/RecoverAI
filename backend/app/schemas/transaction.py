"""
RecoverAI - Transaction REST API Schemas (Step 25)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TransactionResponse(BaseModel):
    """Base response schema for a single Transaction."""
    id: str = Field(..., description="Transaction UUID.")
    merchant_id: str = Field(..., description="Merchant UUID.")
    customer_id: str = Field(..., description="Customer UUID.")
    razorpay_payment_id: Optional[str] = Field(None, description="Razorpay payment ID.")
    razorpay_order_id: Optional[str] = Field(None, description="Razorpay order ID.")
    razorpay_payment_link_id: Optional[str] = Field(None, description="Razorpay payment link ID.")
    razorpay_subscription_id: Optional[str] = Field(None, description="Razorpay subscription ID.")
    razorpay_invoice_id: Optional[str] = Field(None, description="Razorpay invoice ID.")
    amount: float = Field(..., description="Transaction amount in INR.")
    currency: str = Field(default="INR", description="Currency code.")
    status: str = Field(..., description="Authoritative transaction lifecycle status.")
    scenario_type: str = Field(..., description="Failure scenario classification.")
    retry_count: int = Field(default=0, description="Retry attempt counter.")
    recovery_cycle: int = Field(default=1, description="Recovery cycle counter.")
    mode: str = Field(default="SIMULATION", description="Execution mode (REAL_TEST or SIMULATION).")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")

    model_config = ConfigDict(from_attributes=True)


class DiagnosisSummary(BaseModel):
    """Summary of root cause diagnosis for transaction."""
    id: str = Field(..., description="Diagnosis UUID.")
    failure_code: str = Field(..., description="Failure reason code.")
    failure_category: str = Field(..., description="Failure category taxonomy.")
    root_cause_explanation: str = Field(..., description="Human-readable root cause explanation.")
    confidence_score: float = Field(..., description="Diagnosis confidence score.")
    diagnosis_source: str = Field(..., description="Diagnosis source (RULES, ML, LLM, HUMAN).")
    created_at: datetime = Field(..., description="Diagnosis timestamp.")

    model_config = ConfigDict(from_attributes=True)


class RecoveryAttemptSummary(BaseModel):
    """Summary of recovery attempt execution."""
    id: str = Field(..., description="Attempt UUID.")
    logical_operation_key: str = Field(..., description="Unique logical operation key.")
    recommended_action: str = Field(..., description="Action strategy executed.")
    policy_status: str = Field(..., description="Policy evaluation outcome.")
    execution_status: str = Field(..., description="Execution status (PENDING, EXECUTING, SUCCESS, FAILURE, UNKNOWN).")
    external_resource_type: str = Field(..., description="Type of external resource.")
    razorpay_payment_link_id: Optional[str] = Field(None, description="Created Razorpay Payment Link ID.")
    razorpay_reference_id: Optional[str] = Field(None, description="Custom reference ID.")
    generated_message_text: Optional[str] = Field(None, description="Generated recovery message text preview.")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp.")
    created_at: datetime = Field(..., description="Record creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class RecoveryAttributionSummary(BaseModel):
    """Summary of recovery attribution record."""
    id: str = Field(..., description="Attribution UUID.")
    recovery_source: str = Field(..., description="Source mode (REAL_TEST or SIMULATION).")
    attribution_status: str = Field(..., description="Status (ATTRIBUTED, UNATTRIBUTED, NATURAL_RECOVERY).")
    attribution_method: str = Field(..., description="Method classification.")
    recovered_amount: float = Field(..., description="Attributed recovered amount in INR.")
    refunded_amount: float = Field(default=0.0, description="Refunded amount in INR.")
    recovery_timestamp: datetime = Field(..., description="Timestamp of recovery.")

    model_config = ConfigDict(from_attributes=True)


class AuditTimelineItem(BaseModel):
    """Audit event item for transaction lifecycle timeline."""
    id: str = Field(..., description="Audit event UUID.")
    event_type: str = Field(..., description="Lifecycle event type.")
    actor: str = Field(..., description="System actor or component.")
    state_from: Optional[str] = Field(None, description="Previous state.")
    state_to: Optional[str] = Field(None, description="Target state.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured event payload.")
    event_hash: str = Field(..., description="Cryptographic SHA-256 event hash.")
    created_at: datetime = Field(..., description="Event timestamp.")

    model_config = ConfigDict(from_attributes=True)


class TransactionDetailResponse(TransactionResponse):
    """Detailed transaction view including customer info, diagnosis, attempts, attributions, and audit timeline."""
    customer_email: Optional[str] = Field(None, description="Customer email address.")
    diagnosis: Optional[DiagnosisSummary] = Field(None, description="Latest root cause diagnosis.")
    recovery_attempts: List[RecoveryAttemptSummary] = Field(default_factory=list, description="List of recovery attempts.")
    recovery_attributions: List[RecoveryAttributionSummary] = Field(default_factory=list, description="List of attributions.")
    audit_timeline: List[AuditTimelineItem] = Field(default_factory=list, description="Chronological audit timeline.")


class TransactionPaginatedResponse(BaseModel):
    """Paginated list response for transactions."""
    total: int = Field(..., description="Total matching transaction count.")
    page: int = Field(..., description="Current page index.")
    limit: int = Field(..., description="Page size limit.")
    items: List[TransactionResponse] = Field(..., description="Transaction list items.")
