"""
RecoverAI - Diagnosis Engine Pydantic Schemas (Step 11)

Defines data structures for failure root cause classification, diagnosis sources,
precedence routing results, and API request/response payloads.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiagnosisSource(str, Enum):
    """Precedence hierarchy sources for failure diagnosis."""
    RULE_ENGINE = "RULE_ENGINE"
    ML_CLASSIFIER = "ML_CLASSIFIER"
    LLM_FALLBACK = "LLM_FALLBACK"
    HUMAN_REVIEW_FALLBACK = "HUMAN_REVIEW_FALLBACK"


class FailureCategory(str, Enum):
    """Standardized failure categories across payment scenarios."""
    BANK_DECLINE = "BANK_DECLINE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    EXPIRED_CARD = "EXPIRED_CARD"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    TECHNICAL_TIMEOUT = "TECHNICAL_TIMEOUT"
    USER_ABANDONMENT = "USER_ABANDONMENT"
    UNKNOWN_DECLINE = "UNKNOWN_DECLINE"


class DiagnosisRequest(BaseModel):
    """Input payload for transaction failure root cause diagnosis."""
    transaction_id: str = Field(..., min_length=1, description="Unique transaction ID")
    merchant_id: Optional[str] = Field(default=None, description="Optional merchant ID for multi-tenant scoping")
    failure_code: str = Field(..., description="Raw or normalized decline error code")
    error_description: Optional[str] = Field(default=None, description="Detailed decline message")
    raw_payload: Optional[Dict[str, Any]] = Field(default=None, description="Raw event payload for LLM fallback analysis")
    feature_vector: Optional[List[float]] = Field(default=None, description="Extracted numerical features if available")


class DiagnosisResult(BaseModel):
    """Output schema carrying root cause diagnosis details and metadata."""
    transaction_id: str = Field(..., description="Transaction ID diagnosed")
    failure_code: str = Field(..., description="Decline error code evaluated")
    failure_category: str = Field(..., description="Standardized failure category")
    root_cause_explanation: str = Field(..., description="Human-readable root cause explanation")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score (0.0 to 1.0)")
    diagnosis_source: DiagnosisSource = Field(..., description="Precedence source used for diagnosis")
    requires_human_review: bool = Field(default=False, description="Flag set if confidence < 0.60 or fallback invoked")
