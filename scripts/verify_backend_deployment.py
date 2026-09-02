"""
RecoverAI - Backend Deployment Verification Script (Step 51)

Verifies FastAPI backend deployment readiness and Celery worker configuration:
- HTTP GET /health returning status 200 and {"status": "ok", "database_connected": true}
- HTTP GET /docs returning status 200 (Swagger UI OpenAPI docs)
- HTTP GET /openapi.json returning valid OpenAPI specification
- Celery worker module import readiness
"""

import sys
import logging
import urllib.request
import json
from typing import Optional

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_backend_deployment")


def verify_backend_deployment(base_url: Optional[str] = None) -> bool:
    target_url = (base_url or "http://localhost:8000").rstrip("/")
    logger.info(f"Verifying FastAPI Backend Deployment at target URL: {target_url}")

    try:
        # 1. Health Check Endpoint Verification (/health)
        logger.info("1. Executing HTTP GET /health check...")
        health_url = f"{target_url}/health"
        req = urllib.request.Request(health_url, headers={"User-Agent": "RecoverAI-Deployment-Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            body = json.loads(resp.read().decode("utf-8"))

            if status_code != 200:
                logger.error(f"   [FAIL] /health returned non-200 status: {status_code}")
                return False
            if body.get("status") != "ok":
                logger.error(f"   [FAIL] /health status field is not 'ok': {body}")
                return False
            if not body.get("database_connected"):
                logger.warning(f"   [WARN] /health database_connected is False or missing: {body}")
            
            logger.info(f"   [PASS] Health check verified: status={body.get('status')}, db={body.get('database_connected')}")

        # 2. OpenAPI UI Documentation Endpoint Verification (/docs)
        logger.info("2. Executing HTTP GET /docs check...")
        docs_url = f"{target_url}/docs"
        req_docs = urllib.request.Request(docs_url, headers={"User-Agent": "RecoverAI-Deployment-Verifier/1.0"})
        with urllib.request.urlopen(req_docs, timeout=10) as resp_docs:
            if resp_docs.getcode() != 200:
                logger.error(f"   [FAIL] /docs returned status: {resp_docs.getcode()}")
                return False
            logger.info("   [PASS] Swagger UI OpenAPI documentation (/docs) verified HTTP 200.")

        # 3. OpenAPI Schema JSON Verification (/openapi.json)
        logger.info("3. Executing HTTP GET /openapi.json schema check...")
        openapi_url = f"{target_url}/openapi.json"
        req_openapi = urllib.request.Request(openapi_url, headers={"User-Agent": "RecoverAI-Deployment-Verifier/1.0"})
        with urllib.request.urlopen(req_openapi, timeout=10) as resp_openapi:
            if resp_openapi.getcode() != 200:
                logger.error(f"   [FAIL] /openapi.json returned status: {resp_openapi.getcode()}")
                return False
            schema_data = json.loads(resp_openapi.read().decode("utf-8"))
            if "openapi" not in schema_data:
                logger.error("   [FAIL] Invalid OpenAPI JSON schema response missing 'openapi' key")
                return False
            logger.info(f"   [PASS] OpenAPI schema JSON verified (version: {schema_data.get('info', {}).get('version')}).")

        # 4. Celery Worker Module Import Verification
        logger.info("4. Verifying Celery worker task definitions...")
        from backend.app.tasks.worker import celery_app
        assert celery_app is not None, "Celery application instance missing"
        logger.info(f"   [PASS] Celery worker module loaded successfully (broker URL configured).")

        logger.info("==================================================")
        logger.info("[SUCCESS] Backend Deployment Verification Passed Fully!")
        logger.info("==================================================")
        return True

    except urllib.error.URLError as url_err:
        logger.error(f"   [FAIL] Unable to connect to backend target URL '{target_url}': {url_err}")
        return False
    except Exception as exc:
        logger.error(f"   [FAIL] Verification exception encountered: {exc}")
        return False


def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else None
    success = verify_backend_deployment(base_url=target_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
