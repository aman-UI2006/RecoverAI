"""
RecoverAI - Database Deployment Verification Script (Step 50)

Verifies database connectivity, Alembic migration status, table creation across
all 13 core tables, schema column presence (including ltv_score and generated_message_text),
and existence of default seed records (merchant m_alpha_123, policy v1.0).
"""

import sys
import logging
from typing import Optional
from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_db_deployment")

EXPECTED_TABLES = {
    "merchants", "customers", "transactions", "events",
    "decision_contexts", "recovery_action_scores", "diagnoses",
    "policies", "recovery_attempts", "recovery_attributions",
    "audit_events", "evaluation_runs", "human_reviews"
}


def verify_database_deployment(db_url: Optional[str] = None) -> bool:
    target_url = db_url or settings.DATABASE_URL
    sync_url = target_url.replace("postgresql+asyncpg://", "postgresql://")

    logger.info(f"Verifying target database deployment at: {sync_url.split('@')[-1] if '@' in sync_url else sync_url}")
    engine = create_engine(sync_url)
    inspector = inspect(engine)

    with engine.connect() as conn:
        # 1. Verify Database Connection
        logger.info("1. Verifying database connection...")
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1, "Database connection check failed"
        logger.info("   [PASS] Connection successful.")

        # 2. Verify Relational Tables
        logger.info("2. Verifying schema tables...")
        actual_tables = set(inspector.get_table_names())

        missing_tables = EXPECTED_TABLES - actual_tables
        if missing_tables:
            logger.error(f"   [FAIL] Missing required tables: {missing_tables}")
            return False
        logger.info(f"   [PASS] All {len(EXPECTED_TABLES)} core relational tables present.")

        # 3. Verify Alembic Migration Head
        logger.info("3. Verifying Alembic migration status...")
        if "alembic_version" not in actual_tables:
            logger.error("   [FAIL] alembic_version table missing!")
            return False

        version_res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        if not version_res:
            logger.error("   [FAIL] No version record found in alembic_version!")
            return False

        current_ver = version_res[0]
        logger.info(f"   [INFO] Current Alembic version: {current_ver}")
        if current_ver != "002_add_ltv_generated_message":
            logger.error(f"   [FAIL] Alembic version mismatch! Expected '002_add_ltv_generated_message', got '{current_ver}'")
            return False
        logger.info("   [PASS] Alembic migration head verified.")

        # 4. Verify Column Schema Additions
        logger.info("4. Verifying schema column additions...")
        customer_cols = {col["name"] for col in inspector.get_columns("customers")}
        if "ltv_score" not in customer_cols:
            logger.error("   [FAIL] customers.ltv_score column missing!")
            return False

        attempt_cols = {col["name"] for col in inspector.get_columns("recovery_attempts")}
        if "generated_message_text" not in attempt_cols:
            logger.error("   [FAIL] recovery_attempts.generated_message_text column missing!")
            return False
        logger.info("   [PASS] customers.ltv_score and recovery_attempts.generated_message_text columns verified.")

        # 5. Verify Default Seed Records
        logger.info("5. Verifying default seed records...")
        merchant = conn.execute(text("SELECT id, name FROM merchants WHERE id = 'm_alpha_123'")).fetchone()
        if not merchant:
            logger.error("   [FAIL] Default merchant 'm_alpha_123' not found in database!")
            return False
        logger.info(f"   [PASS] Default merchant verified: {merchant[1]} ({merchant[0]}).")

        policy = conn.execute(text("SELECT id, policy_version, is_active FROM policies WHERE policy_version = 'v1.0'")).fetchone()
        if not policy:
            logger.error("   [FAIL] Default policy 'v1.0' not found in database!")
            return False
        logger.info(f"   [PASS] Default policy verified: version={policy[1]}, active={policy[2]}.")

    logger.info("==================================================")
    logger.info("[SUCCESS] Database Deployment Verification Passed Fully!")
    logger.info("==================================================")
    return True


def main():
    try:
        success = verify_database_deployment()
        sys.exit(0 if success else 1)
    except Exception as exc:
        logger.error(f"Verification exception: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
