"""
RecoverAI - Evaluation REST API Schemas (Step 25)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EvaluationRunResponse(BaseModel):
    """Response schema for an EvaluationRun record."""
    id: str = Field(..., description="Evaluation run UUID.")
    run_name: str = Field(..., description="Human-readable run identifier.")
    dataset_version: str = Field(..., description="Evaluation dataset version string.")
    dataset_size: int = Field(..., description="Dataset size in transactions.")
    random_seed: int = Field(..., description="Random seed used in evaluation.")
    model_version: str = Field(..., description="ML model version string.")
    feature_version: str = Field(..., description="Feature extractor version string.")
    policy_version: str = Field(..., description="Policy engine version string.")
    configuration_version: str = Field(..., description="Configuration version string.")
    code_commit_sha: Optional[str] = Field(None, description="Git commit SHA at evaluation execution time.")
    mode: str = Field(..., description="Execution mode (REAL_TEST or SIMULATION).")
    revenue_at_risk: float = Field(..., description="Total revenue at risk evaluated (in INR).")
    baseline_recovered_amount: float = Field(..., description="Gross recovered amount in baseline control cohort.")
    recoverai_gross_recovered_amount: float = Field(..., description="Gross recovered amount in treatment cohort.")
    incremental_recovered_amount: float = Field(..., description="Estimated incremental recovered revenue.")
    baseline_recovery_rate: float = Field(..., description="Control recovery rate ratio.")
    recoverai_recovery_rate: float = Field(..., description="Treatment recovery rate ratio.")
    summary_metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed dictionary of secondary evaluation metrics.")
    created_at: datetime = Field(..., description="Evaluation run creation timestamp.")

    model_config = ConfigDict(from_attributes=True)


class EvaluationPaginatedResponse(BaseModel):
    """Paginated list response for evaluation runs."""
    total: int = Field(..., description="Total matching evaluation runs count.")
    page: int = Field(..., description="Current page index.")
    limit: int = Field(..., description="Page size limit.")
    items: List[EvaluationRunResponse] = Field(..., description="Evaluation run record items.")
