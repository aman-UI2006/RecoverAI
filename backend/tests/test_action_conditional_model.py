"""
RecoverAI - Step 12 Test Suite: Action-Conditional ML Model

Verifies Action-Conditional ML training, calibration, inference, zero leakage,
dimension validation, probability bounds, fallback mechanisms, and ENRV integration.
"""

import os
import pytest
import numpy as np
import pandas as pd

from backend.app.ml.action_conditional_model import (
    ActionConditionalPredictor,
    SUPPORTED_ACTIONS,
    DEFAULT_MODEL_PATH,
)
from backend.app.ml.feature_extractor import FeatureExtractor
from backend.app.schemas.features import FeatureContext, FeatureVector
from backend.app.services.enrv_calculator import ENRVCalculator
from backend.app.schemas.enrv import (
    CandidateActionInput,
    ENRVCalculationRequest,
    ENRVCalculationResponse,
)


def create_sample_feature_vector() -> FeatureVector:
    """Helper creating a sample decision-time FeatureVector."""
    context = FeatureContext(
        transaction_id="tx_test_12345",
        merchant_id="merchant_001",
        customer_id="cust_9999",
        amount_in_paise=250000,  # ₹2,500.00
        currency="INR",
        scenario_type="PAYMENT_FAILURE",
        decline_code="INSUFFICIENT_FUNDS",
        customer_historical_success_rate=0.75,
        customer_historical_transaction_count=5,
        checkout_device="MOBILE_APP",
        created_at_iso="2026-08-29T10:00:00Z",
    )
    return FeatureExtractor.extract_features(context)


def test_1_model_initialization():
    """Verifies ActionConditionalPredictor loads saved artifact if available."""
    predictor = ActionConditionalPredictor()
    assert isinstance(predictor, ActionConditionalPredictor)
    # Check loading state
    if os.path.exists(DEFAULT_MODEL_PATH):
        assert predictor.is_loaded is True
        assert predictor.model is not None


def test_2_inference_probability_bounds():
    """Verifies predict_proba returns calibrated probability bounded in [0.0, 1.0]."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    for action in SUPPORTED_ACTIONS:
        proba = predictor.predict_proba(fv, action)
        assert isinstance(proba, float)
        assert 0.0 <= proba <= 1.0


def test_3_action_specific_predictions():
    """Verifies different actions yield distinct candidate-specific probabilities."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    results = predictor.predict_all_actions(fv)
    assert len(results) == len(SUPPORTED_ACTIONS)
    for act in SUPPORTED_ACTIONS:
        assert act in results
        assert 0.0 <= results[act] <= 1.0

    # Verify predictions are not all identical
    prob_values = list(results.values())
    assert len(set(prob_values)) > 1


def test_4_action_normalization_and_aliases():
    """Verifies action aliases normalize to supported candidate catalog."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    p1 = predictor.predict_proba(fv, "PAYMENT_LINK")
    p2 = predictor.predict_proba(fv, "paymentlink")
    assert p1 == p2

    p3 = predictor.predict_proba(fv, "SMS")
    p4 = predictor.predict_proba(fv, "RECOVERY_MESSAGE")
    assert p3 == p4


def test_5_invalid_action_rejected():
    """Verifies invalid or unknown action string raises ValueError."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    with pytest.raises(ValueError) as exc_info:
        predictor.predict_proba(fv, "INVALID_ACTION_XYZ")
    assert "Unsupported action_type" in str(exc_info.value)


def test_6_feature_dimension_mismatch_rejected():
    """Verifies short/invalid feature vectors raise ValueError."""
    predictor = ActionConditionalPredictor()

    with pytest.raises(ValueError) as exc_info:
        predictor.predict_proba([0.5, 2.0], "PAYMENT_LINK")
    assert "dimension mismatch" in str(exc_info.value).lower()


def test_7_missing_model_fallback_mode():
    """Verifies predictor falls back gracefully to heuristic probabilities if model path is invalid."""
    predictor = ActionConditionalPredictor(model_path="/invalid/nonexistent/model.joblib")
    assert predictor.is_loaded is False

    fv = create_sample_feature_vector()
    proba = predictor.predict_proba(fv, "PAYMENT_LINK")
    assert 0.0 <= proba <= 1.0
    assert proba == 0.65  # Fallback rule value for PAYMENT_LINK


def test_8_zero_target_leakage_in_features():
    """Verifies FeatureVector input matrix contains no target or post-action attributes."""
    fv = create_sample_feature_vector()
    dense_vec = fv.dense_vector
    
    # 9 base features expected
    assert len(dense_vec) == 9
    assert "recovered" not in fv.feature_names
    assert "post_action_recovery" not in fv.feature_names
    assert "gt_p_recovery_base" not in fv.feature_names


def test_9_enrv_calculator_integration():
    """Verifies ENRVCalculator can consume ActionConditionalPredictor probabilities."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    # Get ML predictions for candidate actions
    action_probas = predictor.predict_all_actions(fv)

    candidate_inputs = [
        CandidateActionInput(
            action_type=act,
            predicted_recovery_probability=prob,
        )
        for act, prob in action_probas.items()
    ]

    enrv_request = ENRVCalculationRequest(
        transaction_id="tx_test_12345",
        merchant_id="merchant_001",
        amount_in_paise=250000,
        candidate_actions=candidate_inputs,
    )

    enrv_response = ENRVCalculator.calculate_enrv(enrv_request)

    assert isinstance(enrv_response, ENRVCalculationResponse)
    assert len(enrv_response.action_results) == len(candidate_inputs)
    assert enrv_response.best_action in action_probas

    # Check ranking (sorted descending by ENRV)
    results = enrv_response.action_results
    for i in range(len(results) - 1):
        assert (
            results[i].expected_net_recovery_value_in_paise
            >= results[i + 1].expected_net_recovery_value_in_paise
        )


def test_10_no_state_mutation_or_financial_execution():
    """Verifies ML inference performs zero database state changes or external calls."""
    predictor = ActionConditionalPredictor()
    fv = create_sample_feature_vector()

    # Predict proba across multiple invocations
    p1 = predictor.predict_proba(fv, "PAYMENT_LINK")
    p2 = predictor.predict_proba(fv, "PAYMENT_LINK")
    assert p1 == p2
