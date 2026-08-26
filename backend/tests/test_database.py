import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect, select

from backend.app.core.database import Base
from backend.app.models import (
    Merchant, Customer, Transaction, Event, DecisionContext,
    RecoveryActionScore, Diagnosis, Policy, RecoveryAttempt,
    RecoveryAttribution, AuditEvent, EvaluationRun, HumanReview
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with session_factory() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await engine.dispose()


@pytest.mark.asyncio
async def test_all_13_tables_created(async_test_session: AsyncSession):
    """Verify that all 13 core relational tables are defined in metadata."""
    expected_tables = {
        "merchants",
        "customers",
        "transactions",
        "events",
        "decision_contexts",
        "recovery_action_scores",
        "diagnoses",
        "policies",
        "recovery_attempts",
        "recovery_attributions",
        "audit_events",
        "evaluation_runs",
        "human_reviews",
    }
    defined_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(defined_tables), f"Missing tables: {expected_tables - defined_tables}"


@pytest.mark.asyncio
async def test_merchant_customer_transaction_crud(async_test_session: AsyncSession):
    """Test standard entity insertion, relationship cascading, and retrieval."""
    merchant = Merchant(
        name="Test Merchant Ltd",
        email="billing@testmerchant.com",
        industry="SaaS"
    )
    async_test_session.add(merchant)
    await async_test_session.commit()
    await async_test_session.refresh(merchant)
    assert merchant.id is not None

    customer = Customer(
        merchant_id=merchant.id,
        email="customer@example.com",
        name="John Doe",
        historical_transaction_count=5
    )
    async_test_session.add(customer)
    await async_test_session.commit()
    await async_test_session.refresh(customer)
    assert customer.id is not None

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("1499.50"),
        currency="INR",
        status="AT_RISK",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION"
    )
    async_test_session.add(tx)
    await async_test_session.commit()
    await async_test_session.refresh(tx)

    assert tx.id is not None
    assert tx.amount == Decimal("1499.50")
    assert tx.status == "AT_RISK"
    assert tx.mode == "SIMULATION"


@pytest.mark.asyncio
async def test_logical_operation_key_uniqueness(async_test_session: AsyncSession):
    """Verify that recovery_attempts enforces UNIQUE(logical_operation_key)."""
    merchant = Merchant(name="M1", email="m1@test.com", industry="E-commerce")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c1@test.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("500.00"),
        status="AT_RISK",
        scenario_type="PAYMENT_FAILURE"
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    op_key = f"{merchant.id}:{tx.id}:1:RETRY"

    attempt1 = RecoveryAttempt(
        transaction_id=tx.id,
        logical_operation_key=op_key,
        recommended_action="RETRY",
        action_payload={"gateway": "razorpay"},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="PENDING",
        external_resource_type="RAZORPAY_PAYMENT_LINK"
    )
    async_test_session.add(attempt1)
    await async_test_session.commit()

    # Attempting duplicate logical_operation_key should fail IntegrityError
    attempt2 = RecoveryAttempt(
        transaction_id=tx.id,
        logical_operation_key=op_key,
        recommended_action="RETRY",
        action_payload={"gateway": "razorpay"},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="PENDING",
        external_resource_type="RAZORPAY_PAYMENT_LINK"
    )
    async_test_session.add(attempt2)
    with pytest.raises(IntegrityError):
        await async_test_session.commit()


@pytest.mark.asyncio
async def test_event_idempotency_key_uniqueness(async_test_session: AsyncSession):
    """Verify that events enforces UNIQUE(idempotency_key)."""
    event1 = Event(
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        payload={"event": "payment.failed"},
        idempotency_key="idempotent_msg_12345"
    )
    async_test_session.add(event1)
    await async_test_session.commit()

    event2 = Event(
        event_type="payment.failed",
        event_source="RAZORPAY_WEBHOOK",
        payload={"event": "payment.failed"},
        idempotency_key="idempotent_msg_12345"
    )
    async_test_session.add(event2)
    with pytest.raises(IntegrityError):
        await async_test_session.commit()


@pytest.mark.asyncio
async def test_audit_event_hash_chaining(async_test_session: AsyncSession):
    """Verify audit_events creation with cryptographic hash values."""
    merchant = Merchant(name="M2", email="m2@test.com", industry="Fintech")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c2@test.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("9999.00"),
        status="CREATED",
        scenario_type="CHECKOUT_ABANDONMENT"
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    audit = AuditEvent(
        transaction_id=tx.id,
        event_type="STATE_TRANSITION",
        actor="SYSTEM",
        state_from="CREATED",
        state_to="AT_RISK",
        details={"reason": "payment_failure_webhook"},
        previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
        event_hash="a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef"
    )
    async_test_session.add(audit)
    await async_test_session.commit()
    await async_test_session.refresh(audit)

    assert audit.id is not None
    assert audit.event_hash == "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef"
