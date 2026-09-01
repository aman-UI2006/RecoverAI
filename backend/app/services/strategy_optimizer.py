"""
RecoverAI - Strategy Optimizer Service (Step 43)

Refines Expected Net Recovery Value (ENRV) calculations using multi-objective optimization:
- Evaluates long-term merchant profitability by integrating customer Lifetime Value (LTV) and churn risk.
- Formulates Churn Risk Penalty: Penalty = ChurnRisk * CustomerLTV * AggressivenessWeight(Action).
- Optimized ENRV = Base ENRV - Churn Risk Penalty.
- Prioritizes soft nudges (RECOVERY_MESSAGE, WHATSAPP_REMINDER) over high-friction interventions
  (RETRY, MANUAL_OUTREACH) for high-LTV / high-churn-risk customers.
- Gracefully falls back to neutral base ENRV ranking if LTV or churn risk parameters are missing.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.enrv import (
    CandidateActionInput,
    ENRVActionResult,
    ENRVCalculationRequest,
    ENRVCalculationResponse,
)
from backend.app.services.enrv_calculator import ENRVCalculator

logger = logging.getLogger("recoverai.strategy_optimizer")

# Action Aggressiveness Weights (0.0 = zero friction, 1.0 = maximum aggressive outreach)
ACTION_AGGRESSIVENESS_WEIGHTS: Dict[str, float] = {
    "MANUAL_OUTREACH": 1.0,      # Highest friction / agent disturbance
    "RETRY": 0.8,                # High friction / gateway retry attempts
    "PAYMENT_LINK": 0.4,         # Moderate friction / explicit payment request
    "WHATSAPP_REMINDER": 0.2,    # Low friction / soft messaging
    "RECOVERY_MESSAGE": 0.1,     # Very low friction / soft nudge
    "NO_ACTION": 0.0,            # Zero friction
}


class OptimizedActionResult(BaseModel):
    """Result schema for multi-objective strategy optimization of a single recovery action."""
    action_type: str = Field(..., description="Action identifier")
    predicted_recovery_probability: float = Field(..., description="Recovery probability P(R | X, a)")
    base_enrv_in_paise: int = Field(..., description="Base ENRV before LTV churn penalty in paise")
    base_enrv_rupees: float = Field(..., description="Base ENRV in rupees")
    churn_risk_score: float = Field(..., description="Customer churn risk score [0.0, 1.0]")
    customer_ltv_rupees: float = Field(..., description="Customer lifetime value in rupees")
    aggressiveness_weight: float = Field(..., description="Action friction/aggressiveness weight")
    churn_penalty_in_paise: int = Field(..., description="Calculated churn risk penalty in paise")
    churn_penalty_rupees: float = Field(..., description="Calculated churn risk penalty in rupees")
    optimized_enrv_in_paise: int = Field(..., description="Multi-objective optimized ENRV in paise")
    optimized_enrv_rupees: float = Field(..., description="Multi-objective optimized ENRV in rupees")
    rank: int = Field(..., ge=1, description="Final optimized rank (1 = highest optimized ENRV)")
    is_soft_nudge: bool = Field(..., description="Flag indicating if action is classified as a soft nudge")


class StrategyOptimizationRequest(BaseModel):
    """Request schema for strategy optimization."""
    transaction_id: str = Field(..., min_length=1, description="Unique transaction identifier")
    merchant_id: Optional[str] = Field(default=None, description="Merchant context ID")
    amount_in_paise: int = Field(..., gt=0, description="Transaction amount in minor units (paise)")
    candidate_actions: List[CandidateActionInput] = Field(..., min_length=1, description="Candidate actions to evaluate")
    customer_ltv_rupees: Optional[float] = Field(default=0.0, ge=0.0, description="Optional customer lifetime value in rupees")
    churn_risk_score: Optional[float] = Field(default=0.0, ge=0.0, le=1.0, description="Optional customer churn probability [0.0, 1.0]")


class StrategyOptimizationResponse(BaseModel):
    """Response schema for multi-objective strategy optimization."""
    transaction_id: str = Field(..., description="Transaction ID evaluated")
    merchant_id: Optional[str] = Field(default=None, description="Merchant ID context")
    amount_in_paise: int = Field(..., gt=0, description="Transaction amount in paise")
    customer_ltv_rupees: float = Field(..., description="Evaluated customer LTV in rupees")
    churn_risk_score: float = Field(..., description="Evaluated customer churn risk score")
    best_action: str = Field(..., description="Top-ranked candidate action by optimized ENRV")
    max_optimized_enrv_in_paise: int = Field(..., description="Highest optimized ENRV in paise")
    max_optimized_enrv_rupees: float = Field(..., description="Highest optimized ENRV in rupees")
    base_best_action: str = Field(..., description="Top action according to base ENRV prior to LTV adjustment")
    is_ltv_penalty_applied: bool = Field(..., description="True if non-zero churn penalty influenced optimization")
    action_results: List[OptimizedActionResult] = Field(..., description="Ranked list of optimized candidate action results")


class StrategyOptimizerService:
    """Service executing multi-objective strategy optimization considering LTV and churn risk."""

    @classmethod
    def get_aggressiveness_weight(cls, action_type: str) -> float:
        """Retrieves action aggressiveness weight, defaulting to 0.5 for unknown actions."""
        norm_type = action_type.upper().strip()
        return ACTION_AGGRESSIVENESS_WEIGHTS.get(norm_type, 0.5)

    @classmethod
    def is_soft_nudge(cls, action_type: str) -> bool:
        """Determines if action is a low-friction soft nudge."""
        norm_type = action_type.upper().strip()
        return norm_type in ("RECOVERY_MESSAGE", "WHATSAPP_REMINDER")

    @classmethod
    def calculate_churn_penalty(
        cls,
        action_type: str,
        customer_ltv_rupees: Optional[float],
        churn_risk_score: Optional[float],
    ) -> int:
        """
        Calculates the churn risk penalty in paise:
        Penalty = int(round(ChurnRisk * CustomerLTV_in_paise * AggressivenessWeight))

        Defaults to 0 if LTV or ChurnRisk is missing/zero.
        """
        ltv = float(customer_ltv_rupees) if customer_ltv_rupees is not None and customer_ltv_rupees > 0 else 0.0
        churn = float(churn_risk_score) if churn_risk_score is not None and churn_risk_score > 0 else 0.0
        if ltv <= 0 or churn <= 0:
            return 0

        # Clamp churn risk to [0.0, 1.0]
        churn = min(1.0, churn)
        # Authoritative Decimal calculation for minor units (paise)
        aggressiveness = cls.get_aggressiveness_weight(action_type)
        churn_dec = Decimal(str(churn))
        aggr_dec = Decimal(str(aggressiveness))
        ltv_paise_dec = Decimal(str(ltv)) * Decimal("100")
        penalty_dec = churn_dec * ltv_paise_dec * aggr_dec
        penalty_paise = int(penalty_dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return max(0, penalty_paise)

    @classmethod
    def optimize_strategy(
        cls,
        request: StrategyOptimizationRequest,
    ) -> StrategyOptimizationResponse:
        """
        Calculates multi-objective optimized ENRV across candidate actions and ranks them.

        Args:
            request: StrategyOptimizationRequest containing transaction details, actions, LTV, and churn risk.

        Returns:
            StrategyOptimizationResponse with ranked optimized results and LTV penalty details.
        """
        ltv = request.customer_ltv_rupees if request.customer_ltv_rupees is not None else 0.0
        churn = request.churn_risk_score if request.churn_risk_score is not None else 0.0

        # Calculate base ENRV for all candidate actions via ENRVCalculator
        base_request = ENRVCalculationRequest(
            transaction_id=request.transaction_id,
            merchant_id=request.merchant_id,
            amount_in_paise=request.amount_in_paise,
            candidate_actions=request.candidate_actions,
        )
        base_response = ENRVCalculator.calculate_enrv(base_request)
        base_best_action = base_response.best_action

        unranked_optimized: List[OptimizedActionResult] = []

        for base_item in base_response.action_results:
            action_type = base_item.action_type
            churn_penalty_paise = cls.calculate_churn_penalty(action_type, ltv, churn)
            churn_penalty_rupees = float(Decimal(churn_penalty_paise) / Decimal("100"))

            optimized_enrv_paise = base_item.expected_net_recovery_value_in_paise - churn_penalty_paise
            optimized_enrv_rupees = float(Decimal(optimized_enrv_paise) / Decimal("100"))

            unranked_optimized.append(
                OptimizedActionResult(
                    action_type=action_type,
                    predicted_recovery_probability=base_item.predicted_recovery_probability,
                    base_enrv_in_paise=base_item.expected_net_recovery_value_in_paise,
                    base_enrv_rupees=base_item.expected_net_recovery_value_rupees,
                    churn_risk_score=churn,
                    customer_ltv_rupees=ltv,
                    aggressiveness_weight=cls.get_aggressiveness_weight(action_type),
                    churn_penalty_in_paise=churn_penalty_paise,
                    churn_penalty_rupees=churn_penalty_rupees,
                    optimized_enrv_in_paise=optimized_enrv_paise,
                    optimized_enrv_rupees=optimized_enrv_rupees,
                    rank=1,
                    is_soft_nudge=cls.is_soft_nudge(action_type),
                )
            )

        # Sort descending by optimized ENRV, then ascending by penalty, then ascending by action type
        sorted_optimized = sorted(
            unranked_optimized,
            key=lambda x: (
                -x.optimized_enrv_in_paise,
                x.churn_penalty_in_paise,
                x.action_type,
            ),
        )

        ranked_results: List[OptimizedActionResult] = []
        for rank_idx, item in enumerate(sorted_optimized, start=1):
            ranked_item = item.model_copy(update={"rank": rank_idx})
            ranked_results.append(ranked_item)

        best_result = ranked_results[0]
        penalty_applied = any(r.churn_penalty_in_paise > 0 for r in ranked_results)

        return StrategyOptimizationResponse(
            transaction_id=request.transaction_id,
            merchant_id=request.merchant_id,
            amount_in_paise=request.amount_in_paise,
            customer_ltv_rupees=ltv,
            churn_risk_score=churn,
            best_action=best_result.action_type,
            max_optimized_enrv_in_paise=best_result.optimized_enrv_in_paise,
            max_optimized_enrv_rupees=best_result.optimized_enrv_rupees,
            base_best_action=base_best_action,
            is_ltv_penalty_applied=penalty_applied,
            action_results=ranked_results,
        )
