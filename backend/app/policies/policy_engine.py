"""
RecoverAI — Deterministic Policy Engine Service (Step 15)

Evaluates merchant safety rules, cooldown windows, and amount caps.
Positioned strictly between CapabilityResolver (Step 14) and ActionExecutor (Step 17).
Transitioning transaction lifecycle state via StateTransitionService.
"""

from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.capability import CapabilityResolutionResult
from backend.app.schemas.policy import (
    PolicyStatus,
    PolicyRejectionCode,
    PolicyEvaluationResult,
)
from backend.app.policies.rules import PolicyRuleEvaluator
from backend.app.models.domain import (
    Transaction,
    Policy,
    RecoveryAttempt,
    AuditEvent,
    generate_uuid,
)
from backend.app.services.state_transition_service import StateTransitionService
from backend.app.schemas.state_machine import TransactionStatus


class PolicyEngine:
    """
    Deterministic Policy Engine for RecoverAI.
    Enforces non-negotiable safety guardrails that AI can never override or bypass.
    """

    def __init__(self):
        self.evaluator = PolicyRuleEvaluator()

    async def get_merchant_policy(
        self,
        session: AsyncSession,
        merchant_id: str,
    ) -> Optional[Policy]:
        """Fetches active policy for merchant from database."""
        stmt = (
            select(Policy)
            .where(Policy.merchant_id == merchant_id, Policy.is_active == True)
            .order_by(Policy.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_recovery_attempt(
        self,
        session: AsyncSession,
        transaction_id: str,
    ) -> Optional[RecoveryAttempt]:
        """Fetches the most recent recovery attempt for cooldown window verification."""
        stmt = (
            select(RecoveryAttempt)
            .where(RecoveryAttempt.transaction_id == transaction_id)
            .order_by(RecoveryAttempt.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def evaluate_and_transition(
        self,
        session: AsyncSession,
        transaction_id: str,
        capability_result: CapabilityResolutionResult,
        merchant_id: Optional[str] = None,
        candidate_probability: Optional[float] = None,
        actor: str = "POLICY_ENGINE",
    ) -> Tuple[PolicyEvaluationResult, Transaction]:
        """
        Evaluates policy guardrails for a transaction and executes state transitions.

        Steps:
        1. Multi-tenant merchant isolation check.
        2. Transition transaction lifecycle state: INTERVENTION_SELECTED -> POLICY_CHECK.
        3. Evaluate deterministic policy rules against Merchant policy or Global defaults.
        4. Transition state: POLICY_CHECK -> APPROVED (if passed) or STOPPED/ESCALATED (if rejected).
        5. Insert recovery attempt metadata record in database.

        Returns:
            Tuple of (PolicyEvaluationResult, updated Transaction).
        """
        # 1. Acquire transaction row with SELECT FOR UPDATE via StateTransitionService
        # Transition to POLICY_CHECK state first
        tx, audit_check = await StateTransitionService.transition(
            session=session,
            transaction_id=transaction_id,
            target_state=TransactionStatus.POLICY_CHECK.value,
            actor=actor,
            reason=f"Initiating policy check for capability '{capability_result.resolved_action}'",
            details={
                "capability_resolved_action": capability_result.resolved_action,
                "capability_status": capability_result.status.value,
                "capability_execution_mode": capability_result.execution_mode.value,
            },
        )

        # Multi-tenant merchant isolation check
        if merchant_id and tx.merchant_id != merchant_id:
            raise ValueError(
                f"Merchant ID mismatch for transaction '{transaction_id}': "
                f"expected '{merchant_id}', got '{tx.merchant_id}'"
            )

        # 2. Fetch merchant policy and latest attempt record
        policy = await self.get_merchant_policy(session, tx.merchant_id)
        last_attempt = await self.get_latest_recovery_attempt(session, transaction_id)

        # 3. Evaluate deterministic rules
        policy_result = self.evaluator.evaluate(
            capability_result=capability_result,
            transaction=tx,
            policy=policy,
            candidate_probability=candidate_probability,
            last_attempt=last_attempt,
        )

        # 4. Transition state based on evaluation outcome
        if policy_result.is_approved:
            target_state = TransactionStatus.APPROVED.value
            reason = f"Policy check passed for action '{policy_result.resolved_action}'."
        else:
            # Check if rejection code warrants escalation to human review
            if policy_result.rejection_code in (
                PolicyRejectionCode.AMOUNT_EXCEEDS_CAP,
                PolicyRejectionCode.MIN_PROBABILITY_NOT_MET,
            ):
                target_state = TransactionStatus.ESCALATED.value
                reason = f"Policy rejected action '{policy_result.resolved_action}' ({policy_result.rejection_code.value}): escalated for human review."
            else:
                target_state = TransactionStatus.STOPPED.value
                reason = f"Policy rejected action '{policy_result.resolved_action}' ({policy_result.rejection_code.value})."

        tx_final, audit_final = await StateTransitionService.transition(
            session=session,
            transaction_id=transaction_id,
            target_state=target_state,
            actor=actor,
            reason=reason,
            details={
                "policy_version": policy_result.policy_version,
                "is_approved": policy_result.is_approved,
                "rejection_code": policy_result.rejection_code.value if policy_result.rejection_code else None,
                "rejection_reason": policy_result.rejection_reason,
                "applied_rules": policy_result.applied_rules,
                "attempt_number": policy_result.attempt_number,
            },
        )

        # 5. Record attempt record in recovery_attempts
        attempt_id = generate_uuid()
        recovery_cycle = getattr(tx_final, "recovery_cycle", 1)
        attempt_seq = policy_result.attempt_number
        op_key = f"{tx_final.merchant_id}:{transaction_id}:{recovery_cycle}:{policy_result.resolved_action}"
        if attempt_seq > 1:
            op_key += f":{attempt_seq}"

        attempt_record = RecoveryAttempt(
            id=attempt_id,
            transaction_id=transaction_id,
            logical_operation_key=op_key,
            recommended_action=policy_result.resolved_action,
            action_payload={
                "execution_mode": capability_result.execution_mode.value,
                "capability_status": capability_result.status.value,
                "applied_rules": policy_result.applied_rules,
            },
            policy_status=policy_result.status.value,
            policy_reason=policy_result.rejection_reason,
            policy_version=policy_result.policy_version,
            execution_status="PENDING",
            external_resource_type=capability_result.resolved_action,
        )
        session.add(attempt_record)
        await session.flush()

        return policy_result, tx_final
