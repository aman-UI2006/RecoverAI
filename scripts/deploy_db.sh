#!/usr/bin/env bash
# RecoverAI - Shell script wrapper for Step 50 Database Deployment
set -e

echo "Starting RecoverAI Database Deployment (Step 50)..."
python scripts/deploy_db.py
