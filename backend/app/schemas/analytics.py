"""
RecoverAI - Control/Treatment Measurement Engine Schemas (Step 21)

Defines Pydantic data transfer objects for cohort measurement, incremental lift analysis,
and evaluation metrics reporting.
"""

from typing import Any, Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CohortMetrics(BaseModel):
    """Metrics for a specific transaction cohort (Treatment or Baseline Control)."""

    total_eligible_count: int = Field(default=0, description="Total eligible failed transactions in cohort.")
    total_eligible_amount: float = Field(default=0.0, description="Total monetary value at risk in cohort (in INR).")
    recovered_count: int = Field(default=0, description="Count of recovered transactions in cohort.")
    recovered_amount: float = Field(default=0.0, description="Total monetary value recovered in cohort (in INR).")
    recovery_rate: float = Field(default=0.0, description="Recovery rate ratio (recovered_count / total_eligible_count).")
    refunded_amount: float = Field(default=0.0, description="Total refunded amount in cohort (in INR).")
    intervention_cost: float = Field(default=0.0, description="Total operational and intervention cost in cohort (in INR).")

    model_config = ConfigDict(from_attributes=True)


class MeasurementRequest(BaseModel):
    """Payload for executing measurement computation."""

    merchant_id: Optional[str] = Field(None, description="Optional merchant UUID filter for multi-tenant isolation.")
    start_time: Optional[datetime] = Field(None, description="Optional start datetime filter for evaluation window.")
    end_time: Optional[datetime] = Field(None, description="Optional end datetime filter for evaluation window.")
    mode: str = Field(default="SIMULATION", description="Execution mode filter: REAL_TEST or SIMULATION.")
    run_name: str = Field(default="cohort_evaluation_run", description="Human-readable evaluation run identifier.")
    dataset_version: str = Field(default="v1.0", description="Version string of underlying evaluation dataset.")
    dataset_size: int = Field(default=0, description="Total dataset size in transactions.")
    random_seed: int = Field(default=42, description="Random seed used during dataset generation or split.")
    model_version: str = Field(default="v1.0", description="Version string of ML action-conditional model.")
    feature_version: str = Field(default="v1.0", description="Version string of feature extractor.")
    policy_version: str = Field(default="v1.0", description="Version string of policy engine rules.")
    configuration_version: str = Field(default="v1.0", description="Version string of system configuration.")
    code_commit_sha: Optional[str] = Field(None, description="Git commit SHA at execution time.")
    persist_evaluation_run: bool = Field(default=True, description="Whether to persist the summary record into evaluation_runs table.")

    model_config = ConfigDict(from_attributes=True)


class MeasurementResponse(BaseModel):
    """Response payload containing computed treatment vs control lift metrics and ROI."""

    evaluation_run_id: Optional[str] = Field(None, description="UUID of persisted EvaluationRun database record.")
    run_name: str = Field(..., description="Name of evaluation run.")
    mode: str = Field(..., description="Execution mode: REAL_TEST or SIMULATION.")
    merchant_id: Optional[str] = Field(None, description="Merchant UUID filter if applicable.")
    
    treatment_metrics: CohortMetrics = Field(..., description="Metrics for Treatment cohort (RecoverAI interventions).")
    control_metrics: CohortMetrics = Field(..., description="Metrics for Baseline Control cohort.")

    treatment_recovery_rate: float = Field(..., description="Treatment group recovery rate ratio.")
    control_recovery_rate: float = Field(..., description="Control group recovery rate ratio.")
    incremental_recovery_rate: float = Field(..., description="Absolute rate lift (Treatment Rate - Control Rate).")
    
    treatment_recovered_amount: float = Field(..., description="Authoritative treatment group gross recovered amount.")
    control_recovered_amount: float = Field(..., description="Authoritative control group gross recovered amount.")
    estimated_incremental_recovered_amount: float = Field(..., description="Estimated incremental recovered revenue amount.")
    net_incremental_revenue: float = Field(..., description="Net incremental revenue after deducting refunds and costs.")
    
    summary_metrics: Dict[str, Any] = Field(default_factory=dict, description="Detailed dictionary of secondary metrics.")
    created_at: datetime = Field(..., description="Timestamp when measurement was evaluated.")

    model_config = ConfigDict(from_attributes=True)


class IndustryBenchmark(BaseModel):
    """Industry cohort aggregate benchmark."""

    industry: str = Field(..., description="Industry category (e.g. SaaS, E-commerce, EdTech).")
    decline_categories: Dict[str, float] = Field(default_factory=dict, description="Decline breakdown percentage mapping.")
    avg_turnaround_minutes: float = Field(default=0.0, description="Average recovery turnaround time in minutes.")
    top_performing_channels: List[Dict[str, Any]] = Field(default_factory=list, description="Ranked recovery action channel performance.")

    model_config = ConfigDict(from_attributes=True)


class MerchantIntelligenceResponse(BaseModel):
    """Response payload for GET /api/v1/analytics/merchant delivering merchant cohort intelligence."""

    merchant_id: Optional[str] = Field(None, description="Merchant UUID filter.")
    industry: str = Field(default="SaaS", description="Merchant industry cohort classification.")
    total_transactions_analyzed: int = Field(default=0, description="Total transactions in cohort.")
    merchant_decline_categories: Dict[str, float] = Field(default_factory=dict, description="Merchant decline code percentage distribution.")
    avg_turnaround_minutes: float = Field(default=0.0, description="Average turnaround time in minutes.")
    top_channel: str = Field(default="PAYMENT_LINK", description="Top performing recovery action channel.")
    channel_performance: Dict[str, float] = Field(default_factory=dict, description="Channel recovery rate percentage mapping.")
    industry_benchmarks: List[IndustryBenchmark] = Field(default_factory=list, description="Comparative benchmark metrics across industry cohorts.")

    model_config = ConfigDict(from_attributes=True)

