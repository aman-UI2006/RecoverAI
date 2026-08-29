"""
RecoverAI — Policy Engine Schemas (Step 15)

Defines policy evaluation result schemas, statuses, and rejection reason codes.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class PolicyStatus(str, Enum):
    """Outcome of PolicyEngine evaluation."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class PolicyRejectionCode(str, Enum):
    """Reason codes for policy rule rejections."""
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    EXPLICIT_STOP = "EXPLICIT_STOP"
    MAX_ATTEMPTS_EXCEEDED = "MAX_ATTEMPTS_EXCEEDED"
    AMOUNT_EXCEEDS_CAP = "AMOUNT_EXCEEDS_CAP"
    MIN_PROBABILITY_NOT_MET = "MIN_PROBABILITY_NOT_MET"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    MERCHANT_POLICY_DISABLED = "MERCHANT_POLICY_DISABLED"


class PolicyEvaluationResult(BaseModel):
    """
    Structured result of PolicyEngine guardrail evaluation.
    Passed downstream to ActionExecutor (Step 17) or HumanReviewService (Step 16).
    """
    resolved_action: str = Field(
        ...,
        description="Action strategy evaluated by the policy engine."
    )
    status: PolicyStatus = Field(
        ...,
        description="Policy evaluation status (APPROVED, REJECTED, ESCALATED)."
    )
    is_approved: bool = Field(
        ...,
        description="True if all policy guardrails passed and action is approved for execution."
    )
    rejection_code: Optional[PolicyRejectionCode] = Field(
        default=None,
        description="Structured rejection reason code if policy failed."
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of rule decision."
    )
    policy_version: str = Field(
        default="v1.0",
        description="Version string of the policy engine rules applied."
    )
    applied_rules: List[str] = Field(
        default_factory=list,
        description="List of rule names evaluated during this policy check."
    )
    attempt_number: int = Field(
        default=1,
        description="Recovery attempt sequence number."
    )
