"""
RecoverAI - Database Deployment & Seeding Script (Step 50)

Performs PostgreSQL database setup by applying Alembic migrations to current head
and seeding default merchant account and policy v1.0 parameters.
"""

import sys
import logging
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy_db")


def run_migrations():
    """Applies all Alembic migrations up to head."""
    logger.info("Running Alembic database migrations to head...")
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        # Ensure database URL matches current settings (sync driver)
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("[SUCCESS] Alembic migrations applied successfully.")
    except Exception as e:
        logger.error(f"[ERROR] Alembic migration failed: {e}")
        raise e


def seed_initial_data(db_url: Optional[str] = None):
    """Inserts initial seed data for default merchant account and policy v1.0."""
    target_url = db_url or settings.DATABASE_URL
    sync_url = target_url.replace("postgresql+asyncpg://", "postgresql://")

    logger.info(f"Connecting to database to verify/insert initial seed data...")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Seed Default Merchant if not exists
        merchant_check = session.execute(
            text("SELECT id FROM merchants WHERE id = 'm_alpha_123'")
        ).fetchone()

        if not merchant_check:
            logger.info("Seeding default merchant 'm_alpha_123'...")
            session.execute(
                text("""
                    INSERT INTO merchants (id, name, email, industry, created_at)
                    VALUES ('m_alpha_123', 'Alpha E-Commerce Merchant', 'merchant@example.com', 'E-commerce', CURRENT_TIMESTAMP)
                """)
            )
            logger.info("[SUCCESS] Default merchant seeded.")
        else:
            logger.info("Default merchant 'm_alpha_123' already present.")

        # 2. Seed Default Policy v1.0 if not exists
        policy_check = session.execute(
            text("SELECT id FROM policies WHERE policy_version = 'v1.0' AND merchant_id IS NULL")
        ).fetchone()

        if not policy_check:
            logger.info("Seeding default policy parameters 'v1.0'...")
            session.execute(
                text("""
                    INSERT INTO policies (id, merchant_id, policy_version, max_recovery_attempts, max_auto_action_amount, min_recovery_probability, cooldown_hours, is_active, created_at)
                    VALUES ('pol_default_v1', NULL, 'v1.0', 3, 50000.00, 0.15, 24, true, CURRENT_TIMESTAMP)
                """)
            )
            logger.info("[SUCCESS] Default policy v1.0 seeded.")
        else:
            logger.info("Default policy 'v1.0' already present.")

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[ERROR] Database seeding failed: {e}")
        raise e
    finally:
        session.close()


def main():
    try:
        run_migrations()
        seed_initial_data()
        logger.info("==================================================")
        logger.info("[COMPLETE] Step 50 Database Deployment Finished Successfully!")
        logger.info("==================================================")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Database deployment aborted due to failure: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
