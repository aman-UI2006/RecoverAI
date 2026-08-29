"""
RecoverAI - Feature Extractor Service (Step 9)

Transforms raw decision-time transaction context into standardized, zero-leakage
numerical feature vectors for ML model inference.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from backend.app.schemas.features import FeatureContext, FeatureVector

logger = logging.getLogger("recoverai.feature_extractor")

# Frozen Categorical Encoding Mappings
SCENARIO_ENCODING: Dict[str, int] = {
    "PAYMENT_FAILURE": 0,
    "CHECKOUT_ABANDONMENT": 1,
    "SUBSCRIPTION_FAILURE": 2,
    "OVERDUE_RECEIVABLE": 3,
}
DEFAULT_SCENARIO_CODE = 4

DECLINE_CODE_ENCODING: Dict[str, int] = {
    "BAD_REQUEST": 0,
    "AUTHENTICATION_FAILED": 1,
    "INSUFFICIENT_FUNDS": 2,
    "GATEWAY_ERROR": 3,
    "EXPIRED_CARD": 4,
    "NETWORK_TIMEOUT": 5,
}
DEFAULT_DECLINE_CODE = 6

DEVICE_ENCODING: Dict[str, int] = {
    "DESKTOP": 0,
    "MOBILE_APP": 1,
    "MOBILE_WEB": 2,
    "TABLET": 3,
}
DEFAULT_DEVICE_CODE = 4

# Standardized Feature Vector Column Names
FEATURE_NAMES: List[str] = [
    "customer_historical_success_rate",
    "customer_historical_transaction_count",
    "amount_in_paise",
    "amount_log",
    "hour_of_day",
    "day_of_week",
    "scenario_encoded",
    "decline_code_encoded",
    "device_encoded",
]

# Baseline Defaults for Missing / Cold-Start Attributes
DEFAULT_HISTORICAL_SUCCESS_RATE = 0.50
DEFAULT_HISTORICAL_TX_COUNT = 0


class FeatureExtractor:
    """Service extracting numerical feature vectors from decision-time transaction contexts."""

    @staticmethod
    def encode_scenario(scenario_type: str) -> int:
        """Categorically encodes scenario identifier."""
        normal_key = scenario_type.upper().replace("-", "_").replace(" ", "_")
        return SCENARIO_ENCODING.get(normal_key, DEFAULT_SCENARIO_CODE)

    @staticmethod
    def encode_decline_code(decline_code: Optional[str]) -> int:
        """Categorically encodes payment decline/error code."""
        if not decline_code:
            return DEFAULT_DECLINE_CODE
        normal_key = decline_code.upper().replace("-", "_").replace(" ", "_")
        return DECLINE_CODE_ENCODING.get(normal_key, DEFAULT_DECLINE_CODE)

    @staticmethod
    def encode_device(checkout_device: Optional[str]) -> int:
        """Categorically encodes checkout device type."""
        if not checkout_device:
            return DEFAULT_DEVICE_CODE
        normal_key = checkout_device.upper().replace("-", "_").replace(" ", "_")
        return DEVICE_ENCODING.get(normal_key, DEFAULT_DEVICE_CODE)

    @classmethod
    def extract_features(cls, context: FeatureContext) -> FeatureVector:
        """
        Transforms raw decision-time context into a validated FeatureVector.

        Args:
            context: FeatureContext Pydantic object.

        Returns:
            FeatureVector: Structured numerical vector and dense float array.

        Raises:
            ValueError: If amount_in_paise is non-positive.
        """
        if context.amount_in_paise <= 0:
            raise ValueError(f"amount_in_paise must be positive, got: {context.amount_in_paise}")

        # 1. Cold-start / missing customer history handling
        tx_count = context.customer_historical_transaction_count
        if tx_count is None or tx_count < 0:
            tx_count = DEFAULT_HISTORICAL_TX_COUNT

        hist_rate = context.customer_historical_success_rate
        if hist_rate is None:
            hist_rate = DEFAULT_HISTORICAL_SUCCESS_RATE
        else:
            hist_rate = max(0.0, min(1.0, float(hist_rate)))

        # 2. Financial log transformation (log1p of rupees)
        amount_rupees = context.amount_in_paise / 100.0
        amount_log = round(float(math.log1p(amount_rupees)), 6)

        # 3. Temporal feature extraction
        if context.created_at_iso:
            try:
                dt = datetime.fromisoformat(context.created_at_iso.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        hour_of_day = dt.hour
        day_of_week = dt.weekday()

        # 4. Categorical encoding
        scenario_encoded = cls.encode_scenario(context.scenario_type)
        decline_code_encoded = cls.encode_decline_code(context.decline_code)
        device_encoded = cls.encode_device(context.checkout_device)

        # 5. Construct ordered dense float vector
        dense_vector: List[float] = [
            float(hist_rate),
            float(tx_count),
            float(context.amount_in_paise),
            float(amount_log),
            float(hour_of_day),
            float(day_of_week),
            float(scenario_encoded),
            float(decline_code_encoded),
            float(device_encoded),
        ]

        return FeatureVector(
            transaction_id=context.transaction_id,
            customer_historical_success_rate=hist_rate,
            customer_historical_transaction_count=tx_count,
            amount_in_paise=context.amount_in_paise,
            amount_log=amount_log,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            scenario_encoded=scenario_encoded,
            decline_code_encoded=decline_code_encoded,
            device_encoded=device_encoded,
            dense_vector=dense_vector,
            feature_names=FEATURE_NAMES,
        )
