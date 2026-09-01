"""
RecoverAI — Deterministic Policy Rules Evaluator (Step 15)

Implements the deterministic rule hierarchy:
Global Rules -> Merchant Rules -> Context Rules.
Evaluates max recovery attempts, transaction amount cap, minimum probability, and cooldown hours.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple
from backend.app.schemas.capability import CapabilityResolutionResult
from backend.app.schemas.policy import (
    PolicyStatus,
    PolicyRejectionCode,
    PolicyEvaluationResult,
)
from backend.app.models.domain import Transaction, Policy, RecoveryAttempt


# Global default policy parameters (fallback when merchant policy record is missing)
GLOBAL_DEFAULT_POLICY = {
    "policy_version": "v1.0",
    "max_recovery_attempts": 3,
    "max_auto_action_amount": Decimal("50000.00"),  # ₹50,000 cap (exact Decimal)
    "min_recovery_probability": 0.15,               # 15% minimum success probability
    "cooldown_hours": 24,                           # 24-hour minimum window between retries
}


class PolicyRuleEvaluator:
    """
    Evaluates deterministic safety guardrails for RecoverAI actions.
    No non-deterministic AI logic is permitted inside rules.
    """

    @staticmethod
    def evaluate(
        capability_result: CapabilityResolutionResult,
        transaction: Transaction,
        policy: Optional[Policy] = None,
        candidate_probability: Optional[float] = None,
        last_attempt: Optional[RecoveryAttempt] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluates an action against merchant/global safety policy parameters.

        Args:
            capability_result: Outcome from CapabilityResolver (Step 14).
            transaction: Transaction ORM model.
            policy: Merchant Policy model (or None to use global defaults).
            candidate_probability: Predicted recovery probability for the action.
            last_attempt: Most recent prior RecoveryAttempt record for cooldown check.

        Returns:
            PolicyEvaluationResult: Structured policy verdict.
        """
        # Determine effective policy limits (Merchant rule override clamped to Global default bounds)
        raw_max_attempts = policy.max_recovery_attempts if (policy and policy.max_recovery_attempts is not None) else GLOBAL_DEFAULT_POLICY["max_recovery_attempts"]
        max_attempts = min(raw_max_attempts, GLOBAL_DEFAULT_POLICY["max_recovery_attempts"])

        if policy and policy.max_auto_action_amount is not None:
            raw_max_amount = Decimal(str(policy.max_auto_action_amount))
        else:
            raw_max_amount = GLOBAL_DEFAULT_POLICY["max_auto_action_amount"]
        max_amount = min(raw_max_amount, GLOBAL_DEFAULT_POLICY["max_auto_action_amount"])

        raw_min_prob = policy.min_recovery_probability if (policy and policy.min_recovery_probability is not None) else GLOBAL_DEFAULT_POLICY["min_recovery_probability"]
        min_prob = max(0.05, min(0.50, raw_min_prob))

        raw_cooldown_h = policy.cooldown_hours if (policy and policy.cooldown_hours is not None) else GLOBAL_DEFAULT_POLICY["cooldown_hours"]
        cooldown_h = max(raw_cooldown_h, GLOBAL_DEFAULT_POLICY["cooldown_hours"])

        policy_ver = policy.policy_version if (policy and policy.policy_version) else GLOBAL_DEFAULT_POLICY["policy_version"]

        applied_rules: List[str] = []
        action = capability_result.resolved_action

        # Rule 1: Capability Support Check
        applied_rules.append("Rule_1_Capability_Support")
        if not capability_result.is_executable:
            return PolicyEvaluationResult(
                resolved_action=action,
                status=PolicyStatus.REJECTED,
                is_approved=False,
                rejection_code=PolicyRejectionCode.CAPABILITY_UNSUPPORTED,
                rejection_reason=f"Capability '{action}' is not executable in mode '{capability_result.execution_mode.value}'.",
                policy_version=policy_ver,
                applied_rules=applied_rules,
                attempt_number=transaction.retry_count + 1,
            )

        # Rule 2: Explicit STOP Check
        applied_rules.append("Rule_2_Explicit_Stop")
        if action == "STOP":
            return PolicyEvaluationResult(
                resolved_action=action,
                status=PolicyStatus.REJECTED,
                is_approved=False,
                rejection_code=PolicyRejectionCode.EXPLICIT_STOP,
                rejection_reason="Resolved action is STOP; no automated recovery intervention permitted.",
                policy_version=policy_ver,
                applied_rules=applied_rules,
                attempt_number=transaction.retry_count + 1,
            )

        # Rule 3: Max Recovery Attempts Check (<= 3)
        applied_rules.append("Rule_3_Max_Recovery_Attempts")
        current_attempts = transaction.retry_count
        if current_attempts >= max_attempts:
            return PolicyEvaluationResult(
                resolved_action=action,
                status=PolicyStatus.REJECTED,
                is_approved=False,
                rejection_code=PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED,
                rejection_reason=f"Recovery attempts limit reached ({current_attempts} >= max {max_attempts}).",
                policy_version=policy_ver,
                applied_rules=applied_rules,
                attempt_number=current_attempts + 1,
            )

        # Rule 4: Transaction Amount Cap Check (<= ₹50,000)
        applied_rules.append("Rule_4_Transaction_Amount_Cap")
        tx_amount = Decimal(str(transaction.amount))
        if tx_amount > max_amount:
            return PolicyEvaluationResult(
                resolved_action=action,
                status=PolicyStatus.REJECTED,
                is_approved=False,
                rejection_code=PolicyRejectionCode.AMOUNT_EXCEEDS_CAP,
                rejection_reason=f"Transaction amount ₹{tx_amount:,.2f} exceeds auto-action cap of ₹{max_amount:,.2f}.",
                policy_version=policy_ver,
                applied_rules=applied_rules,
                attempt_number=current_attempts + 1,
            )

        # Rule 5: Minimum Probability Threshold Check (>= 0.15)
        applied_rules.append("Rule_5_Min_Probability_Threshold")
        if candidate_probability is not None and candidate_probability < min_prob:
            return PolicyEvaluationResult(
                resolved_action=action,
                status=PolicyStatus.REJECTED,
                is_approved=False,
                rejection_code=PolicyRejectionCode.MIN_PROBABILITY_NOT_MET,
                rejection_reason=f"Predicted probability {candidate_probability:.4f} is below minimum required threshold {min_prob:.2f}.",
                policy_version=policy_ver,
                applied_rules=applied_rules,
                attempt_number=current_attempts + 1,
            )

        # Rule 6: Cooldown Window Check (>= 24 hours)
        applied_rules.append("Rule_6_Cooldown_Hours")
        if last_attempt and last_attempt.created_at:
            now_utc = datetime.now(timezone.utc)
            last_attempt_time = last_attempt.created_at
            if last_attempt_time.tzinfo is None:
                last_attempt_time = last_attempt_time.replace(tzinfo=timezone.utc)
            
            elapsed_hours = (now_utc - last_attempt_time).total_seconds() / 3600.0
            if elapsed_hours < cooldown_h:
                return PolicyEvaluationResult(
                    resolved_action=action,
                    status=PolicyStatus.REJECTED,
                    is_approved=False,
                    rejection_code=PolicyRejectionCode.COOLDOWN_ACTIVE,
                    rejection_reason=f"Cooldown active ({elapsed_hours:.1f}h elapsed since last attempt < required {cooldown_h}h).",
                    policy_version=policy_ver,
                    applied_rules=applied_rules,
                    attempt_number=current_attempts + 1,
                )

        # All deterministic rules PASSED -> APPROVED
        return PolicyEvaluationResult(
            resolved_action=action,
            status=PolicyStatus.APPROVED,
            is_approved=True,
            rejection_code=None,
            rejection_reason=f"Action '{action}' approved by policy rules (version {policy_ver}).",
            policy_version=policy_ver,
            applied_rules=applied_rules,
            attempt_number=current_attempts + 1,
        )
