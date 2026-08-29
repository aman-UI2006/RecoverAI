"""
RecoverAI - API v1 Router Aggregator (Step 5)
"""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import webhooks

api_v1_router = APIRouter()
api_v1_router.include_router(webhooks.router)
