"""Targeted test suite for Step 17 — Action Executor."""

import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.models.domain import Transaction, Merchant, Customer, RecoveryAttempt, current_utc_time
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.schemas.executor import ActionExecutionRequest, ActionExecutionResponse
from backend.app.services.action_executor import ActionExecutor

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for ActionExecutor testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def setup_executor_fixtures(async_test_session: AsyncSession):
    """Fixture providing merchant, customer, and helper for creating transactions."""
    merchant_id = f"m_exec_{uuid4().hex[:8]}"
    customer_id = f"c_exec_{uuid4().hex[:8]}"

    merchant = Merchant(
        id=merchant_id,
        name="Test Executor Merchant",
        email="merchant@example.com",
        industry="ECOMMERCE",
        created_at=current_utc_time(),
    )
    customer = Customer(
        id=customer_id,
        merchant_id=merchant_id,
        email="exec_cust@example.com",
        created_at=current_utc_time(),
    )
    async_test_session.add_all([merchant, customer])
    await async_test_session.commit()

    async def _create_tx(status: str = TransactionStatus.APPROVED.value, mode: str = "REAL_TEST", recovery_cycle: int = 1) -> Transaction:
        tx_id = f"tx_exec_{uuid4().hex[:8]}"
        tx = Transaction(
            id=tx_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=50000,  # 500 INR in paise
            currency="INR",
            status=status,
            scenario_type="PAYMENT_FAILURE",
            mode=mode,
            recovery_cycle=recovery_cycle,
            created_at=current_utc_time(),
            updated_at=current_utc_time(),
        )
        async_test_session.add(tx)
        await async_test_session.commit()
        return tx

    return {
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "create_tx": _create_tx,
    }


@pytest.mark.asyncio
async def test_1_approved_action_execution_path(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """1. Test successful execution of an APPROVED transaction."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value, mode="REAL_TEST")

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
        action_payload={"expire_by_hours": 24},
    )

    res = await ActionExecutor.execute(async_test_session, req)

    assert isinstance(res, ActionExecutionResponse)
    assert res.transaction_id == tx.id
    assert res.merchant_id == merchant_id
    assert res.execution_status == ExecutionStatus.SUCCESS.value
    assert res.logical_operation_key == f"{merchant_id}:{tx.id}:1:PAYMENT_LINK"
    assert res.is_duplicate is False

    # Verify transaction state in DB updated to EXECUTING
    stmt = select(Transaction).where(Transaction.id == tx.id)
    updated_tx = (await async_test_session.execute(stmt)).scalar_one()
    assert updated_tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_2_rejection_of_unapproved_action(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """2. Test that executing a transaction not in APPROVED status raises ValueError."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    # Transaction in DIAGNOSED state
    tx = await create_tx(status=TransactionStatus.DIAGNOSED.value)

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )

    with pytest.raises(ValueError, match="action execution requires APPROVED status"):
        await ActionExecutor.execute(async_test_session, req)


@pytest.mark.asyncio
async def test_3_defensive_capability_gate_enforcement(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """3. Test defensive capability check rejection when action is unexecutable in mode."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value, mode="REAL_TEST")

    # In REAL_TEST, UNSUPPORTED_TEST_ACTION is not executable
    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="UNSUPPORTED_TEST_ACTION",
    )

    with pytest.raises(ValueError, match="Defensive capability check failed"):
        await ActionExecutor.execute(async_test_session, req)


@pytest.mark.asyncio
async def test_4_logical_operation_key_format(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """4. Contract Test: Verifies logical_operation_key format merchant_id:tx_id:cycle:action (no attempt_seq)."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value, recovery_cycle=2)

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )

    res = await ActionExecutor.execute(async_test_session, req)

    expected_key = f"{merchant_id}:{tx.id}:2:PAYMENT_LINK"
    assert res.logical_operation_key == expected_key
    assert "attempt_seq" not in res.logical_operation_key


@pytest.mark.asyncio
async def test_5_duplicate_logical_operation_protection(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """5. Test idempotency: second execution with identical key returns existing attempt marked is_duplicate=True."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value)

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )

    res1 = await ActionExecutor.execute(async_test_session, req)
    assert res1.is_duplicate is False

    # Second execution attempt
    res2 = await ActionExecutor.execute(async_test_session, req)
    assert res2.is_duplicate is True
    assert res2.execution_id == res1.execution_id
    assert res2.logical_operation_key == res1.logical_operation_key


@pytest.mark.asyncio
async def test_6_database_uniqueness_enforcement(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """6. Test DB unique constraint on RecoveryAttempt.logical_operation_key."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value)
    key = f"{merchant_id}:{tx.id}:1:PAYMENT_LINK"

    attempt1 = RecoveryAttempt(
        id=f"att_1_{uuid4().hex[:8]}",
        transaction_id=tx.id,
        logical_operation_key=key,
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="1.0",
        execution_status="SUCCESS",
        external_resource_type="REAL_TEST",
        created_at=current_utc_time(),
    )
    async_test_session.add(attempt1)
    await async_test_session.commit()

    # Attempting to insert duplicate manually triggers DB IntegrityError
    attempt2 = RecoveryAttempt(
        id=f"att_2_{uuid4().hex[:8]}",
        transaction_id=tx.id,
        logical_operation_key=key,
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="1.0",
        execution_status="PENDING",
        external_resource_type="REAL_TEST",
        created_at=current_utc_time(),
    )
    async_test_session.add(attempt2)
    with pytest.raises(Exception):
        await async_test_session.commit()

    await async_test_session.rollback()


@pytest.mark.asyncio
async def test_7_unknown_execution_result_handling(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """7. Test that adapter network timeout/exception sets attempt execution_status = UNKNOWN."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value, mode="REAL_TEST")

    class FailingAdapterDelegate:
        async def execute_action(self, transaction, request):
            raise TimeoutError("External network timeout contacting Razorpay API")

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )

    res = await ActionExecutor.execute(
        session=async_test_session,
        request=req,
        adapter_delegate=FailingAdapterDelegate(),
    )

    assert res.execution_status == ExecutionStatus.UNKNOWN.value

    # Verify transaction status remains EXECUTING (not RECOVERED or FAILED)
    stmt = select(Transaction).where(Transaction.id == tx.id)
    updated_tx = (await async_test_session.execute(stmt)).scalar_one()
    assert updated_tx.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_8_merchant_isolation(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """8. Test merchant isolation: transaction belonging to merchant A rejected for merchant B."""
    create_tx = setup_executor_fixtures["create_tx"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value)

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id="m_malicious_attacker_999",
        action_type="PAYMENT_LINK",
    )

    with pytest.raises(ValueError, match="Merchant ID mismatch"):
        await ActionExecutor.execute(async_test_session, req)


@pytest.mark.asyncio
async def test_9_real_test_vs_simulation_separation(async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """9. Test clear distinction between REAL_TEST and SIMULATION execution modes."""
    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx_real = await create_tx(status=TransactionStatus.APPROVED.value, mode="REAL_TEST")
    tx_sim = await create_tx(status=TransactionStatus.APPROVED.value, mode="SIMULATION")

    req_real = ActionExecutionRequest(
        transaction_id=tx_real.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )
    res_real = await ActionExecutor.execute(async_test_session, req_real)
    assert res_real.external_resource_type == "REAL_TEST"

    req_sim = ActionExecutionRequest(
        transaction_id=tx_sim.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )
    res_sim = await ActionExecutor.execute(async_test_session, req_sim)
    assert res_sim.external_resource_type == "SIMULATION"


@pytest.mark.asyncio
async def test_10_air_gap_security(monkeypatch, async_test_session: AsyncSession, setup_executor_fixtures: dict):
    """10. Air-gap Safety Test: Verifies ActionExecutor makes ZERO external HTTP network calls."""
    def block_external_net(*args, **kwargs):
        raise RuntimeError("AIR-GAP VIOLATION: External network call detected during Step 17 ActionExecutor operation!")

    monkeypatch.setattr("httpx.AsyncClient.send", block_external_net, raising=False)
    monkeypatch.setattr("urllib.request.urlopen", block_external_net, raising=False)

    create_tx = setup_executor_fixtures["create_tx"]
    merchant_id = setup_executor_fixtures["merchant_id"]

    tx = await create_tx(status=TransactionStatus.APPROVED.value)

    req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant_id,
        action_type="PAYMENT_LINK",
    )

    res = await ActionExecutor.execute(async_test_session, req)
    assert res.execution_status == ExecutionStatus.SUCCESS.value
