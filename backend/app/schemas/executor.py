"""Schemas for RecoverAI Step 17 Action Executor."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionExecutionRequest(BaseModel):
    """Schema for requesting execution of a policy-approved recovery action."""

    transaction_id: str = Field(..., description="UUID of target transaction to execute recovery for")
    merchant_id: str = Field(..., description="UUID of initiating merchant for multi-tenant isolation")
    decision_context_id: Optional[str] = Field(None, description="Optional UUID of decision context")
    action_type: str = Field(..., description="Approved recovery action type (e.g., PAYMENT_LINK)")
    action_payload: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters payload")
    mode_override: Optional[str] = Field(None, description="Optional execution mode override (REAL_TEST or SIMULATION)")


class ActionExecutionResponse(BaseModel):
    """Schema for Action Executor execution result."""

    execution_id: str = Field(..., description="UUID of recorded RecoveryAttempt")
    transaction_id: str = Field(..., description="UUID of target transaction")
    merchant_id: str = Field(..., description="UUID of merchant")
    logical_operation_key: str = Field(..., description="Canonical merchant_id:transaction_id:recovery_cycle:action key")
    action_type: str = Field(..., description="Executed recovery action type")
    execution_status: str = Field(..., description="Execution status (PENDING, EXECUTING, SUCCESS, FAILURE, UNKNOWN)")
    external_resource_type: str = Field(..., description="Execution mode or resource type (REAL_TEST, SIMULATION)")
    external_resource_id: Optional[str] = Field(None, description="External resource ID if created")
    razorpay_payment_link_id: Optional[str] = Field(None, description="Razorpay Payment Link ID if created")
    razorpay_reference_id: Optional[str] = Field(None, description="Razorpay reference ID if created")
    audit_event_id: str = Field(..., description="SHA-256 chained audit event ID from state transition")
    executed_at: datetime = Field(..., description="Timestamp when execution occurred")
    is_duplicate: bool = Field(False, description="True if idempotently replaying an existing execution attempt")
