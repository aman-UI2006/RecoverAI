"""
RecoverAI - Step 52 Frontend Deployment Test Suite

Tests frontend deployment requirements:
1. Static production asset bundle compilation in frontend/dist/ (index.html)
2. Nginx configuration (frontend/nginx.conf) for SPA fallback try_files and Security HTTP Headers
3. Frontend multi-stage Dockerfile configuration (builder & Nginx runner)
4. Docker Compose service configuration for React SPA frontend container
5. Automated frontend deployment verification utility (verify_frontend_deployment)
"""

import pytest
from pathlib import Path
import yaml

from scripts.verify_frontend_deployment import (
    verify_frontend_build_artifacts,
    verify_nginx_security_config,
    verify_frontend_deployment,
)


def test_frontend_dist_build_artifacts_exist():
    """Test 1: Verify frontend/dist/index.html static bundle exists and contains root mount container."""
    is_valid = verify_frontend_build_artifacts()
    assert is_valid is True, "Frontend build artifacts missing or invalid"


def test_nginx_security_headers_and_spa_routing():
    """Test 2: Verify frontend/nginx.conf contains SPA try_files routing and mandatory Security HTTP Headers."""
    is_valid = verify_nginx_security_config()
    assert is_valid is True, "Nginx configuration missing required security headers or SPA routing"

    nginx_conf = Path(__file__).parent.parent.parent / "frontend" / "nginx.conf"
    content = nginx_conf.read_text(encoding="utf-8")

    assert 'add_header X-Frame-Options "SAMEORIGIN"' in content
    assert 'add_header X-Content-Type-Options "nosniff"' in content
    assert 'add_header X-XSS-Protection "1; mode=block"' in content
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin"' in content


def test_frontend_dockerfile_configuration():
    """Test 3: Verify frontend/Dockerfile multi-stage build setup."""
    dockerfile = Path(__file__).parent.parent.parent / "frontend" / "Dockerfile"
    assert dockerfile.exists(), "frontend/Dockerfile missing"

    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM node:" in content, "Node builder stage missing"
    assert "FROM nginx:" in content, "Nginx runner stage missing"
    assert "COPY frontend/nginx.conf" in content or "COPY --from=builder /app/dist" in content
    assert "HEALTHCHECK" in content, "Health check directive missing in frontend Dockerfile"
    assert "EXPOSE 80" in content, "Port 80 exposure missing in frontend Dockerfile"


def test_docker_compose_frontend_service_config():
    """Test 4: Verify docker-compose.yml frontend service configuration."""
    compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml missing"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    assert "frontend" in services, "frontend service missing in docker-compose.yml"

    frontend_svc = services["frontend"]
    assert "healthcheck" in frontend_svc, "healthcheck missing for frontend service"
    assert "depends_on" in frontend_svc, "depends_on missing for frontend service"


def test_verify_frontend_deployment_script():
    """Test 5: Verify verify_frontend_deployment script execution."""
    success = verify_frontend_deployment(target_url=None)
    assert success is True
