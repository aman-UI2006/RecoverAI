"""
RecoverAI — Capability Resolver Service (Step 14)

Evaluates whether an AI-recommended recovery action is executable in the active
operational mode (REAL_TEST vs SIMULATION). Positioned strictly between AI Recommender
(Step 13) and Policy Engine (Step 15) to guarantee non-bypassable air-gap execution safety.
"""

from typing import Optional, List, Dict, Set
from backend.app.schemas.capability import (
    ExecutionMode,
    CapabilityStatus,
    CapabilityResolutionResult,
)
from backend.app.schemas.ai_recommendation import AIRecommendationResponse
from backend.app.schemas.enrv import ENRVCalculationResponse
from backend.app.models.domain import Transaction


# Authoritative Mode-Aware Capability Matrix
CAPABILITY_MATRIX: Dict[ExecutionMode, Dict[str, CapabilityStatus]] = {
    ExecutionMode.REAL_TEST: {
        "PAYMENT_LINK": CapabilityStatus.SUPPORTED,
        "RECOVERY_MESSAGE": CapabilityStatus.INTERNAL,
        "STOP": CapabilityStatus.INTERNAL,
        "ESCALATE": CapabilityStatus.INTERNAL,
        "HUMAN_REVIEW": CapabilityStatus.INTERNAL,
        "RETRY": CapabilityStatus.UNSUPPORTED,
        "AUTOMATED_GATEWAY_RETRY": CapabilityStatus.UNSUPPORTED,
        "SUBSCRIPTION_RECOVERY": CapabilityStatus.REQUIRES_VERIFICATION,
        "SMART_RETRY_SCHEDULE": CapabilityStatus.REQUIRES_VERIFICATION,
        "DISCOUNT_NUDGE": CapabilityStatus.REQUIRES_VERIFICATION,
    },
    ExecutionMode.SIMULATION: {
        "PAYMENT_LINK": CapabilityStatus.SUPPORTED,
        "RECOVERY_MESSAGE": CapabilityStatus.SUPPORTED,
        "SUBSCRIPTION_RECOVERY": CapabilityStatus.SUPPORTED,
        "RETRY": CapabilityStatus.SUPPORTED,
        "AUTOMATED_GATEWAY_RETRY": CapabilityStatus.SUPPORTED,
        "SMART_RETRY_SCHEDULE": CapabilityStatus.SUPPORTED,
        "DISCOUNT_NUDGE": CapabilityStatus.SUPPORTED,
        "STOP": CapabilityStatus.SUPPORTED,
        "ESCALATE": CapabilityStatus.SUPPORTED,
        "HUMAN_REVIEW": CapabilityStatus.SUPPORTED,
    },
}

# Normalize common action alias strings to canonical keys
ACTION_ALIASES: Dict[str, str] = {
    "PAYMENT_LINK": "PAYMENT_LINK",
    "CREATE_PAYMENT_LINK": "PAYMENT_LINK",
    "RECOVERY_MESSAGE": "RECOVERY_MESSAGE",
    "SEND_RECOVERY_MESSAGE": "RECOVERY_MESSAGE",
    "RETRY": "RETRY",
    "AUTOMATED_GATEWAY_RETRY": "AUTOMATED_GATEWAY_RETRY",
    "SUBSCRIPTION_RECOVERY": "SUBSCRIPTION_RECOVERY",
    "SMART_RETRY_SCHEDULE": "SMART_RETRY_SCHEDULE",
    "DISCOUNT_NUDGE": "DISCOUNT_NUDGE",
    "STOP": "STOP",
    "ESCALATE": "ESCALATE",
    "HUMAN_REVIEW": "HUMAN_REVIEW",
}


class CapabilityResolver:
    """
    Capability Resolver service for RecoverAI.
    Ensures non-executable actions are filtered out before reaching PolicyEngine.
    """

    @staticmethod
    def normalize_action(action: str) -> str:
        """Normalizes action string uppercase and resolves common aliases."""
        clean_action = action.strip().upper()
        return ACTION_ALIASES.get(clean_action, clean_action)

    @staticmethod
    def parse_mode(mode: str | ExecutionMode) -> ExecutionMode:
        """Parses and validates operational execution mode."""
        if isinstance(mode, ExecutionMode):
            return mode
        cleaned = mode.strip().upper()
        if cleaned in ("REAL_TEST", "REAL"):
            return ExecutionMode.REAL_TEST
        elif cleaned == "SIMULATION":
            return ExecutionMode.SIMULATION
        else:
            raise ValueError(f"Invalid operational execution mode: '{mode}'. Must be 'REAL_TEST' or 'SIMULATION'.")

    def is_action_executable(self, action: str, mode: str | ExecutionMode) -> bool:
        """Checks if a single action is technically executable in the given mode."""
        parsed_mode = self.parse_mode(mode)
        norm_action = self.normalize_action(action)
        mode_matrix = CAPABILITY_MATRIX.get(parsed_mode, {})
        status = mode_matrix.get(norm_action, CapabilityStatus.UNSUPPORTED)
        return status in (CapabilityStatus.SUPPORTED, CapabilityStatus.INTERNAL)

    def resolve_action_capability(
        self,
        action: str,
        mode: str | ExecutionMode,
    ) -> CapabilityResolutionResult:
        """
        Resolves capability status for a single action in the given mode.
        """
        parsed_mode = self.parse_mode(mode)
        norm_action = self.normalize_action(action)
        mode_matrix = CAPABILITY_MATRIX.get(parsed_mode, {})
        status = mode_matrix.get(norm_action, CapabilityStatus.UNSUPPORTED)

        executable = status in (CapabilityStatus.SUPPORTED, CapabilityStatus.INTERNAL)

        if executable:
            reason = f"Action '{norm_action}' is executable ({status.value}) in {parsed_mode.value} mode."
        else:
            reason = (
                f"Action '{norm_action}' is not executable ({status.value}) in {parsed_mode.value} mode. "
                f"Only verified capabilities (e.g. PAYMENT_LINK) are executable in REAL_TEST mode."
            )

        return CapabilityResolutionResult(
            resolved_action=norm_action,
            status=status,
            execution_mode=parsed_mode,
            is_executable=executable,
            reason=reason,
            fallback_applied=False,
            original_recommendation=None,
        )

    def resolve_recommendation(
        self,
        recommendation: AIRecommendationResponse,
        enrv_response: Optional[ENRVCalculationResponse] = None,
        mode: str | ExecutionMode = ExecutionMode.SIMULATION,
        transaction: Optional[Transaction] = None,
        merchant_id: Optional[str] = None,
    ) -> CapabilityResolutionResult:
        """
        Resolves AI recommendation capability, performing ENRV-based fallback if top action is unsupported.

        Args:
            recommendation: AI recommendation response payload.
            enrv_response: Optional ENRV calculation response containing ranked candidates.
            mode: Active operational execution mode.
            transaction: Optional transaction ORM model (mode derived if provided).
            merchant_id: Optional merchant ID for multi-tenant isolation check.

        Returns:
            CapabilityResolutionResult: Capability decision for downstream PolicyEngine.
        """
        # Multi-tenant merchant isolation check
        if transaction and merchant_id and transaction.merchant_id != merchant_id:
            raise ValueError(
                f"Merchant ID mismatch for transaction '{transaction.id}': "
                f"expected '{merchant_id}', got '{transaction.merchant_id}'"
            )

        # Mode determination: explicit param or transaction mode attribute
        effective_mode = mode
        if transaction and hasattr(transaction, "mode") and transaction.mode:
            effective_mode = transaction.mode

        parsed_mode = self.parse_mode(effective_mode)
        top_action = self.normalize_action(recommendation.recommended_action)

        # Initial resolution check on top AI recommendation
        top_res = self.resolve_action_capability(top_action, mode=parsed_mode)

        if top_res.is_executable:
            return top_res

        # If top action is unsupported, perform fallback
        original_recommendation = top_action
        fallback_action: Optional[str] = None

        if enrv_response and enrv_response.action_results:
            # Iterate through ENRV-ranked candidate actions in descending order
            sorted_candidates = sorted(
                enrv_response.action_results,
                key=lambda x: getattr(
                    x,
                    "expected_net_recovery_value_rupees",
                    getattr(x, "expected_net_recovery_value_in_paise", getattr(x, "expected_net_recovery_value", 0)),
                ),
                reverse=True,
            )
            for cand in sorted_candidates:
                cand_name = getattr(cand, "action_type", getattr(cand, "action", ""))
                cand_action = self.normalize_action(cand_name)
                if cand_action == top_action:
                    continue
                if self.is_action_executable(cand_action, mode=parsed_mode):
                    fallback_action = cand_action
                    break

        # Fall back to STOP if no candidate action is executable
        if not fallback_action:
            fallback_action = "STOP"

        fallback_res = self.resolve_action_capability(fallback_action, mode=parsed_mode)
        fallback_res.fallback_applied = True
        fallback_res.original_recommendation = original_recommendation
        fallback_res.reason = (
            f"Original AI recommendation '{original_recommendation}' is unsupported in {parsed_mode.value} mode. "
            f"Fell back to executable action '{fallback_action}'."
        )

        return fallback_res
