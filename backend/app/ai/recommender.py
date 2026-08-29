"""
RecoverAI - Structured AI Recommender Service (Step 13B)

Synthesizes diagnosis root cause context, customer communication history, and ENRV
action rankings into advisory recovery strategies and personalized customer text templates.

SAFETY & AIR-GAP GUARANTEES:
- Pure advisory layer: Generates AIRecommendationResponse ONLY.
- Zero capability to execute payment calls, mutate transaction state, or bypass policy engines.
- Strict candidate-action validation: Recommended action MUST exist in the provided ENRV candidates.
- Deterministic fallback: Falls back to top ENRV-ranked candidate if LLM fails, times out, or returns invalid outputs.
- PII Sanitization: Strips email, phone numbers, card details, and credentials prior to prompt submission.
- Encapsulation: Interacts with LLM exclusively through GroqLLMService high-level API.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.schemas.ai_recommendation import AIRecommendationResponse
from backend.app.schemas.diagnosis import DiagnosisResult
from backend.app.schemas.enrv import ENRVCalculationResponse
from backend.app.services.llm_service import GroqLLMService

logger = logging.getLogger("recoverai.structured_ai_recommender")

PII_KEY_PATTERN = re.compile(r"(email|phone|contact|card|cvv|secret|password|token|key)", re.IGNORECASE)


class StructuredAIRecommender:
    """
    AI Recommender synthesizing diagnostic context and ENRV action rankings
    into structured advisory recommendations using Groq LLM API.
    """

    def __init__(self, llm_service: Optional[GroqLLMService] = None):
        self.llm_service = llm_service or GroqLLMService()

    @classmethod
    def sanitize_context(cls, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitizes optional decision-time context dictionary to prevent PII leakage.
        """
        if not context:
            return {}
        sanitized = {}
        for key, val in context.items():
            if PII_KEY_PATTERN.search(str(key)):
                sanitized[key] = "[REDACTED_PII]"
            elif isinstance(val, str) and (
                "@" in val or re.search(r"\b\d{10,16}\b", val)
            ):
                sanitized[key] = "[REDACTED_PII]"
            elif isinstance(val, dict):
                sanitized[key] = cls.sanitize_context(val)
            else:
                sanitized[key] = val
        return sanitized

    def generate_recommendation(
        self,
        diagnosis: DiagnosisResult,
        enrv_response: ENRVCalculationResponse,
        decision_context: Optional[Dict[str, Any]] = None,
    ) -> AIRecommendationResponse:
        """
        Generates structured AI recommendation for a diagnosed transaction.

        Args:
            diagnosis: Verified DiagnosisResult from Step 11.
            enrv_response: Ranked ENRVCalculationResponse from Step 10.
            decision_context: Optional customer/communication context dictionary.

        Returns:
            AIRecommendationResponse: Validated structured recommendation.
        """
        # Extract valid candidate action types from ENRV response
        valid_candidate_actions = [res.action_type.upper().strip() for res in enrv_response.action_results]
        top_enrv_action = enrv_response.best_action.upper().strip()

        # Sanitize optional context
        clean_context = self.sanitize_context(decision_context)

        # Attempt LLM recommendation if service configured
        if self.llm_service.is_configured():
            try:
                recommendation = self._call_llm(
                    diagnosis=diagnosis,
                    enrv_response=enrv_response,
                    clean_context=clean_context,
                    valid_candidate_actions=valid_candidate_actions,
                )
                if recommendation:
                    return recommendation
            except Exception as exc:
                logger.warning(f"Structured AI Recommender LLM call failed: {exc}. Invoking ENRV fallback.")

        # Fallback to top ENRV-ranked candidate
        return self._create_deterministic_fallback(
            top_action=top_enrv_action,
            diagnosis=diagnosis,
            reason="LLM service unavailable or returned invalid output; falling back to top ENRV action."
        )

    def _call_llm(
        self,
        diagnosis: DiagnosisResult,
        enrv_response: ENRVCalculationResponse,
        clean_context: Dict[str, Any],
        valid_candidate_actions: List[str],
    ) -> Optional[AIRecommendationResponse]:
        """Internal helper to construct prompt, call Groq LLM service high-level API, and validate output."""
        prompt = (
            f"You are the RecoverAI Revenue Recovery Recommender.\n"
            f"DIAGNOSIS CONTEXT:\n"
            f"- Failure Category: {diagnosis.failure_category}\n"
            f"- Failure Code: {diagnosis.failure_code}\n"
            f"- Root Cause: {diagnosis.root_cause_explanation}\n"
            f"- Diagnosis Confidence: {diagnosis.confidence_score}\n\n"
            f"ENRV RANKED CANDIDATE ACTIONS:\n"
            f"- Top Action: {enrv_response.best_action} (Max ENRV: {enrv_response.max_enrv_rupees} INR)\n"
            f"- Ranked Candidates: {[f'{res.action_type} (ENRV: {res.expected_net_recovery_value_rupees} INR, Prob: {res.predicted_recovery_probability})' for res in enrv_response.action_results]}\n\n"
            f"DECISION CONTEXT: {json.dumps(clean_context)}\n\n"
            f"CRITICAL RULES:\n"
            f"1. You MUST select recommended_action exclusively from this allowed list: {valid_candidate_actions}.\n"
            f"2. Provide rationale_text supporting why this action fits the diagnosis and ENRV ranking.\n"
            f"3. Provide customer_message_template suitable as a communication template.\n"
            f"4. Provide confidence_score as a float between 0.0 and 1.0.\n"
            f"5. Return ONLY a valid JSON object matching the schema without markdown formatting."
        )

        prompt_messages = [
            {"role": "system", "content": "You are a specialized JSON AI recommender. Output strictly valid JSON."},
            {"role": "user", "content": prompt},
        ]

        # Call high-level GroqLLMService method instead of direct client access
        data = self.llm_service.generate_structured_recommendation(
            prompt_messages=prompt_messages,
            temperature=0.2,
            timeout=10.0,
        )

        if not data:
            return None

        # Validate with Pydantic schema
        rec = AIRecommendationResponse.model_validate(data)

        # Enforce candidate action validity
        rec_action = rec.recommended_action.upper().strip()
        if rec_action not in valid_candidate_actions:
            logger.warning(f"LLM recommended unsupported action '{rec.recommended_action}'. Allowed: {valid_candidate_actions}")
            return None

        # Return validated recommendation with normalized action string
        return rec.model_copy(update={"recommended_action": rec_action})

    def _create_deterministic_fallback(
        self,
        top_action: str,
        diagnosis: DiagnosisResult,
        reason: str,
    ) -> AIRecommendationResponse:
        """Constructs deterministic fallback recommendation using top ENRV action."""
        default_templates = {
            "PAYMENT_LINK": "Your transaction requires attention. Please complete your payment securely using this recovery link.",
            "RECOVERY_MESSAGE": "We noticed your recent payment was incomplete. Tap to resume your transaction.",
            "WHATSAPP_REMINDER": "Hello! Your pending payment is ready for completion. Tap to finalize.",
            "RETRY": "Automatic retry scheduled for your transaction.",
            "MANUAL_OUTREACH": "Our support team will reach out to assist with your transaction.",
            "NO_ACTION": "No recovery action scheduled for this transaction.",
        }

        template = default_templates.get(
            top_action,
            "Your transaction requires attention. Please complete your payment securely."
        )

        return AIRecommendationResponse(
            recommended_action=top_action,
            rationale_text=f"Deterministic ENRV Fallback: Selected top-ranked action '{top_action}' based on ENRV optimization. {reason}",
            customer_message_template=template,
            confidence_score=0.50,
        )
