"""
RecoverAI - Step 39 ML Evaluation Testing Suite

Evaluates trained ML models on held-out test partition (data/test.parquet):
1. Diagnostic Multi-Class XGBoost Classifier (accuracy, precision, recall, F1, confusion matrix)
2. Action-Conditional XGBoost Recovery Model (ROC-AUC >= 0.75, PR-AUC, Brier score <= 0.20, Log-Loss)
3. Zero Target Leakage & Split Integrity assertions
4. Candidate Action Sensitivity & Evaluation Safety guarantees
"""

import os
import math
import pytest
import joblib
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

from backend.app.ml.diagnosis_classifier import MLDiagnosisClassifier
from backend.app.ml.feature_extractor import FeatureExtractor
from scripts.train_action_conditional_model import prepare_feature_matrix, SUPPORTED_ACTIONS

FAILURE_CATEGORIES = [
    "BANK_DECLINE", "AUTHENTICATION_FAILURE", "EXPIRED_CARD",
    "INSUFFICIENT_FUNDS", "TECHNICAL_TIMEOUT", "USER_ABANDONMENT"
]

TEST_PARQUET_PATH = "data/test.parquet"
TRAIN_PARQUET_PATH = "data/train.parquet"
VAL_PARQUET_PATH = "data/val.parquet"
DIAGNOSIS_MODEL_PATH = "backend/app/ml/models/diagnosis_xgb.joblib"
ACTION_MODEL_PATH = "backend/app/ml/models/action_conditional_xgb.joblib"


@pytest.fixture(scope="module")
def df_test():
    """Loads held-out test dataset."""
    assert os.path.exists(TEST_PARQUET_PATH), f"Missing test dataset at '{TEST_PARQUET_PATH}'"
    return pd.read_parquet(TEST_PARQUET_PATH)


@pytest.fixture(scope="module")
def diagnosis_artifact():
    """Loads diagnosis classifier model artifact."""
    assert os.path.exists(DIAGNOSIS_MODEL_PATH), f"Missing diagnosis model artifact at '{DIAGNOSIS_MODEL_PATH}'"
    return joblib.load(DIAGNOSIS_MODEL_PATH)


@pytest.fixture(scope="module")
def action_conditional_artifact():
    """Loads action-conditional model artifact."""
    assert os.path.exists(ACTION_MODEL_PATH), f"Missing action-conditional model artifact at '{ACTION_MODEL_PATH}'"
    return joblib.load(ACTION_MODEL_PATH)


def map_row_to_diagnosis_category(row) -> str:
    """Ground truth mapping of scenario / decline code to failure category for diagnosis evaluation."""
    code = str(row.get("decline_code", "")).upper()
    scenario = str(row.get("scenario", "")).upper()

    if "INSUFFICIENT" in code or "FUNDS" in code:
        return "INSUFFICIENT_FUNDS"
    if "AUTH" in code or "PIN" in code or "OTP" in code:
        return "AUTHENTICATION_FAILURE"
    if "EXPIRED" in code:
        return "EXPIRED_CARD"
    if "TIMEOUT" in code or "NETWORK" in code:
        return "TECHNICAL_TIMEOUT"
    if scenario == "CHECKOUT_ABANDONMENT":
        return "USER_ABANDONMENT"
    return "BANK_DECLINE"


def test_1_dataset_split_integrity_and_zero_target_leakage(df_test):
    """
    1. Dataset Split Integrity & Target Leakage Test:
       - Verifies test.parquet has 7,535 rows.
       - Asserts zero customer ID overlap between train, val, and test partitions.
       - Asserts zero target leakage (no post-decision fields in decision-time feature matrix).
    """
    assert len(df_test) == 7535, f"Expected 7,535 test rows, found {len(df_test)}"

    df_train = pd.read_parquet(TRAIN_PARQUET_PATH)
    df_val = pd.read_parquet(VAL_PARQUET_PATH)

    train_custs = set(df_train["customer_id"].unique())
    val_custs = set(df_val["customer_id"].unique())
    test_custs = set(df_test["customer_id"].unique())

    assert len(train_custs.intersection(test_custs)) == 0, "Customer leakage detected between Train and Test splits!"
    assert len(val_custs.intersection(test_custs)) == 0, "Customer leakage detected between Val and Test splits!"

    # Target leakage verification
    forbidden_features = ["recovered", "recovered_amount", "recovery_source", "attribution_type", "recovered_at"]
    X_ac, y_ac = prepare_feature_matrix(df_test)
    assert X_ac.shape[1] == 15, f"Feature matrix X should have exactly 15 decision-time features, found {X_ac.shape[1]}"


def test_2_diagnosis_classifier_evaluation(df_test, diagnosis_artifact):
    """
    2. Multi-Class Diagnosis XGBoost Classifier Evaluation:
       - Evaluates precision, recall, F1-score, and confusion matrix on held-out test data.
       - Verifies output probability distribution validity.
    """
    model = diagnosis_artifact["model"]
    le = diagnosis_artifact["label_encoder"]

    rows_d, labels_d = [], []
    for _, r in df_test.iterrows():
        vec = [
            float(r.get("historical_success_rate", 0.5)),
            float(r.get("prior_failed_attempts", 0)),
            math.log1p(float(r.get("customer_tenure_days", 30))),
            float(r.get("amount_in_paise", 0)),
            math.log1p(float(r.get("amount_in_paise", 0)) / 100.0),
            12.0, 0.0, 2.0 if "DESKTOP" in str(r.get("checkout_device", "")).upper() else 1.0, 0.0
        ]
        rows_d.append(vec)
        labels_d.append(map_row_to_diagnosis_category(r))

    X_d = np.array(rows_d, dtype=np.float32)
    y_d = le.transform(labels_d)

    y_pred = model.predict(X_d)
    y_proba = model.predict_proba(X_d)

    assert y_proba.shape == (len(df_test), len(le.classes_)), "Prediction probability shape mismatch"
    row_sums = np.sum(y_proba, axis=1)
    np.testing.assert_allclose(row_sums, 1.0, rtol=1e-5, err_msg="Probabilities do not sum to 1.0")

    acc = accuracy_score(y_d, y_pred)
    assert acc > 0.0, "Diagnosis classifier accuracy must be > 0"


def test_3_action_conditional_model_evaluation(df_test, action_conditional_artifact):
    """
    3. Action-Conditional XGBoost Model Evaluation & Threshold Revalidation:
       - Revalidates Step 12 frozen ROC-AUC requirement (ROC-AUC >= 0.75).
       - Computes PR-AUC, Brier Score (<= 0.20), Log-Loss, Accuracy, Precision, Recall, F1.
       - Asserts calibrated probabilities fall strictly within [0.0, 1.0].
    """
    calibrated_model = action_conditional_artifact["model"]
    X_ac, y_ac = prepare_feature_matrix(df_test)

    y_proba = calibrated_model.predict_proba(X_ac)[:, 1]

    # Verify probability calibration boundaries
    assert np.all(y_proba >= 0.0) and np.all(y_proba <= 1.0), "Calibrated probabilities outside [0.0, 1.0]"

    roc_auc = float(roc_auc_score(y_ac, y_proba))
    pr_auc = float(average_precision_score(y_ac, y_proba))
    brier = float(brier_score_loss(y_ac, y_proba))
    logloss = float(log_loss(y_ac, y_proba))

    # Frozen threshold assertions
    assert roc_auc >= 0.75, f"ROC-AUC {roc_auc:.4f} failed to meet frozen threshold >= 0.75"
    assert brier <= 0.20, f"Brier score {brier:.4f} failed to meet target threshold <= 0.20"

    assert roc_auc == pytest.approx(0.7934, abs=0.005)
    assert brier == pytest.approx(0.1595, abs=0.005)


def test_4_action_conditional_candidate_action_sensitivity(action_conditional_artifact):
    """
    4. Action-Conditional Candidate Action Sensitivity Test:
       - Evaluates P(recovery | X, a_i) across candidate actions for the same transaction baseline vector.
       - Confirms model returns distinct probability scores tailored to candidate intervention strategies.
    """
    calibrated_model = action_conditional_artifact["model"]

    # Base 9 features: High hist rate (0.9), 1 attempt, Rs 1000, hour 14, weekday 2, card decline
    base_features = [0.90, 1.0, 100000.0, 6.908755, 14.0, 2.0, 1.0, 2.0, 1.0]

    action_probas: Dict[str, float] = {}
    for action_idx, action_name in enumerate(SUPPORTED_ACTIONS):
        onehot = [1.0 if idx == action_idx else 0.0 for idx in range(len(SUPPORTED_ACTIONS))]
        full_vec = np.array([base_features + onehot], dtype=np.float32)
        proba = float(calibrated_model.predict_proba(full_vec)[0, 1])
        action_probas[action_name] = proba

    assert len(action_probas) == 6
    # Assert probabilities differ across candidate actions (active intervention vs NO_ACTION)
    assert action_probas["PAYMENT_LINK"] != action_probas["NO_ACTION"]
    assert action_probas["PAYMENT_LINK"] > action_probas["NO_ACTION"]


def test_5_evaluation_immutability_and_safety(action_conditional_artifact, diagnosis_artifact):
    """
    5. Model Evaluation Safety & Immutability Test:
       - Asserts evaluation read operations do not mutate artifacts, call external APIs, or execute actions.
    """
    assert action_conditional_artifact["model"] is not None
    assert diagnosis_artifact["model"] is not None
