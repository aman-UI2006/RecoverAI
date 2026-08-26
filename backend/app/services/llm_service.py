import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import groq

from backend.app.core.config import settings

logger = logging.getLogger("recoverai.llm_service")


class ActionRecommendation(BaseModel):
    """
    Structured response model returned by the LLM recommendation service.
    Note: This is ONLY an advisory recommendation. It CANNOT execute actions.
    """
    recommended_action: str = Field(description="Advisory recovery action identifier")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Diagnostic explanation supporting the recommendation")
    risk_assessment: str = Field(description="Qualitative risk evaluation of the action")


class GroqLLMService:
    """
    Groq LLM Service Abstraction for RecoverAI.
    
    SAFETY BOUNDARY GUARANTEES:
    - Pure advisory layer: Generates ActionRecommendation instances ONLY.
    - Zero capability to invoke Razorpay APIs, mutate transaction state, or bypass policy engines.
    - Mandatory structured output validation via Pydantic.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.base_url = base_url or settings.GROQ_BASE_URL
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[groq.Groq] = None

    @property
    def client(self) -> groq.Groq:
        """Lazy initialization of Groq API client."""
        if self._client is None:
            if not self.api_key or self.api_key == "gsk_YourGroqApiKeyHere":
                raise ValueError("GROQ_API_KEY is not configured or contains default placeholder.")
            self._client = groq.Groq(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def is_configured(self) -> bool:
        """Check if Groq API key is configured."""
        return bool(self.api_key and self.api_key != "gsk_YourGroqApiKeyHere")

    def generate_recovery_recommendation(
        self,
        failure_category: str,
        failure_code: str,
        amount: float,
        currency: str,
        retry_count: int,
        available_actions: List[str]
    ) -> ActionRecommendation:
        """
        Generate advisory action recommendation given transaction failure context.
        
        If Groq API is unavailable, unconfigured, or encounters rate limits / timeouts,
        a deterministic fallback advisory recommendation is returned.
        """
        fallback_action = available_actions[0] if available_actions else "MANUAL_REVIEW"

        if not self.is_configured():
            logger.warning("Groq API key not configured. Returning fallback recommendation.")
            return ActionRecommendation(
                recommended_action=fallback_action,
                confidence_score=0.50,
                reasoning="Groq API key not provided; returning deterministic fallback recommendation.",
                risk_assessment="LOW - Fallback advisory default"
            )

        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "You are RecoverAI's Diagnostic & Recommendation Assistant. "
                    "Analyze transaction failures and recommend the optimal advisory recovery action. "
                    "Respond STRICTLY in valid JSON matching this structure: "
                    '{"recommended_action": "<action>", "confidence_score": <float 0.0-1.0>, '
                    '"reasoning": "<explanation>", "risk_assessment": "<assessment>"}. '
                    f"Available actions: {json.dumps(available_actions)}"
                )
            },
            {
                "role": "user",
                "content": json.dumps({
                    "failure_category": failure_category,
                    "failure_code": failure_code,
                    "amount": amount,
                    "currency": currency,
                    "retry_count": retry_count,
                    "available_actions": available_actions
                })
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=prompt_messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=10.0
            )

            raw_content = response.choices[0].message.content
            parsed_json = json.loads(raw_content)

            # Validate against Pydantic model
            recommendation = ActionRecommendation(**parsed_json)

            # Ensure recommended action is within allowed list
            if recommendation.recommended_action not in available_actions:
                logger.warning(
                    f"Groq recommended invalid action '{recommendation.recommended_action}'. "
                    f"Falling back to '{fallback_action}'."
                )
                recommendation.recommended_action = fallback_action

            return recommendation

        except (groq.GroqError, json.JSONDecodeError, ValueError, Exception) as err:
            logger.error(f"Groq API call failed: {type(err).__name__} - {err}. Using fallback.")
            return ActionRecommendation(
                recommended_action=fallback_action,
                confidence_score=0.50,
                reasoning=f"Groq API error ({type(err).__name__}); fallback recommendation issued.",
                risk_assessment="LOW - Fallback advisory default"
            )
