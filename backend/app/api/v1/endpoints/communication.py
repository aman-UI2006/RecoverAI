"""
RecoverAI - Customer Communication REST API Endpoint Controller (Step 48)

Exposes POST /api/v1/communication/generate endpoint for customer recovery copy generation,
tone selection, PII masking, and execution boundary enforcement.
"""

from fastapi import APIRouter, Depends
from backend.app.schemas.communication import CommunicationRequest, CommunicationResponse
from backend.app.ai.communication_engine import CommunicationEngine

router = APIRouter(prefix="/communication", tags=["communication"])


@router.post("/generate", response_model=CommunicationResponse)
async def generate_communication(request: CommunicationRequest):
    """
    Generate tone-conditioned customer recovery copy with PII masking and explicit
    execution boundary handling (REAL_TEST content generation vs SIMULATION modeling).
    """
    engine = CommunicationEngine()
    return engine.generate_communication(request)
