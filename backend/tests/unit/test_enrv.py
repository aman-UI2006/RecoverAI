"""
RecoverAI - Step 37 Unit Tests: ENRV Calculator Formula Edge Cases & Action Ranking
"""

import pytest
from backend.app.schemas.enrv import (
    ActionCostConfig,
    CandidateActionInput,
    ENRVActionResult,
    ENRVCalculationRequest,
    ENRVCalculationResponse,
)
from backend.app.services.enrv_calculator import ENRVCalculator, DEFAULT_ACTION_COSTS


def test_enrv_cost_config_lookup_known_actions():
    """Verify cost configuration retrieval for standard known recovery actions."""
    payment_link_cost = ENRVCalculator.get_action_cost_config("PAYMENT_LINK")
    assert payment_link_cost.action_type == "PAYMENT_LINK"
    assert payment_link_cost.intervention_cost_in_paise == 300
    assert payment_link_cost.operational_cost_in_paise == 50
    assert payment_link_cost.expected_refund_cost_in_paise == 0

    no_action_cost = ENRVCalculator.get_action_cost_config("NO_ACTION")
    assert no_action_cost.intervention_cost_in_paise == 0
    assert no_action_cost.operational_cost_in_paise == 0


def test_enrv_cost_config_lookup_unknown_action_defaults_to_zero():
    """Verify unrecognized action types default gracefully to zero costs without throwing."""
    unknown_cost = ENRVCalculator.get_action_cost_config("CUSTOM_UNKNOWN_ACTION")
    assert unknown_cost.action_type == "CUSTOM_UNKNOWN_ACTION"
    assert unknown_cost.intervention_cost_in_paise == 0
    assert unknown_cost.operational_cost_in_paise == 0
    assert unknown_cost.expected_refund_cost_in_paise == 0


def test_enrv_standard_calculation():
    """Verify standard ENRV formula calculation: ENRV = P * Amount - Costs."""
    amount_paise = 10000  # ₹100.00
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.80,
    )

    result = ENRVCalculator.calculate_action_enrv(
        amount_in_paise=amount_paise,
        candidate_input=candidate,
    )

    # Expected gross recovery = 0.80 * 10000 = 8000 paise
    # Total costs = 300 (intervention) + 50 (operational) + 0 (refund) = 350 paise
    # Net ENRV in paise = 8000 - 350 = 7650 paise
    # Net ENRV in rupees = 76.50
    assert result.action_type == "PAYMENT_LINK"
    assert result.predicted_recovery_probability == 0.80
    assert result.expected_gross_recovery_in_paise == 8000
    assert result.total_cost_in_paise == 350
    assert result.expected_net_recovery_value_in_paise == 7650
    assert result.expected_net_recovery_value_rupees == pytest.approx(76.50, abs=1e-2)


def test_enrv_edge_case_zero_and_negative_amount_raises_value_error():
    """Verify zero or negative transaction amount raises ValueError."""
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.50,
    )

    with pytest.raises(ValueError, match="Amount in paise must be a positive integer"):
        ENRVCalculator.calculate_action_enrv(amount_in_paise=0, candidate_input=candidate)

    with pytest.raises(ValueError, match="Amount in paise must be a positive integer"):
        ENRVCalculator.calculate_action_enrv(amount_in_paise=-500, candidate_input=candidate)


def test_enrv_edge_case_hundred_percent_probability():
    """Verify 100% probability (P=1.0) yields full gross recovery minus costs."""
    amount_paise = 50000  # ₹500.00
    candidate = CandidateActionInput(
        action_type="RECOVERY_MESSAGE",
        predicted_recovery_probability=1.0,
    )

    result = ENRVCalculator.calculate_action_enrv(
        amount_in_paise=amount_paise,
        candidate_input=candidate,
    )

    # Gross recovery = 1.0 * 50000 = 50000 paise
    # Total costs = 50 + 10 = 60 paise
    # ENRV = 50000 - 60 = 49940 paise (₹499.40)
    assert result.expected_gross_recovery_in_paise == 50000
    assert result.total_cost_in_paise == 60
    assert result.expected_net_recovery_value_in_paise == 49940
    assert result.expected_net_recovery_value_rupees == pytest.approx(499.40, abs=1e-2)


def test_enrv_edge_case_zero_percent_probability():
    """Verify 0% probability (P=0.0) yields 0 gross recovery and negative ENRV (cost loss)."""
    amount_paise = 25000  # ₹250.00
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.0,
    )

    result = ENRVCalculator.calculate_action_enrv(
        amount_in_paise=amount_paise,
        candidate_input=candidate,
    )

    # Gross recovery = 0 paise
    # Total costs = 350 paise
    # ENRV = -350 paise (₹-3.50)
    assert result.expected_gross_recovery_in_paise == 0
    assert result.total_cost_in_paise == 350
    assert result.expected_net_recovery_value_in_paise == -350
    assert result.expected_net_recovery_value_rupees == pytest.approx(-3.50, abs=1e-2)


def test_enrv_out_of_bounds_probability_clamped():
    """Verify probabilities outside [0.0, 1.0] are clamped defensively."""
    amount_paise = 10000

    # Over 1.0 (e.g. 1.25) -> Clamped to 1.0
    cand_high = CandidateActionInput(
        action_type="RETRY",
        predicted_recovery_probability=1.25,
    )
    result_high = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=cand_high)
    assert result_high.expected_gross_recovery_in_paise == 10000

    # Below 0.0 (e.g. -0.15) -> Clamped to 0.0
    cand_low = CandidateActionInput(
        action_type="RETRY",
        predicted_recovery_probability=-0.15,
    )
    result_low = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=cand_low)
    assert result_low.expected_gross_recovery_in_paise == 0


def test_enrv_custom_cost_overrides():
    """Verify custom intervention, operational, and expected refund cost overrides."""
    amount_paise = 20000
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.50,
        custom_intervention_cost_in_paise=500,
        custom_operational_cost_in_paise=100,
        custom_expected_refund_cost_in_paise=200,
    )

    result = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=candidate)
    # Total custom costs = 500 + 100 + 200 = 800 paise
    # Gross recovery = 0.50 * 20000 = 10000 paise
    # ENRV = 10000 - 800 = 9200 paise
    assert result.total_cost_in_paise == 800
    assert result.expected_net_recovery_value_in_paise == 9200
    assert result.expected_net_recovery_value_rupees == pytest.approx(92.00, abs=1e-2)


def test_enrv_rank_candidate_actions_descending_order():
    """Verify batch ranking orders candidate actions in descending order of ENRV."""
    amount_paise = 100000  # ₹1,000.00
    candidates = [
        CandidateActionInput(action_type="RETRY", predicted_recovery_probability=0.20),             # Gross 20000 - 170 = 19830
        CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.60),      # Gross 60000 - 350 = 59650
        CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.40),  # Gross 40000 - 60 = 39940
        CandidateActionInput(action_type="NO_ACTION", predicted_recovery_probability=0.00),         # Gross 0 - 0 = 0
    ]

    request = ENRVCalculationRequest(
        transaction_id="tx_test_enrv_001",
        merchant_id="m_test_123",
        amount_in_paise=amount_paise,
        candidate_actions=candidates,
    )

    response = ENRVCalculator.calculate_enrv(request)

    assert response.transaction_id == "tx_test_enrv_001"
    assert response.best_action == "PAYMENT_LINK"
    assert response.max_enrv_in_paise == 59650
    assert len(response.action_results) == 4

    # Verify descending rank order
    enrv_scores = [score.expected_net_recovery_value_in_paise for score in response.action_results]
    assert enrv_scores == sorted(enrv_scores, reverse=True)
    assert enrv_scores[0] == 59650  # PAYMENT_LINK
    assert enrv_scores[1] == 39940  # RECOVERY_MESSAGE
    assert enrv_scores[2] == 19830  # RETRY
    assert enrv_scores[3] == 0      # NO_ACTION


def test_enrv_zero_intervention_cost():
    """Verify ENRV calculation when intervention, operational, and refund costs are all zero."""
    amount_paise = 15000  # ₹150.00
    candidate = CandidateActionInput(
        action_type="NO_ACTION",
        predicted_recovery_probability=0.50,
        custom_intervention_cost_in_paise=0,
        custom_operational_cost_in_paise=0,
        custom_expected_refund_cost_in_paise=0,
    )

    result = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=candidate)
    assert result.total_cost_in_paise == 0
    assert result.expected_gross_recovery_in_paise == 7500
    assert result.expected_net_recovery_value_in_paise == 7500
    assert result.expected_net_recovery_value_rupees == pytest.approx(75.00, abs=1e-2)


def test_enrv_cost_exceeds_expected_recovery_negative_enrv():
    """Verify low recovery probability where total cost exceeds gross recovery results in negative ENRV."""
    amount_paise = 10000  # ₹100.00
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",  # cost = 350 paise
        predicted_recovery_probability=0.01,  # gross = 100 paise
    )

    result = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=candidate)
    assert result.expected_gross_recovery_in_paise == 100
    assert result.total_cost_in_paise == 350
    assert result.expected_net_recovery_value_in_paise == -250
    assert result.expected_net_recovery_value_rupees == pytest.approx(-2.50, abs=1e-2)


def test_enrv_paise_rounding_precision():
    """Verify fractional gross recovery rounding to exact integer paise."""
    amount_paise = 10000  # ₹100.00
    candidate = CandidateActionInput(
        action_type="RETRY",  # cost = 150 + 20 = 170 paise
        predicted_recovery_probability=0.3333,  # 3333.0 paise
    )

    result = ENRVCalculator.calculate_action_enrv(amount_in_paise=amount_paise, candidate_input=candidate)
    assert result.expected_gross_recovery_in_paise == 3333
    assert result.total_cost_in_paise == 170
    assert result.expected_net_recovery_value_in_paise == 3163
    assert result.expected_net_recovery_value_rupees == pytest.approx(31.63, abs=1e-2)

