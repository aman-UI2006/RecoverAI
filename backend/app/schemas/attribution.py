"""
RecoverAI - Attribution Engine Schemas (Step 20)

Defines Pydantic data transfer objects and canonical status/method enums
for attribution evaluation and revenue accounting.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AttributionStatus(str, Enum):

    """Canonical attribution status categories."""

    ATTRIBUTED = "ATTRIBUTED"
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    UNATTRIBUTED = "UNATTRIBUTED"


class AttributionMethod(str, Enum):
    """Canonical attribution evaluation methods."""

    DIRECT_REFERENCE = "DIRECT_REFERENCE"
    WINDOW_MATCH = "WINDOW_MATCH"
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    UNATTRIBUTED = "UNATTRIBUTED"


class AttributionRequest(BaseModel):
    """Payload for evaluating transaction recovery attribution."""

    transaction_id: str = Field(..., description="UUID of the recovered transaction.")
    recovery_attempt_id: Optional[str] = Field(None, description="UUID of the RecoveryAttempt if available.")
    payment_id: Optional[str] = Field(None, description="Razorpay payment ID if available.")
    attribution_window_minutes: int = Field(
        default=4320,
        description="Attribution window threshold in minutes (default: 72 hours / 4320 minutes).",
    )


class AttributionResultResponse(BaseModel):
    """Response model representing a persisted RecoveryAttribution record."""

    id: str = Field(..., description="UUID of the attribution record.")
    transaction_id: str = Field(..., description="UUID of the transaction.")
    recovery_attempt_id: Optional[str] = Field(None, description="UUID of the recovery attempt.")
    recovery_source: str = Field(..., description="Source mode: REAL_TEST or SIMULATION.")
    attribution_status: str = Field(..., description="Classification: ATTRIBUTED, NATURAL_RECOVERY, UNATTRIBUTED.")
    attribution_method: str = Field(..., description="Method: DIRECT_REFERENCE, WINDOW_MATCH, NATURAL_RECOVERY, UNATTRIBUTED.")
    attribution_window_minutes: int = Field(..., description="Configured attribution window in minutes.")
    recovered_amount: float = Field(..., description="Authoritative recovered revenue amount.")
    refunded_amount: float = Field(default=0.0, description="Refunded amount if any.")
    intervention_timestamp: Optional[datetime] = Field(None, description="Timestamp of recovery attempt execution.")
    recovery_timestamp: datetime = Field(..., description="Timestamp when attribution was recorded.")
    is_duplicate: bool = Field(default=False, description="Flag indicating if this was an idempotent replay.")

    model_config = ConfigDict(from_attributes=True)

