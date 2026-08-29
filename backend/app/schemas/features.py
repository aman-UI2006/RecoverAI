"""
RecoverAI - Feature Schema Definition (Step 9)

Pydantic schemas representing input feature context and dense numerical feature vectors
for ML model inference (Diagnosis Classification & Action-Conditional Recovery).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FeatureContext(BaseModel):
    """Raw context parameters supplied to FeatureExtractor."""
    transaction_id: str
    amount_in_paise: int = Field(gt=0, description="Amount in minor units (paise)")
    scenario_type: str
    decline_code: Optional[str] = "UNKNOWN"
    checkout_device: Optional[str] = "UNKNOWN"
    customer_historical_success_rate: Optional[float] = None
    customer_historical_transaction_count: Optional[int] = 0
    created_at_iso: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class FeatureVector(BaseModel):
    """Structured numerical feature vector schema for ML inference."""
    model_config = ConfigDict(frozen=True)

    transaction_id: str

    # Numerical features
    customer_historical_success_rate: float = Field(ge=0.0, le=1.0)
    customer_historical_transaction_count: int = Field(ge=0)
    amount_in_paise: int = Field(gt=0)
    amount_log: float
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)

    # Categorical encoded features
    scenario_encoded: int
    decline_code_encoded: int
    device_encoded: int

    # Ordered dense float vector for model inference
    dense_vector: List[float] = Field(description="Ordered float array for model inference")
    feature_names: List[str] = Field(description="Column names corresponding to dense_vector elements")
