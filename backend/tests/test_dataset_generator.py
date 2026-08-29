"""
RecoverAI - Step 3 Synthetic Dataset Generator Test Suite

Exhaustive testing of dataset schema, reproducibility, anti-leakage boundaries,
DEC-007/008/009 policy compliance, and Parquet serialization integrity.
"""

import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from backend.app.services.dataset_generator import (
    SyntheticDatasetGenerator,
    SCENARIO_PAYMENT_FAILURE,
    SCENARIO_CHECKOUT_ABANDONMENT,
    SCENARIO_SUBSCRIPTION_FAILURE,
    SCENARIO_OVERDUE_RECEIVABLE,
    SCENARIOS,
)
from backend.app.services.dataset_service import (
    DatasetService,
    DECISION_TIME_FEATURE_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture(scope="module")
def generated_df() -> pd.DataFrame:
    """Fixture generating a 50,000 record dataset using seed 42."""
    generator = SyntheticDatasetGenerator(random_seed=42)
    return generator.generate_dataset(num_records=50000)


def test_1_record_count(generated_df: pd.DataFrame):
    """1. Verify total record count is >= 50,000."""
    assert len(generated_df) >= 50000, f"Expected >= 50000 records, got {len(generated_df)}"


def test_2_exact_required_schema(generated_df: pd.DataFrame):
    """2. Verify all required schema columns exist."""
    required_cols = [
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
    for col in required_cols:
        assert col in generated_df.columns, f"Missing column: {col}"


def test_3_datatype_correctness(generated_df: pd.DataFrame):
    """3. Verify column datatypes adhere to standards."""
    assert pd.api.types.is_integer_dtype(generated_df["amount_in_paise"]), "amount_in_paise must be integer (INT64)"
    assert pd.api.types.is_float_dtype(generated_df["amount"]), "amount must be float"
    assert pd.api.types.is_integer_dtype(generated_df["customer_tenure_days"]), "customer_tenure_days must be int"
    assert pd.api.types.is_integer_dtype(generated_df["prior_failed_attempts"]), "prior_failed_attempts must be int"
    assert pd.api.types.is_integer_dtype(generated_df["recovered"]), "recovered must be integer (0/1)"
    assert pd.api.types.is_float_dtype(generated_df["gt_p_recovery_base"]), "probabilities must be float"


def test_4_scenario_coverage(generated_df: pd.DataFrame):
    """4. Verify all 4 required scenarios are present."""
    scenarios_present = set(generated_df["scenario"].unique())
    expected_scenarios = set(SCENARIOS)
    assert expected_scenarios.issubset(scenarios_present), f"Missing scenarios: {expected_scenarios - scenarios_present}"


def test_5_valid_scenario_values(generated_df: pd.DataFrame):
    """5. Verify no unexpected scenario values exist."""
    invalid_scenarios = set(generated_df["scenario"].unique()) - set(SCENARIOS)
    assert len(invalid_scenarios) == 0, f"Found invalid scenarios: {invalid_scenarios}"


def test_6_monetary_representation(generated_df: pd.DataFrame):
    """6. Verify monetary amounts follow money safety rules (Paise INT64 & exact rupee ratio)."""
    assert (generated_df["amount_in_paise"] > 0).all(), "All amounts must be positive"
    # Verify integer paise ratio matches float rupees within rounding tolerance
    computed_rupees = generated_df["amount_in_paise"] / 100.0
    diff = (computed_rupees - generated_df["amount"]).abs()
    assert (diff < 1e-4).all(), "amount_in_paise and amount mismatch"


def test_7_probability_ranges(generated_df: pd.DataFrame):
    """7. Verify ground-truth probabilities are strictly within [0.0, 1.0]."""
    for col in GROUND_TRUTH_COLUMNS:
        assert (generated_df[col] >= 0.0).all() and (generated_df[col] <= 1.0).all(), f"Out-of-range probabilities in {col}"


def test_8_no_mandatory_missing_values(generated_df: pd.DataFrame):
    """8. Verify no missing null values in mandatory fields."""
    mandatory_cols = [
        "transaction_id", "merchant_id", "customer_id", "scenario",
        "amount_in_paise", "currency", "created_at", "historical_action", "recovered"
    ]
    for col in mandatory_cols:
        assert generated_df[col].isnull().sum() == 0, f"Null values found in mandatory column: {col}"


def test_9_unique_transaction_ids(generated_df: pd.DataFrame):
    """9. Verify all transaction IDs are 100% unique."""
    assert generated_df["transaction_id"].nunique() == len(generated_df), "Duplicate transaction_id detected!"


def test_10_valid_customer_merchant_relationships(generated_df: pd.DataFrame):
    """10. Verify realistic multi-transaction pooling per merchant and customer."""
    assert generated_df["merchant_id"].nunique() == 10, "Expected 10 unique merchants"
    assert generated_df["customer_id"].nunique() == 5000, "Expected 5000 unique customers"


def test_11_historical_action_validity(generated_df: pd.DataFrame):
    """11. Verify historical actions belong to valid catalog."""
    allowed_actions = {"PAYMENT_LINK", "RECOVERY_MESSAGE", "RETRY", "SUBSCRIPTION_RECOVERY", "STOP"}
    actions_present = set(generated_df["historical_action"].unique())
    assert actions_present.issubset(allowed_actions), f"Invalid action found: {actions_present - allowed_actions}"


def test_12_approved_historical_action_policy(generated_df: pd.DataFrame):
    """12. Verify DEC-008 scenario-conditioned historical action proportions."""
    # PAYMENT_FAILURE: PAYMENT_LINK 45%, RETRY 35%, STOP 20%
    pf_df = generated_df[generated_df["scenario"] == SCENARIO_PAYMENT_FAILURE]
    pf_link_pct = (pf_df["historical_action"] == "PAYMENT_LINK").mean()
    assert pytest.approx(pf_link_pct, abs=0.03) == 0.45

    # CHECKOUT_ABANDONMENT: RECOVERY_MESSAGE 50%
    ca_df = generated_df[generated_df["scenario"] == SCENARIO_CHECKOUT_ABANDONMENT]
    ca_msg_pct = (ca_df["historical_action"] == "RECOVERY_MESSAGE").mean()
    assert pytest.approx(ca_msg_pct, abs=0.03) == 0.50

    # OVERDUE_RECEIVABLE: PAYMENT_LINK 60%
    or_df = generated_df[generated_df["scenario"] == SCENARIO_OVERDUE_RECEIVABLE]
    or_link_pct = (or_df["historical_action"] == "PAYMENT_LINK").mean()
    assert pytest.approx(or_link_pct, abs=0.03) == 0.60


def test_13_recovered_binary(generated_df: pd.DataFrame):
    """13. Verify recovered is strictly binary {0, 1}."""
    values = set(generated_df["recovered"].unique())
    assert values == {0, 1}, f"Unexpected recovered values: {values}"


def test_14_ground_truth_not_in_features(generated_df: pd.DataFrame):
    """14. Verify DatasetService feature getter strictly excludes ground truth and target columns."""
    features = DatasetService.get_decision_time_features(generated_df)
    for gt_col in GROUND_TRUTH_COLUMNS:
        assert gt_col not in features.columns, f"Ground-truth column {gt_col} leaked into features!"
    assert TARGET_COLUMN not in features.columns, "Target column leaked into decision-time features!"


def test_15_no_target_leakage(generated_df: pd.DataFrame):
    """15. Explicit anti-leakage test ensuring zero post-outcome signals in features."""
    features = DatasetService.get_decision_time_features(generated_df)
    prohibited_terms = ["recovered", "outcome", "result", "future", "gt_p"]
    for col in features.columns:
        for term in prohibited_terms:
            assert term not in col, f"Leaked column name detected in features: {col}"


def test_16_deterministic_seed_behavior():
    """16. Verify seed=42 produces 100% identical DataFrame across consecutive runs."""
    df1 = SyntheticDatasetGenerator(random_seed=42).generate_dataset(num_records=1000)
    df2 = SyntheticDatasetGenerator(random_seed=42).generate_dataset(num_records=1000)
    pd.testing.assert_frame_equal(df1, df2)


def test_17_deterministic_ordering(generated_df: pd.DataFrame):
    """17. Verify dataset is deterministically sorted by created_at and transaction_id."""
    sorted_df = generated_df.sort_values(by=["created_at", "transaction_id"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(generated_df, sorted_df)


def test_18_parquet_read_write(generated_df: pd.DataFrame):
    """18. Verify Parquet serialization and deserialization integrity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_parquet = os.path.join(tmp_dir, "test.parquet")
        generated_df.to_parquet(tmp_parquet, engine="pyarrow", index=False)
        loaded = DatasetService.load_dataset(tmp_parquet)

        assert len(loaded) == len(generated_df)
        pd.testing.assert_frame_equal(loaded, generated_df)


def test_19_action_support_reporting(generated_df: pd.DataFrame):
    """19. Verify every action has robust sample support (> 1,000 records)."""
    action_counts = generated_df["historical_action"].value_counts()
    for action, count in action_counts.items():
        assert count > 1000, f"Action support too low for {action}: {count} records"


def test_20_schema_validator(generated_df: pd.DataFrame):
    """20. Verify DatasetService schema validation utility."""
    is_valid, errors = DatasetService.validate_schema(generated_df)
    assert is_valid is True, f"Schema validation failed: {errors}"
    assert len(errors) == 0
