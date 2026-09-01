"""
RecoverAI - Step 37 Unit Tests: State Machine Transition Matrix & Exception Handling
"""

import pytest
from backend.app.schemas.state_machine import (
    TransactionStatus,
    PaymentStatus,
    ExecutionStatus,
    AttributionStatus,
    VALID_TRANSACTION_TRANSITIONS,
    InvalidStateTransitionException,
)


def test_valid_transaction_transitions_matrix_completeness():
    """Verify all authoritative TransactionStatus enum values are defined in VALID_TRANSACTION_TRANSITIONS."""
    for status in TransactionStatus:
        assert status.value in VALID_TRANSACTION_TRANSITIONS, f"Status '{status.value}' missing from transition matrix"


def test_allowed_transaction_state_transitions():
    """Verify all valid transaction state transition paths specified in the matrix."""
    # CREATED -> AT_RISK, FAILED, STOPPED
    assert TransactionStatus.AT_RISK.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.CREATED.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.CREATED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.CREATED.value]

    # AT_RISK -> DIAGNOSED, FAILED, STOPPED, EXPIRED
    assert TransactionStatus.DIAGNOSED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.AT_RISK.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.AT_RISK.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.AT_RISK.value]
    assert TransactionStatus.EXPIRED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.AT_RISK.value]

    # DIAGNOSED -> INTERVENTION_SELECTED, FAILED, STOPPED, ESCALATED
    assert TransactionStatus.INTERVENTION_SELECTED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.DIAGNOSED.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.DIAGNOSED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.DIAGNOSED.value]
    assert TransactionStatus.ESCALATED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.DIAGNOSED.value]

    # INTERVENTION_SELECTED -> POLICY_CHECK, FAILED, STOPPED
    assert TransactionStatus.POLICY_CHECK.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.INTERVENTION_SELECTED.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.INTERVENTION_SELECTED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.INTERVENTION_SELECTED.value]

    # POLICY_CHECK -> APPROVED, FAILED, STOPPED, ESCALATED
    assert TransactionStatus.APPROVED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.POLICY_CHECK.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.POLICY_CHECK.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.POLICY_CHECK.value]
    assert TransactionStatus.ESCALATED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.POLICY_CHECK.value]

    # APPROVED -> EXECUTING, STOPPED, ESCALATED
    assert TransactionStatus.EXECUTING.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.APPROVED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.APPROVED.value]
    assert TransactionStatus.ESCALATED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.APPROVED.value]

    # EXECUTING -> RECOVERED, FAILED, STOPPED, ESCALATED, EXPIRED, REFUNDED
    assert TransactionStatus.RECOVERED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]
    assert TransactionStatus.ESCALATED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]
    assert TransactionStatus.EXPIRED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]
    assert TransactionStatus.REFUNDED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]

    # RECOVERED -> REFUNDED
    assert TransactionStatus.REFUNDED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.RECOVERED.value]

    # FAILED -> AT_RISK, STOPPED, ESCALATED
    assert TransactionStatus.AT_RISK.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.FAILED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.FAILED.value]
    assert TransactionStatus.ESCALATED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.FAILED.value]

    # ESCALATED -> APPROVED, STOPPED, FAILED
    assert TransactionStatus.APPROVED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.ESCALATED.value]
    assert TransactionStatus.STOPPED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.ESCALATED.value]
    assert TransactionStatus.FAILED.value in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.ESCALATED.value]


def test_forbidden_transaction_state_transitions():
    """Verify invalid transition attempts fail transition matrix checks."""
    # Direct illegal jumps
    assert TransactionStatus.RECOVERED.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.CREATED.value]
    assert TransactionStatus.EXECUTING.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.AT_RISK.value]
    assert TransactionStatus.APPROVED.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.DIAGNOSED.value]
    assert TransactionStatus.RECOVERED.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.APPROVED.value]

    # Reverse transitions
    assert TransactionStatus.CREATED.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.RECOVERED.value]
    assert TransactionStatus.DIAGNOSED.value not in VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXECUTING.value]


def test_terminal_states_have_zero_outgoing_transitions():
    """Verify terminal transaction states (STOPPED, EXPIRED, REFUNDED) permit zero outgoing transitions."""
    assert len(VALID_TRANSACTION_TRANSITIONS[TransactionStatus.STOPPED.value]) == 0
    assert len(VALID_TRANSACTION_TRANSITIONS[TransactionStatus.EXPIRED.value]) == 0
    assert len(VALID_TRANSACTION_TRANSITIONS[TransactionStatus.REFUNDED.value]) == 0


def test_invalid_state_transition_exception_formatting():
    """Verify InvalidStateTransitionException attributes and string message representation."""
    exc = InvalidStateTransitionException(
        state_from="CREATED",
        state_to="RECOVERED",
        transaction_id="tx_test_999",
    )

    assert exc.state_from == "CREATED"
    assert exc.state_to == "RECOVERED"
    assert exc.transaction_id == "tx_test_999"
    assert "Invalid state transition for transaction tx_test_999" in str(exc)
    assert "cannot transition from 'CREATED' to 'RECOVERED'" in str(exc)


def test_ancillary_state_enums():
    """Verify enum value constants for PaymentStatus, ExecutionStatus, and AttributionStatus."""
    assert PaymentStatus.CAPTURED.value == "CAPTURED"
    assert ExecutionStatus.SUCCESS.value == "SUCCESS"
    assert ExecutionStatus.UNKNOWN.value == "UNKNOWN"
    assert ExecutionStatus.RECONCILIATION.value == "RECONCILIATION"
    assert AttributionStatus.ATTRIBUTED.value == "ATTRIBUTED"
    assert AttributionStatus.NATURAL_RECOVERY.value == "NATURAL_RECOVERY"


def test_terminal_state_transition_matrix_rejection():
    """Verify attempting transition from any terminal state (STOPPED, EXPIRED, REFUNDED) returns False in matrix lookup."""
    terminal_states = [TransactionStatus.STOPPED, TransactionStatus.EXPIRED, TransactionStatus.REFUNDED]
    target_states = list(TransactionStatus)

    for term_state in terminal_states:
        for target in target_states:
            assert target.value not in VALID_TRANSACTION_TRANSITIONS[term_state.value], f"Terminal state {term_state.value} allowed transition to {target.value}"


def test_unauthorized_direct_state_jump_rejection():
    """Verify unauthorized state jumps (e.g. CREATED to EXECUTING) fail valid matrix lookup."""
    unauthorized_jumps = [
        (TransactionStatus.CREATED, TransactionStatus.EXECUTING),
        (TransactionStatus.CREATED, TransactionStatus.RECOVERED),
        (TransactionStatus.AT_RISK, TransactionStatus.RECOVERED),
        (TransactionStatus.DIAGNOSED, TransactionStatus.EXECUTING),
        (TransactionStatus.POLICY_CHECK, TransactionStatus.RECOVERED),
    ]

    for source, dest in unauthorized_jumps:
        assert dest.value not in VALID_TRANSACTION_TRANSITIONS[source.value]

