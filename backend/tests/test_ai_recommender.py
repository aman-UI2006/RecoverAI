"""
RecoverAI - Unit Tests for Step 13A, Step 13B & Step 13C AI Recommendation Service

Validates AIRecommendationResponse schema constraints, StructuredAIRecommender LLM integration via GroqLLMService high-level API,
candidate action enforcement, PII protection, deterministic fallback, air-gap safety isolation, decision context persistence,
and authoritative state transition to INTERVENTION_SELECTED.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, DecisionContext, RecoveryActionScore, AuditEvent
from backend.app.schemas.ai_recommendation import AIRecommendationResponse
from backend.app.schemas.diagnosis import DiagnosisResult, DiagnosisSource, FailureCategory
from backend.app.schemas.enrv import ENRVActionResult, ENRVCalculationResponse
from backend.app.schemas.state_machine import InvalidStateTransitionException
from backend.app.services.llm_service import GroqLLMService
from backend.app.ai.recommender import StructuredAIRecommender


# ==========================================
# STEP 13A TESTS: SCHEMA VALIDATION (1-7)
# ==========================================

def test_ai_recommendation_valid_response():
    """Test 1: Verify a valid response can be constructed and attributes populated correctly."""
    response = AIRecommendationResponse(
        recommended_action="PAYMENT_LINK",
        rationale_text="Soft decline detected due to insufficient funds; payment link provides frictionless retry path.",
        customer_message_template="Hi Customer, your transaction of INR 1,500 requires attention. Click here to complete payment.",
        confidence_score=0.88
    )
    assert response.recommended_action == "PAYMENT_LINK"
    assert "Soft decline" in response.rationale_text
    assert "Hi Customer" in response.customer_message_template
    assert response.confidence_score == 0.88


def test_ai_recommendation_confidence_lower_boundary():
    """Test 2: Verify confidence_score = 0.0 is accepted as valid lower boundary."""
    response = AIRecommendationResponse(
        recommended_action="NO_ACTION",
        rationale_text="Uncertain diagnosis.",
        customer_message_template="No message required.",
        confidence_score=0.0
    )
    assert response.confidence_score == 0.0


def test_ai_recommendation_confidence_upper_boundary():
    """Test 3: Verify confidence_score = 1.0 is accepted as valid upper boundary."""
    response = AIRecommendationResponse(
        recommended_action="WHATSAPP_REMINDER",
        rationale_text="Deterministic failure diagnosis.",
        customer_message_template="Your order is waiting.",
        confidence_score=1.0
    )
    assert response.confidence_score == 1.0


def test_ai_recommendation_confidence_below_zero():
    """Test 4: Verify confidence_score < 0.0 raises Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            rationale_text="Test rationale",
            customer_message_template="Test message",
            confidence_score=-0.01
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("confidence_score",) for err in errors)


def test_ai_recommendation_confidence_above_one():
    """Test 5: Verify confidence_score > 1.0 raises Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            rationale_text="Test rationale",
            customer_message_template="Test message",
            confidence_score=1.01
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("confidence_score",) for err in errors)


def test_ai_recommendation_missing_required_fields():
    """Test 6: Verify missing any required field causes Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        AIRecommendationResponse(
            rationale_text="Test rationale",
            customer_message_template="Test message",
            confidence_score=0.85
        )

    with pytest.raises(ValidationError):
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            customer_message_template="Test message",
            confidence_score=0.85
        )

    with pytest.raises(ValidationError):
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            rationale_text="Test rationale",
            confidence_score=0.85
        )

    with pytest.raises(ValidationError):
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            rationale_text="Test rationale",
            customer_message_template="Test message"
        )


def test_ai_recommendation_wrong_confidence_type():
    """Test 7: Verify non-numeric string or invalid type for confidence_score causes ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AIRecommendationResponse(
            recommended_action="PAYMENT_LINK",
            rationale_text="Test rationale",
            customer_message_template="Test message",
            confidence_score="not_a_number"
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("confidence_score",) for err in errors)


# ==========================================
# FIXTURES FOR STEP 13B & 13C RECOMMENDER
# ==========================================

@pytest.fixture
def mock_diagnosis():
    return DiagnosisResult(
        transaction_id="tx_12345",
        failure_code="BAD_REQUEST_PAYMENT_DECLINED",
        failure_category=FailureCategory.INSUFFICIENT_FUNDS.value,
        root_cause_explanation="Card issuer declined payment due to insufficient funds.",
        confidence_score=0.95,
        diagnosis_source=DiagnosisSource.RULE_ENGINE,
        requires_human_review=False
    )


@pytest.fixture
def mock_enrv_response():
    action1 = ENRVActionResult(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.75,
        amount_in_paise=50000,
        expected_gross_recovery_in_paise=37500,
        intervention_cost_in_paise=300,
        operational_cost_in_paise=50,
        expected_refund_cost_in_paise=0,
        total_cost_in_paise=350,
        expected_net_recovery_value_in_paise=37150,
        expected_net_recovery_value_rupees=371.50,
        rank=1
    )
    action2 = ENRVActionResult(
        action_type="RETRY",
        predicted_recovery_probability=0.40,
        amount_in_paise=50000,
        expected_gross_recovery_in_paise=20000,
        intervention_cost_in_paise=150,
        operational_cost_in_paise=20,
        expected_refund_cost_in_paise=0,
        total_cost_in_paise=170,
        expected_net_recovery_value_in_paise=19830,
        expected_net_recovery_value_rupees=198.30,
        rank=2
    )
    return ENRVCalculationResponse(
        transaction_id="tx_12345",
        merchant_id="merch_99",
        amount_in_paise=50000,
        best_action="PAYMENT_LINK",
        max_enrv_in_paise=37150,
        max_enrv_rupees=371.50,
        action_results=[action1, action2]
    )


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
async def diagnosed_transaction(in_memory_db: AsyncSession):
    """Creates sample Merchant, Customer, and Transaction in DIAGNOSED status."""
    merchant = Merchant(
        id="mch_rec_100",
        name="Rec Merchant",
        email="rec@example.com",
        industry="SaaS",
    )
    customer = Customer(
        id="cust_rec_200",
        merchant_id="mch_rec_100",
        email="cust_rec@example.com",
    )
    tx = Transaction(
        id="tx_rec_300",
        merchant_id="mch_rec_100",
        customer_id="cust_rec_200",
        amount=5000.00,
        currency="INR",
        status="DIAGNOSED",
        scenario_type="PAYMENT_FAILURE_RECOVERY",
    )
    in_memory_db.add(merchant)
    in_memory_db.add(customer)
    in_memory_db.add(tx)
    await in_memory_db.commit()
    return tx


# ==========================================
# STEP 13B TESTS: CORE RECOMMENDER (8-18)
# ==========================================

def test_step13b_1_valid_llm_recommendation(mock_diagnosis, mock_enrv_response):
    """Test 8 (Step 13B-1): Mock LLM service returning valid recommendation for valid candidate."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    mock_llm_output = {
        "recommended_action": "PAYMENT_LINK",
        "rationale_text": "Payment link provides optimal friction-free recovery path for soft decline.",
        "customer_message_template": "Please complete your payment of INR 500.",
        "confidence_score": 0.90
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_llm_output):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        assert res.recommended_action == "PAYMENT_LINK"
        assert res.confidence_score == 0.90
        assert "friction-free" in res.rationale_text


def test_step13b_2_unsupported_llm_action_fallback(mock_diagnosis, mock_enrv_response):
    """Test 9 (Step 13B-2): Mock LLM service returning unsupported action triggers top ENRV fallback."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    mock_llm_output = {
        "recommended_action": "REFUND",  # Unsupported action!
        "rationale_text": "Refund transaction immediately.",
        "customer_message_template": "Refund issued.",
        "confidence_score": 0.99
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_llm_output):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        assert res.recommended_action == "PAYMENT_LINK"  # Top ENRV fallback
        assert "Deterministic ENRV Fallback" in res.rationale_text
        assert res.confidence_score == 0.50


def test_step13b_3_invalid_json_fallback(mock_diagnosis, mock_enrv_response):
    """Test 10 (Step 13B-3): Empty/None output from LLM service triggers fallback without crash."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    with patch.object(llm_service, "generate_structured_recommendation", return_value=None):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        assert res.recommended_action == "PAYMENT_LINK"
        assert res.confidence_score == 0.50


def test_step13b_4_llm_exception_fallback(mock_diagnosis, mock_enrv_response):
    """Test 11 (Step 13B-4): Groq API exception in LLM service triggers deterministic fallback."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    with patch.object(llm_service, "generate_structured_recommendation", side_effect=Exception("Groq API Timeout")):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        assert res.recommended_action == "PAYMENT_LINK"
        assert "LLM service unavailable" in res.rationale_text


def test_step13b_5_pydantic_validation_failure_fallback(mock_diagnosis, mock_enrv_response):
    """Test 12 (Step 13B-5): Structurally invalid LLM payload triggers fallback."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    mock_llm_output = {
        "recommended_action": "PAYMENT_LINK",
        # Missing rationale_text and customer_message_template!
        "confidence_score": 2.5  # Invalid confidence!
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_llm_output):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        assert res.recommended_action == "PAYMENT_LINK"
        assert res.confidence_score == 0.50


def test_step13b_6_pii_protection(mock_diagnosis, mock_enrv_response):
    """Test 13 (Step 13B-6): Verify synthetic PII values are redacted from prompt payload passed to GroqLLMService."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    sensitive_context = {
        "email": "sensitive_user@example.com",
        "phone": "9876543210",
        "card_number": "4111222233334444",
        "secret_token": "bearer_secret_xyz123",
        "safe_attr": "desktop_browser"
    }

    mock_llm_output = {
        "recommended_action": "PAYMENT_LINK",
        "rationale_text": "Safe rationale.",
        "customer_message_template": "Safe message.",
        "confidence_score": 0.85
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_llm_output) as mock_gen:
        _ = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response,
            decision_context=sensitive_context
        )

        call_args = mock_gen.call_args
        prompt_messages = call_args.kwargs["prompt_messages"]
        prompt_content = prompt_messages[1]["content"]

        assert "sensitive_user@example.com" not in prompt_content
        assert "9876543210" not in prompt_content
        assert "4111222233334444" not in prompt_content
        assert "bearer_secret_xyz123" not in prompt_content
        assert "[REDACTED_PII]" in prompt_content
        assert "desktop_browser" in prompt_content


def test_step13b_7_enrv_candidate_enforcement(mock_diagnosis, mock_enrv_response):
    """Test 14 (Step 13B-7): LLM attempting action outside candidate set triggers fallback."""
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    mock_llm_output = {
        "recommended_action": "WHATSAPP_REMINDER",  # Not in candidates (PAYMENT_LINK, RETRY)
        "rationale_text": "Send WhatsApp reminder.",
        "customer_message_template": "Reminder message.",
        "confidence_score": 0.80
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_llm_output):
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert res.recommended_action == "PAYMENT_LINK"  # Fallback
        assert "Deterministic ENRV Fallback" in res.rationale_text


def test_step13b_8_top_enrv_fallback_exact_match(mock_diagnosis):
    """Test 15 (Step 13B-8): Verify exact top ENRV candidate is returned on forced fallback."""
    unconfigured_llm = GroqLLMService(api_key="")
    recommender = StructuredAIRecommender(llm_service=unconfigured_llm)

    action1 = ENRVActionResult(
        action_type="MANUAL_OUTREACH",
        predicted_recovery_probability=0.90,
        amount_in_paise=100000,
        expected_gross_recovery_in_paise=90000,
        intervention_cost_in_paise=500,
        operational_cost_in_paise=100,
        expected_refund_cost_in_paise=0,
        total_cost_in_paise=600,
        expected_net_recovery_value_in_paise=89400,
        expected_net_recovery_value_rupees=894.00,
        rank=1
    )
    action2 = ENRVActionResult(
        action_type="PAYMENT_LINK",
        predicted_recovery_probability=0.70,
        amount_in_paise=100000,
        expected_gross_recovery_in_paise=70000,
        intervention_cost_in_paise=300,
        operational_cost_in_paise=50,
        expected_refund_cost_in_paise=0,
        total_cost_in_paise=350,
        expected_net_recovery_value_in_paise=69650,
        expected_net_recovery_value_rupees=696.50,
        rank=2
    )
    custom_enrv = ENRVCalculationResponse(
        transaction_id="tx_12345",
        merchant_id="merch_99",
        amount_in_paise=100000,
        best_action="MANUAL_OUTREACH",
        max_enrv_in_paise=89400,
        max_enrv_rupees=894.00,
        action_results=[action1, action2]
    )

    res = recommender.generate_recommendation(
        diagnosis=mock_diagnosis,
        enrv_response=custom_enrv
    )

    assert res.recommended_action == "MANUAL_OUTREACH"
    assert "MANUAL_OUTREACH" in res.rationale_text


def test_step13b_9_no_state_mutation(mock_diagnosis, mock_enrv_response):
    """Test 16 (Step 13B-9): Verify recommender generate_recommendation invocation performs ZERO state transition."""
    unconfigured_llm = GroqLLMService(api_key="")
    recommender = StructuredAIRecommender(llm_service=unconfigured_llm)

    with patch("backend.app.services.state_transition_service.StateTransitionService.transition") as mock_transition:
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        mock_transition.assert_not_called()


def test_step13b_10_no_razorpay_external_execution(mock_diagnosis, mock_enrv_response):
    """Test 17 (Step 13B-10): Verify recommender makes zero calls to external payment APIs or adapters."""
    unconfigured_llm = GroqLLMService(api_key="")
    recommender = StructuredAIRecommender(llm_service=unconfigured_llm)

    with patch("httpx.AsyncClient.post") as mock_httpx_post:
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        assert isinstance(res, AIRecommendationResponse)
        mock_httpx_post.assert_not_called()


def test_recommender_uses_llm_service_abstraction(mock_diagnosis, mock_enrv_response):
    """
    Test 18 (Architectural Boundary Test): Verify StructuredAIRecommender calls GroqLLMService
    public method generate_structured_recommendation without accessing low-level client attributes.
    """
    llm_service = GroqLLMService(api_key="gsk_mock_valid_key_123")
    recommender = StructuredAIRecommender(llm_service=llm_service)

    mock_output = {
        "recommended_action": "PAYMENT_LINK",
        "rationale_text": "High-level API abstraction test rationale.",
        "customer_message_template": "Abstraction test template.",
        "confidence_score": 0.88
    }

    with patch.object(llm_service, "generate_structured_recommendation", return_value=mock_output) as mock_service_method:
        res = recommender.generate_recommendation(
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response
        )

        # Assert public service method was called exactly once
        mock_service_method.assert_called_once()
        assert res.recommended_action == "PAYMENT_LINK"
        assert res.confidence_score == 0.88


# ==========================================
# STEP 13C TESTS: STATE TRANSITION & PERSISTENCE (19-22)
# ==========================================

@pytest.mark.asyncio
async def test_step13c_1_recommend_and_transition_success(
    in_memory_db: AsyncSession,
    diagnosed_transaction: Transaction,
    mock_diagnosis: DiagnosisResult,
    mock_enrv_response: ENRVCalculationResponse,
):
    """Test 19 (Step 13C-1): Verify successful recommend_and_transition execution."""
    recommender = StructuredAIRecommender(llm_service=GroqLLMService(api_key=""))
    mock_diagnosis.transaction_id = diagnosed_transaction.id
    mock_enrv_response.transaction_id = diagnosed_transaction.id
    mock_enrv_response.merchant_id = diagnosed_transaction.merchant_id

    rec, audit_event = await recommender.recommend_and_transition(
        session=in_memory_db,
        transaction_id=diagnosed_transaction.id,
        diagnosis=mock_diagnosis,
        enrv_response=mock_enrv_response,
        merchant_id=diagnosed_transaction.merchant_id,
    )

    # 1. Assert recommendation response returned
    assert isinstance(rec, AIRecommendationResponse)
    assert rec.recommended_action == "PAYMENT_LINK"

    # 2. Assert transaction state mutated to INTERVENTION_SELECTED
    stmt_tx = select(Transaction).where(Transaction.id == diagnosed_transaction.id)
    updated_tx = (await in_memory_db.execute(stmt_tx)).scalar_one()
    assert updated_tx.status == "INTERVENTION_SELECTED"

    # 3. Assert AuditEvent created
    assert audit_event is not None
    assert audit_event.transaction_id == diagnosed_transaction.id
    assert audit_event.event_type == "STATE_TRANSITION"

    # 4. Assert DecisionContext & RecoveryActionScore records persisted
    stmt_ctx = select(DecisionContext).where(DecisionContext.transaction_id == diagnosed_transaction.id)
    ctx = (await in_memory_db.execute(stmt_ctx)).scalar_one_or_none()
    assert ctx is not None
    assert ctx.model_version == "v1.0"

    stmt_scores = select(RecoveryActionScore).where(RecoveryActionScore.decision_context_id == ctx.id)
    scores = (await in_memory_db.execute(stmt_scores)).scalars().all()
    assert len(scores) == 2


@pytest.mark.asyncio
async def test_step13c_2_transaction_not_found(
    in_memory_db: AsyncSession,
    mock_diagnosis: DiagnosisResult,
    mock_enrv_response: ENRVCalculationResponse,
):
    """Test 20 (Step 13C-2): Verify passing non-existent transaction ID raises ValueError."""
    recommender = StructuredAIRecommender(llm_service=GroqLLMService(api_key=""))

    with pytest.raises(ValueError) as exc_info:
        await recommender.recommend_and_transition(
            session=in_memory_db,
            transaction_id="tx_nonexistent_999",
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response,
        )

    assert "Transaction with ID 'tx_nonexistent_999' not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_step13c_3_merchant_mismatch_error(
    in_memory_db: AsyncSession,
    diagnosed_transaction: Transaction,
    mock_diagnosis: DiagnosisResult,
    mock_enrv_response: ENRVCalculationResponse,
):
    """Test 21 (Step 13C-3): Verify passing mismatched merchant_id raises ValueError."""
    recommender = StructuredAIRecommender(llm_service=GroqLLMService(api_key=""))

    with pytest.raises(ValueError) as exc_info:
        await recommender.recommend_and_transition(
            session=in_memory_db,
            transaction_id=diagnosed_transaction.id,
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response,
            merchant_id="mch_wrong_merchant_888",
        )

    assert "Merchant ID mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_step13c_4_invalid_state_transition_fails(
    in_memory_db: AsyncSession,
    diagnosed_transaction: Transaction,
    mock_diagnosis: DiagnosisResult,
    mock_enrv_response: ENRVCalculationResponse,
):
    """Test 22 (Step 13C-4): Verify attempting transition from invalid status raises InvalidStateTransitionException."""
    recommender = StructuredAIRecommender(llm_service=GroqLLMService(api_key=""))
    # Manually set status to EXECUTING (invalid source state for INTERVENTION_SELECTED)
    diagnosed_transaction.status = "EXECUTING"
    await in_memory_db.commit()

    with pytest.raises(InvalidStateTransitionException) as exc_info:
        await recommender.recommend_and_transition(
            session=in_memory_db,
            transaction_id=diagnosed_transaction.id,
            diagnosis=mock_diagnosis,
            enrv_response=mock_enrv_response,
        )

    assert exc_info.value.state_from == "EXECUTING"
    assert exc_info.value.state_to == "INTERVENTION_SELECTED"
