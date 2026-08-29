"""
RecoverAI - Expected Net Recovery Value (ENRV) Pydantic Schemas (Step 10)

Defines data models for action cost configurations, candidate action probability inputs,
ENRV calculation details per action, and decision ranking responses.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator


class ActionCostConfig(BaseModel):
    """Cost breakdown parameters for a specific recovery action type in minor units (paise)."""
    action_type: str = Field(..., description="Action classification identifier (e.g. PAYMENT_LINK, RECOVERY_MESSAGE)")
    intervention_cost_in_paise: int = Field(default=0, ge=0, description="Direct execution cost (e.g., gateway fee, SMS cost)")
    operational_cost_in_paise: int = Field(default=0, ge=0, description="Operational handling cost (e.g., notification overhead)")
    expected_refund_cost_in_paise: int = Field(default=0, ge=0, description="Expected refund or chargeback processing cost")

    @property
    def total_cost_in_paise(self) -> int:
        """Total action cost in paise."""
        return self.intervention_cost_in_paise + self.operational_cost_in_paise + self.expected_refund_cost_in_paise


class CandidateActionInput(BaseModel):
    """Input payload for a candidate recovery action evaluation."""
    action_type: str = Field(..., description="Candidate action identifier (e.g. PAYMENT_LINK, RETRY, WHATSAPP_REMINDER)")
    predicted_recovery_probability: float = Field(..., description="Predicted recovery probability P(R | X, a_i)")
    custom_intervention_cost_in_paise: Optional[int] = Field(default=None, ge=0, description="Optional override for intervention cost")
    custom_operational_cost_in_paise: Optional[int] = Field(default=None, ge=0, description="Optional override for operational cost")
    custom_expected_refund_cost_in_paise: Optional[int] = Field(default=None, ge=0, description="Optional override for refund cost")


class ENRVActionResult(BaseModel):
    """Detailed ENRV financial calculation result for a single candidate action."""
    action_type: str = Field(..., description="Action identifier")
    predicted_recovery_probability: float = Field(..., ge=0.0, le=1.0, description="Clamped recovery probability P(R | X, a_i)")
    amount_in_paise: int = Field(..., gt=0, description="Transaction amount in minor units (paise)")
    expected_gross_recovery_in_paise: int = Field(..., description="Expected gross recovery (P * amount) in paise")
    intervention_cost_in_paise: int = Field(..., ge=0, description="Intervention cost in paise")
    operational_cost_in_paise: int = Field(..., ge=0, description="Operational cost in paise")
    expected_refund_cost_in_paise: int = Field(..., ge=0, description="Expected refund cost in paise")
    total_cost_in_paise: int = Field(..., ge=0, description="Total costs in paise")
    expected_net_recovery_value_in_paise: int = Field(..., description="ENRV in paise (Gross Recovery - Total Cost)")
    expected_net_recovery_value_rupees: float = Field(..., description="ENRV converted to standard rupees")
    rank: int = Field(..., ge=1, description="Action rank (1 = highest ENRV)")


class ENRVCalculationRequest(BaseModel):
    """Request schema for evaluating and ranking candidate recovery actions."""
    transaction_id: str = Field(..., min_length=1, description="Unique transaction ID")
    merchant_id: Optional[str] = Field(default=None, description="Optional merchant ID for multi-tenant isolation")
    amount_in_paise: int = Field(..., gt=0, description="Transaction amount in minor units (paise)")
    candidate_actions: List[CandidateActionInput] = Field(..., min_length=1, description="List of candidate actions to evaluate")

    @field_validator("candidate_actions")
    @classmethod
    def validate_unique_action_types(cls, actions: List[CandidateActionInput]) -> List[CandidateActionInput]:
        seen = set()
        for act in actions:
            norm_action = act.action_type.upper().strip()
            if norm_action in seen:
                raise ValueError(f"Duplicate candidate action type in request: '{act.action_type}'")
            seen.add(norm_action)
        return actions


class ENRVCalculationResponse(BaseModel):
    """Response schema containing ranked ENRV candidate action results."""
    transaction_id: str = Field(..., description="Transaction ID evaluated")
    merchant_id: Optional[str] = Field(default=None, description="Merchant ID context")
    amount_in_paise: int = Field(..., gt=0, description="Transaction amount evaluated in paise")
    best_action: str = Field(..., description="Top-ranked candidate action by ENRV")
    max_enrv_in_paise: int = Field(..., description="Highest ENRV achieved in paise")
    max_enrv_rupees: float = Field(..., description="Highest ENRV achieved in rupees")
    action_results: List[ENRVActionResult] = Field(..., description="Ranked list of evaluated candidate actions")
