"""
RecoverAI - Synthetic Dataset Generation Script (Step 3)

Generates 50,000+ deterministic synthetic transactions using seed 42.
Outputs dataset to data/synthetic_50k.parquet and data/synthetic_50k.csv.
Reports summary metrics and dataset integrity verification.
"""

import hashlib
import os
import sys

# Ensure backend modules are resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.dataset_generator import SyntheticDatasetGenerator
from backend.app.services.dataset_service import DatasetService


def main() -> None:
    print("=" * 60)
    print("RecoverAI - Synthetic Dataset Generation (Step 3)")
    print("=" * 60)

    seed = 42
    target_records = 50000
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(output_dir, exist_ok=True)

    parquet_path = os.path.join(output_dir, "synthetic_50k.parquet")
    csv_path = os.path.join(output_dir, "synthetic_50k.csv")

    print(f"[1/4] Initializing generator with random_seed={seed}...")
    generator = SyntheticDatasetGenerator(random_seed=seed)

    print(f"[2/4] Generating {target_records:,} synthetic transaction records...")
    df = generator.generate_dataset(num_records=target_records)

    print(f"[3/4] Exporting dataset to Parquet and CSV...")
    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    df.to_csv(csv_path, index=False)

    print(f"[4/4] Validating generated dataset...")
    loaded_df = DatasetService.load_dataset(parquet_path)
    is_valid, errors = DatasetService.validate_schema(loaded_df)

    if not is_valid:
        print("ERROR: Dataset validation failed with errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    # Compute SHA-256 hash of Parquet file
    with open(parquet_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Summary Statistics
    total_records = len(loaded_df)
    total_amount_paise = loaded_df["amount_in_paise"].sum()
    total_amount_rupees = loaded_df["amount"].sum()

    scenario_counts = loaded_df["scenario"].value_counts().to_dict()
    action_counts = loaded_df["historical_action"].value_counts().to_dict()
    overall_recovery_rate = float(loaded_df["recovered"].mean()) * 100.0

    print("\n" + "=" * 60)
    print("SYNTHETIC DATASET SUMMARY REPORT")
    print("=" * 60)
    print(f"Dataset Version:             v1.0")
    print(f"Random Seed:                 {seed}")
    print(f"Total Records:               {total_records:,}")
    print(f"Parquet Path:                {parquet_path}")
    print(f"Parquet Size:                {os.path.getsize(parquet_path) / (1024*1024):.2f} MB")
    print(f"Parquet SHA-256 Hash:        {file_hash}")
    print(f"Total Revenue At Risk:       INR {total_amount_rupees:,.2f} ({total_amount_paise:,} paise)")
    print(f"Overall Recovery Rate:       {overall_recovery_rate:.2f}%")

    print("\n--- Scenario Distribution ---")
    for scenario, count in scenario_counts.items():
        pct = (count / total_records) * 100.0
        print(f"  - {scenario:30s}: {count:6,} records ({pct:5.2f}%)")

    print("\n--- Historical Action Distribution (Overall) ---")
    for action, count in action_counts.items():
        pct = (count / total_records) * 100.0
        print(f"  - {action:30s}: {count:6,} records ({pct:5.2f}%)")

    print("\n--- Historical Action Distribution (Per Scenario) ---")
    for scenario in scenario_counts.keys():
        sc_df = loaded_df[loaded_df["scenario"] == scenario]
        sc_total = len(sc_df)
        print(f"\nScenario: {scenario} (N={sc_total:,})")
        for act, act_cnt in sc_df["historical_action"].value_counts().to_dict().items():
            act_pct = (act_cnt / sc_total) * 100.0
            print(f"  * {act:30s}: {act_cnt:6,} records ({act_pct:5.2f}%)")

            # Check action support audit warning
            if act_cnt < 500:
                print(f"    WARNING: Low action support detected for {act} in scenario {scenario} (count={act_cnt})")

    print("\n" + "=" * 60)
    print("STEP 3 DATASET GENERATION VERIFIED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
