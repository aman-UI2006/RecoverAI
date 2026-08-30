"""
RecoverAI - Analytics REST API Endpoint Controller (Step 25)

Provides GET /api/v1/analytics/summary delivering Command Center KPI metrics
via the authoritative MeasurementEngine.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.services.measurement_engine import MeasurementEngine
from backend.app.schemas.analytics import MeasurementRequest, MeasurementResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=MeasurementResponse)
async def get_analytics_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    mode: str = Query("SIMULATION", description="Execution mode (REAL_TEST or SIMULATION)."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve summary analytics KPI metrics comparing Treatment cohorts against Baseline Control cohorts.
    """
    effective_merchant_id = merchant_id or x_merchant_id

    req = MeasurementRequest(
        merchant_id=effective_merchant_id,
        mode=mode,
        run_name="analytics_summary_api",
        persist_evaluation_run=False,  # Summary API call does not pollute evaluation_runs table
    )

    response = await MeasurementEngine.evaluate_measurement(session=session, request=req)
    return response
