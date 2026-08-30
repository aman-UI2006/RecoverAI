"""
RecoverAI - API v1 Router Aggregator (Step 24)
"""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import webhooks, human_review

api_v1_router = APIRouter()
api_v1_router.include_router(webhooks.router)
api_v1_router.include_router(human_review.router)
