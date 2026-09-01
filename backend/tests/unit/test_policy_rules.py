"""
RecoverAI - Step 37 Unit Tests: Policy Engine Hierarchy & Rule Threshold Boundaries
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from backend.app.schemas.capability import CapabilityResolutionResult, CapabilityStatus, ExecutionMode
from backend.app.schemas.policy import PolicyStatus, PolicyRejectionCode, PolicyEvaluationResult
from backend.app.models.domain import Transaction, Policy, RecoveryAttempt
from backend.app.policies.rules import PolicyRuleEvaluator, GLOBAL_DEFAULT_POLICY


def create_dummy_transaction(
    amount: Decimal = Decimal("1000.00"),
    retry_count: int = 0,
    merchant_id: str = "merchant_test_1",
) -> Transaction:
    """Helper to construct dummy Transaction model for offline unit testing."""
    tx = Transaction()
    tx.id = "tx_dummy_123"
    tx.merchant_id = merchant_id
    tx.amount = amount
    tx.currency = "INR"
    tx.retry_count = retry_count
    tx.status = "DIAGNOSED"
    tx.created_at = datetime.now(timezone.utc)
    return tx


def create_dummy_capability(
    resolved_action: str = "PAYMENT_LINK",
    is_executable: bool = True,
    execution_mode: ExecutionMode = ExecutionMode.REAL_TEST,
) -> CapabilityResolutionResult:
    """Helper to construct dummy CapabilityResolutionResult for offline unit testing."""
    return CapabilityResolutionResult(
        resolved_action=resolved_action,
        status=CapabilityStatus.SUPPORTED if is_executable else CapabilityStatus.UNSUPPORTED,
        is_executable=is_executable,
        execution_mode=execution_mode,
        reason="Capability verified",
    )


def test_rule_1_capability_unsupported():
    """Verify Rule 1 rejects actions when CapabilityResolver reports is_executable=False."""
    tx = create_dummy_transaction()
    cap = create_dummy_capability(resolved_action="UNSUPPORTED_GATEWAY_RETRY", is_executable=False)

    res = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx)

    assert res.is_approved is False
    assert res.status == PolicyStatus.REJECTED
    assert res.rejection_code == PolicyRejectionCode.CAPABILITY_UNSUPPORTED
    assert "Rule_1_Capability_Support" in res.applied_rules


def test_rule_2_explicit_stop():
    """Verify Rule 2 rejects actions when resolved_action is explicit 'STOP'."""
    tx = create_dummy_transaction()
    cap = create_dummy_capability(resolved_action="STOP", is_executable=True)

    res = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx)

    assert res.is_approved is False
    assert res.status == PolicyStatus.REJECTED
    assert res.rejection_code == PolicyRejectionCode.EXPLICIT_STOP
    assert "Rule_2_Explicit_Stop" in res.applied_rules


def test_rule_3_max_recovery_attempts_boundary():
    """Verify Rule 3 allows attempts below max limit and rejects at or above max limit (<= 3)."""
    tx_valid_0 = create_dummy_transaction(retry_count=0)
    tx_valid_1 = create_dummy_transaction(retry_count=1)
    tx_valid_2 = create_dummy_transaction(retry_count=2)
    tx_invalid_3 = create_dummy_transaction(retry_count=3)
    tx_invalid_4 = create_dummy_transaction(retry_count=4)

    cap = create_dummy_capability(resolved_action="PAYMENT_LINK")

    # Retry count 0, 1, 2 should be approved
    assert PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_valid_0).is_approved is True
    assert PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_valid_1).is_approved is True
    assert PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_valid_2).is_approved is True

    # Retry count 3 (max=3) should be rejected
    res_3 = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_invalid_3)
    assert res_3.is_approved is False
    assert res_3.rejection_code == PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED
    assert "Rule_3_Max_Recovery_Attempts" in res_3.applied_rules

    # Retry count 4 (> max=3) should be rejected
    res_4 = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_invalid_4)
    assert res_4.is_approved is False
    assert res_4.rejection_code == PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED


def test_rule_4_transaction_amount_cap_boundary():
    """Verify Rule 4 allows amounts <= max cap (₹50,000.00) and rejects amounts > max cap."""
    cap = create_dummy_capability(resolved_action="PAYMENT_LINK")

    tx_valid = create_dummy_transaction(amount=Decimal("50000.00"))
    res_valid = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_valid)
    assert res_valid.is_approved is True

    tx_exceeded = create_dummy_transaction(amount=Decimal("50000.01"))
    res_exceeded = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_exceeded)
    assert res_exceeded.is_approved is False
    assert res_exceeded.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP
    assert "Rule_4_Transaction_Amount_Cap" in res_exceeded.applied_rules


def test_rule_5_min_probability_threshold_boundary():
    """Verify Rule 5 allows probabilities >= min threshold (0.15) and rejects probabilities < 0.15."""
    cap = create_dummy_capability(resolved_action="PAYMENT_LINK")
    tx = create_dummy_transaction()

    # Prob = 0.15 -> Approved
    res_15 = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, candidate_probability=0.15)
    assert res_15.is_approved is True

    # Prob = 0.80 -> Approved
    res_80 = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, candidate_probability=0.80)
    assert res_80.is_approved is True

    # Prob = 0.1499 -> Rejected
    res_1499 = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, candidate_probability=0.1499)
    assert res_1499.is_approved is False
    assert res_1499.rejection_code == PolicyRejectionCode.MIN_PROBABILITY_NOT_MET
    assert "Rule_5_Min_Probability_Threshold" in res_1499.applied_rules

    # Prob = None -> Probability rule bypassed (approved if all other rules pass)
    res_none = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, candidate_probability=None)
    assert res_none.is_approved is True


def test_rule_6_cooldown_window_boundary():
    """Verify Rule 6 allows attempts when elapsed time >= 24h and rejects when elapsed < 24h."""
    cap = create_dummy_capability(resolved_action="PAYMENT_LINK")
    tx = create_dummy_transaction(retry_count=1)

    now_utc = datetime.now(timezone.utc)

    # Attempt 25 hours ago -> Cooldown passed
    attempt_25h = RecoveryAttempt()
    attempt_25h.created_at = now_utc - timedelta(hours=25)
    res_25h = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, last_attempt=attempt_25h)
    assert res_25h.is_approved is True

    # Attempt 23.9 hours ago -> Cooldown active
    attempt_23_9h = RecoveryAttempt()
    attempt_23_9h.created_at = now_utc - timedelta(hours=23, minutes=54)
    res_23_9h = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, last_attempt=attempt_23_9h)
    assert res_23_9h.is_approved is False
    assert res_23_9h.rejection_code == PolicyRejectionCode.COOLDOWN_ACTIVE
    assert "Rule_6_Cooldown_Hours" in res_23_9h.applied_rules

    # last_attempt = None -> Cooldown check bypassed
    res_no_attempt = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, last_attempt=None)
    assert res_no_attempt.is_approved is True


def test_policy_hierarchy_merchant_overrides_and_clamping():
    """Verify merchant policy rules override default policy but remain clamped by global hard bounds."""
    cap = create_dummy_capability(resolved_action="PAYMENT_LINK")

    # Stricter merchant policy: max retries = 2, max amount = ₹20,000.00
    merchant_policy = Policy()
    merchant_policy.policy_version = "v1.2-merchant-custom"
    merchant_policy.max_recovery_attempts = 2
    merchant_policy.max_auto_action_amount = Decimal("20000.00")
    merchant_policy.min_recovery_probability = 0.25
    merchant_policy.cooldown_hours = 48

    # Tx retry_count = 2 (exceeds merchant limit of 2)
    tx = create_dummy_transaction(amount=Decimal("15000.00"), retry_count=2)
    res = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx, policy=merchant_policy)
    assert res.is_approved is False
    assert res.rejection_code == PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED
    assert res.policy_version == "v1.2-merchant-custom"

    # Merchant trying to bypass global max amount (setting ₹100,000) -> Clamped to global max ₹50,000
    permissive_policy = Policy()
    permissive_policy.policy_version = "v1.0-permissive"
    permissive_policy.max_auto_action_amount = Decimal("100000.00")

    tx_60k = create_dummy_transaction(amount=Decimal("60000.00"))
    res_clamped = PolicyRuleEvaluator.evaluate(capability_result=cap, transaction=tx_60k, policy=permissive_policy)
    assert res_clamped.is_approved is False
    assert res_clamped.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP


def test_policy_real_test_vs_simulation_mode_evaluation():
    """Verify PolicyRuleEvaluator correctly respects execution mode from CapabilityResolutionResult."""
    tx = create_dummy_transaction()

    # SIMULATION mode supported capability
    cap_sim = create_dummy_capability(resolved_action="PAYMENT_LINK", is_executable=True, execution_mode=ExecutionMode.SIMULATION)
    res_sim = PolicyRuleEvaluator.evaluate(capability_result=cap_sim, transaction=tx)
    assert res_sim.is_approved is True

    # REAL_TEST mode unsupported capability
    cap_real_unsupported = create_dummy_capability(resolved_action="DIRECT_DEBIT", is_executable=False, execution_mode=ExecutionMode.REAL_TEST)
    res_real = PolicyRuleEvaluator.evaluate(capability_result=cap_real_unsupported, transaction=tx)
    assert res_real.is_approved is False
    assert res_real.rejection_code == PolicyRejectionCode.CAPABILITY_UNSUPPORTED
    assert "REAL_TEST" in res_real.rejection_reason


def test_policy_all_rejection_codes_coverage():
    """Verify all defined PolicyRejectionCode values can be emitted by PolicyRuleEvaluator."""
    rejection_codes = {
        PolicyRejectionCode.CAPABILITY_UNSUPPORTED,
        PolicyRejectionCode.EXPLICIT_STOP,
        PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED,
        PolicyRejectionCode.AMOUNT_EXCEEDS_CAP,
        PolicyRejectionCode.MIN_PROBABILITY_NOT_MET,
        PolicyRejectionCode.COOLDOWN_ACTIVE,
    }

    # 1. CAPABILITY_UNSUPPORTED
    res1 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(is_executable=False),
        transaction=create_dummy_transaction(),
    )
    assert res1.rejection_code == PolicyRejectionCode.CAPABILITY_UNSUPPORTED

    # 2. EXPLICIT_STOP
    res2 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(resolved_action="STOP"),
        transaction=create_dummy_transaction(),
    )
    assert res2.rejection_code == PolicyRejectionCode.EXPLICIT_STOP

    # 3. MAX_ATTEMPTS_EXCEEDED
    res3 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(),
        transaction=create_dummy_transaction(retry_count=3),
    )
    assert res3.rejection_code == PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED

    # 4. AMOUNT_EXCEEDS_CAP
    res4 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(),
        transaction=create_dummy_transaction(amount=Decimal("999999.00")),
    )
    assert res4.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP

    # 5. MIN_PROBABILITY_NOT_MET
    res5 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(),
        transaction=create_dummy_transaction(),
        candidate_probability=0.01,
    )
    assert res5.rejection_code == PolicyRejectionCode.MIN_PROBABILITY_NOT_MET

    # 6. COOLDOWN_ACTIVE
    attempt_recent = RecoveryAttempt()
    attempt_recent.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    res6 = PolicyRuleEvaluator.evaluate(
        capability_result=create_dummy_capability(),
        transaction=create_dummy_transaction(retry_count=1),
        last_attempt=attempt_recent,
    )
    assert res6.rejection_code == PolicyRejectionCode.COOLDOWN_ACTIVE

    # Verify all rejection codes were tested
    tested_codes = {res1.rejection_code, res2.rejection_code, res3.rejection_code, res4.rejection_code, res5.rejection_code, res6.rejection_code}
    assert tested_codes == rejection_codes

