import pytest
from unittest.mock import MagicMock, patch
import groq

from backend.app.core.config import Settings
from backend.app.services.llm_service import GroqLLMService, ActionRecommendation


def test_groq_config_loading():
    """Verify Groq settings load default values correctly."""
    custom_settings = Settings(
        GROQ_API_KEY="gsk_test_key_12345",
        GROQ_BASE_URL="https://api.groq.com/openai/v1",
        GROQ_MODEL="llama-3.3-70b-versatile"
    )
    assert custom_settings.GROQ_API_KEY == "gsk_test_key_12345"
    assert custom_settings.GROQ_BASE_URL == "https://api.groq.com/openai/v1"
    assert custom_settings.GROQ_MODEL == "llama-3.3-70b-versatile"


def test_groq_service_initialization_and_unconfigured():
    """Verify GroqLLMService detects unconfigured key and raises ValueError when accessing client directly."""
    service = GroqLLMService(api_key="gsk_YourGroqApiKeyHere")
    assert service.is_configured() is False
    with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
        _ = service.client


def test_groq_service_fallback_when_unconfigured():
    """Verify unconfigured Groq service returns deterministic fallback recommendation."""
    service = GroqLLMService(api_key=None)
    recommendation = service.generate_recovery_recommendation(
        failure_category="CARD_FAILURE",
        failure_code="INSUFFICIENT_FUNDS",
        amount=1500.00,
        currency="INR",
        retry_count=1,
        available_actions=["SMART_RETRY_SCHEDULE", "CUSTOMER_NOTIFY_LINK"]
    )
    assert isinstance(recommendation, ActionRecommendation)
    assert recommendation.recommended_action == "SMART_RETRY_SCHEDULE"
    assert recommendation.confidence_score == 0.50
    assert "not provided" in recommendation.reasoning


def test_groq_structured_recommendation_mock_success():
    """Verify structured output parsing from Groq API response."""
    service = GroqLLMService(
        api_key="gsk_mock_valid_key_9999",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile"
    )

    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(
            message=MagicMock(
                content='{"recommended_action": "SMART_RETRY_SCHEDULE", "confidence_score": 0.88, "reasoning": "Soft decline indicates temporary balance issue.", "risk_assessment": "LOW"}'
            )
        )
    ]

    with patch.object(service, "_client") as mock_client:
        mock_client.chat.completions.create.return_value = mock_completion
        recommendation = service.generate_recovery_recommendation(
            failure_category="CARD_FAILURE",
            failure_code="INSUFFICIENT_FUNDS",
            amount=5000.00,
            currency="INR",
            retry_count=0,
            available_actions=["SMART_RETRY_SCHEDULE", "CUSTOMER_NOTIFY_LINK"]
        )

        assert recommendation.recommended_action == "SMART_RETRY_SCHEDULE"
        assert recommendation.confidence_score == 0.88
        assert recommendation.reasoning == "Soft decline indicates temporary balance issue."
        assert recommendation.risk_assessment == "LOW"


def test_groq_error_fallback_handling():
    """Verify rate-limit, timeout, or API errors trigger graceful fallback recommendation."""
    service = GroqLLMService(api_key="gsk_mock_valid_key_9999")

    with patch.object(service, "_client") as mock_client:
        mock_client.chat.completions.create.side_effect = groq.APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None
        )
        recommendation = service.generate_recovery_recommendation(
            failure_category="AUTHENTICATION_FAILURE",
            failure_code="OTP_EXPIRED",
            amount=2000.00,
            currency="INR",
            retry_count=1,
            available_actions=["CUSTOMER_NOTIFY_LINK", "MANUAL_REVIEW"]
        )

        assert isinstance(recommendation, ActionRecommendation)
        assert recommendation.recommended_action == "CUSTOMER_NOTIFY_LINK"
        assert recommendation.confidence_score == 0.50
        assert "Groq API error" in recommendation.reasoning


def test_ai_safety_isolation_boundary():
    """Verify GroqLLMService cannot execute Razorpay actions or alter database state."""
    service = GroqLLMService()
    # Confirm no razorpay or execution methods exist on LLM service
    forbidden_methods = [
        "call_razorpay", "create_payment_link", "charge_card",
        "bypass_policy", "mark_recovered", "update_transaction_status"
    ]
    for method in forbidden_methods:
        assert not hasattr(service, method), f"Forbidden safety boundary violation: {method} exists on GroqLLMService!"
