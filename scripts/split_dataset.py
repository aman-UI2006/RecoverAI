"""
RecoverAI - Dataset Partitioning Script (Step 4)

Partitions data/synthetic_50k.parquet into Train (70%), Validation (15%), and Test (15%) splits
with strict Customer-Group Partitioning (DEC-007) guaranteeing zero customer_id overlap.
Applies deterministic internal chronological ordering by created_at and transaction_id.
"""

import hashlib
import json
import os
import sys
from typing import Dict, Any

import numpy as np
import pandas as pd

# Ensure backend modules are resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.dataset_service import DatasetService


def compute_sha256(file_path: str) -> str:
    """Computes SHA-256 hash of a file."""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def split_dataset(
    source_path: str,
    output_dir: str,
    random_seed: int = 42,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> Dict[str, Any]:
    """
    Partitions synthetic dataset into train, val, and test splits following DEC-007.

    Args:
        source_path: Path to source dataset (synthetic_50k.parquet).
        output_dir: Target directory for partition files.
        random_seed: Random seed for customer allocation.
        train_ratio: Target fraction of customers for training.
        val_ratio: Target fraction of customers for validation.

    Returns:
        Dict[str, Any]: Split metadata dictionary.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source dataset not found at: {source_path}")

    os.makedirs(output_dir, exist_ok=True)

    print(f"[1/5] Loading source dataset from {source_path}...")
    source_df = DatasetService.load_dataset(source_path)

    # Validate source schema
    is_valid, errors = DatasetService.validate_schema(source_df)
    if not is_valid:
        raise ValueError(f"Source dataset schema validation failed: {errors}")

    source_sha256 = compute_sha256(source_path)
    total_records = len(source_df)

    print(f"[2/5] Partitioning {total_records:,} records by customer_id (DEC-007)...")
    unique_customers = sorted(source_df["customer_id"].unique())
    num_customers = len(unique_customers)

    # Deterministic customer shuffling using RandomState(42)
    rng = np.random.RandomState(random_seed)
    shuffled_customers = unique_customers.copy()
    rng.shuffle(shuffled_customers)

    n_train_cust = int(num_customers * train_ratio)
    n_val_cust = int(num_customers * val_ratio)
    # Remaining customers go to test split to ensure exact customer accounting
    n_test_cust = num_customers - n_train_cust - n_val_cust

    train_cust_set = set(shuffled_customers[:n_train_cust])
    val_cust_set = set(shuffled_customers[n_train_cust : n_train_cust + n_val_cust])
    test_cust_set = set(shuffled_customers[n_train_cust + n_val_cust :])

    # Subset DataFrames
    train_df = source_df[source_df["customer_id"].isin(train_cust_set)].copy()
    val_df = source_df[source_df["customer_id"].isin(val_cust_set)].copy()
    test_df = source_df[source_df["customer_id"].isin(test_cust_set)].copy()

    # Mandatory Invariant Checks
    print(f"[3/5] Verifying split hard invariants...")

    # 1. Total row conservation
    assert (
        len(train_df) + len(val_df) + len(test_df) == total_records
    ), f"Row loss/addition error: {len(train_df)} + {len(val_df)} + {len(test_df)} != {total_records}"

    # 2. Customer isolation
    assert (
        len(train_cust_set & val_cust_set) == 0
    ), "Customer leakage detected between Train and Validation!"
    assert (
        len(train_cust_set & test_cust_set) == 0
    ), "Customer leakage detected between Train and Test!"
    assert (
        len(val_cust_set & test_cust_set) == 0
    ), "Customer leakage detected between Validation and Test!"

    # 3. Transaction isolation
    train_tx = set(train_df["transaction_id"])
    val_tx = set(val_df["transaction_id"])
    test_tx = set(test_df["transaction_id"])
    assert len(train_tx & val_tx) == 0, "Transaction duplication between Train and Validation!"
    assert len(train_tx & test_tx) == 0, "Transaction duplication between Train and Test!"
    assert len(val_tx & test_tx) == 0, "Transaction duplication between Validation and Test!"

    # 4. Money datatype integrity
    for split_name, df_subset in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        assert (
            df_subset["amount_in_paise"].dtype == "int64"
        ), f"Monetary amount_in_paise in {split_name} is not int64!"

    print(f"[4/5] Applying deterministic internal ordering (created_at ASC, transaction_id ASC)...")
    train_df.sort_values(by=["created_at", "transaction_id"], ascending=[True, True], inplace=True)
    val_df.sort_values(by=["created_at", "transaction_id"], ascending=[True, True], inplace=True)
    test_df.sort_values(by=["created_at", "transaction_id"], ascending=[True, True], inplace=True)

    train_df.reset_index(drop=True, inplace=True)
    val_df.reset_index(drop=True, inplace=True)
    test_df.reset_index(drop=True, inplace=True)

    # Output paths
    train_path = os.path.join(output_dir, "train.parquet")
    val_path = os.path.join(output_dir, "val.parquet")
    test_path = os.path.join(output_dir, "test.parquet")
    meta_path = os.path.join(output_dir, "split_metadata.json")

    print(f"[5/5] Exporting partition Parquet files...")
    train_df.to_parquet(train_path, engine="pyarrow", index=False)
    val_df.to_parquet(val_path, engine="pyarrow", index=False)
    test_df.to_parquet(test_path, engine="pyarrow", index=False)

    train_sha256 = compute_sha256(train_path)
    val_sha256 = compute_sha256(val_path)
    test_sha256 = compute_sha256(test_path)

    metadata: Dict[str, Any] = {
        "dataset_version": "v1.0",
        "random_seed": random_seed,
        "source_file": source_path,
        "source_record_count": total_records,
        "source_sha256": source_sha256,
        "split_strategy": "DEC-007 Customer-Group Partitioning with Deterministic Internal Ordering",
        "splits": {
            "train": {
                "record_count": len(train_df),
                "customer_count": len(train_cust_set),
                "percentage": round(len(train_df) / total_records * 100.0, 2),
                "recovered_rate_pct": round(float(train_df["recovered"].mean()) * 100.0, 2),
                "sha256": train_sha256,
                "file_path": train_path,
            },
            "val": {
                "record_count": len(val_df),
                "customer_count": len(val_cust_set),
                "percentage": round(len(val_df) / total_records * 100.0, 2),
                "recovered_rate_pct": round(float(val_df["recovered"].mean()) * 100.0, 2),
                "sha256": val_sha256,
                "file_path": val_path,
            },
            "test": {
                "record_count": len(test_df),
                "customer_count": len(test_cust_set),
                "percentage": round(len(test_df) / total_records * 100.0, 2),
                "recovered_rate_pct": round(float(test_df["recovered"].mean()) * 100.0, 2),
                "sha256": test_sha256,
                "file_path": test_path,
            },
        },
        "validation_checks": {
            "zero_customer_overlap": True,
            "zero_transaction_overlap": True,
            "total_row_conservation": True,
            "money_datatype_int64": True,
        },
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main() -> None:
    print("=" * 60)
    print("RecoverAI - Dataset Partitioning & Validation (Step 4)")
    print("=" * 60)

    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    source_path = os.path.join(data_dir, "synthetic_50k.parquet")

    metadata = split_dataset(source_path=source_path, output_dir=data_dir, random_seed=42)

    print("\n" + "=" * 60)
    print("STEP 4 DATASET PARTITIONING SUMMARY REPORT")
    print("=" * 60)
    print(f"Strategy:              {metadata['split_strategy']}")
    print(f"Random Seed:           {metadata['random_seed']}")
    print(f"Source Records:        {metadata['source_record_count']:,}")

    print("\n--- Split Partition Metrics ---")
    for name, stats in metadata["splits"].items():
        print(f"Partition: {name.upper():5s}")
        print(f"  - Record Count:      {stats['record_count']:6,} ({stats['percentage']:5.2f}%)")
        print(f"  - Unique Customers:  {stats['customer_count']:6,}")
        print(f"  - Recovery Rate:     {stats['recovered_rate_pct']:5.2f}%")
        print(f"  - SHA-256 Hash:      {stats['sha256']}")

    print("\n--- Invariant Verification ---")
    for check, status in metadata["validation_checks"].items():
        status_str = "PASSED" if status else "FAILED"
        print(f"  - {check:30s}: {status_str}")

    print("\n" + "=" * 60)
    print("STEP 4 DATASET PARTITIONING COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
