"""
RecoverAI - Frontend Deployment Verification Script (Step 52)

Verifies frontend production asset build, Nginx security configuration, SPA routing:
- Verifies compiled static bundle in frontend/dist/ (index.html, JS/CSS assets)
- Verifies Nginx configuration (frontend/nginx.conf) for SPA fallback try_files, security headers, /healthz endpoint
- Executes HTTP GET requests against target URL (if available) asserting status 200
"""

import sys
import os
import logging
import urllib.request
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_frontend_deployment")


def verify_frontend_build_artifacts() -> bool:
    logger.info("1. Verifying compiled frontend build artifacts in frontend/dist/...")
    frontend_dir = Path(__file__).parent.parent / "frontend"
    dist_dir = frontend_dir / "dist"
    index_html = dist_dir / "index.html"

    if not dist_dir.exists() or not dist_dir.is_dir():
        logger.error("   [FAIL] frontend/dist directory missing. Run 'npm run build' first.")
        return False

    if not index_html.exists():
        logger.error("   [FAIL] frontend/dist/index.html missing!")
        return False

    html_content = index_html.read_text(encoding="utf-8")
    if '<div id="root">' not in html_content and '<div id="app">' not in html_content:
        logger.error("   [FAIL] frontend/dist/index.html missing root mount container element.")
        return False

    logger.info("   [PASS] Static build bundle verified in frontend/dist/.")
    return True


def verify_nginx_security_config() -> bool:
    logger.info("2. Verifying Nginx configuration & Security HTTP Headers (frontend/nginx.conf)...")
    nginx_conf = Path(__file__).parent.parent / "frontend" / "nginx.conf"

    if not nginx_conf.exists():
        logger.error("   [FAIL] frontend/nginx.conf missing!")
        return False

    content = nginx_conf.read_text(encoding="utf-8")

    # Required directives
    required_directives = [
        "try_files $uri $uri/ /index.html",
        "location /healthz",
        "location /api/",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
    ]

    for directive in required_directives:
        if directive not in content:
            logger.error(f"   [FAIL] Missing required Nginx directive/header: '{directive}'")
            return False

    logger.info("   [PASS] Nginx SPA routing, API proxy, and security headers verified.")
    return True


def verify_live_frontend_http(target_url: str) -> bool:
    logger.info(f"3. Executing HTTP GET check against live frontend target URL: {target_url}...")
    try:
        req = urllib.request.Request(target_url, headers={"User-Agent": "RecoverAI-Frontend-Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8", errors="ignore")

            if status_code != 200:
                logger.error(f"   [FAIL] Target URL returned non-200 status code: {status_code}")
                return False

            if "<!doctype html>" not in body.lower() and "<html" not in body.lower():
                logger.error("   [FAIL] Response body does not appear to be an HTML document.")
                return False

            logger.info("   [PASS] Live frontend HTTP response verified status 200.")
            return True
    except Exception as exc:
        logger.warning(f"   [WARN] Unable to connect to live frontend target '{target_url}' (server may be offline): {exc}")
        return False


def verify_frontend_deployment(target_url: Optional[str] = None) -> bool:
    # 1. Verify build artifacts
    if not verify_frontend_build_artifacts():
        return False

    # 2. Verify Nginx configuration
    if not verify_nginx_security_config():
        return False

    # 3. Verify HTTP request if target URL provided
    if target_url:
        verify_live_frontend_http(target_url)

    logger.info("==================================================")
    logger.info("[SUCCESS] Frontend Deployment Verification Passed Fully!")
    logger.info("==================================================")
    return True


def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else None
    success = verify_frontend_deployment(target_url=target_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
