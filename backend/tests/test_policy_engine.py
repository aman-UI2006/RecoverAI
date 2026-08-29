"""
RecoverAI — Step 15 Test Suite: Policy Engine

Tests the PolicyEngine service, rule evaluators, and policy schemas.
Verifies rule hierarchy (Global -> Merchant -> Context), max attempts cap,
amount cap (<= ₹50,000), minimum probability (>= 0.15), cooldown window (>= 24h),
state machine transitions (INTERVENTION_SELECTED -> POLICY_CHECK -> APPROVED/STOPPED/ESCALATED),
multi-tenant merchant isolation, and air-gap network safety.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base
from backend.app.schemas.capability import (
    ExecutionMode,
    CapabilityStatus,
    CapabilityResolutionResult,
)
from backend.app.schemas.policy import (
    PolicyStatus,
    PolicyRejectionCode,
    PolicyEvaluationResult,
)
from backend.app.policies.rules import PolicyRuleEvaluator, GLOBAL_DEFAULT_POLICY
from backend.app.policies.policy_engine import PolicyEngine
from backend.app.models.domain import Transaction, Merchant, Customer, Policy, RecoveryAttempt
from backend.app.services.state_transition_service import StateTransitionService
from backend.app.schemas.state_machine import TransactionStatus

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for policy engine testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


def helper_make_capability_result(
    action: str = "PAYMENT_LINK",
    status: CapabilityStatus = CapabilityStatus.SUPPORTED,
    mode: ExecutionMode = ExecutionMode.REAL_TEST,
    is_executable: bool = True,
) -> CapabilityResolutionResult:
    """Helper to create a CapabilityResolutionResult mock."""
    return CapabilityResolutionResult(
        resolved_action=action,
        status=status,
        execution_mode=mode,
        is_executable=is_executable,
        reason=f"Action {action} test resolution.",
    )


def test_1_policy_schemas_and_enums():
    """1. Verifies PolicyStatus, PolicyRejectionCode enums and PolicyEvaluationResult model."""
    assert PolicyStatus.APPROVED == "APPROVED"
    assert PolicyStatus.REJECTED == "REJECTED"
    assert PolicyStatus.ESCALATED == "ESCALATED"

    res = PolicyEvaluationResult(
        resolved_action="PAYMENT_LINK",
        status=PolicyStatus.APPROVED,
        is_approved=True,
        policy_version="v1.0",
        applied_rules=["Rule_1", "Rule_2"],
    )
    assert res.is_approved is True
    assert res.rejection_code is None


def test_2_policy_approval_rule_evaluation():
    """2. Verifies that a valid action on a compliant transaction is APPROVED."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=1500.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
        candidate_probability=0.85,
    )

    assert result.is_approved is True
    assert result.status == PolicyStatus.APPROVED
    assert result.rejection_code is None
    assert "Rule_1_Capability_Support" in result.applied_rules


def test_3_unsupported_capability_rejection():
    """3. Verifies Rule 1: Rejection when capability is not executable."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=1500.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("AUTOMATED_GATEWAY_RETRY", is_executable=False)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.CAPABILITY_UNSUPPORTED


def test_4_explicit_stop_action_rejection():
    """4. Verifies Rule 2: Rejection when resolved action is STOP."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=1000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("STOP", is_executable=True)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.EXPLICIT_STOP


def test_5_max_recovery_attempts_exceeded():
    """5. Verifies Rule 3: Rejection when retry_count >= max_recovery_attempts (3)."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=2500.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=3,  # Reached limit 3
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.MAX_ATTEMPTS_EXCEEDED


def test_6_amount_cap_exceeded_rejection():
    """6. Verifies Rule 4: Rejection when transaction amount exceeds ₹50,000 cap."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=75000.00,  # Exceeds 50,000
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP


def test_7_min_probability_not_met_rejection():
    """7. Verifies Rule 5: Rejection when predicted probability < 0.15 threshold."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=2000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
        candidate_probability=0.10,  # Below 0.15
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.MIN_PROBABILITY_NOT_MET


def test_8_cooldown_hours_active_rejection():
    """8. Verifies Rule 6: Rejection when elapsed time since last attempt < 24 hours."""
    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=3000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=1,
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    recent_time = datetime.now(timezone.utc) - timedelta(hours=5)  # 5 hours ago < 24h
    last_attempt = RecoveryAttempt(
        id=str(uuid4()),
        transaction_id=tx.id,
        logical_operation_key=f"op_{uuid4()}",
        recommended_action="PAYMENT_LINK",
        action_payload={},
        policy_status="APPROVED",
        policy_version="v1.0",
        execution_status="SUCCESS",
        external_resource_type="PAYMENT_LINK",
        created_at=recent_time,
    )

    result = evaluator.evaluate(
        capability_result=cap_res,
        transaction=tx,
        last_attempt=last_attempt,
    )

    assert result.is_approved is False
    assert result.status == PolicyStatus.REJECTED
    assert result.rejection_code == PolicyRejectionCode.COOLDOWN_ACTIVE


@pytest.mark.asyncio
async def test_9_evaluate_and_transition_integration(async_test_session: AsyncSession):
    """9. Integration Test: Verifies evaluate_and_transition state machine flow and DB attempt persistence."""
    engine = PolicyEngine()
    m_id = str(uuid4())
    c_id = str(uuid4())

    merchant = Merchant(id=m_id, name="Test Merchant", email="test@merchant.com", industry="SAAS")
    customer = Customer(id=c_id, merchant_id=m_id, email="cust@test.com", phone="+919876543210")
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=m_id,
        customer_id=c_id,
        amount=5000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        mode="REAL_TEST",
    )
    async_test_session.add_all([merchant, customer, tx])
    await async_test_session.flush()

    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result, updated_tx = await engine.evaluate_and_transition(
        session=async_test_session,
        transaction_id=tx.id,
        capability_result=cap_res,
        merchant_id=m_id,
        candidate_probability=0.75,
    )

    assert result.is_approved is True
    assert result.status == PolicyStatus.APPROVED
    assert updated_tx.status == TransactionStatus.APPROVED.value


@pytest.mark.asyncio
async def test_10_multi_tenant_merchant_isolation(async_test_session: AsyncSession):
    """10. Security Test: Verifies ValueError raised on mismatched merchant_id."""
    engine = PolicyEngine()
    m_id_1 = str(uuid4())
    m_id_2 = str(uuid4())
    c_id = str(uuid4())

    merchant = Merchant(id=m_id_1, name="Merchant 1", email="m1@test.com", industry="RETAIL")
    customer = Customer(id=c_id, merchant_id=m_id_1, email="c1@test.com")
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=m_id_1,
        customer_id=c_id,
        amount=1000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
    )
    async_test_session.add_all([merchant, customer, tx])
    await async_test_session.flush()

    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    with pytest.raises(ValueError, match="Merchant ID mismatch"):
        await engine.evaluate_and_transition(
            session=async_test_session,
            transaction_id=tx.id,
            capability_result=cap_res,
            merchant_id=m_id_2,  # Mismatched merchant ID
        )


def test_11_air_gap_no_razorpay_http_execution(monkeypatch):
    """11. Air-gap Safety Test: Verifies PolicyEngine makes 0 external HTTP network calls."""
    def forbidden_http_call(*args, **kwargs):
        pytest.fail("PolicyEngine attempted to make an external HTTP network call!")

    monkeypatch.setattr("httpx.AsyncClient.post", forbidden_http_call, raising=False)
    monkeypatch.setattr("httpx.AsyncClient.get", forbidden_http_call, raising=False)

    evaluator = PolicyRuleEvaluator()
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        customer_id=str(uuid4()),
        amount=4000.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
        retry_count=0,
    )
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result = evaluator.evaluate(cap_res, tx)
    assert result.is_approved is True


def test_12_decimal_monetary_boundary_precision():
    """12. Money Safety Test: Verifies exact Decimal boundary checks for ₹50,000 cap."""
    from decimal import Decimal
    evaluator = PolicyRuleEvaluator()
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    # ₹50,000.00 exact -> Approved
    tx_exact = Transaction(
        id=str(uuid4()), merchant_id=str(uuid4()), customer_id=str(uuid4()),
        amount=Decimal("50000.00"), status="INTERVENTION_SELECTED", retry_count=0
    )
    res_exact = evaluator.evaluate(cap_res, tx_exact, candidate_probability=0.50)
    assert res_exact.is_approved is True

    # ₹50,000.01 -> Rejected (AMOUNT_EXCEEDS_CAP)
    tx_over = Transaction(
        id=str(uuid4()), merchant_id=str(uuid4()), customer_id=str(uuid4()),
        amount=Decimal("50000.01"), status="INTERVENTION_SELECTED", retry_count=0
    )
    res_over = evaluator.evaluate(cap_res, tx_over, candidate_probability=0.50)
    assert res_over.is_approved is False
    assert res_over.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP


def test_13_merchant_policy_clamped_to_global_defaults():
    """13. Hierarchy Test: Verifies custom merchant policy cannot weaken global safety bounds."""
    from decimal import Decimal
    evaluator = PolicyRuleEvaluator()
    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    # Merchant policy trying to allow ₹100,000 auto-action amount and 10 attempts
    permissive_merchant_policy = Policy(
        id=str(uuid4()),
        merchant_id=str(uuid4()),
        policy_version="v1.0-custom",
        max_recovery_attempts=10,       # Tried to exceed global limit of 3
        max_auto_action_amount=Decimal("100000.00"), # Tried to exceed global limit of 50,000
        min_recovery_probability=0.01,  # Tried to lower global limit of 0.15
        cooldown_hours=1,               # Tried to lower global limit of 24h
        is_active=True,
    )

    tx_60k = Transaction(
        id=str(uuid4()), merchant_id=permissive_merchant_policy.merchant_id, customer_id=str(uuid4()),
        amount=Decimal("60000.00"), status="INTERVENTION_SELECTED", retry_count=0
    )
    res = evaluator.evaluate(cap_res, tx_60k, policy=permissive_merchant_policy, candidate_probability=0.50)

    # Must be rejected because global ₹50,000 cap is enforced
    assert res.is_approved is False
    assert res.rejection_code == PolicyRejectionCode.AMOUNT_EXCEEDS_CAP


@pytest.mark.asyncio
async def test_14_logical_operation_key_contract_format(async_test_session: AsyncSession):
    """14. Contract Test: Verifies recovery_attempt logical_operation_key follows merchant_id:tx_id:cycle:action format."""
    engine = PolicyEngine()
    m_id = str(uuid4())
    c_id = str(uuid4())

    merchant = Merchant(id=m_id, name="Contract Test Merchant", email="ct@test.com", industry="SAAS")
    customer = Customer(id=c_id, merchant_id=m_id, email="ct_cust@test.com")
    tx = Transaction(
        id=str(uuid4()),
        merchant_id=m_id,
        customer_id=c_id,
        amount=2500.00,
        status="INTERVENTION_SELECTED",
        scenario_type="PAYMENT_FAILURE",
    )
    async_test_session.add_all([merchant, customer, tx])
    await async_test_session.flush()

    cap_res = helper_make_capability_result("PAYMENT_LINK", is_executable=True)

    result, updated_tx = await engine.evaluate_and_transition(
        session=async_test_session,
        transaction_id=tx.id,
        capability_result=cap_res,
        merchant_id=m_id,
        candidate_probability=0.80,
    )

    # Fetch recorded RecoveryAttempt from database
    stmt = select(RecoveryAttempt).where(RecoveryAttempt.transaction_id == tx.id)
    attempt_record = (await async_test_session.execute(stmt)).scalar_one()

    expected_key = f"{m_id}:{tx.id}:1:PAYMENT_LINK"
    assert attempt_record.logical_operation_key == expected_key
    assert attempt_record.execution_status == "PENDING"

