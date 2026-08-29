"""State Machine Schemas and Transition Matrix for RecoverAI Step 7."""

from enum import Enum
from typing import Any, Dict, Optional, Set
from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    """Authoritative transaction lifecycle states."""

    CREATED = "CREATED"
    AT_RISK = "AT_RISK"
    DIAGNOSED = "DIAGNOSED"
    INTERVENTION_SELECTED = "INTERVENTION_SELECTED"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, Enum):
    """Payment lifecycle states."""

    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURE_PENDING = "CAPTURE_PENDING"
    CAPTURED = "CAPTURED"
    REFUNDED = "REFUNDED"


class ExecutionStatus(str, Enum):
    """Execution lifecycle states for recovery attempts."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION = "RECONCILIATION"
    RECONCILED = "RECONCILED"


class AttributionStatus(str, Enum):
    """Attribution status for recovered revenue."""

    ATTRIBUTED = "ATTRIBUTED"
    NATURAL_RECOVERY = "NATURAL_RECOVERY"
    UNATTRIBUTED = "UNATTRIBUTED"


# Authoritative state transition matrix governing transaction lifecycle mutations
VALID_TRANSACTION_TRANSITIONS: Dict[str, Set[str]] = {
    TransactionStatus.CREATED.value: {
        TransactionStatus.AT_RISK.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
    },
    TransactionStatus.AT_RISK.value: {
        TransactionStatus.DIAGNOSED.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.EXPIRED.value,
    },
    TransactionStatus.DIAGNOSED.value: {
        TransactionStatus.INTERVENTION_SELECTED.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.ESCALATED.value,
    },
    TransactionStatus.INTERVENTION_SELECTED.value: {
        TransactionStatus.POLICY_CHECK.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
    },
    TransactionStatus.POLICY_CHECK.value: {
        TransactionStatus.APPROVED.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.ESCALATED.value,
    },
    TransactionStatus.APPROVED.value: {
        TransactionStatus.EXECUTING.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.ESCALATED.value,
    },
    TransactionStatus.EXECUTING.value: {
        TransactionStatus.RECOVERED.value,
        TransactionStatus.FAILED.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.ESCALATED.value,
        TransactionStatus.EXPIRED.value,
        TransactionStatus.REFUNDED.value,
    },
    TransactionStatus.RECOVERED.value: {
        TransactionStatus.REFUNDED.value,
    },
    TransactionStatus.FAILED.value: {
        TransactionStatus.AT_RISK.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.ESCALATED.value,
    },
    TransactionStatus.ESCALATED.value: {
        TransactionStatus.APPROVED.value,
        TransactionStatus.STOPPED.value,
        TransactionStatus.FAILED.value,
    },
    TransactionStatus.STOPPED.value: set(),  # Terminal state
    TransactionStatus.EXPIRED.value: set(),  # Terminal state
    TransactionStatus.REFUNDED.value: set(),  # Terminal state
}


class InvalidStateTransitionException(Exception):
    """Custom exception raised when an invalid transaction state transition is attempted."""

    def __init__(self, state_from: str, state_to: str, transaction_id: str):
        self.state_from = state_from
        self.state_to = state_to
        self.transaction_id = transaction_id
        super().__init__(
            f"Invalid state transition for transaction {transaction_id}: "
            f"cannot transition from '{state_from}' to '{state_to}'."
        )


class StateTransitionRequest(BaseModel):
    """Schema for requesting a state transition."""

    transaction_id: str = Field(..., description="UUID of the transaction to mutate")
    target_state: str = Field(..., description="Target state to transition into")
    actor: str = Field(default="SYSTEM", description="Actor initiating the transition")
    reason: Optional[str] = Field(default=None, description="Optional reason for state transition")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional context payload for audit trail")


class StateTransitionResponse(BaseModel):
    """Schema for successful state transition output."""

    transaction_id: str
    previous_state: str
    current_state: str
    actor: str
    audit_event_id: str
    event_hash: str
