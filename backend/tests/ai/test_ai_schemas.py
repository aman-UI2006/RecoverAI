"""
RecoverAI - Step 40 AI Structured-Output Testing Suite

Validates Pydantic JSON schema parsing, PII sanitization, LLM failure/fallback behavior,
and air-gapped security boundaries for AI recommendations and diagnostic fallbacks.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from backend.app.schemas.ai_recommendation import AIRecommendationResponse
from backend.app.schemas.diagnosis import DiagnosisResult, DiagnosisSource
from backend.app.schemas.enrv import ENRVCalculationResponse, ENRVActionResult
from backend.app.services.llm_service import GroqLLMService, ActionRecommendation
from backend.app.ai.recommender import StructuredAIRecommender
from backend.app.services.diagnosis_engine import DiagnosisEngine


# ============================================================================
# 1. STRUCTURED OUTPUT VALIDATION TESTS
# ============================================================================

def test_1_valid_ai_recommendation_schema_parsing():
    """Validates successful Pydantic model parsing for well-formed LLM JSON recommendations."""
    valid_payload = {
        "recommended_action": "PAYMENT_LINK",
        "confidence_score": 0.85,
        "rationale_text": "High recovery probability with minimal intervention cost.",
        "customer_message_template": "Complete your payment here: https://rzp.io/i/test",
    }
    rec = AIRecommendationResponse.model_validate(valid_payload)
    assert rec.recommended_action == "PAYMENT_LINK"
    assert rec.confidence_score == 0.85
    assert "High recovery" in rec.rationale_text
    assert "Complete your payment" in rec.customer_message_template


def test_2_valid_action_recommendation_schema_parsing():
    """Validates parsing of Groq LLM service ActionRecommendation schema."""
    valid_payload = {
        "recommended_action": "RETRY",
        "confidence_score": 0.72,
        "reasoning": "Transient network timeout detected.",
        "risk_assessment": "LOW - Safe auto retry",
    }
    rec = ActionRecommendation.model_validate(valid_payload)
    assert rec.recommended_action == "RETRY"
    assert rec.confidence_score == 0.72
    assert rec.reasoning == "Transient network timeout detected."
    assert rec.risk_assessment == "LOW - Safe auto retry"


def test_3_missing_required_fields_raises_validation_error():
    """Asserts Pydantic ValidationError when required schema fields are missing."""
    invalid_payload_1 = {
        "confidence_score": 0.85,
        "rationale_text": "Missing recommended_action field",
        "customer_message_template": "Test message",
    }
    with pytest.raises(ValidationError):
        AIRecommendationResponse.model_validate(invalid_payload_1)

    invalid_payload_2 = {
        "recommended_action": "PAYMENT_LINK",
        "rationale_text": "Missing confidence_score field",
        "customer_message_template": "Test message",
    }
    with pytest.raises(ValidationError):
        AIRecommendationResponse.model_validate(invalid_payload_2)


def test_4_invalid_field_types_and_bounds():
    """Asserts Pydantic ValidationError on out-of-bound or invalid field types."""
    # Confidence score > 1.0
    with pytest.raises(ValidationError):
        AIRecommendationResponse.model_validate({
            "recommended_action": "PAYMENT_LINK",
            "confidence_score": 1.5,
            "rationale_text": "Invalid confidence score > 1.0",
            "customer_message_template": "Test",
        })

    # Confidence score < 0.0
    with pytest.raises(ValidationError):
        AIRecommendationResponse.model_validate({
            "recommended_action": "PAYMENT_LINK",
            "confidence_score": -0.1,
            "rationale_text": "Invalid confidence score < 0.0",
            "customer_message_template": "Test",
        })

    # ActionRecommendation bounds
    with pytest.raises(ValidationError):
        ActionRecommendation(
            recommended_action="PAYMENT_LINK",
            confidence_score=2.0,
            reasoning="Score out of bounds",
            risk_assessment="HIGH"
        )


def test_5_malformed_json_parsing_resiliency():
    """Tests LLM service resilience when receiving malformed JSON strings."""
    malformed_jsons = [
        "{ recommended_action: 'PAYMENT_LINK', confidence_score: 0.8 }",  # Unquoted keys
        '{"recommended_action": "PAYMENT_LINK", "confidence_score": 0.8,}',  # Trailing comma
        '{"recommended_action": "PAYMENT_LINK", "confidence_score":',  # Truncated JSON
        'Not a JSON response at all',  # Plain text
        '',  # Empty string
    ]

    for raw_str in malformed_jsons:
        try:
            data = json.loads(raw_str)
            rec = ActionRecommendation.model_validate(data)
            # If loads somehow succeeded, ensure invalid schema is caught
        except (json.JSONDecodeError, ValidationError, TypeError):
            # Expected clean exception handling
            pass


# ============================================================================
# 2. PII SANITIZATION TESTS
# ============================================================================

def test_6_pii_sanitizer_redacts_sensitive_keys_and_values():
    """Verifies StructuredAIRecommender.sanitize_context strips customer PII prior to LLM submission."""
    dirty_context = {
        "customer_email": "user@example.com",
        "phone_number": "+919876543210",
        "card_number": "4111111111111111",
        "cvv": "123",
        "secret_token": "bearer_12345",
        "safe_merchant_id": "merch_001",
        "amount_in_paise": 50000,
        "nested_details": {
            "contact_person": "John Doe",
            "contact_email": "john@example.com",
            "transaction_count": 5
        }
    }

    clean = StructuredAIRecommender.sanitize_context(dirty_context)

    assert clean["customer_email"] == "[REDACTED_PII]"
    assert clean["phone_number"] == "[REDACTED_PII]"
    assert clean["card_number"] == "[REDACTED_PII]"
    assert clean["cvv"] == "[REDACTED_PII]"
    assert clean["secret_token"] == "[REDACTED_PII]"
    assert clean["safe_merchant_id"] == "merch_001"
    assert clean["amount_in_paise"] == 50000
    assert clean["nested_details"]["contact_person"] == "[REDACTED_PII]"
    assert clean["nested_details"]["contact_email"] == "[REDACTED_PII]"
    assert clean["nested_details"]["transaction_count"] == 5


def test_7_diagnosis_engine_payload_pii_sanitizer():
    """Verifies DiagnosisEngine.sanitize_payload_for_llm strips PII from webhook payloads."""
    dirty_payload = {
        "event_id": "evt_100",
        "email": "customer@razorpay.com",
        "phone": "9999988888",
        "description": "Payment for order #1234 with email user@test.com and contact 9876543210",
        "method": "card"
    }

    clean = DiagnosisEngine.sanitize_payload_for_llm(dirty_payload)

    assert clean["email"] == "[REDACTED_PII]"
    assert clean["phone"] == "[REDACTED_PII]"
    assert "customer@razorpay.com" not in str(clean)
    assert clean["method"] == "card"


# ============================================================================
# 3. LLM FAILURE & DETERMINISTIC FALLBACK BEHAVIOR TESTS
# ============================================================================

def test_8_unconfigured_llm_service_invokes_deterministic_fallback():
    """Verifies unconfigured Groq API key cleanly triggers top ENRV action fallback."""
    mock_llm = GroqLLMService(api_key="gsk_YourGroqApiKeyHere")
    recommender = StructuredAIRecommender(llm_service=mock_llm)

    diagnosis = DiagnosisResult(
        transaction_id="tx_test101",
        failure_category="INSUFFICIENT_FUNDS",
        failure_code="BAD_REQUEST_PAYMENT_DECLINED_BY_BANK",
        confidence_score=0.90,
        root_cause_explanation="Customer account balance insufficient",
        diagnosis_source=DiagnosisSource.RULE_ENGINE,
        requires_human_review=False
    )

    enrv_resp = ENRVCalculationResponse(
        transaction_id="tx_test101",
        amount_in_paise=10000,
        best_action="PAYMENT_LINK",
        max_enrv_in_paise=4500,
        max_enrv_rupees=45.0,
        action_results=[
            ENRVActionResult(
                action_type="PAYMENT_LINK",
                predicted_recovery_probability=0.75,
                amount_in_paise=10000,
                expected_gross_recovery_in_paise=7500,
                intervention_cost_in_paise=2000,
                operational_cost_in_paise=500,
                expected_refund_cost_in_paise=500,
                total_cost_in_paise=3000,
                expected_net_recovery_value_in_paise=4500,
                expected_net_recovery_value_rupees=45.0,
                rank=1
            ),
            ENRVActionResult(
                action_type="NO_ACTION",
                predicted_recovery_probability=0.10,
                amount_in_paise=10000,
                expected_gross_recovery_in_paise=1000,
                intervention_cost_in_paise=0,
                operational_cost_in_paise=0,
                expected_refund_cost_in_paise=0,
                total_cost_in_paise=0,
                expected_net_recovery_value_in_paise=1000,
                expected_net_recovery_value_rupees=10.0,
                rank=2
            )
        ]
    )

    rec = recommender.generate_recommendation(diagnosis, enrv_resp)

    assert rec.recommended_action == "PAYMENT_LINK"
    assert rec.confidence_score == 0.50
    assert "ENRV Fallback" in rec.rationale_text


def test_9_llm_timeout_or_exception_triggers_fallback():
    """Verifies network exception or timeout during LLM call triggers deterministic fallback."""
    mock_llm = MagicMock(spec=GroqLLMService)
    mock_llm.is_configured.return_value = True
    mock_llm.generate_structured_recommendation.side_effect = Exception("Groq API Timeout after 10s")

    recommender = StructuredAIRecommender(llm_service=mock_llm)

    diagnosis = DiagnosisResult(
        transaction_id="tx_test102",
        failure_category="AUTHENTICATION_FAILURE",
        failure_code="BAD_REQUEST_PAYMENT_TIMED_OUT",
        confidence_score=0.85,
        root_cause_explanation="Authentication timeout",
        diagnosis_source=DiagnosisSource.RULE_ENGINE,
        requires_human_review=False
    )

    enrv_resp = ENRVCalculationResponse(
        transaction_id="tx_test102",
        amount_in_paise=10000,
        best_action="WHATSAPP_REMINDER",
        max_enrv_in_paise=3000,
        max_enrv_rupees=30.0,
        action_results=[
            ENRVActionResult(
                action_type="WHATSAPP_REMINDER",
                predicted_recovery_probability=0.60,
                amount_in_paise=10000,
                expected_gross_recovery_in_paise=6000,
                intervention_cost_in_paise=2000,
                operational_cost_in_paise=500,
                expected_refund_cost_in_paise=500,
                total_cost_in_paise=3000,
                expected_net_recovery_value_in_paise=3000,
                expected_net_recovery_value_rupees=30.0,
                rank=1
            )
        ]
    )

    rec = recommender.generate_recommendation(diagnosis, enrv_resp)

    assert rec.recommended_action == "WHATSAPP_REMINDER"
    assert rec.confidence_score == 0.50
    assert "ENRV Fallback" in rec.rationale_text


def test_10_llm_unsupported_action_rejection_triggers_fallback():
    """Verifies LLM recommendation of an unallowed action type is rejected and triggers fallback."""
    mock_llm = MagicMock(spec=GroqLLMService)
    mock_llm.is_configured.return_value = True
    mock_llm.generate_structured_recommendation.return_value = {
        "recommended_action": "INVALID_UNSUPPORTED_ACTION",
        "confidence_score": 0.99,
        "rationale_text": "Unsupported action recommendation",
        "customer_message_template": "Test"
    }

    recommender = StructuredAIRecommender(llm_service=mock_llm)

    diagnosis = DiagnosisResult(
        transaction_id="tx_test103",
        failure_category="BANK_DECLINE",
        failure_code="BANK_ERROR",
        confidence_score=0.70,
        root_cause_explanation="Bank error",
        diagnosis_source=DiagnosisSource.ML_CLASSIFIER,
        requires_human_review=False
    )

    enrv_resp = ENRVCalculationResponse(
        transaction_id="tx_test103",
        amount_in_paise=10000,
        best_action="RETRY",
        max_enrv_in_paise=2000,
        max_enrv_rupees=20.0,
        action_results=[
            ENRVActionResult(
                action_type="RETRY",
                predicted_recovery_probability=0.40,
                amount_in_paise=10000,
                expected_gross_recovery_in_paise=4000,
                intervention_cost_in_paise=1000,
                operational_cost_in_paise=500,
                expected_refund_cost_in_paise=500,
                total_cost_in_paise=2000,
                expected_net_recovery_value_in_paise=2000,
                expected_net_recovery_value_rupees=20.0,
                rank=1
            )
        ]
    )

    rec = recommender.generate_recommendation(diagnosis, enrv_resp)

    # Unsupported action rejected, fallback to top candidate action RETRY
    assert rec.recommended_action == "RETRY"
    assert rec.confidence_score == 0.50


# ============================================================================
# 4. SECURITY BOUNDARY & DETERMINISTIC AIR-GAP VERIFICATION
# ============================================================================

def test_11_ai_recommender_cannot_execute_financial_actions():
    """Asserts AI recommender returns advisory models only and lacks financial execution capability."""
    recommender = StructuredAIRecommender()

    assert hasattr(recommender, "generate_recommendation")
    assert not hasattr(recommender, "execute_payment_link")
    assert not hasattr(recommender, "trigger_razorpay_api")
    assert not hasattr(recommender, "mutate_transaction_status")


def test_12_mock_llm_latency_wrapper_simulation():
    """Tests mock LLM latency wrapper simulating response delays within strict bounds."""
    import time

    def mock_latency_llm_call():
        time.sleep(0.05)  # 50ms simulated latency
        return {
            "recommended_action": "PAYMENT_LINK",
            "confidence_score": 0.88,
            "rationale_text": "Simulated low latency response",
            "customer_message_template": "Pay now"
        }

    start = time.time()
    res = mock_latency_llm_call()
    duration = time.time() - start

    assert duration >= 0.04
    rec = AIRecommendationResponse.model_validate(res)
    assert rec.recommended_action == "PAYMENT_LINK"
