"""Unit and Integration Tests for Step 7: Authoritative State Transition Service."""

from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, AuditEvent
from backend.app.schemas.state_machine import (
    TransactionStatus,
    InvalidStateTransitionException,
)
from backend.app.services.state_transition_service import StateTransitionService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for state machine testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_1_valid_state_transitions(async_test_session: AsyncSession):
    """1. Test full sequence of valid transaction lifecycle transitions."""
    merchant = Merchant(name="Merchant ST1", email="st1@merchant.com", industry="SaaS")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c1@st1.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("1500.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    # Step 1: CREATED -> AT_RISK
    tx, audit1 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.AT_RISK.value,
        actor="REVENUE_RISK_ENGINE",
        reason="Detected payment failure webhook",
    )
    assert tx.status == TransactionStatus.AT_RISK.value
    assert audit1.state_from == TransactionStatus.CREATED.value
    assert audit1.state_to == TransactionStatus.AT_RISK.value

    # Step 2: AT_RISK -> DIAGNOSED
    tx, audit2 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.DIAGNOSED.value,
        actor="DIAGNOSIS_ENGINE",
        reason="Classified decline root cause",
    )
    assert tx.status == TransactionStatus.DIAGNOSED.value

    # Step 3: DIAGNOSED -> INTERVENTION_SELECTED
    tx, audit3 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.INTERVENTION_SELECTED.value,
        actor="RECOMMENDER",
        reason="Selected PAYMENT_LINK action",
    )
    assert tx.status == TransactionStatus.INTERVENTION_SELECTED.value

    # Step 4: INTERVENTION_SELECTED -> POLICY_CHECK
    tx, audit4 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.POLICY_CHECK.value,
        actor="POLICY_ENGINE",
    )
    assert tx.status == TransactionStatus.POLICY_CHECK.value

    # Step 5: POLICY_CHECK -> APPROVED
    tx, audit5 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.APPROVED.value,
        actor="POLICY_ENGINE",
        reason="Policy checks passed",
    )
    assert tx.status == TransactionStatus.APPROVED.value

    # Step 6: APPROVED -> EXECUTING
    tx, audit6 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.EXECUTING.value,
        actor="ACTION_EXECUTOR",
    )
    assert tx.status == TransactionStatus.EXECUTING.value

    # Step 7: EXECUTING -> RECOVERED
    tx, audit7 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.RECOVERED.value,
        actor="ATTRIBUTION_ENGINE",
        reason="Payment link paid webhook verified",
    )
    assert tx.status == TransactionStatus.RECOVERED.value


@pytest.mark.asyncio
async def test_2_invalid_state_transition_rejected(async_test_session: AsyncSession):
    """2. Test illegal transition is rejected and leaves database unchanged."""
    merchant = Merchant(name="Merchant ST2", email="st2@merchant.com", industry="E-commerce")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c2@st2.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("2500.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="CHECKOUT_ABANDONMENT",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    # Attempt illegal transition CREATED -> RECOVERED
    with pytest.raises(InvalidStateTransitionException) as exc_info:
        await StateTransitionService.transition(
            session=async_test_session,
            transaction_id=tx.id,
            target_state=TransactionStatus.RECOVERED.value,
            actor="SYSTEM",
        )

    assert exc_info.value.state_from == TransactionStatus.CREATED.value
    assert exc_info.value.state_to == TransactionStatus.RECOVERED.value

    # Verify transaction in database remains CREATED
    res = await async_test_session.execute(select(Transaction).where(Transaction.id == tx.id))
    db_tx = res.scalar_one()
    assert db_tx.status == TransactionStatus.CREATED.value


@pytest.mark.asyncio
async def test_3_terminal_state_transitions_rejected(async_test_session: AsyncSession):
    """3. Test transition out of terminal state (STOPPED) is rejected."""
    merchant = Merchant(name="Merchant ST3", email="st3@merchant.com", industry="Retail")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c3@st3.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("5000.00"),
        status=TransactionStatus.STOPPED.value,
        scenario_type="SUBSCRIPTION_FAILURE",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    with pytest.raises(InvalidStateTransitionException):
        await StateTransitionService.transition(
            session=async_test_session,
            transaction_id=tx.id,
            target_state=TransactionStatus.APPROVED.value,
            actor="SYSTEM",
        )


@pytest.mark.asyncio
async def test_4_audit_event_hash_chaining(async_test_session: AsyncSession):
    """4. Test SHA-256 tamper-evident audit event hash chaining across multiple transitions."""
    merchant = Merchant(name="Merchant ST4", email="st4@merchant.com", industry="Services")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="c4@st4.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("10000.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="OVERDUE_RECEIVABLE",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    # Transition 1: CREATED -> AT_RISK
    tx, audit1 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.AT_RISK.value,
        actor="SYSTEM",
        reason="Initial risk assessment",
    )
    assert audit1.previous_hash == "0" * 64
    assert len(audit1.event_hash) == 64

    # Transition 2: AT_RISK -> DIAGNOSED
    tx, audit2 = await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.DIAGNOSED.value,
        actor="DIAGNOSIS_ENGINE",
    )
    assert audit2.previous_hash == audit1.event_hash
    assert len(audit2.event_hash) == 64
    assert audit2.event_hash != audit1.event_hash


@pytest.mark.asyncio
async def test_5_nonexistent_transaction_raises_error(async_test_session: AsyncSession):
    """5. Test state transition on non-existent transaction raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        await StateTransitionService.transition(
            session=async_test_session,
            transaction_id="non_existent_uuid_9999",
            target_state=TransactionStatus.AT_RISK.value,
        )
    assert "not found" in str(exc_info.value)
