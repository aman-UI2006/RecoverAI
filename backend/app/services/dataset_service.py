"""
RecoverAI - Dataset Service Module (Step 3)

Provides dataset loading utilities, decision-time feature isolation,
and schema validation services.
"""

import os
from typing import List, Tuple

import pandas as pd

# Decision-time features allowed for ML model training and inference
DECISION_TIME_FEATURE_COLUMNS: List[str] = [
    "scenario",
    "amount_in_paise",
    "payment_method",
    "decline_code",
    "customer_tenure_days",
    "historical_success_rate",
    "prior_failed_attempts",
    "checkout_device",
    "historical_action",
]

# Ground-truth columns that MUST NOT be included in model feature matrices (Target Leakage Isolation)
GROUND_TRUTH_COLUMNS: List[str] = [
    "gt_p_recovery_base",
    "gt_p_recovery_payment_link",
    "gt_p_recovery_message",
    "gt_p_recovery_retry",
    "gt_p_recovery_subscription_recovery",
]

# Target column
TARGET_COLUMN: str = "recovered"


class DatasetService:
    """Utility service for loading, parsing, and validating synthetic datasets."""

    @staticmethod
    def load_dataset(file_path: str) -> pd.DataFrame:
        """
        Loads dataset from Parquet or CSV file.

        Args:
            file_path: Path to dataset file.

        Returns:
            pd.DataFrame: Loaded dataset.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found at: {file_path}")

        if file_path.endswith(".parquet"):
            return pd.read_parquet(file_path)
        elif file_path.endswith(".csv"):
            return pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format for {file_path}")

    @staticmethod
    def get_decision_time_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts ONLY decision-time features X from dataset, guaranteeing zero
        target leakage from ground-truth columns or observed recovery outcomes.

        Args:
            df: Input dataset DataFrame.

        Returns:
            pd.DataFrame: DataFrame containing decision-time feature columns only.
        """
        # Strict anti-leakage check
        for gt_col in GROUND_TRUTH_COLUMNS:
            if gt_col in DECISION_TIME_FEATURE_COLUMNS:
                raise ValueError(f"CRITICAL TARGET LEAKAGE: Ground-truth column {gt_col} in feature list!")

        if TARGET_COLUMN in DECISION_TIME_FEATURE_COLUMNS:
            raise ValueError(f"CRITICAL TARGET LEAKAGE: Target column {TARGET_COLUMN} in feature list!")

        return df[DECISION_TIME_FEATURE_COLUMNS].copy()

    @staticmethod
    def validate_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validates that DataFrame satisfies Step 3 schema requirements.

        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        required_columns = [
            "transaction_id",
            "merchant_id",
            "customer_id",
            "scenario",
            "amount_in_paise",
            "amount",
            "currency",
            "payment_method",
            "decline_code",
            "customer_tenure_days",
            "historical_success_rate",
            "prior_failed_attempts",
            "checkout_device",
            "created_at",
            "historical_action",
            "gt_p_recovery_base",
            "gt_p_recovery_payment_link",
            "gt_p_recovery_message",
            "gt_p_recovery_retry",
            "gt_p_recovery_subscription_recovery",
            "recovered",
            "dataset_version",
            "random_seed",
        ]

        for col in required_columns:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")

        if len(df) < 50000:
            errors.append(f"Dataset record count {len(df)} is less than required minimum 50,000")

        return (len(errors) == 0, errors)
