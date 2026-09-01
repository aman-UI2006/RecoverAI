"""
RecoverAI - Revenue Risk Engine Service (Step 8)

Quantifies financial exposure across the 4 transaction scenarios, calculates eligible revenue at risk,
and transitions transactions from CREATED to AT_RISK using the authoritative StateTransitionService.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, current_utc_time
from backend.app.schemas.risk_assessment import RiskAssessmentResponse
from backend.app.schemas.canonical_event import NormalizedEvent
from backend.app.services.state_transition_service import StateTransitionService

logger = logging.getLogger("recoverai.revenue_risk_engine")

# Frozen Base Risk Scores for the 4 core transaction scenarios
SCENARIO_RISK_SCORES: Dict[str, float] = {
    "PAYMENT_FAILURE": 0.95,
    "CHECKOUT_ABANDONMENT": 0.70,
    "SUBSCRIPTION_FAILURE": 0.90,
    "OVERDUE_RECEIVABLE": 0.85,
}


class RevenueRiskEngine:
    """Analytical service identifying at-risk revenue exposure across payment scenarios."""

    @staticmethod
    def calculate_risk_score(scenario_type: str) -> float:
        """
        Determines base risk score for a given transaction scenario.

        Args:
            scenario_type: Scenario identifier string.

        Returns:
            float: Risk score between 0.0 and 1.0.

        Raises:
            ValueError: If scenario_type is unhandled or invalid.
        """
        normal_scenario = scenario_type.upper().replace("-", "_").replace(" ", "_")
        if normal_scenario not in SCENARIO_RISK_SCORES:
            raise ValueError(f"Invalid or unhandled transaction scenario type: '{scenario_type}'")
        return SCENARIO_RISK_SCORES[normal_scenario]

    @classmethod
    async def assess_and_transition(
        cls,
        session: AsyncSession,
        transaction_id: str,
        scenario_type: str,
        amount_in_paise: int,
        currency: str = "INR",
        merchant_id: Optional[str] = None,
        eligibility_window_hours: int = 72,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessmentResponse:
        """
        Assesses revenue risk for a transaction and transitions it to AT_RISK via StateTransitionService.

        Args:
            session: Active AsyncSession.
            transaction_id: Unique UUID of transaction.
            scenario_type: Scenario classification (PAYMENT_FAILURE, etc.).
            amount_in_paise: Transaction amount in minor units (paise).
            currency: ISO currency code.
            merchant_id: Optional merchant ID for authorization validation.
            eligibility_window_hours: At-risk window duration in hours (default 72).
            metadata: Optional additional context.

        Returns:
            RiskAssessmentResponse: Assessed risk details.
        """
        if amount_in_paise <= 0:
            raise ValueError(f"Amount in paise must be a positive integer, got: {amount_in_paise}")

        # 1. Validate merchant scoping if provided BEFORE state transition
        if merchant_id:
            stmt = select(Transaction).where(Transaction.id == transaction_id)
            result = await session.execute(stmt)
            existing_tx = result.scalar_one_or_none()
            if not existing_tx:
                raise ValueError(f"Transaction with ID '{transaction_id}' not found.")
            if existing_tx.merchant_id != merchant_id:
                raise ValueError(
                    f"Merchant ID mismatch for transaction '{transaction_id}': "
                    f"expected '{merchant_id}', got '{existing_tx.merchant_id}'"
                )

        # 2. Calculate risk score
        try:
            risk_score = cls.calculate_risk_score(scenario_type)
        except ValueError as e:
            logger.error(f"Risk calculation failed for tx '{transaction_id}': {str(e)}")
            raise e

        # 3. Compute eligible revenue at risk (Authoritative Decimal minor unit calculation)
        amount_dec = Decimal(amount_in_paise)
        risk_dec = Decimal(str(risk_score))
        eligible_paise = int((amount_dec * risk_dec).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        eligible_rupees = float(Decimal(eligible_paise) / Decimal("100"))

        now = current_utc_time()
        expires_at = now + timedelta(hours=eligibility_window_hours)

        assessment_details = {
            "scenario_type": scenario_type,
            "risk_score": risk_score,
            "amount_in_paise": amount_in_paise,
            "eligible_revenue_at_risk_in_paise": eligible_paise,
            "eligible_revenue_at_risk": eligible_rupees,
            "eligibility_window_hours": eligibility_window_hours,
            "detected_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "event_type": "REVENUE_AT_RISK_DETECTED",
        }
        if metadata:
            assessment_details["custom_metadata"] = metadata

        # 4. Transition state atomically via StateTransitionService
        tx, audit_event = await StateTransitionService.transition(
            session=session,
            transaction_id=transaction_id,
            target_state="AT_RISK",
            actor="REVENUE_RISK_ENGINE",
            reason=f"Revenue at risk detected for scenario {scenario_type}",
            details=assessment_details,
        )

        return RiskAssessmentResponse(
            transaction_id=tx.id,
            merchant_id=tx.merchant_id,
            scenario_type=scenario_type,
            risk_score=risk_score,
            amount_in_paise=amount_in_paise,
            eligible_revenue_at_risk_in_paise=eligible_paise,
            eligible_revenue_at_risk=eligible_rupees,
            currency=currency,
            eligibility_window_hours=eligibility_window_hours,
            detected_at=now,
            expires_at=expires_at,
            status=tx.status,
        )

    @classmethod
    async def process_normalized_event(
        cls,
        session: AsyncSession,
        normalized_event: NormalizedEvent,
    ) -> Optional[RiskAssessmentResponse]:
        """
        Helper method consuming a canonical NormalizedEvent and assessing revenue risk if applicable.

        Args:
            session: Active AsyncSession.
            normalized_event: Canonical event emitted by Step 6.

        Returns:
            Optional[RiskAssessmentResponse]: Risk assessment response if eligible, None if duplicate or missing tx ID.
        """
        if normalized_event.is_duplicate or not normalized_event.transaction_id or not normalized_event.scenario:
            return None

        amount_in_paise = normalized_event.amount_in_paise or 0
        if amount_in_paise <= 0:
            return None

        return await cls.assess_and_transition(
            session=session,
            transaction_id=normalized_event.transaction_id,
            scenario_type=normalized_event.scenario,
            amount_in_paise=amount_in_paise,
            currency=normalized_event.currency or "INR",
            merchant_id=normalized_event.merchant_id,
        )
