"""
RecoverAI - Step 22 Reconciliation Engine Test Suite

Tests for ReconciliationEngine polling external payment link status for UNKNOWN attempts,
verifying state machine transitions via StateTransitionService, attribution hook triggers,
multi-tenant isolation, mode separation, and zero duplicate attempt creations.
"""

import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.domain import Base, Transaction, RecoveryAttempt, RecoveryAttribution, Merchant
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.services.reconciliation_engine import ReconciliationEngine
from backend.app.services.result_processor import ResultProcessor
from backend.app.services.attribution_engine import AttributionEngine
from backend.app.workers.reconciliation_worker import run_reconciliation_cycle
from backend.app.integrations.razorpay_adapter import RazorpayAdapter


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite DB session fixture for async testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def register_attribution_hook():
    """Register Step 20 Attribution Engine hook in ResultProcessor prior to test execution."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    yield
    ResultProcessor.reset_attribution_hook()


async def create_test_merchant(session: AsyncSession, name: str = "Merchant Rec") -> Merchant:
    """Utility helper to create a test merchant record."""
    merchant = Merchant(
        id=str(uuid.uuid4()),
        name=name,
        email=f"rec_{uuid.uuid4().hex[:6]}@example.com",
        industry="FINTECH",
    )
    session.add(merchant)
    await session.commit()
    return merchant


async def create_test_transaction(
    session: AsyncSession,
    merchant_id: str,
    amount: Decimal = Decimal("1500.00"),
    status: str = TransactionStatus.EXECUTING.value,
    mode: str = "SIMULATION",
) -> Transaction:
    """Utility helper to create a test transaction."""
    tx = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=merchant_id,
        customer_id=f"cust_{uuid.uuid4().hex[:8]}",
        amount=amount,
        currency="INR",
        status=status,
        scenario_type="PAYMENT_FAILURE",
        recovery_cycle=1,
        mode=mode,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=15),
    )
    session.add(tx)
    await session.commit()
    return tx


async def create_test_attempt(
    session: AsyncSession,
    transaction: Transaction,
    execution_status: str = ExecutionStatus.UNKNOWN.value,
    link_id_suffix: str = "paid_123",
    age_minutes: int = 10,
) -> RecoveryAttempt:
    """Utility helper to create a RecoveryAttempt record."""
    link_id = f"plink_test_{link_id_suffix}"
    attempt = RecoveryAttempt(
        id=str(uuid.uuid4()),
        transaction_id=transaction.id,
        logical_operation_key=f"{transaction.merchant_id}:{transaction.id}:{transaction.recovery_cycle}:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": int(transaction.amount * 100)},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status=execution_status,
        external_resource_type=transaction.mode,
        external_resource_id=link_id,
        razorpay_payment_link_id=link_id,
        razorpay_reference_id=f"RAI-{str(transaction.id)[:12]}-1",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=age_minutes),
    )
    session.add(attempt)
    await session.commit()
    return attempt


@pytest.mark.asyncio
async def test_1_reconcile_paid_payment_link_success(db_session: AsyncSession):
    """Test reconciling a paid payment link transitions attempt to SUCCESS and transaction to RECOVERED with attribution."""
    merchant = await create_test_merchant(db_session, "Paid Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id, Decimal("2500.00"))
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="paid_abc")

    engine = ReconciliationEngine()
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    assert summary["total_scanned"] == 1
    assert summary["reconciled_success"] == 1
    assert summary["reconciled_failure"] == 0

    # Refresh records
    await db_session.refresh(attempt)
    await db_session.refresh(tx)

    assert attempt.execution_status == ExecutionStatus.SUCCESS.value
    assert tx.status == TransactionStatus.RECOVERED.value

    # Verify recovery cycle and logical_operation_key remained untouched
    assert tx.recovery_cycle == 1
    assert attempt.logical_operation_key == f"{merchant.id}:{tx.id}:1:PAYMENT_LINK"

    # Verify Step 20 Attribution record created
    stmt = select(RecoveryAttribution).where(RecoveryAttribution.transaction_id == tx.id)
    attr = (await db_session.execute(stmt)).scalar_one_or_none()
    assert attr is not None
    assert attr.recovery_attempt_id == attempt.id
    assert attr.recovered_amount == Decimal("2500.00")


@pytest.mark.asyncio
async def test_2_reconcile_expired_payment_link_failure(db_session: AsyncSession):
    """Test reconciling an expired payment link transitions attempt to FAILURE and transaction to EXPIRED."""
    merchant = await create_test_merchant(db_session, "Expired Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id, Decimal("1200.00"))
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="expired_xyz")

    engine = ReconciliationEngine()
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    assert summary["reconciled_failure"] == 1

    await db_session.refresh(attempt)
    await db_session.refresh(tx)

    assert attempt.execution_status == ExecutionStatus.FAILURE.value
    assert tx.status == TransactionStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_3_reconcile_cancelled_payment_link_failure(db_session: AsyncSession):
    """Test reconciling a cancelled payment link transitions attempt to FAILURE and transaction to FAILED."""
    merchant = await create_test_merchant(db_session, "Cancelled Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id, Decimal("1800.00"))
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="cancelled_999")

    engine = ReconciliationEngine()
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    assert summary["reconciled_failure"] == 1

    await db_session.refresh(attempt)
    await db_session.refresh(tx)

    assert attempt.execution_status == ExecutionStatus.FAILURE.value
    assert tx.status == TransactionStatus.FAILED.value


@pytest.mark.asyncio
async def test_4_reconcile_pending_created_link_unchanged(db_session: AsyncSession):
    """Test pending created payment link remains UNKNOWN and EXECUTING during reconciliation."""
    merchant = await create_test_merchant(db_session, "Pending Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id, Decimal("3000.00"))
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="created_pending")

    engine = ReconciliationEngine()
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    assert summary["pending"] == 1
    assert summary["reconciled_success"] == 0
    assert summary["reconciled_failure"] == 0

    await db_session.refresh(attempt)
    await db_session.refresh(tx)

    assert attempt.execution_status == ExecutionStatus.UNKNOWN.value
    assert tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_5_reconcile_network_error_resilience(db_session: AsyncSession):
    """Test exception resilience when external API call fails during reconciliation check."""
    merchant = await create_test_merchant(db_session, "Error Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id, Decimal("500.00"))
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="paid_err")

    mock_adapter = RazorpayAdapter()
    mock_adapter.fetch_payment_link = AsyncMock(side_effect=TimeoutError("Network timeout"))

    engine = ReconciliationEngine(razorpay_adapter=mock_adapter)
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    assert summary["errors"] == 1
    assert summary["reconciled_success"] == 0

    await db_session.refresh(attempt)
    await db_session.refresh(tx)

    assert attempt.execution_status == ExecutionStatus.UNKNOWN.value
    assert tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_6_zero_duplicate_attempt_creations(db_session: AsyncSession):
    """Test zero new RecoveryAttempt rows are created during reconciliation."""
    merchant = await create_test_merchant(db_session, "No Duplicate Merchant")
    tx = await create_test_transaction(db_session, merchant.id)
    await create_test_attempt(db_session, tx, link_id_suffix="paid_no_dup")

    stmt_count = select(func.count(RecoveryAttempt.id))
    initial_count = (await db_session.execute(stmt_count)).scalar()

    engine = ReconciliationEngine()
    await engine.reconcile_pending_attempts(db_session, min_age_seconds=60)

    final_count = (await db_session.execute(stmt_count)).scalar()
    assert final_count == initial_count


@pytest.mark.asyncio
async def test_7_multi_tenant_isolation_in_reconciliation(db_session: AsyncSession):
    """Test merchant_id filter enforces multi-tenant isolation during reconciliation cycles."""
    m1 = await create_test_merchant(db_session, "Merchant One")
    m2 = await create_test_merchant(db_session, "Merchant Two")

    tx1 = await create_test_transaction(db_session, m1.id)
    att1 = await create_test_attempt(db_session, tx1, link_id_suffix="paid_m1")

    tx2 = await create_test_transaction(db_session, m2.id)
    att2 = await create_test_attempt(db_session, tx2, link_id_suffix="paid_m2")

    engine = ReconciliationEngine()

    # Reconcile specifying ONLY Merchant One
    summary = await engine.reconcile_pending_attempts(db_session, min_age_seconds=60, merchant_id=m1.id)

    assert summary["reconciled_success"] == 1

    await db_session.refresh(att1)
    await db_session.refresh(att2)

    # Merchant One attempt updated to SUCCESS
    assert att1.execution_status == ExecutionStatus.SUCCESS.value
    # Merchant Two attempt remains UNKNOWN
    assert att2.execution_status == ExecutionStatus.UNKNOWN.value


@pytest.mark.asyncio
async def test_8_reconciliation_worker_task_integration(db_session: AsyncSession):
    """Test background worker task wrapper function run_reconciliation_cycle."""
    merchant = await create_test_merchant(db_session, "Worker Rec Merchant")
    tx = await create_test_transaction(db_session, merchant.id)
    attempt = await create_test_attempt(db_session, tx, link_id_suffix="paid_worker")

    with patch("backend.app.workers.reconciliation_worker.AsyncSessionLocal", return_value=db_session):
        # Override session closing on exit to preserve in-memory SQLite session
        db_session.close = AsyncMock()

        summary = await run_reconciliation_cycle(min_age_seconds=60)
        assert summary["reconciled_success"] == 1

    await db_session.refresh(attempt)
    assert attempt.execution_status == ExecutionStatus.SUCCESS.value
