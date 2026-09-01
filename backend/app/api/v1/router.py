"""
RecoverAI - API v1 Router Aggregator (Step 24)
"""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    webhooks,
    human_review,
    transactions,
    analytics,
    audit,
    policies,
    evaluations,
    ai_decisions,
    communication,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(webhooks.router)
api_v1_router.include_router(human_review.router)
api_v1_router.include_router(transactions.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(audit.router)
api_v1_router.include_router(policies.router)
api_v1_router.include_router(evaluations.router)
api_v1_router.include_router(ai_decisions.router)
api_v1_router.include_router(communication.router)



