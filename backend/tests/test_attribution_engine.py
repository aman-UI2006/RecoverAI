"""
RecoverAI - Step 20 Attribution Engine Tests

Comprehensive unit test suite validating attribution classification logic,
direct reference matching, window match evaluations, natural recovery,
unattributed outcomes, multi-tenant isolation, idempotency, and ResultProcessor integration.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool


from backend.app.models.domain import Base, Transaction, RecoveryAttempt, RecoveryAttribution
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.schemas.attribution import (
    AttributionStatus,
    AttributionMethod,
    AttributionRequest,
)
from backend.app.services.attribution_engine import AttributionEngine
from backend.app.services.result_processor import ResultProcessor
from backend.app.services.state_transition_service import StateTransitionService


@pytest_asyncio.fixture
async def async_session():
    """Create an in-memory SQLite database session for isolated testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def ensure_attribution_hook_registered():
    """Ensure AttributionEngine hook is registered with ResultProcessor for tests."""
    ResultProcessor.register_attribution_hook(AttributionEngine.result_processor_hook_handler)
    yield
    ResultProcessor.reset_attribution_hook()


from backend.app.models.domain import Base, Merchant, Customer, Transaction, RecoveryAttempt, RecoveryAttribution


async def create_test_transaction(
    session: AsyncSession,
    tx_id: str,
    merchant_id: str = "merch_100",
    amount: float = 1500.00,
    status: str = TransactionStatus.EXECUTING.value,
) -> Transaction:
    """Helper to create a test Transaction record with Merchant and Customer."""
    cust_id = f"cust_{tx_id}"

    stmt_mer = select(Merchant).where(Merchant.id == merchant_id)
    merchant = (await session.execute(stmt_mer)).scalar_one_or_none()
    if not merchant:
        merchant = Merchant(
            id=merchant_id,
            name=f"Merchant {merchant_id}",
            email=f"{merchant_id}@example.com",
            industry="ECOMMERCE",
        )
        session.add(merchant)

    customer = Customer(
        id=cust_id,
        merchant_id=merchant_id,
        name=f"Customer {cust_id}",
        email=f"{cust_id}@example.com",
    )
    session.add(customer)

    tx = Transaction(
        id=tx_id,
        merchant_id=merchant_id,
        customer_id=cust_id,
        amount=amount,
        currency="INR",
        status=status,
        scenario_type="PAYMENT_FAILURE",
        recovery_cycle=1,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(tx)
    await session.commit()
    return tx



async def create_test_attempt(
    session: AsyncSession,
    attempt_id: str,
    tx_id: str,
    mode: str = "SIMULATION",
    link_id: str = None,
    ref_id: str = None,
    ext_id: str = None,
    executed_at: datetime = None,
    execution_status: str = ExecutionStatus.SUCCESS.value,
) -> RecoveryAttempt:
    """Helper to create a test RecoveryAttempt record."""
    if executed_at is None:
        executed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    attempt = RecoveryAttempt(
        id=attempt_id,
        transaction_id=tx_id,
        recommended_action="PAYMENT_LINK",
        action_payload={"amount": 1500.00},
        policy_status="APPROVED",
        policy_reason="Policy approved for execution",
        policy_version="1.0",
        execution_status=execution_status,
        external_resource_type=mode,
        razorpay_payment_link_id=link_id,
        razorpay_reference_id=ref_id,
        external_resource_id=ext_id,
        logical_operation_key=f"merch_100:{tx_id}:{attempt_id}:PAYMENT_LINK",
        executed_at=executed_at,
        created_at=executed_at,
    )
    session.add(attempt)
    await session.commit()
    return attempt




@pytest.mark.asyncio
async def test_direct_reference_attribution(async_session: AsyncSession):
    """Test Case 1: DIRECT_REFERENCE attribution via razorpay_payment_link_id."""
    tx = await create_test_transaction(async_session, "tx_dir_1")
    attempt = await create_test_attempt(
        async_session,
        "att_dir_1",
        tx.id,
        mode="REAL_TEST",
        link_id="plink_123456",
        ref_id="RAI-tx_dir_1-1",
    )

    req = AttributionRequest(transaction_id=tx.id, recovery_attempt_id=attempt.id)
    res = await AttributionEngine.evaluate_attribution(async_session, req)

    assert res.attribution_status == AttributionStatus.ATTRIBUTED.value
    assert res.attribution_method == AttributionMethod.DIRECT_REFERENCE.value
    assert res.recovery_source == "REAL_TEST"
    assert res.recovered_amount == 1500.00
    assert res.is_duplicate is False


@pytest.mark.asyncio
async def test_window_match_attribution(async_session: AsyncSession):
    """Test Case 2: WINDOW_MATCH attribution within window (e.g., 2 hours elapsed)."""
    tx = await create_test_transaction(async_session, "tx_win_1")
    # Executed 2 hours ago, no direct payment link ID on attempt
    two_hours_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    attempt = await create_test_attempt(
        async_session,
        "att_win_1",
        tx.id,
        mode="SIMULATION",
        executed_at=two_hours_ago,
    )

    req = AttributionRequest(
        transaction_id=tx.id,
        recovery_attempt_id=attempt.id,
        attribution_window_minutes=4320,  # 72 hours
    )
    res = await AttributionEngine.evaluate_attribution(async_session, req)

    assert res.attribution_status == AttributionStatus.ATTRIBUTED.value
    assert res.attribution_method == AttributionMethod.WINDOW_MATCH.value
    assert res.recovery_source == "SIMULATION"


@pytest.mark.asyncio
async def test_natural_recovery_attribution(async_session: AsyncSession):
    """Test Case 3: NATURAL_RECOVERY when transaction recovered with no attempt."""
    tx = await create_test_transaction(async_session, "tx_nat_1")

    req = AttributionRequest(transaction_id=tx.id, recovery_attempt_id=None)
    res = await AttributionEngine.evaluate_attribution(async_session, req)

    assert res.attribution_status == AttributionStatus.NATURAL_RECOVERY.value
    assert res.attribution_method == AttributionMethod.NATURAL_RECOVERY.value
    assert res.recovery_attempt_id is None


@pytest.mark.asyncio
async def test_unattributed_outside_window(async_session: AsyncSession):
    """Test Case 4: UNATTRIBUTED when attempt is outside 72h attribution window."""
    tx = await create_test_transaction(async_session, "tx_unatt_1")
    # Executed 80 hours ago (> 72 hours)
    eighty_hours_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=80)
    attempt = await create_test_attempt(
        async_session,
        "att_unatt_1",
        tx.id,
        mode="SIMULATION",
        executed_at=eighty_hours_ago,
    )

    req = AttributionRequest(
        transaction_id=tx.id,
        recovery_attempt_id=attempt.id,
        attribution_window_minutes=4320,  # 72 hours
    )
    res = await AttributionEngine.evaluate_attribution(async_session, req)

    assert res.attribution_status == AttributionStatus.UNATTRIBUTED.value
    assert res.attribution_method == AttributionMethod.UNATTRIBUTED.value


@pytest.mark.asyncio
async def test_idempotent_duplicate_attribution(async_session: AsyncSession):
    """Test Case 6: Duplicate attribution processing returns existing record with is_duplicate=True."""
    tx = await create_test_transaction(async_session, "tx_idem_1")
    attempt = await create_test_attempt(async_session, "att_idem_1", tx.id, link_id="plink_idem")

    req = AttributionRequest(transaction_id=tx.id, recovery_attempt_id=attempt.id)
    res1 = await AttributionEngine.evaluate_attribution(async_session, req)
    assert res1.is_duplicate is False

    # Second call for same transaction & attempt
    res2 = await AttributionEngine.evaluate_attribution(async_session, req)
    assert res2.is_duplicate is True
    assert res2.id == res1.id


@pytest.mark.asyncio
async def test_multi_tenant_isolation_breach_rejection(async_session: AsyncSession):
    """Test Case 7: Merchant A cannot attribute Merchant B's recovery attempt."""
    tx_a = await create_test_transaction(async_session, "tx_merchant_a", merchant_id="merch_A")
    tx_b = await create_test_transaction(async_session, "tx_merchant_b", merchant_id="merch_B")

    attempt_b = await create_test_attempt(async_session, "att_b", tx_b.id)

    # Attempting to assign Merchant B's attempt to Merchant A's transaction request
    req = AttributionRequest(transaction_id=tx_a.id, recovery_attempt_id=attempt_b.id)

    with pytest.raises(ValueError, match="does not match request transaction ID"):
        await AttributionEngine.evaluate_attribution(async_session, req)


@pytest.mark.asyncio
async def test_missing_transaction_rejection(async_session: AsyncSession):
    """Test Case 8: Invalid / non-existent transaction raises ValueError."""
    req = AttributionRequest(transaction_id="non_existent_tx", recovery_attempt_id=None)
    with pytest.raises(ValueError, match="Transaction 'non_existent_tx' not found"):
        await AttributionEngine.evaluate_attribution(async_session, req)


@pytest.mark.asyncio
async def test_window_match_boundary_timestamps(async_session: AsyncSession):
    """Test Case 10: Boundary timestamp window evaluation (exact minute thresholds)."""
    tx = await create_test_transaction(async_session, "tx_bound_1")

    # 50 minutes ago (well within 60 minutes window)
    fifty_mins_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=50)
    attempt = await create_test_attempt(
        async_session,
        "att_bound_1",
        tx.id,
        executed_at=fifty_mins_ago,
    )

    # Window of 60 minutes -> Should match (<= 60)
    req_inside = AttributionRequest(
        transaction_id=tx.id,
        recovery_attempt_id=attempt.id,
        attribution_window_minutes=60,
    )
    res_inside = await AttributionEngine.evaluate_attribution(async_session, req_inside)
    assert res_inside.attribution_status == AttributionStatus.ATTRIBUTED.value

    # Reset and test 65 mins ago against 60 min window
    tx2 = await create_test_transaction(async_session, "tx_bound_2")
    sixty_five_mins_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=65)
    attempt2 = await create_test_attempt(
        async_session,
        "att_bound_2",
        tx2.id,
        executed_at=sixty_five_mins_ago,
    )
    req_outside = AttributionRequest(
        transaction_id=tx2.id,
        recovery_attempt_id=attempt2.id,
        attribution_window_minutes=60,
    )
    res_outside = await AttributionEngine.evaluate_attribution(async_session, req_outside)
    assert res_outside.attribution_status == AttributionStatus.UNATTRIBUTED.value


@pytest.mark.asyncio
async def test_real_test_vs_simulation_source_preservation(async_session: AsyncSession):
    """Test Cases 11 & 12: REAL_TEST and SIMULATION source modes are preserved explicitly."""
    tx_real = await create_test_transaction(async_session, "tx_real_1")
    att_real = await create_test_attempt(async_session, "att_real_1", tx_real.id, mode="REAL_TEST", link_id="plink_r1")

    tx_sim = await create_test_transaction(async_session, "tx_sim_1")
    att_sim = await create_test_attempt(async_session, "att_sim_1", tx_sim.id, mode="SIMULATION", link_id="plink_s1")

    res_real = await AttributionEngine.evaluate_attribution(
        async_session, AttributionRequest(transaction_id=tx_real.id, recovery_attempt_id=att_real.id)
    )
    res_sim = await AttributionEngine.evaluate_attribution(
        async_session, AttributionRequest(transaction_id=tx_sim.id, recovery_attempt_id=att_sim.id)
    )

    assert res_real.recovery_source == "REAL_TEST"
    assert res_sim.recovery_source == "SIMULATION"


@pytest.mark.asyncio
async def test_transaction_status_unmutated_by_attribution(async_session: AsyncSession):
    """Test Case 13: Attribution evaluation does NOT mutate transaction.status."""
    tx = await create_test_transaction(async_session, "tx_no_mutate", status=TransactionStatus.EXECUTING.value)
    attempt = await create_test_attempt(async_session, "att_no_mutate", tx.id, link_id="plink_nomut")

    await AttributionEngine.evaluate_attribution(
        async_session, AttributionRequest(transaction_id=tx.id, recovery_attempt_id=attempt.id)
    )

    # Re-fetch transaction from DB
    stmt = select(Transaction).where(Transaction.id == tx.id)
    tx_refreshed = (await async_session.execute(stmt)).scalar_one()

    assert tx_refreshed.status == TransactionStatus.EXECUTING.value


@pytest.mark.asyncio
async def test_result_processor_hook_integration(async_session: AsyncSession):
    """Test Case 15: Step 19 ResultProcessor triggers AttributionEngine via registered hook."""
    tx = await create_test_transaction(async_session, "tx_proc_hook", status=TransactionStatus.EXECUTING.value)
    attempt = await create_test_attempt(
        async_session,
        "att_proc_hook",
        tx.id,
        link_id="plink_hook123",
        ref_id="RAI-tx_proc_hook-1",
        execution_status=ExecutionStatus.EXECUTING.value,
    )


    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink_hook123",
                    "status": "paid",
                    "reference_id": "RAI-tx_proc_hook-1",
                    "notes": {"merchant_id": "merch_100"},
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_hook999",
                    "status": "captured",
                    "captured": True,
                }
            },
        },
    }

    res = await ResultProcessor.process_payload(async_session, payload)

    assert res["status"] == "SUCCESS_RECOVERED"
    assert res["transaction_status"] == TransactionStatus.RECOVERED.value

    # Verify attribution hook payload
    attribution_hook_data = res.get("attribution_hook")
    assert attribution_hook_data is not None
    assert attribution_hook_data["transaction_id"] == tx.id
    assert attribution_hook_data["recovery_attempt_id"] == attempt.id
    assert attribution_hook_data["attribution_status"] == AttributionStatus.ATTRIBUTED.value
    assert attribution_hook_data["attribution_method"] == AttributionMethod.DIRECT_REFERENCE.value
