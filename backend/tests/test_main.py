"""
RecoverAI - Unit and Integration Tests for Step 24: FastAPI Foundation
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_1_health_check_endpoint():
    """1. Test GET /health returns HTTP 200 with status ok and system metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["system"] == "RecoverAI"
        assert "environment" in data
        assert "database_connected" in data


@pytest.mark.asyncio
async def test_2_cors_middleware_headers():
    """2. Test CORS middleware allows allowed origin (http://localhost:5173)."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.options("/health", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_3_request_id_middleware_auto_generation():
    """3. Test RequestIDMiddleware generates X-Trace-ID header automatically when omitted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert "x-trace-id" in response.headers
        assert len(response.headers["x-trace-id"]) > 0


@pytest.mark.asyncio
async def test_4_custom_request_id_propagation():
    """4. Test RequestIDMiddleware preserves provided X-Trace-ID header."""
    custom_trace_id = "test-trace-uuid-12345"
    headers = {"X-Trace-ID": custom_trace_id}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("x-trace-id") == custom_trace_id


@pytest.mark.asyncio
async def test_5_http_exception_handler_formatting():
    """5. Test global HTTPException handler formats 404 errors with trace_id and standardized schema."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/nonexistent-endpoint-route")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert data["status"] == "error"
        assert data["code"] == 404
        assert "trace_id" in data


@pytest.mark.asyncio
async def test_6_validation_error_handler_formatting():
    """6. Test global RequestValidationError handler formats 422 errors with standardized schema and details."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # POST malformed JSON to simulator endpoint
        response = await client.post("/api/v1/webhooks/simulator-event", json={"invalid_field": True})
        assert response.status_code == 422
        data = response.json()
        assert data["error"] is True
        assert data["status"] == "error"
        assert data["code"] == 422
        assert "details" in data
        assert "trace_id" in data


@pytest.mark.asyncio
async def test_7_openapi_schema_generation():
    """7. Test OpenAPI docs and schema generation includes api_v1 routes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "RecoverAI"
        paths = schema["paths"]
        assert "/health" in paths
        assert "/api/v1/webhooks/razorpay" in paths
        assert "/api/v1/human-review/queue" in paths
