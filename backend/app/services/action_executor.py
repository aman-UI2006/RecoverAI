"""Step 17 — Action Executor Service for RecoverAI.

Orchestrates execution of policy-approved recovery interventions safely, idempotently,
and with strict air-gap adapter boundary isolation.
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, RecoveryAttempt, current_utc_time, generate_uuid
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.schemas.executor import ActionExecutionRequest, ActionExecutionResponse
from backend.app.services.capability_resolver import CapabilityResolver
from backend.app.services.state_transition_service import StateTransitionService

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Service handling execution dispatching for policy-approved recovery actions."""

    @staticmethod
    async def execute(
        session: AsyncSession,
        request: ActionExecutionRequest,
        adapter_delegate: Optional[Any] = None,
    ) -> ActionExecutionResponse:
        """Execute a policy-approved recovery action with idempotency and state safety.

        Args:
            session: Active SQLAlchemy AsyncSession.
            request: ActionExecutionRequest payload.
            adapter_delegate: Optional external execution delegate/adapter (Step 18 interface).

        Returns:
            ActionExecutionResponse details.

        Raises:
            ValueError: If transaction is missing, merchant ID mismatches, transaction is not APPROVED,
                        or defensive capability check fails.
        """
        # 1. Row-lock transaction & fetch authoritative state
        stmt_tx = (
            select(Transaction)
            .where(Transaction.id == request.transaction_id)
            .with_for_update()
        )
        tx = (await session.execute(stmt_tx)).scalar_one_or_none()

        if not tx:
            raise ValueError(f"Transaction with ID '{request.transaction_id}' not found.")

        # 2. Multi-Tenant Merchant Isolation Check
        if tx.merchant_id != request.merchant_id:
            raise ValueError(
                f"Merchant ID mismatch: transaction '{tx.id}' belongs to merchant '{tx.merchant_id}', "
                f"not '{request.merchant_id}'."
            )

        # 3. Approved-Action Gate Check (APPROVED or EXECUTING for replay)
        if tx.status not in (TransactionStatus.APPROVED.value, TransactionStatus.EXECUTING.value):
            raise ValueError(
                f"Transaction '{tx.id}' is in status '{tx.status}'; action execution requires APPROVED status."
            )

        # 4. Authoritative Logical Operation Key Construction
        # Format: merchant_id:transaction_id:recovery_cycle:action
        logical_op_key = f"{request.merchant_id}:{tx.id}:{tx.recovery_cycle}:{request.action_type}"

        # 5. Check existing RecoveryAttempt for Idempotency Replay
        stmt_existing = select(RecoveryAttempt).where(
            RecoveryAttempt.logical_operation_key == logical_op_key
        )
        existing_attempt = (await session.execute(stmt_existing)).scalar_one_or_none()

        if existing_attempt:
            # Replay protection: if attempt is already SUCCESS, EXECUTING, or UNKNOWN, return existing record
            if existing_attempt.execution_status in (
                ExecutionStatus.SUCCESS.value,
                ExecutionStatus.EXECUTING.value,
                ExecutionStatus.UNKNOWN.value,
            ):
                logger.info(
                    f"Idempotent execution replay detected for key '{logical_op_key}'. "
                    f"Returning existing execution ID '{existing_attempt.id}'."
                )

                return ActionExecutionResponse(
                    execution_id=existing_attempt.id,
                    transaction_id=tx.id,
                    merchant_id=request.merchant_id,
                    logical_operation_key=logical_op_key,
                    action_type=request.action_type,
                    execution_status=existing_attempt.execution_status,
                    external_resource_type=existing_attempt.external_resource_type,
                    external_resource_id=existing_attempt.external_resource_id,
                    razorpay_payment_link_id=existing_attempt.razorpay_payment_link_id,
                    razorpay_reference_id=existing_attempt.razorpay_reference_id,
                    audit_event_id="audit_idempotent_replay",
                    executed_at=existing_attempt.executed_at or existing_attempt.created_at,
                    is_duplicate=True,
                )

        # If tx is in EXECUTING state without a matching existing attempt for this operation key, block execution
        if tx.status == TransactionStatus.EXECUTING.value:
            raise ValueError(
                f"Transaction '{tx.id}' is in status EXECUTING; cannot execute new action '{request.action_type}'."
            )

        # 6. Defensive Capability Check immediately before execution
        resolver = CapabilityResolver()
        effective_mode = request.mode_override or getattr(tx, "mode", "REAL_TEST")
        cap_res = resolver.resolve_action_capability(
            action=request.action_type,
            mode=effective_mode,
        )

        if not cap_res.is_executable:
            raise ValueError(
                f"Defensive capability check failed for action '{request.action_type}': {cap_res.reason}"
            )

        mode_str = cap_res.execution_mode.value if hasattr(cap_res.execution_mode, "value") else str(cap_res.execution_mode)

        # 7. Check for existing RecoveryAttempt record or create a new PENDING one
        now = current_utc_time()
        stmt_existing = select(RecoveryAttempt).where(
            RecoveryAttempt.logical_operation_key == logical_op_key
        )
        existing_attempt = (await session.execute(stmt_existing)).scalar_one_or_none()

        if existing_attempt:
            attempt = existing_attempt
            attempt_id = existing_attempt.id
            if existing_attempt.execution_status in (ExecutionStatus.SUCCESS.value, ExecutionStatus.EXECUTING.value):
                return ActionExecutionResponse(
                    execution_id=existing_attempt.id,
                    transaction_id=tx.id,
                    merchant_id=request.merchant_id,
                    logical_operation_key=logical_op_key,
                    action_type=request.action_type,
                    execution_status=existing_attempt.execution_status,
                    external_resource_type=existing_attempt.external_resource_type or mode_str,
                    external_resource_id=existing_attempt.external_resource_id,
                    razorpay_payment_link_id=existing_attempt.razorpay_payment_link_id,
                    razorpay_reference_id=existing_attempt.razorpay_reference_id,
                    audit_event_id="audit_existing_duplicate",
                    executed_at=existing_attempt.executed_at or existing_attempt.created_at,
                    is_duplicate=True,
                )
        else:
            attempt_id = generate_uuid()
            attempt = RecoveryAttempt(
                id=attempt_id,
                transaction_id=tx.id,
                decision_context_id=request.decision_context_id,
                logical_operation_key=logical_op_key,
                recommended_action=request.action_type,
                action_payload=request.action_payload,
                policy_status="APPROVED",
                policy_reason="Policy approved for execution",
                policy_version="1.0",
                execution_status=ExecutionStatus.PENDING.value,
                external_resource_type=mode_str,
                created_at=now,
            )
            session.add(attempt)
            await session.flush()

        # 8. Authoritative State Mutation via StateTransitionService: APPROVED -> EXECUTING
        updated_tx, audit_record = await StateTransitionService.transition(
            session=session,
            transaction_id=tx.id,
            target_state=TransactionStatus.EXECUTING.value,
            actor="ACTION_EXECUTOR",
            reason=f"Dispatching execution for action '{request.action_type}'",
            details={
                "logical_operation_key": logical_op_key,
                "execution_mode": mode_str,
                "attempt_id": attempt_id,
            },
        )

        # 9. Mode Dispatching & Execution
        execution_status = ExecutionStatus.EXECUTING.value
        external_resource_id = None
        rzp_payment_link_id = None
        rzp_reference_id = None
        executed_time = current_utc_time()

        if mode_str == "REAL_TEST":
            if adapter_delegate:
                try:
                    delegate_res = await adapter_delegate.execute_action(
                        transaction=updated_tx,
                        request=request,
                    )
                    if delegate_res.get("success", False):
                        execution_status = ExecutionStatus.SUCCESS.value
                        external_resource_id = delegate_res.get("external_resource_id")
                        rzp_payment_link_id = delegate_res.get("razorpay_payment_link_id")
                        rzp_reference_id = delegate_res.get("razorpay_reference_id")
                    else:
                        execution_status = ExecutionStatus.FAILURE.value
                except (TimeoutError, Exception) as exc:
                    logger.warning(
                        f"External adapter execution timed out or failed for transaction '{tx.id}': {exc}"
                    )
                    # UNKNOWN Result Safety Protection: Network/Timeout errors transition attempt to UNKNOWN
                    execution_status = ExecutionStatus.UNKNOWN.value
            else:
                # Stub / Interface execution for Step 17 before Step 18 concrete adapter
                execution_status = ExecutionStatus.SUCCESS.value
                rzp_payment_link_id = f"plink_test_{generate_uuid()[:12]}"
                rzp_reference_id = f"ref_{generate_uuid()[:8]}"
                external_resource_id = rzp_payment_link_id

        elif mode_str == "SIMULATION":
            if adapter_delegate:
                delegate_res = await adapter_delegate.execute_action(
                    transaction=updated_tx,
                    request=request,
                )
                execution_status = delegate_res.get("execution_status", ExecutionStatus.SUCCESS.value)
                external_resource_id = delegate_res.get("external_resource_id")
                rzp_payment_link_id = delegate_res.get("razorpay_payment_link_id")
                rzp_reference_id = delegate_res.get("razorpay_reference_id")
            else:
                execution_status = ExecutionStatus.SUCCESS.value
                external_resource_id = f"plink_sim_{generate_uuid()[:12]}"
                rzp_payment_link_id = external_resource_id
                rzp_reference_id = f"ref_{generate_uuid()[:8]}"

        # 10. Update RecoveryAttempt execution status & details
        attempt.execution_status = execution_status
        attempt.external_resource_id = external_resource_id
        attempt.razorpay_payment_link_id = rzp_payment_link_id
        attempt.razorpay_reference_id = rzp_reference_id
        attempt.executed_at = executed_time

        await session.commit()
        await session.refresh(attempt)

        return ActionExecutionResponse(
            execution_id=attempt.id,
            transaction_id=tx.id,
            merchant_id=request.merchant_id,
            logical_operation_key=logical_op_key,
            action_type=request.action_type,
            execution_status=execution_status,
            external_resource_type=mode_str,
            external_resource_id=external_resource_id,
            razorpay_payment_link_id=rzp_payment_link_id,
            razorpay_reference_id=rzp_reference_id,
            audit_event_id=audit_record.id,
            executed_at=executed_time,
            is_duplicate=False,
        )
