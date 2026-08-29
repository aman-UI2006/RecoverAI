"""
RecoverAI - FastAPI Application Entry Point (Step 5)
"""

from fastapi import FastAPI
from backend.app.core.config import settings
from backend.app.core.database import check_database_connection
from backend.app.api.v1.router import api_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise AI Revenue Recovery System for Razorpay Ecosystem",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register API V1 router under /api/v1
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint verifying database connectivity."""
    db_ok = await check_database_connection()
    return {
        "status": "healthy" if db_ok else "unhealthy",
        "system": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database_connected": db_ok,
    }
