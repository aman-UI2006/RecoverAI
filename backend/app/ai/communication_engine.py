"""
RecoverAI - Customer Communication Engine (Step 48)

Builds customer communication template generator tailoring message tone based on customer segment,
failure scenario, and transaction amount.

EXPLICIT EXECUTION BOUNDARIES:
- REAL_TEST: Generates communication content ONLY. No external message is dispatched unless a separately verified messaging provider is integrated.
- SIMULATION: Models message generation, delivery simulation, and conversion engagement probability.
- PII MASKING: Enforces strict regex-based PII redaction on preview outputs (emails, phones, card numbers).
"""

import logging
import re
from typing import Optional

from backend.app.schemas.communication import CommunicationRequest, CommunicationResponse
from backend.app.services.llm_service import GroqLLMService

logger = logging.getLogger("recoverai.communication_engine")

# PII Redaction Regex Patterns
EMAIL_PATTERN = re.compile(r"\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b")
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


class CommunicationEngine:
    """
    Tone-conditioned customer communication engine providing personalized recovery messages,
    PII masking, dynamic payment link placeholders, and execution boundary enforcement.
    """

    def __init__(self, llm_service: Optional[GroqLLMService] = None):
        self.llm_service = llm_service or GroqLLMService()

    @staticmethod
    def select_tone(
        scenario_type: str,
        failure_code: Optional[str] = None,
        amount_rupees: float = 0.0,
        customer_segment: Optional[str] = None,
    ) -> str:
        """
        Determines the optimal message tone based on customer segment and scenario.
        - Empathetic: Subscription / recurring billing failures.
        - Urgent: Overdue receivables, insufficient funds, or high amount.
        - Direct: VIP or enterprise merchant accounts.
        - Informative: Standard technical/gateway failures.
        """
        scenario_upper = (scenario_type or "").upper()
        code_upper = (failure_code or "").upper()
        segment_upper = (customer_segment or "").upper()

        if segment_upper in ("VIP", "ENTERPRISE", "HIGH_VALUE"):
            return "Direct"

        if "SUBSCRIPTION" in scenario_upper or "RECURRING" in scenario_upper or code_upper == "SUBSCRIPTION_LAPSE":
            return "Empathetic"

        if (
            "INSUFFICIENT" in scenario_upper
            or "OVERDUE" in scenario_upper
            or "EXPIRED" in scenario_upper
            or code_upper in ("INSUFFICIENT_FUNDS", "PAYMENT_LINK_EXPIRED")
            or amount_rupees >= 10000.0
        ):
            return "Urgent"

        return "Informative"

    @staticmethod
    def mask_pii(text: str) -> str:
        """
        Masks sensitive PII (emails, phone numbers, credit card numbers) from text for preview display.
        """
        if not text:
            return ""

        def _mask_email(match):
            user, domain = match.group(1), match.group(2)
            if len(user) <= 2:
                masked_user = user[0] + "*"
            else:
                masked_user = user[0] + "*" * (len(user) - 2) + user[-1]
            return f"{masked_user}@{domain}"

        def _mask_phone(match):
            phone = match.group(0)
            digits = re.sub(r"\D", "", phone)
            if len(digits) >= 10:
                masked_digits = digits[-10:-8] + "****" + digits[-4:]
                if phone.strip().startswith("+"):
                    return f"+{digits[:-10]} {masked_digits}".strip() if len(digits) > 10 else f"+91 {masked_digits}"
                return masked_digits
            return "****"

        def _mask_card(match):
            card = match.group(0)
            digits = re.sub(r"\D", "", card)
            if len(digits) >= 12:
                return "**** **** **** " + digits[-4:]
            return "****"

        sanitized = CARD_PATTERN.sub(_mask_card, text)
        sanitized = PHONE_PATTERN.sub(_mask_phone, sanitized)
        sanitized = EMAIL_PATTERN.sub(_mask_email, sanitized)

        return sanitized

    def generate_communication(self, request: CommunicationRequest) -> CommunicationResponse:
        """
        Generates customer communication text based on tone, channel, and execution mode boundaries.
        """
        tone = self.select_tone(
            scenario_type=request.scenario_type,
            failure_code=request.failure_code,
            amount_rupees=request.amount_rupees,
            customer_segment=request.customer_segment,
        )

        payment_link = request.payment_link or "https://rzp.io/i/recov_demo"
        amount_str = f"₹{request.amount_rupees:,.2f}" if request.amount_rupees > 0 else "your payment"

        # Deterministic tone template lookup
        templates = {
            "Empathetic": (
                f"We noticed your recent payment of {amount_str} didn't go through. "
                f"We understand these things happen! You can easily update your payment details using this secure link: {payment_link}"
            ),
            "Urgent": (
                f"Payment Action Required: Your transaction of {amount_str} is currently pending resolution. "
                f"Please complete your payment immediately via secure link: {payment_link}"
            ),
            "Direct": (
                f"RecoverAI Payment Update: Account balance {amount_str} requires settlement. "
                f"Direct payment link: {payment_link}"
            ),
            "Informative": (
                f"Your payment of {amount_str} could not be completed due to a temporary network issue. "
                f"You can retry safely using your direct payment link: {payment_link}"
            ),
        }

        raw_text = templates.get(tone, templates["Informative"])

        # PII-masked preview text
        masked_preview = self.mask_pii(raw_text)

        # Enforce execution boundaries
        mode_upper = (request.mode or "SIMULATION").upper()
        if mode_upper == "REAL_TEST":
            # REAL_TEST Boundary: Content generation ONLY. No external message dispatched.
            is_sent = False
            sim_status = "NOT_SENT_REAL_TEST_CONTENT_ONLY"
            sim_prob = None
        else:
            # SIMULATION Boundary: Model delivery and engagement recovery probability
            is_sent = True
            sim_status = "DELIVERED"
            sim_prob = 0.78 if tone in ("Empathetic", "Urgent") else 0.65

        return CommunicationResponse(
            tone=tone,
            channel=request.preferred_channel.upper(),
            raw_message_text=raw_text,
            masked_preview_text=masked_preview,
            payment_link_placeholder=payment_link,
            execution_mode=mode_upper,
            is_sent=is_sent,
            simulated_delivery_status=sim_status,
            simulated_open_probability=sim_prob,
        )
