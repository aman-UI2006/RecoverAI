"""
RecoverAI - Feature Extractor Test Suite (Step 9)

Verifies numerical feature vector extraction, categorical encodings, cold-start fallbacks,
PII safety, and zero future target leakage.
"""

import math
import pytest
from datetime import datetime, timezone

from backend.app.schemas.features import FeatureContext, FeatureVector
from backend.app.ml.feature_extractor import (
    FeatureExtractor,
    FEATURE_NAMES,
    DEFAULT_HISTORICAL_SUCCESS_RATE,
    DEFAULT_HISTORICAL_TX_COUNT,
)


def test_1_standard_feature_extraction():
    """Verifies extraction of numerical features and dense vector from complete context."""
    context = FeatureContext(
        transaction_id="tx_test_901",
        amount_in_paise=500000,  # 5,000 INR
        scenario_type="PAYMENT_FAILURE",
        decline_code="INSUFFICIENT_FUNDS",
        checkout_device="MOBILE_APP",
        customer_historical_success_rate=0.85,
        customer_historical_transaction_count=12,
        created_at_iso="2026-06-15T14:30:00+00:00",
    )

    vector = FeatureExtractor.extract_features(context)

    assert isinstance(vector, FeatureVector)
    assert vector.transaction_id == "tx_test_901"
    assert vector.customer_historical_success_rate == 0.85
    assert vector.customer_historical_transaction_count == 12
    assert vector.amount_in_paise == 500000
    assert vector.amount_log == round(math.log1p(5000.0), 6)
    assert vector.hour_of_day == 14
    assert vector.day_of_week == 0  # 2026-06-15 is Monday (0)

    # Categorical encodings
    assert vector.scenario_encoded == 0  # PAYMENT_FAILURE
    assert vector.decline_code_encoded == 2  # INSUFFICIENT_FUNDS
    assert vector.device_encoded == 1  # MOBILE_APP

    # Dense vector verification
    assert len(vector.dense_vector) == len(FEATURE_NAMES)
    assert vector.dense_vector[0] == 0.85
    assert vector.dense_vector[1] == 12.0
    assert vector.dense_vector[2] == 500000.0


def test_2_categorical_encoding_all_options():
    """Verifies encoding mappings across all scenario, decline code, and device values."""
    assert FeatureExtractor.encode_scenario("PAYMENT_FAILURE") == 0
    assert FeatureExtractor.encode_scenario("CHECKOUT_ABANDONMENT") == 1
    assert FeatureExtractor.encode_scenario("SUBSCRIPTION_FAILURE") == 2
    assert FeatureExtractor.encode_scenario("OVERDUE_RECEIVABLE") == 3
    assert FeatureExtractor.encode_scenario("UNKNOWN_SCENARIO") == 4

    assert FeatureExtractor.encode_decline_code("BAD_REQUEST") == 0
    assert FeatureExtractor.encode_decline_code("AUTHENTICATION_FAILED") == 1
    assert FeatureExtractor.encode_decline_code("INSUFFICIENT_FUNDS") == 2
    assert FeatureExtractor.encode_decline_code("GATEWAY_ERROR") == 3
    assert FeatureExtractor.encode_decline_code("EXPIRED_CARD") == 4
    assert FeatureExtractor.encode_decline_code("NETWORK_TIMEOUT") == 5
    assert FeatureExtractor.encode_decline_code("UNKNOWN_ERROR") == 6
    assert FeatureExtractor.encode_decline_code(None) == 6

    assert FeatureExtractor.encode_device("DESKTOP") == 0
    assert FeatureExtractor.encode_device("MOBILE_APP") == 1
    assert FeatureExtractor.encode_device("MOBILE_WEB") == 2
    assert FeatureExtractor.encode_device("TABLET") == 3
    assert FeatureExtractor.encode_device("UNKNOWN_DEVICE") == 4
    assert FeatureExtractor.encode_device(None) == 4


def test_3_cold_start_customer_fallbacks():
    """Verifies default median fallback for new/cold-start customers."""
    context = FeatureContext(
        transaction_id="tx_cold_start",
        amount_in_paise=100000,
        scenario_type="CHECKOUT_ABANDONMENT",
        customer_historical_success_rate=None,
        customer_historical_transaction_count=0,
    )

    vector = FeatureExtractor.extract_features(context)

    assert vector.customer_historical_success_rate == DEFAULT_HISTORICAL_SUCCESS_RATE
    assert vector.customer_historical_transaction_count == DEFAULT_HISTORICAL_TX_COUNT
    assert vector.dense_vector[0] == 0.50
    assert vector.dense_vector[1] == 0.0


def test_4_missing_attributes_graceful_handling():
    """Verifies that missing optional attributes return safe default encoded values without KeyError."""
    context = FeatureContext(
        transaction_id="tx_missing_opt",
        amount_in_paise=250000,
        scenario_type="SUBSCRIPTION_FAILURE",
        decline_code=None,
        checkout_device=None,
        created_at_iso=None,
    )

    vector = FeatureExtractor.extract_features(context)

    assert vector.decline_code_encoded == 6
    assert vector.device_encoded == 4
    assert 0 <= vector.hour_of_day <= 23
    assert 0 <= vector.day_of_week <= 6


def test_5_zero_future_leakage_isolation():
    """Verifies zero future target leakage by asserting target fields are completely excluded from schemas."""
    context = FeatureContext(
        transaction_id="tx_leakage_check",
        amount_in_paise=300000,
        scenario_type="OVERDUE_RECEIVABLE",
    )

    vector = FeatureExtractor.extract_features(context)

    fields = FeatureVector.model_fields.keys()
    forbidden_target_fields = [
        "recovered",
        "gt_recovered",
        "post_action_recovery",
        "gt_p_recovery_base",
        "attribution_status",
        "recovered_amount",
    ]

    for forbidden in forbidden_target_fields:
        assert forbidden not in fields
        assert forbidden not in vector.feature_names


def test_6_non_positive_amount_raises_value_error():
    """Verifies that non-positive amount_in_paise raises ValidationError or ValueError."""
    with pytest.raises(Exception):
        FeatureContext(
            transaction_id="tx_invalid_amt",
            amount_in_paise=0,
            scenario_type="PAYMENT_FAILURE",
        )


def test_7_pii_safety_check():
    """Verifies that raw PII identifiers (emails, names, phones) are excluded from numerical features."""
    context = FeatureContext(
        transaction_id="tx_pii_check",
        amount_in_paise=150000,
        scenario_type="PAYMENT_FAILURE",
        custom_metadata={"email": "secret@example.com", "customer_name": "John Doe"},
    )

    vector = FeatureExtractor.extract_features(context)

    # Confirm PII strings do not leak into vector or feature names
    for name in vector.feature_names:
        assert "email" not in name.lower()
        assert "name" not in name.lower()
        assert "phone" not in name.lower()
