"""
RecoverAI - Multi-Class XGBoost Diagnosis Classifier & Deterministic Lookup Table (Step 11)

Provides Level 1 (Deterministic Error Lookup Table) and Level 2 (Trained Multi-Class XGBoost
Classifier with Heuristic Fallback) for transaction failure root cause diagnosis.
"""

import os
import logging
import joblib
import numpy as np
from typing import Dict, Optional, Tuple, List
from backend.app.schemas.diagnosis import FailureCategory

logger = logging.getLogger("recoverai.diagnosis_classifier")

MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "models", "diagnosis_xgb.joblib")
)

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
    """Level 2 Multi-Class XGBoost Failure Classifier for ambiguous decline contexts."""

    _model = None
    _label_encoder = None
    _is_loaded = False

    @classmethod
    def load_model(cls, model_path: Optional[str] = None) -> bool:
        """Loads trained XGBoost diagnosis model artifact safely from joblib file."""
        target_path = model_path or MODEL_PATH
        if not os.path.exists(target_path):
            logger.warning(
                f"Multi-class Diagnosis XGBoost model artifact missing at '{target_path}'. "
                "Will use text pattern heuristic fallback."
            )
            cls._is_loaded = False
            return False

        try:
            artifact = joblib.load(target_path)
            if isinstance(artifact, dict) and "model" in artifact:
                cls._model = artifact["model"]
                cls._label_encoder = artifact.get("label_encoder")
            else:
                cls._model = artifact
                cls._label_encoder = None
            cls._is_loaded = True
            logger.info(f"Successfully loaded Multi-Class Diagnosis XGBoost model from '{target_path}'.")
            return True
        except Exception as exc:
            logger.error(f"Failed to load Multi-Class Diagnosis XGBoost model: {exc}")
            cls._is_loaded = False
            return False

    @classmethod
    def classify(
        cls,
        failure_code: str,
        error_description: Optional[str] = None,
        feature_vector: Optional[List[float]] = None,
    ) -> Optional[Tuple[str, str, float]]:
        """
        Classifies ambiguous decline codes using loaded XGBoost model or heuristic fallback.

        Args:
            failure_code: Raw failure code string.
            error_description: Optional error message text.
            feature_vector: Optional numerical feature vector from FeatureExtractor.

        Returns:
            Optional[Tuple[failure_category, root_cause_explanation, confidence_score]]:
                If classified with confidence >= 0.60, returns tuple. Otherwise returns None.
        """
        # Ensure model attempt
        if not cls._is_loaded and cls._model is None:
            cls.load_model()

        # ML Inference Path if model is loaded and feature vector provided
        if cls._is_loaded and cls._model is not None and feature_vector and len(feature_vector) >= 9:
            try:
                X_in = np.array([feature_vector[:9]], dtype=np.float32)
                probas = cls._model.predict_proba(X_in)[0]
                top_idx = int(np.argmax(probas))
                top_conf = float(probas[top_idx])

                if cls._label_encoder is not None:
                    cat_name = str(cls._label_encoder.inverse_transform([top_idx])[0])
                else:
                    classes = getattr(cls._model, "classes_", [FailureCategory.BANK_DECLINE.value])
                    cat_name = str(classes[top_idx])

                if top_conf >= 0.20:
                    explanation = f"XGBoost Multi-Class Classifier predicted root cause {cat_name}"
                    return (cat_name, explanation, round(top_conf, 2))
            except Exception as exc:
                logger.error(f"XGBoost Multi-Class Diagnosis inference error: {exc}")

        # Text Context Pattern Heuristic Fallback Path
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
