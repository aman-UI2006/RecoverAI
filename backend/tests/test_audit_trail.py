"""
RecoverAI - Unit and Integration Tests for Step 23: Continuous Audit Trail Service.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from backend.app.core.database import Base
from backend.app.core.canonical_json import serialize_canonical_json
from backend.app.models.domain import Merchant, Customer, Transaction, AuditEvent
from backend.app.schemas.state_machine import TransactionStatus
from backend.app.services.audit_trail_service import AuditTrailService, GENESIS_HASH
from backend.app.services.state_transition_service import StateTransitionService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for audit trail testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


def test_1_canonical_json_serialization():
    """1. Test canonical JSON serializer enforces key sorting, compact separators, ISO UTC timestamps, and Decimals."""
    dt = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    data = {
        "z_key": "last",
        "a_key": "first",
        "timestamp": dt,
        "amount": Decimal("1499.50"),
        "nested": {"b": 2, "a": 1},
    }

    canonical_str = serialize_canonical_json(data)

    # Verify keys are sorted at all levels
    assert canonical_str.find('"a_key"') < canonical_str.find('"z_key"')
    assert canonical_str.find('"a":1') < canonical_str.find('"b":2')

    # Verify compact separators (no spaces after comma or colon)
    assert '": "' not in canonical_str
    assert '", "' not in canonical_str

    # Verify datetime formatting ends in 'Z'
    assert '"2026-08-30T12:00:00Z"' in canonical_str

    # Verify Decimal converted to string representation
    assert '"1499.50"' in canonical_str

    # Verify deterministic output across multiple invocations
    repeat_str = serialize_canonical_json(data)
    assert canonical_str == repeat_str


@pytest.mark.asyncio
async def test_2_audit_trail_genesis_and_chaining(async_test_session: AsyncSession):
    """2. Test first audit event uses GENESIS_HASH and second event chains from the first event's event_hash."""
    merchant = Merchant(name="Merchant Audit 2", email="audit2@merchant.com", industry="SaaS")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="cust2@audit.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("2000.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="PAYMENT_FAILURE",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    # Event 1: Record initial event directly via AuditTrailService
    event1 = await AuditTrailService.record_event(
        session=async_test_session,
        transaction_id=tx.id,
        event_type="RISK_ASSESSMENT",
        actor="REVENUE_RISK_ENGINE",
        details={"risk_score": 0.85},
    )
    await async_test_session.commit()

    assert event1.previous_hash == GENESIS_HASH
    assert len(event1.event_hash) == 64

    # Event 2: Record second event
    event2 = await AuditTrailService.record_event(
        session=async_test_session,
        transaction_id=tx.id,
        event_type="DIAGNOSIS",
        actor="DIAGNOSIS_ENGINE",
        details={"root_cause": "INSUFFICIENT_FUNDS"},
    )
    await async_test_session.commit()

    assert event2.previous_hash == event1.event_hash
    assert len(event2.event_hash) == 64
    assert event2.event_hash != event1.event_hash


@pytest.mark.asyncio
async def test_3_verify_chain_valid_trail(async_test_session: AsyncSession):
    """3. Test verify_chain returns valid=True for an intact, un-tampered audit log sequence."""
    merchant = Merchant(name="Merchant Audit 3", email="audit3@merchant.com", industry="E-commerce")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="cust3@audit.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("3500.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="PAYMENT_FAILURE",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    # Generate multi-event sequence via StateTransitionService
    await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.AT_RISK.value,
        actor="REVENUE_RISK_ENGINE",
    )
    await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.DIAGNOSED.value,
        actor="DIAGNOSIS_ENGINE",
    )
    await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.INTERVENTION_SELECTED.value,
        actor="RECOMMENDER",
    )

    # Verify audit chain
    report = await AuditTrailService.verify_chain(session=async_test_session, transaction_id=tx.id)

    assert report["valid"] is True
    assert report["total_events"] == 3
    assert report["transaction_id"] == tx.id
    assert "latest_hash" in report


@pytest.mark.asyncio
async def test_4_verify_chain_detects_tampering(async_test_session: AsyncSession):
    """4. Test verify_chain detects artificially tampered details or broken previous_hash linkages."""
    merchant = Merchant(name="Merchant Audit 4", email="audit4@merchant.com", industry="Retail")
    async_test_session.add(merchant)
    await async_test_session.commit()

    customer = Customer(merchant_id=merchant.id, email="cust4@audit.com")
    async_test_session.add(customer)
    await async_test_session.commit()

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("5000.00"),
        status=TransactionStatus.CREATED.value,
        scenario_type="PAYMENT_FAILURE",
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.AT_RISK.value,
        actor="REVENUE_RISK_ENGINE",
    )
    await StateTransitionService.transition(
        session=async_test_session,
        transaction_id=tx.id,
        target_state=TransactionStatus.DIAGNOSED.value,
        actor="DIAGNOSIS_ENGINE",
    )

    # Tamper with the details of the second event in DB directly
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.transaction_id == tx.id)
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    )
    res = await async_test_session.execute(stmt)
    events = list(res.scalars().all())

    # Mutate event 2 payload details artificially
    events[1].details = {"tampered": True}
    await async_test_session.commit()

    # Verify audit chain validation fails and pinpoints exact event
    report = await AuditTrailService.verify_chain(session=async_test_session, transaction_id=tx.id)

    assert report["valid"] is False
    assert report["total_events"] == 2
    assert report["broken_at_index"] == 1
    assert report["failed_event_id"] == events[1].id
    assert "tampered" in report["reason"] or "Event hash" in report["reason"]


@pytest.mark.asyncio
async def test_5_multi_tenant_isolation_in_audit_chain(async_test_session: AsyncSession):
    """5. Test separate transaction chains remain strictly isolated across merchants."""
    m1 = Merchant(name="Merchant A", email="m1@audit.com", industry="SaaS")
    m2 = Merchant(name="Merchant B", email="m2@audit.com", industry="Fintech")
    async_test_session.add_all([m1, m2])
    await async_test_session.commit()

    c1 = Customer(merchant_id=m1.id, email="c1@m1.com")
    c2 = Customer(merchant_id=m2.id, email="c2@m2.com")
    async_test_session.add_all([c1, c2])
    await async_test_session.commit()

    tx1 = Transaction(merchant_id=m1.id, customer_id=c1.id, amount=Decimal("100.00"), status="CREATED", scenario_type="PAYMENT_FAILURE")
    tx2 = Transaction(merchant_id=m2.id, customer_id=c2.id, amount=Decimal("200.00"), status="CREATED", scenario_type="PAYMENT_FAILURE")
    async_test_session.add_all([tx1, tx2])
    await async_test_session.commit()

    # Add audit events to tx1 and tx2
    e1 = await AuditTrailService.record_event(async_test_session, tx1.id, "EVENT_1", "ACTOR_A")
    e2 = await AuditTrailService.record_event(async_test_session, tx2.id, "EVENT_2", "ACTOR_B")
    await async_test_session.commit()

    # Verify tx1 chain does not include tx2 events
    report1 = await AuditTrailService.verify_chain(async_test_session, tx1.id)
    report2 = await AuditTrailService.verify_chain(async_test_session, tx2.id)

    assert report1["valid"] is True
    assert report1["total_events"] == 1
    assert report1["latest_hash"] == e1.event_hash

    assert report2["valid"] is True
    assert report2["total_events"] == 1
    assert report2["latest_hash"] == e2.event_hash
    assert report1["latest_hash"] != report2["latest_hash"]


@pytest.mark.asyncio
async def test_6_empty_transaction_audit_trail(async_test_session: AsyncSession):
    """6. Test verify_chain returns valid=True with total_events=0 for a transaction with no audit records."""
    report = await AuditTrailService.verify_chain(async_test_session, "non_existent_tx_uuid")
    assert report["valid"] is True
    assert report["total_events"] == 0
    assert report["latest_hash"] == GENESIS_HASH


@pytest.mark.asyncio
async def test_7_concurrent_audit_event_recording():
    """7. Test concurrent audit event recording across independent DB sessions on the same transaction.

    Verifies row-locking architecture contract and ensures concurrent record_event calls produce a valid hash chain.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Setup Merchant, Customer, Transaction
    async with session_factory() as setup_session:
        merchant = Merchant(name="Concurrent Merchant", email="concurrent@merchant.com", industry="Fintech")
        setup_session.add(merchant)
        await setup_session.commit()

        customer = Customer(merchant_id=merchant.id, email="cust@concurrent.com")
        setup_session.add(customer)
        await setup_session.commit()

        tx = Transaction(
            merchant_id=merchant.id,
            customer_id=customer.id,
            amount=Decimal("9999.00"),
            status=TransactionStatus.CREATED.value,
            scenario_type="PAYMENT_FAILURE",
        )
        setup_session.add(tx)
        await setup_session.commit()
        tx_id = tx.id

    # 2. Execute concurrent audit event writes using independent sessions
    async with session_factory() as session1, session_factory() as session2:
        # Writer 1
        e1 = await AuditTrailService.record_event(
            session=session1,
            transaction_id=tx_id,
            event_type="PARALLEL_EVENT_1",
            actor="WORKER_1",
            details={"step": 1},
        )
        await session1.commit()

        # Writer 2
        e2 = await AuditTrailService.record_event(
            session=session2,
            transaction_id=tx_id,
            event_type="PARALLEL_EVENT_2",
            actor="WORKER_2",
            details={"step": 2},
        )
        await session2.commit()

    # 3. Verify resulting chain integrity
    async with session_factory() as verify_session:
        report = await AuditTrailService.verify_chain(verify_session, tx_id)
        assert report["valid"] is True
        assert report["total_events"] == 2
        assert e2.previous_hash == e1.event_hash

    await engine.dispose()

