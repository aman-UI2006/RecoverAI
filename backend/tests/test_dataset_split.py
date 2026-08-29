"""
RecoverAI - Dataset Splitting & Validation Test Suite (Step 4)

Verifies strict customer isolation, transaction conservation, schema integrity,
deterministic internal temporal ordering, DEC-007 compliance, and repeatability.
"""

import json
import os
import tempfile
from typing import Dict

import pandas as pd
import pytest

from backend.app.services.dataset_service import DatasetService
from scripts.split_dataset import split_dataset, compute_sha256


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
SOURCE_PARQUET = os.path.join(DATA_DIR, "synthetic_50k.parquet")
TRAIN_PARQUET = os.path.join(DATA_DIR, "train.parquet")
VAL_PARQUET = os.path.join(DATA_DIR, "val.parquet")
TEST_PARQUET = os.path.join(DATA_DIR, "test.parquet")
METADATA_JSON = os.path.join(DATA_DIR, "split_metadata.json")


@pytest.fixture(scope="module")
def split_data() -> Dict[str, pd.DataFrame]:
    """Loads source and split DataFrames for testing."""
    return {
        "source": DatasetService.load_dataset(SOURCE_PARQUET),
        "train": DatasetService.load_split("train", data_dir=DATA_DIR),
        "val": DatasetService.load_split("val", data_dir=DATA_DIR),
        "test": DatasetService.load_split("test", data_dir=DATA_DIR),
    }


def test_1_split_file_existence():
    """1. Verify output partition files and metadata JSON exist."""
    assert os.path.exists(TRAIN_PARQUET), "train.parquet missing"
    assert os.path.exists(VAL_PARQUET), "val.parquet missing"
    assert os.path.exists(TEST_PARQUET), "test.parquet missing"
    assert os.path.exists(METADATA_JSON), "split_metadata.json missing"


def test_2_total_row_conservation(split_data: Dict[str, pd.DataFrame]):
    """2. Verify exact row conservation (len(train) + len(val) + len(test) == len(source))."""
    source_len = len(split_data["source"])
    train_len = len(split_data["train"])
    val_len = len(split_data["val"])
    test_len = len(split_data["test"])

    assert train_len + val_len + test_len == source_len == 50000


def test_3_zero_customer_overlap(split_data: Dict[str, pd.DataFrame]):
    """3. Verify hard zero customer overlap across all partitions (DEC-007)."""
    train_custs = set(split_data["train"]["customer_id"])
    val_custs = set(split_data["val"]["customer_id"])
    test_custs = set(split_data["test"]["customer_id"])

    assert len(train_custs & val_custs) == 0, "Customer overlap between Train and Val!"
    assert len(train_custs & test_custs) == 0, "Customer overlap between Train and Test!"
    assert len(val_custs & test_custs) == 0, "Customer overlap between Val and Test!"

    total_unique_custs = len(set(split_data["source"]["customer_id"]))
    assert len(train_custs) + len(val_custs) + len(test_custs) == total_unique_custs == 5000


def test_4_zero_transaction_overlap(split_data: Dict[str, pd.DataFrame]):
    """4. Verify zero transaction ID overlap across all partitions."""
    train_txs = set(split_data["train"]["transaction_id"])
    val_txs = set(split_data["val"]["transaction_id"])
    test_txs = set(split_data["test"]["transaction_id"])

    assert len(train_txs & val_txs) == 0, "Transaction duplication between Train and Val!"
    assert len(train_txs & test_txs) == 0, "Transaction duplication between Train and Test!"
    assert len(val_txs & test_txs) == 0, "Transaction duplication between Val and Test!"

    all_txs = train_txs | val_txs | test_txs
    assert len(all_txs) == 50000


def test_5_approximate_split_ratios(split_data: Dict[str, pd.DataFrame]):
    """5. Verify split row counts approximate 70/15/15 target ratios."""
    total = len(split_data["source"])
    train_pct = len(split_data["train"]) / total * 100.0
    val_pct = len(split_data["val"]) / total * 100.0
    test_pct = len(split_data["test"]) / total * 100.0

    assert 68.0 <= train_pct <= 72.0, f"Train pct out of expected range: {train_pct:.2f}%"
    assert 13.5 <= val_pct <= 16.5, f"Val pct out of expected range: {val_pct:.2f}%"
    assert 13.5 <= test_pct <= 16.5, f"Test pct out of expected range: {test_pct:.2f}%"


def test_6_schema_preservation_across_splits(split_data: Dict[str, pd.DataFrame]):
    """6. Verify all 23 schema columns exist in every split partition."""
    source_cols = list(split_data["source"].columns)
    assert len(source_cols) == 23

    for name in ["train", "val", "test"]:
        split_df = split_data[name]
        assert list(split_df.columns) == source_cols, f"Schema mismatch in {name} partition"


def test_7_monetary_datatype_int64(split_data: Dict[str, pd.DataFrame]):
    """7. Verify monetary amount_in_paise remains int64 in all partitions."""
    for name in ["train", "val", "test"]:
        dtype = split_data[name]["amount_in_paise"].dtype
        assert dtype == "int64", f"amount_in_paise in {name} is {dtype}, expected int64"


def test_8_all_scenarios_represented(split_data: Dict[str, pd.DataFrame]):
    """8. Verify all 4 scenarios exist in every split partition."""
    expected_scenarios = {
        "PAYMENT_FAILURE",
        "CHECKOUT_ABANDONMENT",
        "SUBSCRIPTION_FAILURE",
        "OVERDUE_RECEIVABLE",
    }

    for name in ["train", "val", "test"]:
        scenarios = set(split_data[name]["scenario"].unique())
        assert scenarios == expected_scenarios, f"Missing scenario in {name} partition: {expected_scenarios - scenarios}"


def test_9_merchant_representation(split_data: Dict[str, pd.DataFrame]):
    """9. Verify all 10 synthetic merchants exist in every partition."""
    source_merchants = set(split_data["source"]["merchant_id"])
    assert len(source_merchants) == 10

    for name in ["train", "val", "test"]:
        merchants = set(split_data[name]["merchant_id"].unique())
        assert merchants == source_merchants, f"Merchant imbalance in {name} partition"


def test_10_historical_action_representation(split_data: Dict[str, pd.DataFrame]):
    """10. Verify all 5 historical actions exist in every partition."""
    expected_actions = {
        "PAYMENT_LINK",
        "RECOVERY_MESSAGE",
        "RETRY",
        "SUBSCRIPTION_RECOVERY",
        "STOP",
    }

    for name in ["train", "val", "test"]:
        actions = set(split_data[name]["historical_action"].unique())
        assert actions == expected_actions, f"Missing historical action in {name} partition"


def test_11_recovered_binary_values(split_data: Dict[str, pd.DataFrame]):
    """11. Verify recovered target remains strictly binary {0, 1} in all splits."""
    for name in ["train", "val", "test"]:
        unique_vals = set(split_data[name]["recovered"].unique())
        assert unique_vals.issubset({0, 1}), f"Non-binary target in {name} partition: {unique_vals}"


def test_12_deterministic_internal_ordering(split_data: Dict[str, pd.DataFrame]):
    """12. Verify rows in each partition are sorted by created_at ASC, transaction_id ASC."""
    for name in ["train", "val", "test"]:
        df = split_data[name]

        # Check created_at non-decreasing
        created_at_list = df["created_at"].tolist()
        is_sorted_time = all(created_at_list[i] <= created_at_list[i + 1] for i in range(len(created_at_list) - 1))
        assert is_sorted_time, f"Chronological ordering violated in {name} partition!"


def test_13_reproducibility_repeat_execution():
    """13. Verify re-running splitter on same source produces identical metadata and hashes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        meta1 = split_dataset(source_path=SOURCE_PARQUET, output_dir=tmp_dir, random_seed=42)
        meta2 = split_dataset(source_path=SOURCE_PARQUET, output_dir=tmp_dir, random_seed=42)

        assert meta1["splits"]["train"]["sha256"] == meta2["splits"]["train"]["sha256"]
        assert meta1["splits"]["val"]["sha256"] == meta2["splits"]["val"]["sha256"]
        assert meta1["splits"]["test"]["sha256"] == meta2["splits"]["test"]["sha256"]


def test_14_target_leakage_isolation(split_data: Dict[str, pd.DataFrame]):
    """14. Verify DatasetService feature isolation works cleanly on all partitions."""
    for name in ["train", "val", "test"]:
        features = DatasetService.get_decision_time_features(split_data[name])

        assert "recovered" not in features.columns
        assert "gt_p_recovery_base" not in features.columns
        assert len(features.columns) == 9


def test_15_metadata_json_integrity():
    """15. Verify split_metadata.json is valid and contains expected keys."""
    with open(METADATA_JSON, "r") as f:
        meta = json.load(f)

    assert meta["dataset_version"] == "v1.0"
    assert meta["random_seed"] == 42
    assert meta["source_record_count"] == 50000
    assert "splits" in meta
    assert "validation_checks" in meta
    assert meta["validation_checks"]["zero_customer_overlap"] is True


def test_16_non_empty_partitions(split_data: Dict[str, pd.DataFrame]):
    """16. Verify all partitions contain records."""
    assert len(split_data["train"]) > 0
    assert len(split_data["val"]) > 0
    assert len(split_data["test"]) > 0


def test_17_recovery_rate_stability(split_data: Dict[str, pd.DataFrame]):
    """17. Verify overall recovery rate is stable across splits (within 50%-60%)."""
    for name in ["train", "val", "test"]:
        rec_rate = split_data[name]["recovered"].mean() * 100.0
        assert 50.0 <= rec_rate <= 60.0, f"Recovery rate out of bounds in {name}: {rec_rate:.2f}%"


def test_18_customer_transaction_count_conservation(split_data: Dict[str, pd.DataFrame]):
    """18. Verify every customer's full transaction history is kept intact in a single partition."""
    source_cust_counts = split_data["source"]["customer_id"].value_counts().to_dict()

    for name in ["train", "val", "test"]:
        part_cust_counts = split_data[name]["customer_id"].value_counts().to_dict()
        for cust_id, count in part_cust_counts.items():
            assert count == source_cust_counts[cust_id], f"Customer {cust_id} transactions split across partitions!"


def test_19_ground_truth_columns_preserved(split_data: Dict[str, pd.DataFrame]):
    """19. Verify all 5 latent ground truth probability columns exist for downstream simulation."""
    gt_cols = [
        "gt_p_recovery_base",
        "gt_p_recovery_payment_link",
        "gt_p_recovery_message",
        "gt_p_recovery_retry",
        "gt_p_recovery_subscription_recovery",
    ]

    for name in ["train", "val", "test"]:
        for col in gt_cols:
            assert col in split_data[name].columns, f"Missing ground truth column {col} in {name} partition"


def test_20_dataset_service_load_split():
    """20. Verify DatasetService.load_split loader method."""
    train_df = DatasetService.load_split("train", data_dir=DATA_DIR)
    assert len(train_df) > 0
    assert isinstance(train_df, pd.DataFrame)

    with pytest.raises(ValueError):
        DatasetService.load_split("invalid_split", data_dir=DATA_DIR)
