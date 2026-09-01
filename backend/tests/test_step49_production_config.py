"""
RecoverAI - Step 49 Production Configuration Tests

Verifies validity of docker-compose orchestration, Dockerfiles, Nginx config,
and production environment template.
"""

import os
import yaml


def test_docker_compose_validity():
    """Verify docker-compose.yml structure and mandatory services."""
    compose_path = os.path.join(os.getcwd(), "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml does not exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "services" in data, "services key missing in docker-compose.yml"
    services = data["services"]

    required_services = ["postgres", "redis", "backend", "celery_worker", "frontend"]
    for svc in required_services:
        assert svc in services, f"Service '{svc}' missing from docker-compose.yml"

    # Verify healthchecks configured
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["redis"]
    assert "healthcheck" in services["backend"]
    assert "healthcheck" in services["frontend"]


def test_dockerfiles_exist():
    """Verify backend and frontend Dockerfiles exist and specify multi-stage builds."""
    backend_df = os.path.join(os.getcwd(), "backend", "Dockerfile")
    frontend_df = os.path.join(os.getcwd(), "frontend", "Dockerfile")

    assert os.path.exists(backend_df), "backend/Dockerfile missing"
    assert os.path.exists(frontend_df), "frontend/Dockerfile missing"

    with open(backend_df, "r", encoding="utf-8") as f:
        backend_content = f.read()
    assert "FROM python:3.11-slim AS builder" in backend_content
    assert "FROM python:3.11-slim AS runner" in backend_content

    with open(frontend_df, "r", encoding="utf-8") as f:
        frontend_content = f.read()
    assert "FROM node:20-alpine AS builder" in frontend_content
    assert "FROM nginx:alpine AS runner" in frontend_content


def test_nginx_and_env_example_exist():
    """Verify Nginx configuration and production environment template exist."""
    nginx_path = os.path.join(os.getcwd(), "frontend", "nginx.conf")
    env_example_path = os.path.join(os.getcwd(), ".env.production.example")

    assert os.path.exists(nginx_path), "frontend/nginx.conf missing"
    assert os.path.exists(env_example_path), ".env.production.example missing"

    with open(nginx_path, "r", encoding="utf-8") as f:
        nginx_content = f.read()
    assert "location /api/" in nginx_content

    with open(env_example_path, "r", encoding="utf-8") as f:
        env_content = f.read()
    assert "RAZORPAY_KEY_ID" in env_content
    assert "GROQ_API_KEY" in env_content
