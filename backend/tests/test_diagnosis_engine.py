"""
RecoverAI - Diagnosis Engine Test Suite (Step 11)

Verifies all 4 precedence levels (Rule Engine -> ML Classifier -> LLM Fallback -> Human Review Fallback),
state transition to DIAGNOSED via StateTransitionService, PII sanitization, database persistence,
and multi-tenant isolation.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, Diagnosis, AuditEvent
from backend.app.schemas.diagnosis import (
    DiagnosisRequest,
    DiagnosisResult,
    DiagnosisSource,
    FailureCategory,
)
from backend.app.schemas.state_machine import InvalidStateTransitionException
from backend.app.services.diagnosis_engine import DiagnosisEngine
from backend.app.services.llm_service import GroqLLMService, ActionRecommendation


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
async def at_risk_transaction(in_memory_db: AsyncSession):
    """Creates sample Merchant, Customer, and Transaction in AT_RISK status."""
    merchant = Merchant(
        id="mch_diag_100",
        name="Diag Merchant",
        email="diag@example.com",
        industry="SaaS",
    )
    customer = Customer(
        id="cust_diag_200",
        merchant_id="mch_diag_100",
        email="cust_diag@example.com",
    )
    tx = Transaction(
        id="tx_diag_300",
        merchant_id="mch_diag_100",
        customer_id="cust_diag_200",
        amount=2500.00,
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
async def test_1_level_1_rule_engine_diagnosis():
    """Verifies Level 1 rule engine deterministic lookup match."""
    req = DiagnosisRequest(
        transaction_id="tx_test_101",
        failure_code="BAD_REQUEST_PAYMENT_OTP_VALIDATION_FAILED",
    )
    res = await DiagnosisEngine.diagnose_root_cause(req)
    assert res.diagnosis_source == DiagnosisSource.RULE_ENGINE
    assert res.failure_category == FailureCategory.AUTHENTICATION_FAILURE.value
    assert res.confidence_score == 1.0
    assert not res.requires_human_review


@pytest.mark.asyncio
async def test_2_level_2_ml_classifier_diagnosis():
    """Verifies Level 2 ML classifier heuristic pattern match."""
    req = DiagnosisRequest(
        transaction_id="tx_test_102",
        failure_code="CUSTOM_GATEWAY_TIMEOUT_ERR_504",
        error_description="Gateway response timed out while contacting processing bank",
    )
    res = await DiagnosisEngine.diagnose_root_cause(req)
    assert res.diagnosis_source == DiagnosisSource.ML_CLASSIFIER
    assert res.failure_category == FailureCategory.TECHNICAL_TIMEOUT.value
    assert res.confidence_score >= 0.60
    assert not res.requires_human_review


@pytest.mark.asyncio
async def test_9_level_2_xgboost_model_artifact_invocation():
    """Verifies Level 2 genuinely loads and executes trained XGBoost multi-class joblib artifact."""
    from backend.app.ml.diagnosis_classifier import MLDiagnosisClassifier
    assert MLDiagnosisClassifier.load_model() is True
    assert MLDiagnosisClassifier._is_loaded is True
    assert MLDiagnosisClassifier._model is not None

    req = DiagnosisRequest(
        transaction_id="tx_xgb_diag_109",
        failure_code="AMBIGUOUS_DECLINE_CODE_X",
        feature_vector=[0.5, 2.0, 3.4, 50000.0, 10.8, 14.0, 2.0, 1.0, 0.0],
    )
    res = await DiagnosisEngine.diagnose_root_cause(req)
    assert res.diagnosis_source == DiagnosisSource.ML_CLASSIFIER
    assert "XGBoost Multi-Class Classifier" in res.root_cause_explanation
    assert res.confidence_score >= 0.0


@pytest.mark.asyncio
async def test_3_level_3_llm_fallback_diagnosis():
    """Verifies Level 3 structured LLM fallback diagnosis when rule and ML yield no match."""
    mock_llm = AsyncMock(spec=GroqLLMService)
    mock_llm.generate_recovery_recommendation.return_value = ActionRecommendation(
        recommended_action="RECOVERY_MESSAGE",
        confidence_score=0.82,
        reasoning="BANK_DECLINE: The issuing bank rejected the mandate signature due to temporary auth limits.",
        risk_assessment="LOW",
    )

    req = DiagnosisRequest(
        transaction_id="tx_test_103",
        failure_code="ERR_UNKNOWN_BANK_CODE_99",
        error_description="Custom unclassified bank response code",
        raw_payload={"email": "user@test.com", "card_number": "4111222233334444"},
    )
    res = await DiagnosisEngine.diagnose_root_cause(req, llm_service=mock_llm)
    assert res.diagnosis_source == DiagnosisSource.LLM_FALLBACK
    assert res.failure_category == FailureCategory.BANK_DECLINE.value
    assert res.confidence_score == 0.82
    assert not res.requires_human_review


@pytest.mark.asyncio
async def test_4_level_4_human_review_fallback():
    """Verifies Level 4 human review fallback when LLM fails or is unavailable."""
    req = DiagnosisRequest(
        transaction_id="tx_test_104",
        failure_code="UNCLASSIFIABLE_RANDOM_STRING_XYZ",
    )
    res = await DiagnosisEngine.diagnose_root_cause(req)
    assert res.diagnosis_source == DiagnosisSource.HUMAN_REVIEW_FALLBACK
    assert res.failure_category == FailureCategory.UNKNOWN_DECLINE.value
    assert res.confidence_score == 0.0
    assert res.requires_human_review


@pytest.mark.asyncio
async def test_5_pii_sanitization():
    """Verifies payload sanitization for LLM integration."""
    raw_payload = {
        "email": "john.doe@example.com",
        "phone": "9876543210",
        "secret_token": "sk_test_12345",
        "error_msg": "User john.doe@example.com failed auth with phone 9876543210",
    }
    sanitized = DiagnosisEngine.sanitize_payload_for_llm(raw_payload)
    assert sanitized["email"] == "[REDACTED_PII]"
    assert sanitized["phone"] == "[REDACTED_PII]"
    assert sanitized["secret_token"] == "[REDACTED_PII]"
    assert "[REDACTED_EMAIL]" in sanitized["error_msg"]
    assert "[REDACTED_PHONE]" in sanitized["error_msg"]


@pytest.mark.asyncio
async def test_6_diagnose_and_transition_integration(in_memory_db: AsyncSession, at_risk_transaction: Transaction):
    """Verifies end-to-end diagnosis, DB persistence, and state transition to DIAGNOSED."""
    req = DiagnosisRequest(
        transaction_id=at_risk_transaction.id,
        merchant_id="mch_diag_100",
        failure_code="BAD_REQUEST_PAYMENT_CARD_EXPIRED",
    )

    diag_res, audit_event = await DiagnosisEngine.diagnose_and_transition(
        session=in_memory_db,
        request=req,
    )

    # 1. Verify DiagnosisResult
    assert diag_res.failure_category == FailureCategory.EXPIRED_CARD.value

    # 2. Verify AuditEvent return metadata
    assert audit_event.state_from == "AT_RISK"
    assert audit_event.state_to == "DIAGNOSED"

    # 3. Verify Transaction DB status updated
    await in_memory_db.refresh(at_risk_transaction)
    assert at_risk_transaction.status == "DIAGNOSED"

    # 4. Verify Diagnosis row saved to DB
    stmt_diag = select(Diagnosis).where(Diagnosis.transaction_id == at_risk_transaction.id)
    diag_row = (await in_memory_db.execute(stmt_diag)).scalar_one()
    assert diag_row.failure_code == "BAD_REQUEST_PAYMENT_CARD_EXPIRED"
    assert diag_row.failure_category == FailureCategory.EXPIRED_CARD.value
    assert diag_row.diagnosis_source == DiagnosisSource.RULE_ENGINE.value

    # 5. Verify AuditEvent created with hash chaining
    stmt_audit = select(AuditEvent).where(AuditEvent.transaction_id == at_risk_transaction.id)
    audit_row = (await in_memory_db.execute(stmt_audit)).scalar_one()
    assert audit_row.event_type == "STATE_TRANSITION"
    assert audit_row.state_from == "AT_RISK"
    assert audit_row.state_to == "DIAGNOSED"


@pytest.mark.asyncio
async def test_7_multi_tenant_merchant_mismatch_raises_error(in_memory_db: AsyncSession, at_risk_transaction: Transaction):
    """Verifies that unauthorized merchant ID mismatch raises ValueError, creates zero DB records, and leaves status AT_RISK."""
    req = DiagnosisRequest(
        transaction_id=at_risk_transaction.id,
        merchant_id="mch_UNAUTHORIZED_999",
        failure_code="BAD_REQUEST_PAYMENT_CARD_EXPIRED",
    )

    with pytest.raises(ValueError, match="Merchant ID mismatch for transaction"):
        await DiagnosisEngine.diagnose_and_transition(
            session=in_memory_db,
            request=req,
        )

    # Verify status remains AT_RISK
    await in_memory_db.refresh(at_risk_transaction)
    assert at_risk_transaction.status == "AT_RISK"

    # Verify zero diagnoses created
    stmt_diag = select(Diagnosis).where(Diagnosis.transaction_id == at_risk_transaction.id)
    diag_rows = (await in_memory_db.execute(stmt_diag)).scalars().all()
    assert len(diag_rows) == 0


@pytest.mark.asyncio
async def test_8_invalid_state_transition_rejected(in_memory_db: AsyncSession, at_risk_transaction: Transaction):
    """Verifies that attempting diagnosis on a STOPPED transaction raises InvalidStateTransitionException."""
    at_risk_transaction.status = "STOPPED"
    await in_memory_db.commit()

    req = DiagnosisRequest(
        transaction_id=at_risk_transaction.id,
        merchant_id="mch_diag_100",
        failure_code="BAD_REQUEST_PAYMENT_CARD_EXPIRED",
    )

    with pytest.raises(InvalidStateTransitionException):
        await DiagnosisEngine.diagnose_and_transition(
            session=in_memory_db,
            request=req,
        )
