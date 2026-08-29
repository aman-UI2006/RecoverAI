"""
RecoverAI - Diagnosis Classifier & Deterministic Lookup Table (Step 11)

Provides Level 1 (Deterministic Error Lookup Table) and Level 2 (ML/Heuristic Failure Classifier)
for transaction failure root cause diagnosis.
"""

import logging
from typing import Dict, Optional, Tuple, List
from backend.app.schemas.diagnosis import FailureCategory

logger = logging.getLogger("recoverai.diagnosis_classifier")

# Level 1: Deterministic Error Code Lookup Table
STATIC_DIAGNOSIS_LOOKUP: Dict[str, Tuple[str, str]] = {
    # Razorpay Standard Payment Decline Codes
    "BAD_REQUEST_PAYMENT_TIMED_OUT": (
        FailureCategory.TECHNICAL_TIMEOUT.value,
        "Payment gateway timed out during processing",
    ),
    "GATEWAY_TIMED_OUT": (
        FailureCategory.TECHNICAL_TIMEOUT.value,
        "Upstream payment gateway response timed out",
    ),
    "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK": (
        FailureCategory.BANK_DECLINE.value,
        "Issuing bank declined payment request",
    ),
    "BAD_REQUEST_PAYMENT_CARD_EXPIRED": (
        FailureCategory.EXPIRED_CARD.value,
        "Payment card expired",
    ),
    "BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS": (
        FailureCategory.INSUFFICIENT_FUNDS.value,
        "Customer account has insufficient funds to complete transaction",
    ),
    "BAD_REQUEST_PAYMENT_ACCOUNT_LIMIT_EXCEEDED": (
        FailureCategory.INSUFFICIENT_FUNDS.value,
        "Transaction exceeds customer daily or per-transaction account limit",
    ),
    "BAD_REQUEST_PAYMENT_OTP_VALIDATION_FAILED": (
        FailureCategory.AUTHENTICATION_FAILURE.value,
        "Customer 2FA OTP validation failed or timed out",
    ),
    "BAD_REQUEST_PAYMENT_UPI_PIN_INVALID": (
        FailureCategory.AUTHENTICATION_FAILURE.value,
        "Customer entered invalid UPI PIN",
    ),
    "BAD_REQUEST_PAYMENT_CANCELLED_BY_USER": (
        FailureCategory.USER_ABANDONMENT.value,
        "Customer manually cancelled checkout payment flow",
    ),
    "CHECKOUT_ABANDONED": (
        FailureCategory.USER_ABANDONMENT.value,
        "Customer abandoned checkout screen before submitting payment",
    ),
    "SUBSCRIPTION_AUTOPAY_FAILED": (
        FailureCategory.BANK_DECLINE.value,
        "Recurring mandate auto-debit failed at bank level",
    ),
}


class MLDiagnosisClassifier:
    """Level 2 ML & Heuristic Failure Classifier for ambiguous decline contexts."""

    @classmethod
    def classify(
        cls,
        failure_code: str,
        error_description: Optional[str] = None,
        feature_vector: Optional[List[float]] = None,
    ) -> Optional[Tuple[str, str, float]]:
        """
        Classifies ambiguous decline codes based on pattern matching and feature context.

        Args:
            failure_code: Raw failure code string.
            error_description: Optional error message text.
            feature_vector: Optional numerical feature vector from FeatureExtractor.

        Returns:
            Optional[Tuple[failure_category, root_cause_explanation, confidence_score]]:
                If classified with confidence >= 0.60, returns tuple. Otherwise returns None.
        """
        text_context = f"{failure_code} {error_description or ''}".upper()

        if any(kw in text_context for kw in ["TIMEOUT", "TIMED_OUT", "GATEWAY_DOWN", "LATENCY"]):
            return (
                FailureCategory.TECHNICAL_TIMEOUT.value,
                "Pattern match indicates gateway or network timeout",
                0.85,
            )

        if any(kw in text_context for kw in ["OTP", "PIN", "AUTH", "3DS", "CHALLENGE", "VERIFICATION"]):
            return (
                FailureCategory.AUTHENTICATION_FAILURE.value,
                "Pattern match indicates 2FA / authentication challenge failure",
                0.80,
            )

        if any(kw in text_context for kw in ["EXPIRED", "EXPIRY", "CARD_EXPIRED"]):
            return (
                FailureCategory.EXPIRED_CARD.value,
                "Pattern match indicates expired payment instrument",
                0.90,
            )

        if any(kw in text_context for kw in ["FUNDS", "BALANCE", "LIMIT", "INSUFFICIENT"]):
            return (
                FailureCategory.INSUFFICIENT_FUNDS.value,
                "Pattern match indicates insufficient funds or card limit breach",
                0.85,
            )

        if any(kw in text_context for kw in ["DECLINED", "REJECTED", "BANK_ERROR", "ISSUER"]):
            return (
                FailureCategory.BANK_DECLINE.value,
                "Pattern match indicates issuing bank decline",
                0.75,
            )

        if any(kw in text_context for kw in ["CANCEL", "ABANDON", "USER_EXIT", "CLOSED"]):
            return (
                FailureCategory.USER_ABANDONMENT.value,
                "Pattern match indicates user abandonment during checkout",
                0.80,
            )

        logger.info(f"MLDiagnosisClassifier could not classify ambiguous failure code '{failure_code}'.")
        return None
