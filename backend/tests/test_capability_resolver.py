"""
RecoverAI — Step 14 Test Suite: Capability Resolver

Tests the CapabilityResolver service and Capability resolution schemas.
Verifies mode isolation (REAL_TEST vs SIMULATION), ENRV-based fallback logic,
merchant isolation, unknown action safety, and air-gap execution isolation.
"""

import pytest
from uuid import uuid4
from backend.app.schemas.capability import (
    ExecutionMode,
    CapabilityStatus,
    CapabilityResolutionResult,
)
from backend.app.schemas.ai_recommendation import AIRecommendationResponse
from backend.app.schemas.enrv import (
    ENRVCalculationResponse,
    ENRVActionResult,
)
from backend.app.services.capability_resolver import CapabilityResolver
from backend.app.models.domain import Transaction


def helper_make_enrv_action_result(
    action_type: str,
    probability: float,
    amount_rupees: float,
    cost_rupees: float,
    rank: int,
) -> ENRVActionResult:
    """Helper to instantiate ENRVActionResult with required schema fields."""
    amount_paise = int(amount_rupees * 100)
    cost_paise = int(cost_rupees * 100)
    expected_gross_paise = int(probability * amount_paise)
    expected_net_paise = expected_gross_paise - cost_paise
    expected_net_rupees = round(expected_net_paise / 100.0, 2)

    return ENRVActionResult(
        action_type=action_type,
        predicted_recovery_probability=probability,
        amount_in_paise=amount_paise,
        expected_gross_recovery_in_paise=expected_gross_paise,
        intervention_cost_in_paise=cost_paise,
        operational_cost_in_paise=0,
        expected_refund_cost_in_paise=0,
        total_cost_in_paise=cost_paise,
        expected_net_recovery_value_in_paise=expected_net_paise,
        expected_net_recovery_value_rupees=expected_net_rupees,
        rank=rank,
    )


def helper_make_enrv_response(
    tx_id: str,
    results: list[ENRVActionResult],
) -> ENRVCalculationResponse:
    """Helper to instantiate ENRVCalculationResponse."""
    top_res = max(results, key=lambda x: x.expected_net_recovery_value_rupees)
    return ENRVCalculationResponse(
        transaction_id=tx_id,
        amount_in_paise=top_res.amount_in_paise,
        best_action=top_res.action_type,
        max_enrv_in_paise=top_res.expected_net_recovery_value_in_paise,
        max_enrv_rupees=top_res.expected_net_recovery_value_rupees,
        action_results=results,
    )


def test_1_capability_schemas_and_enums():
    """1. Verifies ExecutionMode and CapabilityStatus enum values and model validation."""
    assert ExecutionMode.REAL_TEST == "REAL_TEST"
    assert ExecutionMode.SIMULATION == "SIMULATION"
    assert CapabilityStatus.SUPPORTED == "SUPPORTED"
    assert CapabilityStatus.UNSUPPORTED == "UNSUPPORTED"
    assert CapabilityStatus.REQUIRES_VERIFICATION == "REQUIRES_VERIFICATION"
    assert CapabilityStatus.INTERNAL == "INTERNAL"

    res = CapabilityResolutionResult(
        resolved_action="PAYMENT_LINK",
        status=CapabilityStatus.SUPPORTED,
        execution_mode=ExecutionMode.REAL_TEST,
        is_executable=True,
        reason="Payment Link verified executable in REAL_TEST.",
    )
    assert res.resolved_action == "PAYMENT_LINK"
    assert res.is_executable is True
    assert res.fallback_applied is False


def test_2_simulation_mode_all_actions_supported():
    """2. Verifies that all standard candidate actions are executable in SIMULATION mode."""
    resolver = CapabilityResolver()
    actions = [
        "PAYMENT_LINK",
        "RECOVERY_MESSAGE",
        "SUBSCRIPTION_RECOVERY",
        "RETRY",
        "AUTOMATED_GATEWAY_RETRY",
        "SMART_RETRY_SCHEDULE",
        "DISCOUNT_NUDGE",
        "STOP",
        "ESCALATE",
    ]
    for action in actions:
        result = resolver.resolve_action_capability(action, mode=ExecutionMode.SIMULATION)
        assert result.is_executable is True, f"Action {action} should be executable in SIMULATION mode."
        assert result.execution_mode == ExecutionMode.SIMULATION


def test_3_real_test_mode_capability_filtering():
    """3. Verifies that REAL_TEST mode restricts execution strictly to verified actions (PAYMENT_LINK, STOP)."""
    resolver = CapabilityResolver()

    # Executable / Internal actions in REAL_TEST
    pay_link_res = resolver.resolve_action_capability("PAYMENT_LINK", mode=ExecutionMode.REAL_TEST)
    assert pay_link_res.is_executable is True
    assert pay_link_res.status == CapabilityStatus.SUPPORTED

    stop_res = resolver.resolve_action_capability("STOP", mode=ExecutionMode.REAL_TEST)
    assert stop_res.is_executable is True
    assert stop_res.status == CapabilityStatus.INTERNAL

    # Non-executable / Restricted actions in REAL_TEST
    retry_res = resolver.resolve_action_capability("AUTOMATED_GATEWAY_RETRY", mode=ExecutionMode.REAL_TEST)
    assert retry_res.is_executable is False
    assert retry_res.status == CapabilityStatus.UNSUPPORTED

    sub_res = resolver.resolve_action_capability("SUBSCRIPTION_RECOVERY", mode=ExecutionMode.REAL_TEST)
    assert sub_res.is_executable is False
    assert sub_res.status == CapabilityStatus.REQUIRES_VERIFICATION


def test_4_action_alias_normalization():
    """4. Verifies action string normalization and alias resolution."""
    resolver = CapabilityResolver()
    assert resolver.normalize_action(" create_payment_link ") == "PAYMENT_LINK"
    assert resolver.normalize_action("send_recovery_message") == "RECOVERY_MESSAGE"
    assert resolver.normalize_action("STOP") == "STOP"


def test_5_recommendation_resolution_supported_top_action():
    """5. Verifies resolution when top AI recommendation is already executable."""
    resolver = CapabilityResolver()
    rec = AIRecommendationResponse(
        recommended_action="PAYMENT_LINK",
        confidence_score=0.88,
        rationale_text="Customer checkout abandonment; payment link is best option.",
        customer_message_template="Hi User, complete your transaction: {{link}}",
    )
    result = resolver.resolve_recommendation(rec, mode="REAL_TEST")
    assert result.resolved_action == "PAYMENT_LINK"
    assert result.is_executable is True
    assert result.fallback_applied is False
    assert result.original_recommendation is None


def test_6_recommendation_enrv_fallback_in_real_test():
    """6. Verifies fallback to next best ENRV-ranked executable action when top recommendation is unsupported in REAL_TEST."""
    resolver = CapabilityResolver()
    rec = AIRecommendationResponse(
        recommended_action="AUTOMATED_GATEWAY_RETRY",
        confidence_score=0.85,
        rationale_text="Gateway timeout; retry suggested.",
        customer_message_template="Your payment failed.",
    )

    enrv_resp = helper_make_enrv_response(
        "tx_test_123",
        [
            helper_make_enrv_action_result("AUTOMATED_GATEWAY_RETRY", 0.75, 1000.0, 10.0, 1),
            helper_make_enrv_action_result("PAYMENT_LINK", 0.60, 1000.0, 15.0, 2),
            helper_make_enrv_action_result("STOP", 0.0, 1000.0, 0.0, 3),
        ],
    )

    result = resolver.resolve_recommendation(
        recommendation=rec,
        enrv_response=enrv_resp,
        mode="REAL_TEST",
    )

    assert result.resolved_action == "PAYMENT_LINK"
    assert result.is_executable is True
    assert result.fallback_applied is True
    assert result.original_recommendation == "AUTOMATED_GATEWAY_RETRY"
    assert "Fell back to executable action 'PAYMENT_LINK'" in result.reason


def test_7_fallback_to_stop_when_no_candidate_supported():
    """7. Verifies fallback to STOP when all candidate actions are unsupported in REAL_TEST mode."""
    resolver = CapabilityResolver()
    rec = AIRecommendationResponse(
        recommended_action="AUTOMATED_GATEWAY_RETRY",
        confidence_score=0.90,
        rationale_text="Gateway issue.",
        customer_message_template="Notice",
    )

    enrv_resp = helper_make_enrv_response(
        "tx_test_456",
        [
            helper_make_enrv_action_result("AUTOMATED_GATEWAY_RETRY", 0.70, 1000.0, 10.0, 1),
            helper_make_enrv_action_result("SUBSCRIPTION_RECOVERY", 0.50, 1000.0, 20.0, 2),
        ],
    )

    result = resolver.resolve_recommendation(
        recommendation=rec,
        enrv_response=enrv_resp,
        mode="REAL_TEST",
    )

    assert result.resolved_action == "STOP"
    assert result.is_executable is True
    assert result.fallback_applied is True
    assert result.original_recommendation == "AUTOMATED_GATEWAY_RETRY"


def test_8_multi_tenant_merchant_isolation_check():
    """8. Verifies that passing a transaction from a different merchant raises ValueError."""
    resolver = CapabilityResolver()
    m_id_1 = str(uuid4())
    m_id_2 = str(uuid4())

    tx = Transaction(
        id=str(uuid4()),
        merchant_id=m_id_1,
        customer_id=str(uuid4()),
        amount=1500.0,
        status="DIAGNOSED",
        scenario_type="PAYMENT_FAILURE",
        mode="REAL_TEST",
    )

    rec = AIRecommendationResponse(
        recommended_action="PAYMENT_LINK",
        confidence_score=0.80,
        rationale_text="Reason",
        customer_message_template="Msg",
    )

    # Valid merchant check
    res = resolver.resolve_recommendation(rec, transaction=tx, merchant_id=m_id_1)
    assert res.resolved_action == "PAYMENT_LINK"

    # Mismatched merchant check -> must raise ValueError
    with pytest.raises(ValueError, match="Merchant ID mismatch"):
        resolver.resolve_recommendation(rec, transaction=tx, merchant_id=m_id_2)


def test_9_transaction_mode_override():
    """9. Verifies that resolution respects Transaction.mode if provided."""
    resolver = CapabilityResolver()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=2000.0,
        status="DIAGNOSED",
        scenario_type="SUBSCRIPTION_FAILURE",
        mode="REAL_TEST",
    )

    rec = AIRecommendationResponse(
        recommended_action="AUTOMATED_GATEWAY_RETRY",
        confidence_score=0.85,
        rationale_text="Reasoning",
        customer_message_template="Template",
    )

    # Mode explicit is SIMULATION, but tx.mode is REAL_TEST -> should resolve in REAL_TEST mode
    res = resolver.resolve_recommendation(rec, transaction=tx, mode="SIMULATION")
    assert res.execution_mode == ExecutionMode.REAL_TEST
    assert res.resolved_action == "STOP"


def test_10_no_razorpay_external_execution_side_effects(monkeypatch):
    """10. Air-gap safety test: Verifies capability resolution makes 0 HTTP API calls."""
    def forbidden_http_call(*args, **kwargs):
        pytest.fail("CapabilityResolver made an external HTTP network call!")

    monkeypatch.setattr("httpx.AsyncClient.post", forbidden_http_call, raising=False)
    monkeypatch.setattr("httpx.AsyncClient.get", forbidden_http_call, raising=False)

    resolver = CapabilityResolver()
    rec = AIRecommendationResponse(
        recommended_action="PAYMENT_LINK",
        confidence_score=0.95,
        rationale_text="High confidence link recommendation.",
        customer_message_template="Complete payment.",
    )
    result = resolver.resolve_recommendation(rec, mode="REAL_TEST")
    assert result.resolved_action == "PAYMENT_LINK"
    assert result.is_executable is True
