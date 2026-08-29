"""
RecoverAI - Risk Assessment Schemas (Step 8)

Pydantic schemas defining inputs, outputs, and risk parameters for the Revenue Risk Engine.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RiskAssessmentRequest(BaseModel):
    """Input payload for assessing transaction revenue risk."""
    transaction_id: str
    scenario_type: str
    amount_in_paise: int = Field(gt=0, description="Transaction amount in integer minor units (paise)")
    currency: str = Field(default="INR", max_length=10)
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RiskAssessmentResponse(BaseModel):
    """Structured result returned by RevenueRiskEngine."""
    model_config = ConfigDict(frozen=True)

    transaction_id: str
    merchant_id: Optional[str]
    scenario_type: str
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk probability score between 0.0 and 1.0")
    amount_in_paise: int
    eligible_revenue_at_risk_in_paise: int
    eligible_revenue_at_risk: float = Field(description="Eligible revenue at risk in standard currency units (rupees)")
    currency: str
    eligibility_window_hours: int = 72
    detected_at: datetime
    expires_at: datetime
    status: str = "AT_RISK"
