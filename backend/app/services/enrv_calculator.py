"""
RecoverAI - Expected Net Recovery Value (ENRV) Calculator Service (Step 10)

Quantifies net expected financial return per candidate recovery action:
ENRV(a_i) = P(R | X, a_i) * AmountInPaise - InterventionCostInPaise - OperationalCostInPaise - ExpectedRefundCostInPaise

Ranks candidate actions by ENRV to shift decision-making from pure probability to net financial return optimization.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, DecisionContext, RecoveryActionScore
from backend.app.schemas.enrv import (
    ActionCostConfig,
    CandidateActionInput,
    ENRVActionResult,
    ENRVCalculationRequest,
    ENRVCalculationResponse,
)

logger = logging.getLogger("recoverai.enrv_calculator")

# Frozen Default Action Cost Parameters (in minor units / paise)
DEFAULT_ACTION_COSTS: Dict[str, ActionCostConfig] = {
    "PAYMENT_LINK": ActionCostConfig(
        action_type="PAYMENT_LINK",
        intervention_cost_in_paise=300,   # Gateway fee / link creation overhead (3 INR)
        operational_cost_in_paise=50,     # Notification delivery cost (0.50 INR)
        expected_refund_cost_in_paise=0,
    ),
    "RECOVERY_MESSAGE": ActionCostConfig(
        action_type="RECOVERY_MESSAGE",
        intervention_cost_in_paise=50,    # SMS delivery fee (0.50 INR)
        operational_cost_in_paise=10,     # System processing fee (0.10 INR)
        expected_refund_cost_in_paise=0,
    ),
    "WHATSAPP_REMINDER": ActionCostConfig(
        action_type="WHATSAPP_REMINDER",
        intervention_cost_in_paise=100,   # WhatsApp template message fee (1 INR)
        operational_cost_in_paise=20,     # Processing fee (0.20 INR)
        expected_refund_cost_in_paise=0,
    ),
    "RETRY": ActionCostConfig(
        action_type="RETRY",
        intervention_cost_in_paise=150,   # Gateway retry fee (1.50 INR)
        operational_cost_in_paise=20,     # Processing fee (0.20 INR)
        expected_refund_cost_in_paise=0,
    ),
    "MANUAL_OUTREACH": ActionCostConfig(
        action_type="MANUAL_OUTREACH",
        intervention_cost_in_paise=500,   # Agent manual outreach cost (5 INR)
        operational_cost_in_paise=100,    # Agent admin overhead (1 INR)
        expected_refund_cost_in_paise=0,
    ),
    "NO_ACTION": ActionCostConfig(
        action_type="NO_ACTION",
        intervention_cost_in_paise=0,
        operational_cost_in_paise=0,
        expected_refund_cost_in_paise=0,
    ),
}


class ENRVCalculator:
    """Service for calculating Expected Net Recovery Value (ENRV) and ranking candidate recovery actions."""

    @classmethod
    def get_action_cost_config(cls, action_type: str) -> ActionCostConfig:
        """
        Retrieves cost configuration for a given action type, defaulting to 0 costs for unknown actions.

        Args:
            action_type: Candidate action string identifier.

        Returns:
            ActionCostConfig: Cost structure in paise.
        """
        norm_type = action_type.upper().strip()
        if norm_type in DEFAULT_ACTION_COSTS:
            return DEFAULT_ACTION_COSTS[norm_type]
        logger.info(f"Unrecognized action type '{action_type}' for ENRV cost lookup. Defaulting to zero costs.")
        return ActionCostConfig(
            action_type=norm_type,
            intervention_cost_in_paise=0,
            operational_cost_in_paise=0,
            expected_refund_cost_in_paise=0,
        )

    @classmethod
    def calculate_action_enrv(
        cls,
        amount_in_paise: int,
        candidate_input: CandidateActionInput,
    ) -> ENRVActionResult:
        """
        Calculates ENRV for a single candidate action input.

        Args:
            amount_in_paise: Transaction amount in paise (gt=0).
            candidate_input: Probability and optional cost overrides for candidate action.

        Returns:
            ENRVActionResult: Computed financial breakdown (unranked).
        """
        if amount_in_paise <= 0:
            raise ValueError(f"Amount in paise must be a positive integer, got: {amount_in_paise}")

        raw_prob = candidate_input.predicted_recovery_probability
        # Prob clamp [0.0, 1.0]
        if raw_prob < 0.0 or raw_prob > 1.0:
            clamped_prob = max(0.0, min(1.0, raw_prob))
            logger.warning(
                f"Out-of-bounds probability {raw_prob} for action '{candidate_input.action_type}'. "
                f"Clamped to {clamped_prob}."
            )
        else:
            clamped_prob = raw_prob

        # Fetch base cost config
        base_cost = cls.get_action_cost_config(candidate_input.action_type)

        # Apply custom overrides if provided
        intervention_cost = (
            candidate_input.custom_intervention_cost_in_paise
            if candidate_input.custom_intervention_cost_in_paise is not None
            else base_cost.intervention_cost_in_paise
        )
        operational_cost = (
            candidate_input.custom_operational_cost_in_paise
            if candidate_input.custom_operational_cost_in_paise is not None
            else base_cost.operational_cost_in_paise
        )
        expected_refund_cost = (
            candidate_input.custom_expected_refund_cost_in_paise
            if candidate_input.custom_expected_refund_cost_in_paise is not None
            else base_cost.expected_refund_cost_in_paise
        )

        total_cost = intervention_cost + operational_cost + expected_refund_cost

        # Expected Gross Recovery in paise (Authoritative Decimal minor unit calculation)
        amount_dec = Decimal(amount_in_paise)
        prob_dec = Decimal(str(clamped_prob))
        expected_gross = int((prob_dec * amount_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # Expected Net Recovery Value in paise
        enrv_paise = expected_gross - total_cost
        enrv_rupees = float(Decimal(enrv_paise) / Decimal("100"))

        return ENRVActionResult(
            action_type=candidate_input.action_type.upper().strip(),
            predicted_recovery_probability=clamped_prob,
            amount_in_paise=amount_in_paise,
            expected_gross_recovery_in_paise=expected_gross,
            intervention_cost_in_paise=intervention_cost,
            operational_cost_in_paise=operational_cost,
            expected_refund_cost_in_paise=expected_refund_cost,
            total_cost_in_paise=total_cost,
            expected_net_recovery_value_in_paise=enrv_paise,
            expected_net_recovery_value_rupees=enrv_rupees,
            rank=1,  # Temporary rank
        )

    @classmethod
    def calculate_enrv(
        cls,
        request: ENRVCalculationRequest,
    ) -> ENRVCalculationResponse:
        """
        Calculates ENRV across all candidate actions in a request and ranks them in descending ENRV order.

        Args:
            request: ENRVCalculationRequest payload.

        Returns:
            ENRVCalculationResponse: Ranked candidate actions with top action identified.
        """
        unranked_results = [
            cls.calculate_action_enrv(request.amount_in_paise, candidate)
            for candidate in request.candidate_actions
        ]

        # Sort descending by ENRV, then ascending by total cost, then ascending by action type
        sorted_results = sorted(
            unranked_results,
            key=lambda x: (
                -x.expected_net_recovery_value_in_paise,
                x.total_cost_in_paise,
                x.action_type,
            ),
        )

        # Assign final 1-based ranks
        ranked_results: List[ENRVActionResult] = []
        for rank_idx, item in enumerate(sorted_results, start=1):
            ranked_item = item.model_copy(update={"rank": rank_idx})
            ranked_results.append(ranked_item)

        best_result = ranked_results[0]

        return ENRVCalculationResponse(
            transaction_id=request.transaction_id,
            merchant_id=request.merchant_id,
            amount_in_paise=request.amount_in_paise,
            best_action=best_result.action_type,
            max_enrv_in_paise=best_result.expected_net_recovery_value_in_paise,
            max_enrv_rupees=best_result.expected_net_recovery_value_rupees,
            action_results=ranked_results,
        )

    @classmethod
    async def persist_enrv_scores(
        cls,
        session: AsyncSession,
        transaction_id: str,
        enrv_response: ENRVCalculationResponse,
        merchant_id: Optional[str] = None,
        model_version: str = "v1.0",
        feature_version: str = "v1.0",
        policy_version: str = "v1.0",
    ) -> DecisionContext:
        """
        Persists calculated ENRV action scores into `decision_contexts` and `recovery_action_scores` tables.

        Args:
            session: Active AsyncSession.
            transaction_id: Unique transaction ID.
            enrv_response: Evaluated ENRVCalculationResponse.
            merchant_id: Optional merchant ID for multi-tenant isolation validation.
            model_version: Model version identifier.
            feature_version: Feature set version identifier.
            policy_version: Policy version identifier.

        Returns:
            DecisionContext: Created SQLAlchemy model record.

        Raises:
            ValueError: If transaction_id does not exist or merchant_id mismatch occurs.
        """
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        tx = result.scalar_one_or_none()

        if not tx:
            raise ValueError(f"Transaction with ID '{transaction_id}' not found.")

        if merchant_id and tx.merchant_id != merchant_id:
            raise ValueError(
                f"Merchant ID mismatch for transaction '{transaction_id}': "
                f"expected '{merchant_id}', got '{tx.merchant_id}'"
            )

        # Create DecisionContext record
        context = DecisionContext(
            transaction_id=transaction_id,
            model_version=model_version,
            feature_version=feature_version,
            policy_version=policy_version,
        )
        session.add(context)
        await session.flush()  # Generate context.id

        # Create RecoveryActionScore records
        for res in enrv_response.action_results:
            score = RecoveryActionScore(
                decision_context_id=context.id,
                transaction_id=transaction_id,
                action=res.action_type,
                recovery_probability=res.predicted_recovery_probability,
                expected_gross_recovery=res.expected_gross_recovery_in_paise / 100.0,
                intervention_cost=res.total_cost_in_paise / 100.0,
                expected_net_recovery_value=res.expected_net_recovery_value_rupees,
            )
            session.add(score)

        await session.commit()
        await session.refresh(context)
        return context
