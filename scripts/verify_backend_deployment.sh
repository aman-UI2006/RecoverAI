#!/usr/bin/env bash
# RecoverAI - Shell script wrapper for Step 51 Backend Deployment Verification
set -e

TARGET_URL="${1:-http://localhost:8000}"

echo "Starting RecoverAI Backend Deployment Verification (Step 51) against ${TARGET_URL}..."
python -m scripts.verify_backend_deployment "$TARGET_URL"
