"""
RecoverAI - Step 51 Backend Deployment Test Suite

Tests backend deployment requirements:
1. FastAPI /health endpoint returning HTTP 200 and {"status": "ok", "database_connected": ...}
2. Swagger UI documentation (/docs) and OpenAPI spec (/openapi.json) accessibility
3. Celery background worker task configuration and task registry
4. Dockerfile non-root user security hardening (USER recoverai)
5. Docker Compose service configuration for FastAPI backend and Celery worker
6. Automated backend deployment verification utility (verify_backend_deployment)
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import yaml

from backend.app.main import app
from backend.app.tasks.worker import celery_app
from scripts.verify_backend_deployment import verify_backend_deployment


@pytest.fixture
def test_client():
    return TestClient(app)


def test_health_endpoint_returns_200_ok(test_client):
    """Test 1: GET /health returns status code 200 and valid JSON response."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "database_connected" in data
    assert "system" in data


def test_openapi_docs_and_schema_accessible(test_client):
    """Test 2: GET /docs and GET /openapi.json return status code 200."""
    docs_resp = test_client.get("/docs")
    assert docs_resp.status_code == 200
    assert "swagger" in docs_resp.text.lower() or "openapi" in docs_resp.text.lower() or "html" in docs_resp.text.lower()

    openapi_resp = test_client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_data = openapi_resp.json()
    assert "openapi" in openapi_data
    assert openapi_data.get("info", {}).get("title") == "RecoverAI"


def test_celery_worker_configuration():
    """Test 3: Celery worker app instance is loaded with valid configuration."""
    assert celery_app is not None
    assert celery_app.main == "recoverai_tasks"
    # Ensure tasks are registered
    registered_tasks = celery_app.tasks.keys()
    assert any("worker" in task or "execute" in task or "celery" in task for task in registered_tasks)


def test_dockerfile_non_root_user_security():
    """Test 4: backend/Dockerfile enforces non-root container user execution."""
    dockerfile_path = Path(__file__).parent.parent.parent / "backend" / "Dockerfile"
    assert dockerfile_path.exists(), "backend/Dockerfile missing"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "USER recoverai" in content or "USER appuser" in content, "Non-root USER directive missing in backend/Dockerfile"
    assert "useradd" in content, "useradd creation directive missing in backend/Dockerfile"
    assert "HEALTHCHECK" in content, "HEALTHCHECK directive missing in backend/Dockerfile"


def test_docker_compose_backend_and_worker_config():
    """Test 5: docker-compose.yml contains valid backend and celery_worker services."""
    compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml missing"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    assert "backend" in services, "backend service missing in docker-compose.yml"
    assert "celery_worker" in services, "celery_worker service missing in docker-compose.yml"

    backend_svc = services["backend"]
    assert "healthcheck" in backend_svc, "healthcheck missing for backend in docker-compose.yml"
    assert "ports" in backend_svc, "ports configuration missing for backend in docker-compose.yml"

    worker_svc = services["celery_worker"]
    assert "command" in worker_svc, "command missing for celery_worker in docker-compose.yml"
    assert "celery" in worker_svc["command"][0] or "celery" in str(worker_svc["command"])


def test_verify_backend_deployment_script(monkeypatch, test_client):
    """Test 6: verify_backend_deployment function successfully validates a running app."""
    # Mock urllib.request.urlopen to use FastAPI TestClient responses
    class MockHTTPResponse:
        def __init__(self, response):
            self._resp = response

        def getcode(self):
            return self._resp.status_code

        def read(self):
            return self._resp.content

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        path = "/" + url.split("://")[-1].split("/", 1)[-1]
        res = test_client.get(path)
        return MockHTTPResponse(res)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    is_valid = verify_backend_deployment(base_url="http://localhost:8000")
    assert is_valid is True
