"""
RecoverAI — Capability Schema Definitions (Step 14)

Defines execution modes, capability statuses, and resolution result schemas
for the non-bypassable CapabilityResolver gate.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    """Supported execution modes for RecoverAI processing."""
    REAL_TEST = "REAL_TEST"
    SIMULATION = "SIMULATION"


class CapabilityStatus(str, Enum):
    """Status of an action's technical capability in an operational mode."""
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    INTERNAL = "INTERNAL"


class CapabilityResolutionResult(BaseModel):
    """
    Structured outcome of CapabilityResolver inspection.
    Passed downstream to PolicyEngine (Step 15).
    """
    resolved_action: str = Field(
        ...,
        description="The capability-verified executable recovery action."
    )
    status: CapabilityStatus = Field(
        ...,
        description="Capability support status for the resolved action in the active mode."
    )
    execution_mode: ExecutionMode = Field(
        ...,
        description="Active operational mode (REAL_TEST or SIMULATION)."
    )
    is_executable: bool = Field(
        ...,
        description="True if the resolved action can technically be executed in this mode."
    )
    reason: str = Field(
        ...,
        description="Human-readable explanation of capability resolution logic."
    )
    fallback_applied: bool = Field(
        default=False,
        description="True if the original recommendation was unsupported and an ENRV fallback was selected."
    )
    original_recommendation: Optional[str] = Field(
        default=None,
        description="Original AI recommendation prior to capability resolution if fallback was applied."
    )
