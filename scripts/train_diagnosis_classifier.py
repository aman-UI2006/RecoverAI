"""
RecoverAI - Step 11: Multi-Class XGBoost Diagnosis Classifier Training Script

Trains an XGBClassifier multi-class classification model on data/train.parquet to classify
ambiguous transaction failure root causes into standardized failure categories.

Outputs serialized model artifact to backend/app/ml/models/diagnosis_xgb.joblib.
"""

import os
import sys
import math
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

TRAIN_PATH = "data/train.parquet"
VAL_PATH = "data/val.parquet"
TEST_PATH = "data/test.parquet"
MODEL_OUTPUT_DIR = "backend/app/ml/models"
MODEL_OUTPUT_PATH = os.path.join(MODEL_OUTPUT_DIR, "diagnosis_xgb.joblib")

FAILURE_CATEGORIES = [
    "BANK_DECLINE",
    "AUTHENTICATION_FAILURE",
    "EXPIRED_CARD",
    "INSUFFICIENT_FUNDS",
    "TECHNICAL_TIMEOUT",
    "USER_ABANDONMENT",
]

# Mapping scenario / decline code to failure category ground truth for training
def map_row_to_category(row) -> str:
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


def prepare_features_and_labels(df: pd.DataFrame, label_encoder: LabelEncoder):
    rows = []
    labels = []

    for _, r in df.iterrows():
        hist_rate = float(r.get("historical_success_rate", 0.5))
        tx_count = float(r.get("prior_failed_attempts", 0))
        tenure = float(r.get("customer_tenure_days", 30))
        tenure_log = math.log1p(tenure)
        amount_paise = float(r.get("amount_in_paise", 0))
        amount_log = math.log1p(amount_paise / 100.0)

        dt_str = str(r.get("created_at", ""))
        try:
            dt = pd.to_datetime(dt_str)
            hr, dow = float(dt.hour), float(dt.dayofweek)
        except Exception:
            hr, dow = 12.0, 0.0

        device = str(r.get("checkout_device", "DESKTOP_WEB")).upper()
        device_val = 1.0 if "MOBILE" in device else (2.0 if "DESKTOP" in device else 0.0)

        vec = [hist_rate, tx_count, tenure_log, amount_paise, amount_log, hr, dow, device_val, 0.0]
        rows.append(vec)

        cat = map_row_to_category(r)
        labels.append(cat)

    X = np.array(rows, dtype=np.float32)
    y = label_encoder.transform(labels)
    return X, y


def main():
    print("=" * 70)
    print("RECOVERAI — STEP 11: DIAGNOSIS MULTI-CLASS XGBOOST TRAINING")
    print("=" * 70)

    df_train = pd.read_parquet(TRAIN_PATH)
    df_val = pd.read_parquet(VAL_PATH)
    df_test = pd.read_parquet(TEST_PATH)

    le = LabelEncoder()
    le.fit(FAILURE_CATEGORIES)

    X_train, y_train = prepare_features_and_labels(df_train, le)
    X_val, y_val = prepare_features_and_labels(df_val, le)
    X_test, y_test = prepare_features_and_labels(df_test, le)

    print(f"Train samples: {len(X_train)}, Val samples: {len(X_val)}, Test samples: {len(X_test)}")

    model = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=len(FAILURE_CATEGORIES),
        n_estimators=300,
        max_depth=8,
        learning_rate=0.1,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    acc_test = model.score(X_test, y_test)
    print(f"XGBoost Multi-Class Classifier Accuracy on Test Set: {acc_test:.4f}")

    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
    artifact = {
        "model": model,
        "label_encoder": le,
        "classes": list(le.classes_),
        "feature_count": 9,
    }

    joblib.dump(artifact, MODEL_OUTPUT_PATH)
    print(f"Saved diagnosis XGBoost model artifact to: {MODEL_OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
