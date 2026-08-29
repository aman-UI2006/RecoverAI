"""
RecoverAI - Action-Conditional ML Model Training Script (Step 12)

Trains, calibrates, evaluates, and serializes the XGBoost Action-Conditional ML Model
predicting P(recovery | X, action).
"""

import os
import sys
import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV, FrozenEstimator
import xgboost as xgb

from backend.app.ml.feature_extractor import (
    FeatureExtractor,
    SCENARIO_ENCODING,
    DECLINE_CODE_ENCODING,
    DEVICE_ENCODING,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recoverai.train_model")

# Supported candidate actions and model feature contract
SUPPORTED_ACTIONS: List[str] = [
    "PAYMENT_LINK",
    "RECOVERY_MESSAGE",
    "WHATSAPP_REMINDER",
    "RETRY",
    "MANUAL_OUTREACH",
    "NO_ACTION",
]

ACTION_ONEHOT_COLUMNS: List[str] = [f"action_{action}" for action in SUPPORTED_ACTIONS]

BASE_FEATURE_NAMES: List[str] = [
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

ALL_FEATURE_NAMES: List[str] = BASE_FEATURE_NAMES + ACTION_ONEHOT_COLUMNS


def map_historical_action_to_supported(action: str) -> str:
    """Normalizes historical dataset action string to supported candidate action catalog."""
    act_upper = str(action).upper().strip()
    if act_upper in ("PAYMENT_LINK", "PAYMENTLINK"):
        return "PAYMENT_LINK"
    if act_upper in ("RECOVERY_MESSAGE", "RECOVERYMESSAGE", "SMS"):
        return "RECOVERY_MESSAGE"
    if act_upper in ("WHATSAPP_REMINDER", "SUBSCRIPTION_RECOVERY", "WHATSAPP"):
        return "WHATSAPP_REMINDER"
    if act_upper in ("RETRY", "AUTO_RETRY"):
        return "RETRY"
    if act_upper in ("MANUAL_OUTREACH", "MANUAL"):
        return "MANUAL_OUTREACH"
    if act_upper in ("STOP", "NO_ACTION", "NONE"):
        return "NO_ACTION"
    return "NO_ACTION"


def prepare_feature_matrix(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Transforms dataframe into numerical feature matrix X (N, 15) and target array y (N,).

    Zero Target Leakage Guarantee:
    Only decision-time variables and action indicators are included in X.
    Ground-truth synthetic P*, attribution, and post-action fields are excluded.
    """
    rows_x: List[List[float]] = []
    y_list: List[int] = []

    for idx, row in df.iterrows():
        # 1. Base 9 decision-time features
        tx_count = row.get("prior_failed_attempts", 0)
        hist_rate = row.get("historical_success_rate", 0.50)
        amount_paise = float(row.get("amount_in_paise", row.get("amount", 0) * 100))
        amount_log = round(float(math.log1p(amount_paise / 100.0)), 6)

        dt_str = str(row.get("created_at", ""))
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            hour_of_day = float(dt.hour)
            day_of_week = float(dt.weekday())
        except Exception:
            hour_of_day = 12.0
            day_of_week = 0.0

        scenario_enc = float(FeatureExtractor.encode_scenario(str(row.get("scenario", ""))))
        decline_enc = float(FeatureExtractor.encode_decline_code(str(row.get("decline_code", ""))))
        device_enc = float(FeatureExtractor.encode_device(str(row.get("checkout_device", ""))))

        base_vec = [
            float(hist_rate),
            float(tx_count),
            float(amount_paise),
            float(amount_log),
            hour_of_day,
            day_of_week,
            scenario_enc,
            decline_enc,
            device_enc,
        ]

        # 2. Action one-hot encoding
        hist_act = map_historical_action_to_supported(str(row.get("historical_action", "NO_ACTION")))
        action_onehot = [1.0 if hist_act == action else 0.0 for action in SUPPORTED_ACTIONS]

        full_vec = base_vec + action_onehot
        rows_x.append(full_vec)

        # 3. Binary recovery target
        y_val = int(row.get("recovered", 0))
        y_list.append(y_val)

    X = np.array(rows_x, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    return X, y


def train_and_evaluate_model() -> Dict[str, Any]:
    """Trains XGBoost classifier, calibrates probabilities, evaluates test set, and saves artifact."""
    data_dir = "data"
    train_path = os.path.join(data_dir, "train.parquet")
    val_path = os.path.join(data_dir, "val.parquet")
    test_path = os.path.join(data_dir, "test.parquet")

    if not all(os.path.exists(p) for p in [train_path, val_path, test_path]):
        raise FileNotFoundError("One or more required split parquet files missing in data/")

    logger.info("Loading train, val, test parquet datasets...")
    df_train = pd.read_parquet(train_path)
    df_val = pd.read_parquet(val_path)
    df_test = pd.read_parquet(test_path)

    logger.info(f"Train size: {len(df_train)}, Val size: {len(df_val)}, Test size: {len(df_test)}")

    logger.info("Extracting feature matrices X and targets y...")
    X_train, y_train = prepare_feature_matrix(df_train)
    X_val, y_val = prepare_feature_matrix(df_val)
    X_test, y_test = prepare_feature_matrix(df_test)

    logger.info(f"X_train shape: {X_train.shape}, y_train mean: {y_train.mean():.4f}")

    # 1. Base XGBoost Classifier with hyperparameter optimization
    logger.info("Training base XGBoost Classifier...")
    base_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.85,
        gamma=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    base_model.fit(X_train, y_train)

    # 2. Probability Calibration via Isotonic Regression on Validation Set
    logger.info("Calibrating model probabilities using Isotonic Regression on validation set...")
    calibrated_model = CalibratedClassifierCV(
        estimator=FrozenEstimator(base_model),
        method="isotonic",
    )
    calibrated_model.fit(X_val, y_val)

    # 3. Model Evaluation on Test Set
    logger.info("Evaluating calibrated model on test set...")
    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]

    auc_score = float(roc_auc_score(y_test, y_pred_proba))
    logloss_val = float(log_loss(y_test, y_pred_proba))
    brier_val = float(brier_score_loss(y_test, y_pred_proba))

    logger.info("==========================================")
    logger.info("STEP 12 ACTION-CONDITIONAL ML EVALUATION")
    logger.info(f"Test ROC-AUC  : {auc_score:.4f} (Target >= 0.75)")
    logger.info(f"Test Log-Loss : {logloss_val:.4f}")
    logger.info(f"Test Brier    : {brier_val:.4f}")
    logger.info("==========================================")

    if auc_score < 0.75:
        logger.warning(f"ROC-AUC {auc_score:.4f} is below the 0.75 target threshold.")

    # 4. Save Model Artifact
    output_dir = os.path.join("backend", "app", "ml", "models")
    os.makedirs(output_dir, exist_ok=True)
    artifact_path = os.path.join(output_dir, "action_conditional_xgb.joblib")

    artifact_payload = {
        "model": calibrated_model,
        "base_model": base_model,
        "supported_actions": SUPPORTED_ACTIONS,
        "feature_names": ALL_FEATURE_NAMES,
        "base_feature_names": BASE_FEATURE_NAMES,
        "test_roc_auc": auc_score,
        "test_log_loss": logloss_val,
        "test_brier_score": brier_val,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_version": "50k_synthetic_v1",
    }

    joblib.dump(artifact_payload, artifact_path)
    logger.info(f"Successfully saved calibrated model artifact to: {artifact_path}")

    return artifact_payload


if __name__ == "__main__":
    train_and_evaluate_model()
