"""
RecoverAI - Multi-Tiered Diagnosis Engine Service (Step 11)

Classifies transaction failure root causes using a 4-level precedence hierarchy:
1. Deterministic Rule Lookup Table (Rule Engine) -> Confidence 1.0
2. ML / Heuristic Classifier (ML Classifier) -> Confidence >= 0.60
3. Structured LLM Fallback (Groq API) -> PII Sanitized payload reasoning
4. Human Review Fallback -> UNKNOWN_DECLINE, Confidence 0.0, requires_human_review=True

Mutates transaction state from AT_RISK to DIAGNOSED via StateTransitionService
and persists diagnostic records to the `diagnoses` database table.
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.domain import Transaction, Diagnosis
from backend.app.schemas.diagnosis import (
    DiagnosisRequest,
    DiagnosisResult,
    DiagnosisSource,
    FailureCategory,
)
from backend.app.ml.diagnosis_classifier import (
    STATIC_DIAGNOSIS_LOOKUP,
    MLDiagnosisClassifier,
)
from backend.app.services.llm_service import GroqLLMService
from backend.app.services.state_transition_service import StateTransitionService
from backend.app.schemas.state_machine import StateTransitionResponse

logger = logging.getLogger("recoverai.diagnosis_engine")


class DiagnosisEngine:
    """Service executing 4-level precedence root cause diagnosis and transaction state transition."""

    @classmethod
    def sanitize_payload_for_llm(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitizes raw decline payloads to prevent PII and sensitive data leakage to LLM API.

        Args:
            payload: Raw event payload dictionary.

        Returns:
            Dict[str, Any]: PII-sanitized dictionary.
        """
        if not payload:
            return {}

        sanitized = payload.copy()
        # Remove direct PII keys
        pii_keys = {"email", "phone", "contact", "card_number", "cvv", "secret", "password", "token"}
        for key in list(sanitized.keys()):
            if any(p_key in key.lower() for p_key in pii_keys):
                sanitized[key] = "[REDACTED_PII]"

        # Mask regex patterns in string values
        for k, v in list(sanitized.items()):
            if isinstance(v, str):
                # Mask email patterns
                v_clean = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]", v)
                # Mask phone patterns (10+ digits)
                v_clean = re.sub(r"\b\d{10,12}\b", "[REDACTED_PHONE]", v_clean)
                sanitized[k] = v_clean

        return sanitized

    @classmethod
    async def diagnose_root_cause(
        cls,
        request: DiagnosisRequest,
        llm_service: Optional[GroqLLMService] = None,
    ) -> DiagnosisResult:
        """
        Executes the 4-level precedence hierarchy to diagnose failure root cause.

        Precedence: Rules -> ML Classifier -> LLM Fallback -> Human Review Fallback

        Args:
            request: DiagnosisRequest payload.
            llm_service: Optional GroqLLMService instance for Level 3 LLM fallback.

        Returns:
            DiagnosisResult: Standardized diagnosis output.
        """
        failure_code = request.failure_code.strip()

        # -------------------------------------------------------------
        # LEVEL 1: Deterministic Error Code Lookup Table
        # -------------------------------------------------------------
        if failure_code in STATIC_DIAGNOSIS_LOOKUP:
            cat, explanation = STATIC_DIAGNOSIS_LOOKUP[failure_code]
            logger.info(f"Level 1 Rule match for failure code '{failure_code}': {cat}")
            return DiagnosisResult(
                transaction_id=request.transaction_id,
                failure_code=failure_code,
                failure_category=cat,
                root_cause_explanation=explanation,
                confidence_score=1.0,
                diagnosis_source=DiagnosisSource.RULE_ENGINE,
                requires_human_review=False,
            )

        # -------------------------------------------------------------
        # LEVEL 2: ML / Heuristic Failure Classifier
        # -------------------------------------------------------------
        ml_res = MLDiagnosisClassifier.classify(
            failure_code=failure_code,
            error_description=request.error_description,
            feature_vector=request.feature_vector,
        )
        if ml_res is not None:
            cat, explanation, conf = ml_res
            if conf >= 0.20:
                logger.info(f"Level 2 ML Classifier match for '{failure_code}': {cat} (conf={conf})")
                return DiagnosisResult(
                    transaction_id=request.transaction_id,
                    failure_code=failure_code,
                    failure_category=cat,
                    root_cause_explanation=explanation,
                    confidence_score=conf,
                    diagnosis_source=DiagnosisSource.ML_CLASSIFIER,
                    requires_human_review=False,
                )

        # -------------------------------------------------------------
        # LEVEL 3: Structured LLM Fallback Service
        # -------------------------------------------------------------
        if llm_service is not None or request.raw_payload:
            try:
                active_llm = llm_service or GroqLLMService()
                sanitized_payload = cls.sanitize_payload_for_llm(request.raw_payload or {})
                available_actions = ["PAYMENT_LINK", "RECOVERY_MESSAGE", "WHATSAPP_REMINDER", "RETRY", "MANUAL_OUTREACH"]
                
                rec = active_llm.generate_recovery_recommendation(
                    failure_category="UNKNOWN",
                    failure_code=failure_code,
                    amount=0.0,
                    currency="INR",
                    retry_count=0,
                    available_actions=available_actions,
                )
                if rec and rec.reasoning:
                    # Infer category from LLM reasoning or default to UNKNOWN_DECLINE
                    inferred_cat = FailureCategory.UNKNOWN_DECLINE.value
                    upper_expl = rec.reasoning.upper()
                    for f_cat in FailureCategory:
                        if f_cat.value in upper_expl:
                            inferred_cat = f_cat.value
                            break

                    logger.info(f"Level 3 LLM Fallback diagnosis for '{failure_code}': {inferred_cat}")
                    return DiagnosisResult(
                        transaction_id=request.transaction_id,
                        failure_code=failure_code,
                        failure_category=inferred_cat,
                        root_cause_explanation=rec.reasoning,
                        confidence_score=round(rec.confidence_score, 2),
                        diagnosis_source=DiagnosisSource.LLM_FALLBACK,
                        requires_human_review=(rec.confidence_score < 0.60),
                    )
            except Exception as e:
                logger.warning(f"Level 3 LLM Fallback diagnosis failed for transaction '{request.transaction_id}': {e}")

        # -------------------------------------------------------------
        # LEVEL 4: Human Review Fallback (Safe Default)
        # -------------------------------------------------------------
        logger.warning(f"Level 4 Human Review Fallback invoked for transaction '{request.transaction_id}'.")
        return DiagnosisResult(
            transaction_id=request.transaction_id,
            failure_code=failure_code,
            failure_category=FailureCategory.UNKNOWN_DECLINE.value,
            root_cause_explanation="Unclassified payment failure requiring manual human review",
            confidence_score=0.0,
            diagnosis_source=DiagnosisSource.HUMAN_REVIEW_FALLBACK,
            requires_human_review=True,
        )

    @classmethod
    async def diagnose_and_transition(
        cls,
        session: AsyncSession,
        request: DiagnosisRequest,
        llm_service: Optional[GroqLLMService] = None,
    ) -> Tuple[DiagnosisResult, Any]:
        """
        Validates merchant scoping, runs diagnosis precedence hierarchy, saves Diagnosis record,
        and mutates transaction state to DIAGNOSED via StateTransitionService.

        Args:
            session: Active AsyncSession.
            request: DiagnosisRequest.
            llm_service: Optional GroqLLMService.

        Returns:
            Tuple[DiagnosisResult, AuditEvent]: Diagnosis output and created AuditEvent.

        Raises:
            ValueError: If transaction not found or merchant ID mismatch.
        """
        stmt = select(Transaction).where(Transaction.id == request.transaction_id)
        res = await session.execute(stmt)
        tx = res.scalar_one_or_none()

        if not tx:
            raise ValueError(f"Transaction with ID '{request.transaction_id}' not found.")

        # Enforce multi-tenant merchant isolation
        if request.merchant_id and tx.merchant_id != request.merchant_id:
            raise ValueError(
                f"Merchant ID mismatch for transaction '{request.transaction_id}': "
                f"expected '{request.merchant_id}', got '{tx.merchant_id}'"
            )

        # Execute 4-level diagnosis hierarchy
        diagnosis_res = await cls.diagnose_root_cause(request, llm_service=llm_service)

        # Save Diagnosis record
        diag_record = Diagnosis(
            transaction_id=request.transaction_id,
            failure_code=diagnosis_res.failure_code,
            failure_category=diagnosis_res.failure_category,
            root_cause_explanation=diagnosis_res.root_cause_explanation,
            confidence_score=diagnosis_res.confidence_score,
            diagnosis_source=diagnosis_res.diagnosis_source.value,
        )
        session.add(diag_record)
        await session.flush()

        # Authoritative state transition to DIAGNOSED via StateTransitionService
        updated_tx, audit_event = await StateTransitionService.transition(
            session=session,
            transaction_id=request.transaction_id,
            target_state="DIAGNOSED",
            actor="DIAGNOSIS_ENGINE",
            reason=f"Failure root cause diagnosed: {diagnosis_res.failure_category}",
            details={
                "failure_code": diagnosis_res.failure_code,
                "failure_category": diagnosis_res.failure_category,
                "diagnosis_source": diagnosis_res.diagnosis_source.value,
                "confidence_score": diagnosis_res.confidence_score,
                "requires_human_review": diagnosis_res.requires_human_review,
            },
        )

        await session.commit()
        return diagnosis_res, audit_event
