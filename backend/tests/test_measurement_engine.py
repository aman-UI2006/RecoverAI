"""
RecoverAI - Measurement Engine Test Suite (Step 21)

Tests Control/Treatment Measurement Engine calculations, zero division handling,
multi-tenant merchant isolation, mode separation (REAL_TEST vs SIMULATION),
EvaluationRun DB persistence, and zero transaction status mutation.
"""

import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.domain import (
    Base,
    Merchant,
    Customer,
    Transaction,
    RecoveryAttempt,
    RecoveryAttribution,
    EvaluationRun,
)
from backend.app.schemas.analytics import MeasurementRequest
from backend.app.services.measurement_engine import MeasurementEngine


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


@pytest_asyncio.fixture
async def setup_measurement_db(async_session: AsyncSession):
    """Fixture to set up merchants, customers, transactions, attempts, and attributions for measurement testing."""
    m_a = Merchant(
        id=str(uuid.uuid4()),
        name="Measurement Merchant A",
        email="merchant_a@example.com",
        industry="FINTECH",
    )
    m_b = Merchant(
        id=str(uuid.uuid4()),
        name="Measurement Merchant B",
        email="merchant_b@example.com",
        industry="ECOMMERCE",
    )
    async_session.add_all([m_a, m_b])
    await async_session.flush()

    c_a = Customer(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        email="cust_a@example.com",
        phone="+919999999991",
    )
    c_b = Customer(
        id=str(uuid.uuid4()),
        merchant_id=m_b.id,
        email="cust_b@example.com",
        phone="+919999999992",
    )
    async_session.add_all([c_a, c_b])
    await async_session.flush()

    # 1. Treatment Transactions for Merchant A (SIMULATION)
    tx_t1 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=1000.00,
        currency="INR",
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    tx_t2 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=2000.00,
        currency="INR",
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    tx_t3 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=1500.00,
        currency="INR",
        status="FAILED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )

    # 2. Control Transactions for Merchant A (SIMULATION)
    tx_c1 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=1000.00,
        currency="INR",
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    tx_c2 = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=1000.00,
        currency="INR",
        status="FAILED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )

    # 3. REAL_TEST Transaction for Merchant A (Should be excluded from SIMULATION mode evaluation)
    tx_real = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a.id,
        customer_id=c_a.id,
        amount=5000.00,
        currency="INR",
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="REAL_TEST",
    )

    # 4. Merchant B Transaction (Should be excluded when filtering by Merchant A)
    tx_b = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_b.id,
        customer_id=c_b.id,
        amount=3000.00,
        currency="INR",
        status="RECOVERED",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )

    async_session.add_all([tx_t1, tx_t2, tx_t3, tx_c1, tx_c2, tx_real, tx_b])
    await async_session.flush()

    # Create attempts for Treatment transactions
    att_t1 = RecoveryAttempt(
        id=str(uuid.uuid4()),
        transaction_id=tx_t1.id,
        logical_operation_key=f"{m_a.id}:{tx_t1.id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="SUCCESS",
        external_resource_type="SIMULATION",
    )
    att_t2 = RecoveryAttempt(
        id=str(uuid.uuid4()),
        transaction_id=tx_t2.id,
        logical_operation_key=f"{m_a.id}:{tx_t2.id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="SUCCESS",
        external_resource_type="SIMULATION",
    )
    att_t3 = RecoveryAttempt(
        id=str(uuid.uuid4()),
        transaction_id=tx_t3.id,
        logical_operation_key=f"{m_a.id}:{tx_t3.id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="FAILURE",
        external_resource_type="SIMULATION",
    )

    # Real test attempt
    att_real = RecoveryAttempt(
        id=str(uuid.uuid4()),
        transaction_id=tx_real.id,
        logical_operation_key=f"{m_a.id}:{tx_real.id}:1:PAYMENT_LINK",
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="SUCCESS",
        external_resource_type="REAL_TEST",
    )

    async_session.add_all([att_t1, att_t2, att_t3, att_real])
    await async_session.flush()

    # Create attributions for recovered Treatment transactions
    attr_t1 = RecoveryAttribution(
        id=str(uuid.uuid4()),
        transaction_id=tx_t1.id,
        recovery_attempt_id=att_t1.id,
        recovery_source="SIMULATION",
        attribution_status="ATTRIBUTED",
        attribution_method="DIRECT_REFERENCE",
        attribution_window_minutes=4320,
        recovered_amount=1000.00,
        refunded_amount=0.00,
    )
    attr_t2 = RecoveryAttribution(
        id=str(uuid.uuid4()),
        transaction_id=tx_t2.id,
        recovery_attempt_id=att_t2.id,
        recovery_source="SIMULATION",
        attribution_status="ATTRIBUTED",
        attribution_method="DIRECT_REFERENCE",
        attribution_window_minutes=4320,
        recovered_amount=2000.00,
        refunded_amount=0.00,
    )
    attr_real = RecoveryAttribution(
        id=str(uuid.uuid4()),
        transaction_id=tx_real.id,
        recovery_attempt_id=att_real.id,
        recovery_source="REAL_TEST",
        attribution_status="ATTRIBUTED",
        attribution_method="DIRECT_REFERENCE",
        attribution_window_minutes=4320,
        recovered_amount=5000.00,
        refunded_amount=0.00,
    )

    async_session.add_all([attr_t1, attr_t2, attr_real])
    await async_session.commit()

    return {
        "merchant_a": m_a,
        "merchant_b": m_b,
        "tx_t1": tx_t1,
        "tx_t2": tx_t2,
        "tx_t3": tx_t3,
        "tx_c1": tx_c1,
        "tx_c2": tx_c2,
        "tx_real": tx_real,
        "tx_b": tx_b,
    }


def test_pure_lift_calculation_math():
    """Verify exact formula computations in calculate_cohort_lift."""
    calc = MeasurementEngine.calculate_cohort_lift(
        treatment_eligible_count=100,
        treatment_eligible_amount=Decimal("100000.00"),
        treatment_recovered_count=80,
        treatment_recovered_amount=Decimal("80000.00"),
        treatment_refunds=Decimal("1000.00"),
        treatment_costs=Decimal("2000.00"),
        control_eligible_count=100,
        control_eligible_amount=Decimal("100000.00"),
        control_recovered_count=40,
        control_recovered_amount=Decimal("40000.00"),
        control_refunds=Decimal("0.00"),
        control_costs=Decimal("0.00"),
    )

    assert calc["treatment_recovery_rate"] == 0.80
    assert calc["control_recovery_rate"] == 0.40
    assert calc["incremental_recovery_rate"] == 0.40
    # 0.40 * 100,000 = 40,000
    assert calc["estimated_incremental_recovered_amount"] == Decimal("40000.00")
    # 40,000 - 1,000 - 2,000 = 37,000
    assert calc["net_incremental_revenue"] == Decimal("37000.00")


def test_zero_denominator_division_by_zero_handling():
    """Verify zero eligible counts return 0.0 rates without throwing ZeroDivisionError."""
    calc = MeasurementEngine.calculate_cohort_lift(
        treatment_eligible_count=0,
        treatment_eligible_amount=Decimal("0.00"),
        treatment_recovered_count=0,
        treatment_recovered_amount=Decimal("0.00"),
        treatment_refunds=Decimal("0.00"),
        treatment_costs=Decimal("0.00"),
        control_eligible_count=0,
        control_eligible_amount=Decimal("0.00"),
        control_recovered_count=0,
        control_recovered_amount=Decimal("0.00"),
        control_refunds=Decimal("0.00"),
        control_costs=Decimal("0.00"),
    )

    assert calc["treatment_recovery_rate"] == 0.0
    assert calc["control_recovery_rate"] == 0.0
    assert calc["incremental_recovery_rate"] == 0.0
    assert calc["estimated_incremental_recovered_amount"] == Decimal("0.00")
    assert calc["net_incremental_revenue"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_evaluate_measurement_db_integration(
    async_session: AsyncSession, setup_measurement_db: dict
):
    """Test full DB evaluation for Merchant A SIMULATION transactions."""
    m_a = setup_measurement_db["merchant_a"]

    req = MeasurementRequest(
        merchant_id=m_a.id,
        mode="SIMULATION",
        run_name="unit_test_eval_run",
        persist_evaluation_run=True,
    )

    res = await MeasurementEngine.evaluate_measurement(async_session, req)

    assert res.run_name == "unit_test_eval_run"
    assert res.mode == "SIMULATION"
    assert res.merchant_id == m_a.id
    assert res.evaluation_run_id is not None

    # Treatment: 3 eligible (t1=1000, t2=2000, t3=1500 -> total=4500), 2 recovered (t1, t2 -> 3000)
    assert res.treatment_metrics.total_eligible_count == 3
    assert res.treatment_metrics.total_eligible_amount == 4500.00
    assert res.treatment_metrics.recovered_count == 2
    assert res.treatment_metrics.recovered_amount == 3000.00
    assert abs(res.treatment_recovery_rate - (2 / 3)) < 0.0001

    # Control: 2 eligible (c1=1000, c2=1000 -> total=2000), 1 recovered (c1 -> 1000)
    assert res.control_metrics.total_eligible_count == 2
    assert res.control_metrics.total_eligible_amount == 2000.00
    assert res.control_metrics.recovered_count == 1
    assert res.control_metrics.recovered_amount == 1000.00
    assert abs(res.control_recovery_rate - (1 / 2)) < 0.0001

    # Incremental Rate = (2/3) - (1/2) = (4/6) - (3/6) = 1/6 (~0.1667)
    assert abs(res.incremental_recovery_rate - (1 / 6)) < 0.0001

    # Estimated Incremental Recovered = (1/6) * 4500 = 750.00
    assert abs(res.estimated_incremental_recovered_amount - 750.00) < 0.01
    assert abs(res.net_incremental_revenue - 750.00) < 0.01


@pytest.mark.asyncio
async def test_multi_tenant_merchant_isolation(
    async_session: AsyncSession, setup_measurement_db: dict
):
    """Verify that querying for Merchant B excludes Merchant A transactions."""
    m_b = setup_measurement_db["merchant_b"]

    req = MeasurementRequest(
        merchant_id=m_b.id,
        mode="SIMULATION",
        run_name="merchant_b_eval_run",
        persist_evaluation_run=False,
    )

    res = await MeasurementEngine.evaluate_measurement(async_session, req)

    assert res.merchant_id == m_b.id
    # Merchant B has 1 control transaction (tx_b = 3000)
    assert res.treatment_metrics.total_eligible_count == 0
    assert res.control_metrics.total_eligible_count == 1
    assert res.control_metrics.total_eligible_amount == 3000.00
    assert res.control_metrics.recovered_count == 1


@pytest.mark.asyncio
async def test_real_test_vs_simulation_mode_separation(
    async_session: AsyncSession, setup_measurement_db: dict
):
    """Verify REAL_TEST transactions are excluded when querying SIMULATION mode."""
    m_a = setup_measurement_db["merchant_a"]

    req_sim = MeasurementRequest(
        merchant_id=m_a.id,
        mode="SIMULATION",
        persist_evaluation_run=False,
    )
    res_sim = await MeasurementEngine.evaluate_measurement(async_session, req_sim)

    req_real = MeasurementRequest(
        merchant_id=m_a.id,
        mode="REAL_TEST",
        persist_evaluation_run=False,
    )
    res_real = await MeasurementEngine.evaluate_measurement(async_session, req_real)

    # SIMULATION mode should not include tx_real (5000.00)
    assert res_sim.treatment_metrics.total_eligible_amount == 4500.00

    # REAL_TEST mode should only include tx_real (5000.00)
    assert res_real.treatment_metrics.total_eligible_count == 1
    assert res_real.treatment_metrics.total_eligible_amount == 5000.00
    assert res_real.treatment_metrics.recovered_amount == 5000.00


@pytest.mark.asyncio
async def test_evaluation_run_persistence(
    async_session: AsyncSession, setup_measurement_db: dict
):
    """Verify that an EvaluationRun database record is created and queryable."""
    m_a = setup_measurement_db["merchant_a"]

    req = MeasurementRequest(
        merchant_id=m_a.id,
        mode="SIMULATION",
        run_name="persisted_run_test",
        dataset_version="v2.1",
        persist_evaluation_run=True,
    )

    res = await MeasurementEngine.evaluate_measurement(async_session, req)

    assert res.evaluation_run_id is not None

    stmt = select(EvaluationRun).where(EvaluationRun.id == res.evaluation_run_id)
    eval_record = (await async_session.execute(stmt)).scalar_one_or_none()

    assert eval_record is not None
    assert eval_record.run_name == "persisted_run_test"
    assert eval_record.dataset_version == "v2.1"
    assert eval_record.mode == "SIMULATION"
    assert float(eval_record.revenue_at_risk) == 6500.00  # 4500 treatment + 2000 control


@pytest.mark.asyncio
async def test_zero_transaction_state_mutation(
    async_session: AsyncSession, setup_measurement_db: dict
):
    """Verify that running MeasurementEngine leaves transaction statuses completely unchanged."""
    tx_t1 = setup_measurement_db["tx_t1"]
    tx_t3 = setup_measurement_db["tx_t3"]

    status_t1_before = tx_t1.status
    status_t3_before = tx_t3.status

    req = MeasurementRequest(mode="SIMULATION", persist_evaluation_run=False)
    await MeasurementEngine.evaluate_measurement(async_session, req)

    await async_session.refresh(tx_t1)
    await async_session.refresh(tx_t3)

    assert tx_t1.status == status_t1_before
    assert tx_t3.status == status_t3_before
