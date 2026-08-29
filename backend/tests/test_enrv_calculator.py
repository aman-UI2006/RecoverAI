"""
RecoverAI - ENRV Calculator Test Suite (Step 10)

Verifies exact ENRV calculation formula execution, probability clamping, candidate action ranking,
custom cost overrides, database persistence, and multi-tenant isolation.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, DecisionContext, RecoveryActionScore
from backend.app.schemas.enrv import (
    CandidateActionInput,
    ENRVCalculationRequest,
    ENRVCalculationResponse,
    ENRVActionResult,
)
from backend.app.services.enrv_calculator import ENRVCalculator


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
    """Creates sample Merchant, Customer, and Transaction records."""
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
        amount=5000.00,  # 5,000 INR = 500,000 paise
        currency="INR",
        status="AT_RISK",
        scenario_type="PAYMENT_FAILURE",
        mode="SIMULATION",
    )
    in_memory_db.add(merchant)
    in_memory_db.add(customer)
    in_memory_db.add(tx)
    await in_memory_db.commit()
    await in_memory_db.refresh(tx)
    return tx


@pytest.mark.asyncio
async def test_1_single_action_enrv_calculation():
    """Verifies exact ENRV formula execution for a single action."""
    amount_in_paise = 500000  # 5,000 INR
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.80,
    )
    # Expected:
    # Gross recovery = 0.80 * 500,000 = 400,000 paise
    # Total cost = 300 (intervention) + 50 (operational) + 0 (refund) = 350 paise
    # ENRV paise = 400,000 - 350 = 399,650 paise
    # ENRV rupees = 3996.50 INR

    res = ENRVCalculator.calculate_action_enrv(amount_in_paise, candidate)
    assert res.action_type == "PAYMENT_LINK"
    assert res.predicted_recovery_probability == 0.80
    assert res.expected_gross_recovery_in_paise == 400000
    assert res.total_cost_in_paise == 350
    assert res.expected_net_recovery_value_in_paise == 399650
    assert res.expected_net_recovery_value_rupees == 3996.50


@pytest.mark.asyncio
async def test_2_candidate_action_ranking():
    """Verifies candidate action ranking in descending order of ENRV."""
    req = ENRVCalculationRequest(
        transaction_id="tx_test_300",
        amount_in_paise=100000,  # 1,000 INR
        candidate_actions=[
            CandidateActionInput(action_type="NO_ACTION", predicted_recovery_probability=0.00),
            CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.75),
            CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.70),
            CandidateActionInput(action_type="RETRY", predicted_recovery_probability=0.50),
        ],
    )
    # Action ENRV calculations (Amount = 100,000 paise):
    # PAYMENT_LINK: 0.75 * 100,000 = 75,000 gross. Cost = 350. ENRV = 74,650 paise.
    # RECOVERY_MESSAGE: 0.70 * 100,000 = 70,000 gross. Cost = 60. ENRV = 69,940 paise.
    # RETRY: 0.50 * 100,000 = 50,000 gross. Cost = 170. ENRV = 49,830 paise.
    # NO_ACTION: 0.00 * 100,000 = 0 gross. Cost = 0. ENRV = 0 paise.

    response = ENRVCalculator.calculate_enrv(req)
    assert isinstance(response, ENRVCalculationResponse)
    assert response.best_action == "PAYMENT_LINK"
    assert response.max_enrv_in_paise == 74650
    assert response.max_enrv_rupees == 746.50

    results = response.action_results
    assert len(results) == 4
    assert [r.action_type for r in results] == ["PAYMENT_LINK", "RECOVERY_MESSAGE", "RETRY", "NO_ACTION"]
    assert [r.rank for r in results] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_3_probability_clamping():
    """Verifies that out-of-bounds probabilities are clamped to [0.0, 1.0]."""
    candidate_low = CandidateActionInput(action_type="RETRY", predicted_recovery_probability=-0.25)
    candidate_high = CandidateActionInput(action_type="RETRY", predicted_recovery_probability=1.50)

    res_low = ENRVCalculator.calculate_action_enrv(100000, candidate_low)
    res_high = ENRVCalculator.calculate_action_enrv(100000, candidate_high)

    assert res_low.predicted_recovery_probability == 0.0
    assert res_high.predicted_recovery_probability == 1.0


@pytest.mark.asyncio
async def test_4_custom_cost_overrides():
    """Verifies custom cost overrides in candidate action input."""
    candidate = CandidateActionInput(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.50,
        custom_intervention_cost_in_paise=1000,
        custom_operational_cost_in_paise=200,
        custom_expected_refund_cost_in_paise=500,
    )
    # Amount = 100,000 paise. Gross = 50,000 paise.
    # Costs = 1000 + 200 + 500 = 1700 paise.
    # ENRV = 50,000 - 1700 = 48,300 paise = 483.00 INR.

    res = ENRVCalculator.calculate_action_enrv(100000, candidate)
    assert res.intervention_cost_in_paise == 1000
    assert res.operational_cost_in_paise == 200
    assert res.expected_refund_cost_in_paise == 500
    assert res.total_cost_in_paise == 1700
    assert res.expected_net_recovery_value_in_paise == 48300


@pytest.mark.asyncio
async def test_5_non_positive_amount_raises_value_error():
    """Verifies that non-positive monetary amounts raise ValueError."""
    candidate = CandidateActionInput(action_type="RETRY", predicted_recovery_probability=0.50)
    with pytest.raises(ValueError, match="Amount in paise must be a positive integer"):
        ENRVCalculator.calculate_action_enrv(0, candidate)


@pytest.mark.asyncio
async def test_6_duplicate_action_types_rejected():
    """Verifies that request schema validation rejects duplicate action types."""
    with pytest.raises(ValueError, match="Duplicate candidate action type in request"):
        ENRVCalculationRequest(
            transaction_id="tx_test_300",
            amount_in_paise=100000,
            candidate_actions=[
                CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.80),
                CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.70),
            ],
        )


@pytest.mark.asyncio
async def test_7_persist_enrv_scores(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies persisting ENRV calculation results to decision_contexts and recovery_action_scores tables."""
    req = ENRVCalculationRequest(
        transaction_id=sample_transaction.id,
        merchant_id="mch_test_100",
        amount_in_paise=500000,
        candidate_actions=[
            CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.80),
            CandidateActionInput(action_type="RECOVERY_MESSAGE", predicted_recovery_probability=0.60),
        ],
    )
    response = ENRVCalculator.calculate_enrv(req)

    context = await ENRVCalculator.persist_enrv_scores(
        session=in_memory_db,
        transaction_id=sample_transaction.id,
        enrv_response=response,
        merchant_id="mch_test_100",
    )

    assert isinstance(context, DecisionContext)
    assert context.transaction_id == sample_transaction.id

    # Verify action scores persisted
    stmt = select(RecoveryActionScore).where(RecoveryActionScore.decision_context_id == context.id)
    scores = (await in_memory_db.execute(stmt)).scalars().all()
    assert len(scores) == 2
    actions_persisted = {s.action for s in scores}
    assert actions_persisted == {"PAYMENT_LINK", "RECOVERY_MESSAGE"}


@pytest.mark.asyncio
async def test_8_multi_tenant_merchant_mismatch_raises_error(in_memory_db: AsyncSession, sample_transaction: Transaction):
    """Verifies that merchant mismatch on score persistence raises ValueError and writes no records."""
    req = ENRVCalculationRequest(
        transaction_id=sample_transaction.id,
        merchant_id="mch_UNAUTHORIZED_999",
        amount_in_paise=500000,
        candidate_actions=[
            CandidateActionInput(action_type="PAYMENT_LINK", predicted_recovery_probability=0.80),
        ],
    )
    response = ENRVCalculator.calculate_enrv(req)

    with pytest.raises(ValueError, match="Merchant ID mismatch for transaction"):
        await ENRVCalculator.persist_enrv_scores(
            session=in_memory_db,
            transaction_id=sample_transaction.id,
            enrv_response=response,
            merchant_id="mch_UNAUTHORIZED_999",
        )

    # Verify zero DecisionContext records created
    stmt = select(DecisionContext).where(DecisionContext.transaction_id == sample_transaction.id)
    contexts = (await in_memory_db.execute(stmt)).scalars().all()
    assert len(contexts) == 0
