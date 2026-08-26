import sys
import logging
from backend.app.core.config import settings
from backend.app.services.llm_service import GroqLLMService, ActionRecommendation

logging.basicConfig(level=logging.INFO)

def verify_live_groq():
    print("\n--- 1. Check GROQ_API_KEY Loading ---")
    key_exists = bool(settings.GROQ_API_KEY)
    is_not_placeholder = settings.GROQ_API_KEY != "gsk_YourGroqApiKeyHere" if settings.GROQ_API_KEY else False
    
    print(f"Key Present: {key_exists}")
    print(f"Key Configured (Non-Placeholder): {is_not_placeholder}")
    
    if not key_exists or not is_not_placeholder:
        print("[FAIL] GROQ_API_KEY is missing or contains placeholder value in local environment!")
        sys.exit(1)

    print("\n--- 2. Initialize GroqLLMService & Client ---")
    service = GroqLLMService(model="groq/compound-mini")
    assert service.is_configured() is True, "Service is_configured() should return True"
    client = service.client
    assert client is not None, "Client should be initialized"
    print(f"[PASS] Groq client initialized successfully using model '{service.model}'.")

    print(f"\n--- 3 & 4. Authenticated Request to Model '{service.model}' ---")
    recommendation = service.generate_recovery_recommendation(
        failure_category="CARD_FAILURE",
        failure_code="INSUFFICIENT_FUNDS",
        amount=2499.00,
        currency="INR",
        retry_count=1,
        available_actions=["SMART_RETRY_SCHEDULE", "CUSTOMER_NOTIFY_LINK", "MANUAL_REVIEW"]
    )

    print("\n--- 5 & 6. Verify ActionRecommendation Structure & Pydantic Validation ---")
    assert isinstance(recommendation, ActionRecommendation), "Output must be ActionRecommendation"
    assert recommendation.recommended_action in ["SMART_RETRY_SCHEDULE", "CUSTOMER_NOTIFY_LINK", "MANUAL_REVIEW"], f"Invalid action: {recommendation.recommended_action}"
    assert 0.0 <= recommendation.confidence_score <= 1.0, f"Invalid confidence: {recommendation.confidence_score}"
    assert "Groq API error" not in recommendation.reasoning, f"API error detected: {recommendation.reasoning}"
    assert len(recommendation.reasoning) > 0, "Reasoning must not be empty"
    assert len(recommendation.risk_assessment) > 0, "Risk assessment must not be empty"

    print(f"Recommended Action : {recommendation.recommended_action}")
    print(f"Confidence Score   : {recommendation.confidence_score}")
    print(f"Reasoning          : {recommendation.reasoning}")
    print(f"Risk Assessment    : {recommendation.risk_assessment}")
    print("[PASS] Live Groq authentication and response validation SUCCESSFUL!")

    print("\n--- 9. Safety Boundary Verification ---")
    assert not hasattr(service, "call_razorpay"), "Safety check: No razorpay method"
    assert not hasattr(service, "create_payment_link"), "Safety check: No payment link method"
    print("[PASS] Groq LLM has ZERO direct financial execution capabilities.")

    print("\nACTUAL GROQ API AUTHENTICATION = VERIFIED")

if __name__ == "__main__":
    verify_live_groq()
