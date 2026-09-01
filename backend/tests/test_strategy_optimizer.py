"""
RecoverAI - Step 43 Strategy Optimizer Unit Tests

Validates multi-objective Action-Conditional ENRV optimization:
1. Soft nudge prioritization for high-LTV / high-churn-risk customers.
2. Neutral fallback when LTV or churn risk score is zero/missing.
3. Penalty calculation accuracy across action aggressiveness weights.
4. Edge cases (zero amount, out-of-bounds probability, zero churn risk).
"""

import pytest
from backend.app.schemas.enrv import CandidateActionInput
from backend.app.services.strategy_optimizer import (
    StrategyOptimizerService,
    StrategyOptimizationRequest,
    ACTION_AGGRESSIVENESS_WEIGHTS,
)


def test_strategy_optimizer_soft_nudge_prioritization():
    """
    Test 1: High LTV + High Churn Risk customer.
    Verifies that aggressive actions (MANUAL_OUTREACH, RETRY) incur heavy churn risk penalties,
    causing soft nudges (WHATSAPP_REMINDER, RECOVERY_MESSAGE) to be elevated in rank.
    """
    # Candidate actions where MANUAL_OUTREACH has highest raw ENRV initially
    candidate_actions = [
        CandidateActionInput(action_type="MANUAL_OUTREACH", predicted_recovery_probability=0.85),
        CandidateActionInput(action_type="RETRY", predicted_recovery_probability=0.80),
        CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.75),
        CandidateActionInput(action_type="WHATSAPP_REMINDER", predicted_recovery_probability=0.70),
        CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.68),
    ]

    request = StrategyOptimizationRequest(
        transaction_id="tx_high_ltv_churn_001",
        merchant_id="m_saas_enterprise",
        amount_in_paise=1000000,  # 10,000 INR
        candidate_actions=candidate_actions,
        customer_ltv_rupees=50000.0,  # 50,000 INR LTV
        churn_risk_score=0.80,         # High churn risk (80%)
    )

    response = StrategyOptimizerService.optimize_strategy(request)

    assert response.is_ltv_penalty_applied is True
    # Base top action prior to penalty was MANUAL_OUTREACH or RETRY
    assert response.base_best_action in ("MANUAL_OUTREACH", "RETRY")
    # Multi-objective optimization must promote a lower-friction soft nudge or link over agent outreach
    assert response.best_action in ("WHATSAPP_REMINDER", "RECOVERY_MESSAGE", "PAYMENT_LINK")
    assert response.best_action != "MANUAL_OUTREACH"

    # Verify MANUAL_OUTREACH received maximum penalty
    manual_res = next(r for r in response.action_results if r.action_type == "MANUAL_OUTREACH")
    msg_res = next(r for r in response.action_results if r.action_type == "RECOVERY_MESSAGE")

    assert manual_res.churn_penalty_rupees > msg_res.churn_penalty_rupees
    assert manual_res.aggressiveness_weight == 1.0
    assert msg_res.aggressiveness_weight == 0.1


def test_strategy_optimizer_neutral_fallback_when_ltv_zero():
    """
    Test 2: Customer with 0 LTV or missing LTV score.
    Verifies churn penalty defaults to 0 and base ENRV order is preserved intact.
    """
    candidate_actions = [
        CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.80),
        CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.40),
    ]

    request = StrategyOptimizationRequest(
        transaction_id="tx_zero_ltv_002",
        merchant_id="m_standard",
        amount_in_paise=500000,
        candidate_actions=candidate_actions,
        customer_ltv_rupees=0.0,
        churn_risk_score=0.90,
    )

    response = StrategyOptimizerService.optimize_strategy(request)

    assert response.is_ltv_penalty_applied is False
    assert response.best_action == response.base_best_action
    for res in response.action_results:
        assert res.churn_penalty_in_paise == 0
        assert res.optimized_enrv_in_paise == res.base_enrv_in_paise


def test_strategy_optimizer_churn_penalty_math():
    """
    Test 3: Validates mathematical formula for churn risk penalty:
    Penalty_in_paise = int(round(ChurnRisk * LTV_paise * AggressivenessWeight))
    """
    action_type = "RETRY"  # Weight = 0.8
    ltv_rupees = 10000.0   # 1,000,000 paise
    churn_score = 0.50     # 50%

    expected_penalty_paise = int(round(0.50 * 1000000 * 0.8))  # = 400,000 paise (4,000 INR)
    actual_penalty = StrategyOptimizerService.calculate_churn_penalty(
        action_type=action_type,
        customer_ltv_rupees=ltv_rupees,
        churn_risk_score=churn_score,
    )

    assert actual_penalty == expected_penalty_paise == 400000


def test_strategy_optimizer_soft_nudge_helpers():
    """
    Test 4: Utility methods for soft nudge classification and aggressiveness weights.
    """
    assert StrategyOptimizerService.is_soft_nudge("RECOVERY_MESSAGE") is True
    assert StrategyOptimizerService.is_soft_nudge("WHATSAPP_REMINDER") is True
    assert StrategyOptimizerService.is_soft_nudge("MANUAL_OUTREACH") is False
    assert StrategyOptimizerService.is_soft_nudge("RETRY") is False

    assert StrategyOptimizerService.get_aggressiveness_weight("MANUAL_OUTREACH") == 1.0
    assert StrategyOptimizerService.get_aggressiveness_weight("NO_ACTION") == 0.0
    assert StrategyOptimizerService.get_aggressiveness_weight("UNKNOWN_ACTION") == 0.5
