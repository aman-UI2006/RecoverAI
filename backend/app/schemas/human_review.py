"""
RecoverAI - Step 16: Human Review and Escalation Schemas
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class HumanReviewDecision(str, Enum):
    APPROVE_OVERRIDE = "APPROVE_OVERRIDE"
    REJECT_PERMANENT = "REJECT_PERMANENT"


class HumanReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ReviewItemCreate(BaseModel):
    transaction_id: str = Field(..., description="UUID of transaction requiring human review")
    reason: str = Field(..., description="Escalation reason code or details")
    reviewer_notes: Optional[str] = Field(None, description="Optional initial reviewer notes")


class ReviewDecisionSubmit(BaseModel):
    decision: HumanReviewDecision = Field(..., description="Reviewer decision: APPROVE_OVERRIDE or REJECT_PERMANENT")
    reviewer_id: str = Field(..., description="ID or email of human reviewer")
    notes: Optional[str] = Field(None, description="Reviewer notes/rationale")


class HumanReviewResponse(BaseModel):
    id: str = Field(..., description="UUID of human review record")
    transaction_id: str = Field(..., description="UUID of transaction")
    merchant_id: str = Field(..., description="Merchant ID associated with transaction")
    status: str = Field(..., description="Review item status: PENDING, APPROVED, REJECTED, EXPIRED")
    reason: str = Field(..., description="Escalation reason code or description")
    reviewer_id: Optional[str] = Field(None, description="ID of reviewer if resolved")
    decision: Optional[str] = Field(None, description="Decision code if resolved")
    notes: Optional[str] = Field(None, description="Notes recorded during resolution")
    reviewed_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    # Context fields from transaction
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Transaction currency")
    scenario_type: str = Field(..., description="Failure scenario type")
    mode: str = Field(..., description="Operational mode: REAL_TEST or SIMULATION")


class HumanReviewQueueResponse(BaseModel):
    items: List[HumanReviewResponse] = Field(default_factory=list, description="List of review items")
    count: int = Field(..., description="Total review items count")
