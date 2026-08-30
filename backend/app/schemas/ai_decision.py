"""
RecoverAI - AI Decision Context REST API Schemas

Defines structured responses for the GET /api/v1/ai-decisions/{id} read-only endpoint.
Synthesizes persisted DecisionContext, RecoveryActionScores, Diagnosis, AI Recommendation,
Capability Resolution, and Policy evaluation state for AI Decision Center UI transparency.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ActionScoreItem(BaseModel):
    """Action-conditional score item with financial ENRV calculations, capability status, and policy evaluation."""
    id: Optional[str] = Field(None, description="Score record UUID.")
    action: str = Field(..., description="Action classification identifier (e.g. PAYMENT_LINK, RETRY, WHATSAPP_REMINDER).")
    recovery_probability: float = Field(..., ge=0.0, le=1.0, description="Predicted recovery probability P(R | X, a_i).")
    expected_gross_recovery: float = Field(..., description="Expected gross recovery in INR.")
    intervention_cost: float = Field(..., description="Intervention cost in INR.")
    expected_net_recovery_value: float = Field(..., description="Expected net recovery value (ENRV) in INR.")
    rank: int = Field(..., ge=1, description="Rank ordered by ENRV descending.")
    capability_status: str = Field("SUPPORTED", description="Execution capability status (SUPPORTED / UNSUPPORTED).")
    policy_status: str = Field("APPROVED", description="Policy evaluation outcome (APPROVED / REJECTED / ESCALATE).")

    model_config = ConfigDict(from_attributes=True)


class AIDiagnosisSummary(BaseModel):
    """Root cause diagnosis summary for AI Decision Context."""
    id: str = Field(..., description="Diagnosis UUID.")
    failure_code: str = Field(..., description="Failure reason code.")
    failure_category: str = Field(..., description="Failure category taxonomy.")
    root_cause_explanation: str = Field(..., description="Human-readable root cause explanation.")
    confidence_score: float = Field(..., description="Diagnosis confidence score.")
    diagnosis_source: str = Field(..., description="Diagnosis source (RULES, ML, LLM, HUMAN).")
    created_at: datetime = Field(..., description="Diagnosis creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class AIRecommendationSummary(BaseModel):
    """Structured AI recommendation advisory payload."""
    recommended_action: str = Field(..., description="Recommended recovery action identifier.")
    rationale_text: str = Field(..., description="Diagnostic explanation supporting recommendation.")
    customer_message_template: str = Field(..., description="Personalized customer message template.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Recommendation confidence score.")


class PolicyEvaluationSummary(BaseModel):
    """Merchant policy rule evaluation outcome summary."""
    policy_version: str = Field("v1.0", description="Active policy version.")
    policy_status: str = Field("APPROVED", description="Policy evaluation outcome.")
    reason: str = Field("All policy rules satisfied", description="Policy evaluation rationale.")
    max_recovery_attempts: int = Field(3, description="Configured maximum recovery attempts limit.")
    max_auto_action_amount: float = Field(50000.0, description="Maximum threshold for automated execution in INR.")
    min_recovery_probability: float = Field(0.15, description="Minimum recovery probability threshold.")


class CapabilityEvaluationSummary(BaseModel):
    """Capability resolver evaluation outcome summary."""
    execution_mode: str = Field("SIMULATION", description="Active execution mode (REAL_TEST or SIMULATION).")
    is_executable: bool = Field(True, description="Whether top action is executable in active mode.")
    status: str = Field("SUPPORTED", description="Capability status classification.")
    reason: str = Field("Action supported", description="Capability evaluation reason.")


class AIDecisionResponse(BaseModel):
    """Comprehensive read-only AI Decision Context response."""
    transaction_id: str = Field(..., description="Transaction UUID.")
    merchant_id: str = Field(..., description="Merchant UUID.")
    decision_context_id: Optional[str] = Field(None, description="Decision context UUID if persisted.")
    model_version: str = Field("v1.0", description="ML model version used.")
    feature_version: str = Field("v1.0", description="Feature set version used.")
    policy_version: str = Field("v1.0", description="Policy rule version applied.")
    created_at: datetime = Field(..., description="Decision context timestamp.")
    top_action: Optional[str] = Field(None, description="Top-ranked action by ENRV.")
    best_enrv_rupees: Optional[float] = Field(None, description="Maximum ENRV achieved across candidates.")
    diagnosis: Optional[AIDiagnosisSummary] = Field(None, description="Transaction root cause diagnosis.")
    recommendation: Optional[AIRecommendationSummary] = Field(None, description="Structured AI recommendation details.")
    action_scores: List[ActionScoreItem] = Field(default_factory=list, description="Ranked candidate action scores.")
    policy_evaluation: Optional[PolicyEvaluationSummary] = Field(None, description="Policy rule evaluation summary.")
    capability_evaluation: Optional[CapabilityEvaluationSummary] = Field(None, description="Capability resolver summary.")

    model_config = ConfigDict(from_attributes=True)
