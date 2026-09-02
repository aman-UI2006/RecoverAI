"""
RecoverAI - Step 50 Database Deployment Unit & Integration Test Suite

Tests the deployment and verification routines for Step 50:
- Database connectivity & Alembic migration head tracking
- Default merchant 'm_alpha_123' and policy 'v1.0' initial data seeding
- Idempotency of database deployment scripts
- Full deployment status assertion via verify_database_deployment
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.models.domain import Base
from scripts.deploy_db import seed_initial_data
from scripts.verify_db_deployment import verify_database_deployment, EXPECTED_TABLES


@pytest.fixture
def sqlite_test_db(tmp_path):
    """Creates a temporary SQLite database with full schema for deployment testing."""
    db_file = tmp_path / "test_deploy.db"
    sync_url = f"sqlite:///{db_file}"
    engine = create_engine(sync_url)
    
    # Create all tables from Base metadata
    Base.metadata.create_all(engine)

    # Create alembic_version table mock for SQLite unit testing
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('002_add_ltv_generated_message')"))
        conn.commit()

    return sync_url, engine


def test_seed_initial_data_creates_default_merchant_and_policy(sqlite_test_db):
    """Test 1: seed_initial_data creates default merchant 'm_alpha_123' and policy 'v1.0'."""
    sync_url, engine = sqlite_test_db

    # Execute seed_initial_data
    seed_initial_data(db_url=sync_url)

    with engine.connect() as conn:
        merchant = conn.execute(text("SELECT id, name, email FROM merchants WHERE id = 'm_alpha_123'")).fetchone()
        assert merchant is not None
        assert merchant[0] == 'm_alpha_123'
        assert merchant[1] == 'Alpha E-Commerce Merchant'

        policy = conn.execute(text("SELECT id, policy_version, max_recovery_attempts FROM policies WHERE policy_version = 'v1.0'")).fetchone()
        assert policy is not None
        assert policy[1] == 'v1.0'
        assert policy[2] == 3


def test_seed_initial_data_idempotency(sqlite_test_db):
    """Test 2: Executing seed_initial_data multiple times is idempotent and does not create duplicates."""
    sync_url, engine = sqlite_test_db

    # Run seeding twice
    seed_initial_data(db_url=sync_url)
    seed_initial_data(db_url=sync_url)

    with engine.connect() as conn:
        merchant_count = conn.execute(text("SELECT COUNT(*) FROM merchants WHERE id = 'm_alpha_123'")).scalar()
        assert merchant_count == 1

        policy_count = conn.execute(text("SELECT COUNT(*) FROM policies WHERE policy_version = 'v1.0' AND merchant_id IS NULL")).scalar()
        assert policy_count == 1


def test_verify_database_deployment_returns_true(sqlite_test_db):
    """Test 3: verify_database_deployment returns True when target DB meets all criteria."""
    sync_url, _ = sqlite_test_db

    # Seed data first
    seed_initial_data(db_url=sync_url)

    # Run deployment verification
    is_valid = verify_database_deployment(db_url=sync_url)
    assert is_valid is True
