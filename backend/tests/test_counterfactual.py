"""
RecoverAI - Step 45 Counterfactual Evaluation Unit Tests

Validates Doubly Robust counterfactual estimation:
1. Propensity score clipping to range [0.05, 0.95].
2. Dataset-level counterfactual evaluation execution on `data/test.parquet`.
3. Report generation writing `docs/COUNTERFACTUAL_ANALYSIS.md`.
"""

import os
import pytest
from backend.app.ml.counterfactual_evaluator import (
    CounterfactualEvaluator,
    MIN_PROPENSITY_CLIP,
    MAX_PROPENSITY_CLIP,
)


def test_propensity_score_clamping():
    """
    Test 1: Verifies propensity scores are clipped to [0.05, 0.95] to prevent IPW variance explosion.
    """
    assert CounterfactualEvaluator.clip_propensity_score(0.01) == MIN_PROPENSITY_CLIP
    assert CounterfactualEvaluator.clip_propensity_score(0.00) == MIN_PROPENSITY_CLIP
    assert CounterfactualEvaluator.clip_propensity_score(0.99) == MAX_PROPENSITY_CLIP
    assert CounterfactualEvaluator.clip_propensity_score(1.00) == MAX_PROPENSITY_CLIP
    assert CounterfactualEvaluator.clip_propensity_score(0.40) == 0.40


def test_counterfactual_evaluation_dataset():
    """
    Test 2: Executes Doubly Robust counterfactual evaluation on `data/test.parquet`.
    """
    parquet_path = "data/test.parquet"
    if not os.path.exists(parquet_path):
        pytest.skip(f"Test dataset '{parquet_path}' not present.")

    evaluator = CounterfactualEvaluator()
    results = evaluator.evaluate_dataset(parquet_path)

    assert results["num_samples"] > 0
    assert 0.0 <= results["actual_recovery_rate"] <= 1.0
    assert 0.0 <= results["counterfactual_optimal_rate"] <= 1.0
    assert 0.0 <= results["strategy_optimality_pct"] <= 100.0
    assert "action_summary" in results
    assert len(results["action_summary"]) == 6


def test_generate_counterfactual_report(tmp_path):
    """
    Test 3: Verifies report generation creates valid Markdown file.
    """
    parquet_path = "data/test.parquet"
    if not os.path.exists(parquet_path):
        pytest.skip(f"Test dataset '{parquet_path}' not present.")

    evaluator = CounterfactualEvaluator()
    results = evaluator.evaluate_dataset(parquet_path)

    report_path = str(tmp_path / "COUNTERFACTUAL_ANALYSIS.md")
    report_content = evaluator.generate_report(results, output_path=report_path)

    assert os.path.exists(report_path)
    assert "Doubly Robust" in report_content
    assert "Causal Lift" in report_content
    assert "Strategy Optimality" in report_content
