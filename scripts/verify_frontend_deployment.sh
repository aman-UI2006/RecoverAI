#!/usr/bin/env bash
# RecoverAI - Shell script wrapper for Step 52 Frontend Deployment Verification
set -e

TARGET_URL="${1:-http://localhost:5173}"

echo "Starting RecoverAI Frontend Deployment Verification (Step 52)..."
python -m scripts.verify_frontend_deployment "$TARGET_URL"
