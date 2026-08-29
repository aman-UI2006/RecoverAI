"""
RecoverAI - Action-Conditional ML Model & Inference Service (Step 12)

Predicts action-conditional recovery probability P(recovery | X, a_i) using the calibrated
XGBoost ML model artifact saved at backend/app/ml/models/action_conditional_xgb.joblib.

Adheres strictly to zero target leakage, multi-tenant safety, and advisory-only ML boundaries.
"""

import os
import math
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import joblib
import numpy as np

from backend.app.schemas.features import FeatureVector
from backend.app.ml.feature_extractor import FeatureExtractor

logger = logging.getLogger("recoverai.action_conditional_ml")

DEFAULT_MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "models", "action_conditional_xgb.joblib")
)

SUPPORTED_ACTIONS: List[str] = [
    "PAYMENT_LINK",
    "RECOVERY_MESSAGE",
    "WHATSAPP_REMINDER",
    "RETRY",
    "MANUAL_OUTREACH",
    "NO_ACTION",
]

# Action string aliases mapping to standard candidate catalog
ACTION_ALIAS_MAP: Dict[str, str] = {
    "PAYMENT_LINK": "PAYMENT_LINK",
    "PAYMENTLINK": "PAYMENT_LINK",
    "RECOVERY_MESSAGE": "RECOVERY_MESSAGE",
    "RECOVERYMESSAGE": "RECOVERY_MESSAGE",
    "SMS": "RECOVERY_MESSAGE",
    "WHATSAPP_REMINDER": "WHATSAPP_REMINDER",
    "WHATSAPP": "WHATSAPP_REMINDER",
    "SUBSCRIPTION_RECOVERY": "WHATSAPP_REMINDER",
    "RETRY": "RETRY",
    "AUTO_RETRY": "RETRY",
    "MANUAL_OUTREACH": "MANUAL_OUTREACH",
    "MANUAL": "MANUAL_OUTREACH",
    "NO_ACTION": "NO_ACTION",
    "STOP": "NO_ACTION",
    "NONE": "NO_ACTION",
}

# Rule-based heuristic fallback probabilities (used if model artifact is absent or fails)
HEURISTIC_ACTION_FALLBACKS: Dict[str, float] = {
    "PAYMENT_LINK": 0.65,
    "RECOVERY_MESSAGE": 0.55,
    "WHATSAPP_REMINDER": 0.50,
    "RETRY": 0.45,
    "MANUAL_OUTREACH": 0.40,
    "NO_ACTION": 0.15,
}


class ActionConditionalPredictor:
    """
    Inference service for Action-Conditional ML Model predicting P(recovery | X, a_i).

    Advisory Only:
    Does NOT call Razorpay APIs, create payment links, execute payments, or mutate state.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.model: Optional[Any] = None
        self.feature_names: List[str] = []
        self.is_loaded: bool = False
        self._load_model()

    def _load_model(self) -> None:
        """Loads model artifact safely from joblib file."""
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Action-Conditional ML model artifact missing at '{self.model_path}'. "
                "Falling back to heuristic rule-based action probabilities."
            )
            self.is_loaded = False
            return

        try:
            artifact = joblib.load(self.model_path)
            if isinstance(artifact, dict) and "model" in artifact:
                self.model = artifact["model"]
                self.feature_names = artifact.get("feature_names", [])
            else:
                self.model = artifact
                self.feature_names = []
            self.is_loaded = True
            logger.info(f"Successfully loaded Action-Conditional ML model from '{self.model_path}'.")
        except Exception as exc:
            logger.error(
                f"Failed to load Action-Conditional ML model from '{self.model_path}': {exc}. "
                "Falling back to heuristic rule-based action probabilities."
            )
            self.is_loaded = False

    @staticmethod
    def normalize_action(action_type: str) -> str:
        """
        Normalizes action type string to supported candidate action catalog.

        Raises:
            ValueError: If action_type is unknown and cannot be mapped.
        """
        if not action_type or not isinstance(action_type, str):
            raise ValueError(f"Invalid action_type parameter: {action_type}")
        
        act_upper = action_type.upper().strip()
        if act_upper in ACTION_ALIAS_MAP:
            return ACTION_ALIAS_MAP[act_upper]
        
        raise ValueError(
            f"Unsupported action_type '{action_type}'. Must be one of {SUPPORTED_ACTIONS}."
        )

    def _construct_input_vector(
        self,
        feature_vector: Union[FeatureVector, List[float]],
        normalized_action: str,
    ) -> np.ndarray:
        """
        Constructs the 15-dimensional input vector for inference.
        """
        if isinstance(feature_vector, FeatureVector):
            dense_vec = feature_vector.dense_vector
        elif isinstance(feature_vector, list):
            dense_vec = feature_vector
        else:
            raise ValueError(f"Invalid feature_vector type: {type(feature_vector)}")

        if len(dense_vec) < 9:
            raise ValueError(
                f"Feature vector dimension mismatch. Expected at least 9 base features, got {len(dense_vec)}."
            )

        # Base 9 features
        base_features = [float(v) for v in dense_vec[:9]]

        # Action one-hot encoding (6 dimensions)
        action_onehot = [1.0 if normalized_action == act else 0.0 for act in SUPPORTED_ACTIONS]

        full_vec = base_features + action_onehot
        if len(full_vec) != 15:
            raise ValueError(f"Input vector dimension mismatch. Expected 15, got {len(full_vec)}.")

        return np.array([full_vec], dtype=np.float32)

    def predict_proba(
        self,
        feature_vector: Union[FeatureVector, List[float]],
        action_type: str,
    ) -> float:
        """
        Predicts recovery probability P(recovery | X, a_i) for a specific candidate action.

        Args:
            feature_vector: FeatureVector or list of 9+ base numerical features.
            action_type: Action identifier (e.g. 'PAYMENT_LINK', 'RECOVERY_MESSAGE').

        Returns:
            float: Calibrated probability in [0.0, 1.0].
        """
        norm_action = self.normalize_action(action_type)

        # Construct input vector (raises ValueError on dimension mismatch or bad types)
        X_in = self._construct_input_vector(feature_vector, norm_action)

        if not self.is_loaded or self.model is None:
            fallback_proba = HEURISTIC_ACTION_FALLBACKS.get(norm_action, 0.30)
            return float(fallback_proba)

        try:
            proba = float(self.model.predict_proba(X_in)[0, 1])
            # Strict probability clamping [0.0, 1.0]
            return max(0.0, min(1.0, proba))
        except Exception as exc:
            logger.error(f"Inference failure for action '{norm_action}': {exc}. Using fallback.")
            return float(HEURISTIC_ACTION_FALLBACKS.get(norm_action, 0.30))

    def predict_all_actions(
        self,
        feature_vector: Union[FeatureVector, List[float]],
        candidate_actions: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Predicts recovery probabilities P(recovery | X, a_i) for all candidate actions.

        Args:
            feature_vector: FeatureVector or base numerical float array.
            candidate_actions: Optional list of actions to evaluate. Defaults to all supported actions.

        Returns:
            Dict[str, float]: Mapping of action_type -> probability float.
        """
        target_actions = candidate_actions or SUPPORTED_ACTIONS
        results: Dict[str, float] = {}

        for act in target_actions:
            norm_act = self.normalize_action(act)
            proba = self.predict_proba(feature_vector, norm_act)
            results[norm_act] = round(proba, 4)

        return results
