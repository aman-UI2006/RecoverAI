"""
RecoverAI - FastAPI Application Entry Point (Step 24)

Initializes the FastAPI application foundation with CORS, request ID tracing,
global exception handlers, OpenAPI metadata, and health check endpoints.
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import HTTPException as FastAPIHTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import check_database_connection
from backend.app.core.middleware import RequestIDMiddleware
from backend.app.api.v1.router import api_v1_router

logger = logging.getLogger(__name__)

# 1. Instantiate FastAPI application with OpenAPI metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise AI Revenue Recovery System for Razorpay Ecosystem",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 2. Configure CORS middleware allowing requests from frontend development URL
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Add Request ID tracing middleware (X-Trace-ID)
app.add_middleware(RequestIDMiddleware)


# 4. Configure global exception handlers returning standardized error JSON payloads
@app.exception_handler(StarletteHTTPException)
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status": "error",
            "code": exc.status_code,
            "message": str(exc.detail),
            "detail": str(exc.detail),
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status": "error",
            "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Validation Error",
            "detail": exc.errors(),
            "details": exc.errors(),
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error(f"Unhandled Exception: {exc} | TraceID: {trace_id}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status": "error",
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Internal Server Error",
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id},
    )


# 5. Include API v1 router in main application
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint returning HTTP 200 with status ok."""
    db_ok = await check_database_connection()
    return {
        "status": "ok",
        "system": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database_connected": db_ok,
    }
