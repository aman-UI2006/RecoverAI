"""
RecoverAI - Revenue Risk Engine Test Suite (Step 8)

Verifies risk calculation, eligible revenue at risk precision, state transition from CREATED to AT_RISK,
and audit log generation across all 4 transaction scenarios.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import pytest_asyncio

from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, AuditEvent
from backend.app.schemas.canonical_event import NormalizedEvent
from backend.app.schemas.risk_assessment import RiskAssessmentRequest, RiskAssessmentResponse
from backend.app.services.revenue_risk_engine import RevenueRiskEngine, SCENARIO_RISK_SCORES


@pytest_asyncio.fixture
async def in_memory_db():
    """Provides an isolated in-memory SQLite database session for async tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def sample_transaction(in_memory_db: AsyncSession):
    """Creates sample Merchant, Customer, and CREATED Transaction records."""
    merchant = Merchant(
        id="mch_test_100",
        name="Test Merchant",
        email="merchant@example.com",
        industry="SaaS",
    )
    customer = Customer(
        id="cust_test_200",
        merchant_id="mch_test_100",
        email="customer@example.com",
    )
    tx = Transaction(
        id="tx_test_300",
        merchant_id="mch_test_100",
        customer_id="cust_test_200",
        amount=5000.00,  # 5000 rupees = 500000 paise
        currency="INR",
        status="CREATED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
        mode="SIMULATION",
    )
    in_memory_db.add(merchant)
    in_memory_db.add(customer)
    in_memory_db.add(tx)
    await in_memory_db.commit()
    await in_memory_db.refresh(tx)
    return tx


@pytest.mark.asyncio
async def test_1_risk_score_calculation_all_scenarios():
    """Verifies correct base risk scores for all 4 scenario types."""
    assert RevenueRiskEngine.calculate_risk_score("PAYMENT_FAILURE") == 0.95
    assert RevenueRiskEngine.calculate_risk_score("CHECKOUT_ABANDONMENT") == 0.70
    assert RevenueRiskEngine.calculate_risk_score("SUBSCRIPTION_FAILURE") == 0.90
    assert RevenueRiskEngine.calculate_risk_score("OVERDUE_RECEIVABLE") == 0.85


@pytest.mark.asyncio
async def test_2_invalid_scenario_raises_value_error():
    """Verifies that an unhandled or invalid scenario type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid or unhandled transaction scenario type"):
        RevenueRiskEngine.calculate_risk_score("INVALID_SCENARIO_XYZ")


@pytest.mark.asyncio
async def test_3_assess_and_transition_payment_failure(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies risk assessment and state transition from CREATED to AT_RISK for PAYMENT_FAILURE."""
    amount_in_paise = 500000  # 5,000 INR
    response = await RevenueRiskEngine.assess_and_transition(
        session=in_memory_db,
        transaction_id=sample_transaction.id,
        scenario_type="PAYMENT_FAILURE",
        amount_in_paise=amount_in_paise,
        merchant_id="mch_test_100",
    )

    assert isinstance(response, RiskAssessmentResponse)
    assert response.transaction_id == sample_transaction.id
    assert response.scenario_type == "PAYMENT_FAILURE"
    assert response.risk_score == 0.95
    assert response.amount_in_paise == 500000
    assert response.eligible_revenue_at_risk_in_paise == 475000  # 500000 * 0.95
    assert response.eligible_revenue_at_risk == 4750.00
    assert response.status == "AT_RISK"

    # Refresh transaction model from DB
    await in_memory_db.refresh(sample_transaction)
    assert sample_transaction.status == "AT_RISK"


@pytest.mark.asyncio
async def test_4_assess_and_transition_all_scenarios(in_memory_db: AsyncSession):
    """Verifies risk calculations across all 4 scenarios on distinct transactions."""
    scenarios_expected = [
        ("PAYMENT_FAILURE", 100000, 0.95, 95000, 950.00),
        ("CHECKOUT_ABANDONMENT", 200000, 0.70, 140000, 1400.00),
        ("SUBSCRIPTION_FAILURE", 300000, 0.90, 270000, 2700.00),
        ("OVERDUE_RECEIVABLE", 400000, 0.85, 340000, 3400.00),
    ]

    for idx, (scenario, paise, expected_score, expected_eligible_paise, expected_eligible_rupees) in enumerate(scenarios_expected):
        tx_id = f"tx_multi_{idx}"
        tx = Transaction(
            id=tx_id,
            merchant_id="mch_test_100",
            customer_id="cust_test_200",
            amount=paise / 100.0,
            currency="INR",
            status="CREATED",
            scenario_type=scenario,
            mode="SIMULATION",
        )
        in_memory_db.add(tx)
        await in_memory_db.commit()

        res = await RevenueRiskEngine.assess_and_transition(
            session=in_memory_db,
            transaction_id=tx_id,
            scenario_type=scenario,
            amount_in_paise=paise,
        )

        assert res.risk_score == expected_score
        assert res.eligible_revenue_at_risk_in_paise == expected_eligible_paise
        assert res.eligible_revenue_at_risk == expected_eligible_rupees
        assert res.status == "AT_RISK"


@pytest.mark.asyncio
async def test_5_audit_event_logged_on_transition(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies that an AuditEvent with REVENUE_AT_RISK_DETECTED details is emitted and chained."""
    await RevenueRiskEngine.assess_and_transition(
        session=in_memory_db,
        transaction_id=sample_transaction.id,
        scenario_type="PAYMENT_FAILURE",
        amount_in_paise=500000,
    )

    # Inspect created AuditEvent record
    events = (await in_memory_db.execute(
        Transaction.__table__.select().where(Transaction.id == sample_transaction.id)
    )).all()
    assert sample_transaction.status == "AT_RISK"

    audit_records = (await in_memory_db.execute(
        AuditEvent.__table__.select().where(AuditEvent.transaction_id == sample_transaction.id)
    )).all()
    assert len(audit_records) >= 1
    last_audit = audit_records[-1]
    assert last_audit.state_from == "CREATED"
    assert last_audit.state_to == "AT_RISK"
    assert last_audit.actor == "REVENUE_RISK_ENGINE"


@pytest.mark.asyncio
async def test_6_process_normalized_event_integration(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies integration with canonical NormalizedEvent from Step 6."""
    norm_event = NormalizedEvent(
        raw_event_id="evt_norm_100",
        idempotency_key="razorpay:evt_norm_100",
        event_source="RAZORPAY_WEBHOOK",
        event_type="PAYMENT_FAILED",
        merchant_id="mch_test_100",
        customer_id="cust_test_200",
        transaction_id=sample_transaction.id,
        amount_in_paise=500000,
        currency="INR",
        scenario="PAYMENT_FAILURE",
        normalized_payload={},
        occurred_at=datetime.now(timezone.utc),
        is_duplicate=False,
    )

    res = await RevenueRiskEngine.process_normalized_event(
        session=in_memory_db,
        normalized_event=norm_event,
    )

    assert res is not None
    assert res.transaction_id == sample_transaction.id
    assert res.status == "AT_RISK"
    assert res.eligible_revenue_at_risk_in_paise == 475000


@pytest.mark.asyncio
async def test_7_process_duplicate_normalized_event_skipped(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies that duplicate normalized events return None and do not double-transition."""
    norm_event = NormalizedEvent(
        raw_event_id="evt_norm_100",
        idempotency_key="razorpay:evt_norm_100",
        event_source="RAZORPAY_WEBHOOK",
        event_type="PAYMENT_FAILED",
        transaction_id=sample_transaction.id,
        amount_in_paise=500000,
        scenario="PAYMENT_FAILURE",
        normalized_payload={},
        occurred_at=datetime.now(timezone.utc),
        is_duplicate=True,  # Marked as duplicate by Step 6 deduplication
    )

    res = await RevenueRiskEngine.process_normalized_event(
        session=in_memory_db,
        normalized_event=norm_event,
    )

    assert res is None
    await in_memory_db.refresh(sample_transaction)
    assert sample_transaction.status == "CREATED"  # Status remains unchanged


@pytest.mark.asyncio
async def test_8_non_positive_amount_raises_value_error(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies that non-positive monetary amounts raise ValueError."""
    with pytest.raises(ValueError, match="Amount in paise must be a positive integer"):
        await RevenueRiskEngine.assess_and_transition(
            session=in_memory_db,
            transaction_id=sample_transaction.id,
            scenario_type="PAYMENT_FAILURE",
            amount_in_paise=0,
        )


@pytest.mark.asyncio
async def test_9_merchant_mismatch_raises_error(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies DET-001 fix: merchant ID mismatch raises ValueError before state transition and creates no audit events."""
    with pytest.raises(ValueError, match="Merchant ID mismatch for transaction"):
        await RevenueRiskEngine.assess_and_transition(
            session=in_memory_db,
            transaction_id=sample_transaction.id,
            scenario_type="PAYMENT_FAILURE",
            amount_in_paise=500000,
            merchant_id="mch_UNAUTHORIZED_999",
        )

    # Verify transaction status remains unchanged (CREATED)
    await in_memory_db.refresh(sample_transaction)
    assert sample_transaction.status == "CREATED"

    # Verify zero audit events were created
    audit_records = (await in_memory_db.execute(
        AuditEvent.__table__.select().where(AuditEvent.transaction_id == sample_transaction.id)
    )).all()
    assert len(audit_records) == 0

