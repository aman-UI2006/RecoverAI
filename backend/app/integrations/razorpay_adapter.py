"""Step 18 — Razorpay Adapter & Resilience Engine for RecoverAI.

Handles authenticated API interactions with Razorpay Test Mode (POST /v1/payment_links),
retry resilience with exponential backoff, simulation air-gap isolation, and webhook signature validation.
"""

import asyncio
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
import httpx

from decimal import Decimal, InvalidOperation
from backend.app.core.config import settings
from backend.app.schemas.razorpay_dto import (
    PaymentLinkCreateRequest,
    PaymentLinkCreateResponse,
    RazorpayErrorResponse,
)

logger = logging.getLogger(__name__)


def convert_to_minor_units(amount: Any, currency: str = "INR") -> int:
    """Convert monetary amount to integer minor units (paise for INR) safely using Decimal.

    Args:
        amount: Raw amount (Decimal, float, str, or int).
        currency: ISO currency code (defaults to "INR").

    Returns:
        Exact integer amount in minor units (paise).

    Raises:
        ValueError: On non-positive amount, NaN/Infinity, or invalid fractional sub-paise/cents.
    """
    if amount is None:
        raise ValueError("Monetary amount cannot be None")

    try:
        if isinstance(amount, float):
            if amount != amount or amount == float("inf") or amount == float("-inf"):
                raise ValueError("Monetary amount cannot be NaN or Infinity")
            str_val = f"{amount:.10f}".rstrip("0").rstrip(".")
            d = Decimal(str_val)
        else:
            d = Decimal(str(amount))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Invalid monetary amount '{amount}': {exc}") from exc

    if d <= 0:
        raise ValueError(f"Monetary amount must be strictly positive, got {d}")

    paise_decimal = d * Decimal("100")
    if paise_decimal != paise_decimal.to_integral_value():
        raise ValueError(
            f"Monetary amount '{amount}' contains invalid fractional paise/sub-minor units."
        )

    return int(paise_decimal)


class RazorpayAdapter:
    """Razorpay API adapter encapsulating external execution and webhook security."""

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
    ) -> None:
        """Initialize RazorpayAdapter with API credentials and configuration.

        Args:
            key_id: Razorpay API Key ID (defaults to settings.RAZORPAY_KEY_ID).
            key_secret: Razorpay API Key Secret (defaults to settings.RAZORPAY_KEY_SECRET).
            base_url: Razorpay API Base URL (defaults to https://api.razorpay.com).
            max_retries: Maximum backoff retries for transient HTTP errors.
            retry_backoff_factor: Exponential backoff delay factor in seconds.
        """
        self._key_id = key_id or settings.RAZORPAY_KEY_ID
        self._key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.base_url = (base_url or "https://api.razorpay.com").rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor

    def __repr__(self) -> str:
        """Sanitized string representation masking credentials."""
        masked_key = f"{self._key_id[:6]}***" if self._key_id else "None"
        return f"<RazorpayAdapter base_url='{self.base_url}' key_id='{masked_key}'>"

    async def create_payment_link(
        self,
        request: PaymentLinkCreateRequest,
        mode: str = "REAL_TEST",
    ) -> PaymentLinkCreateResponse:
        """Create a Payment Link via Razorpay REST API (POST /v1/payment_links) or synthetic SIMULATION.

        Args:
            request: PaymentLinkCreateRequest payload.
            mode: Operational mode ("REAL_TEST" vs "SIMULATION").

        Returns:
            PaymentLinkCreateResponse details.

        Raises:
            ValueError: On HTTP 400 Bad Request or invalid client parameters.
            httpx.HTTPStatusError: On non-retryable HTTP errors.
            TimeoutError / httpx.RequestError: On network timeouts or connection failures.
        """
        # 1. SIMULATION Mode: Zero network connections, zero credential evaluation
        if mode == "SIMULATION":
            logger.info(f"SIMULATION mode: Generating synthetic payment link response for reference '{request.reference_id}'")
            short_id = request.reference_id.replace("RAI-", "")[:10]
            return PaymentLinkCreateResponse(
                id=f"plink_sim_{short_id}",
                entity="payment_link",
                short_url=f"https://rzp.io/i/sim_{short_id}",
                status="created",
                amount=request.amount,
                amount_paid=0,
                currency=request.currency,
                customer=request.customer,
                reference_id=request.reference_id,
                created_at=1700000000,
                notes=request.notes,
            )

        # 2. REAL_TEST Mode: Execute authenticated HTTPS API request against Razorpay Test Mode
        url = f"{self.base_url}/v1/payment_links"
        auth = (self._key_id, self._key_secret)
        payload = request.model_dump(exclude_none=True)

        attempt = 0
        while attempt <= self.max_retries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        url,
                        auth=auth,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                # Success path (HTTP 200 or 201)
                if response.status_code in (200, 201):
                    res_data = response.json()
                    return PaymentLinkCreateResponse(**res_data)

                # Bad Request (HTTP 400): Non-retryable parameter error
                if response.status_code == 400:
                    err_json = response.json() if response.content else {}
                    err_detail = err_json.get("error", {}).get("description", "Bad Request")
                    logger.error(f"Razorpay HTTP 400 Bad Request: {err_detail}")
                    raise ValueError(f"Razorpay API Bad Request: {err_detail}")

                # Unauthorized (HTTP 401)
                if response.status_code == 401:
                    logger.error("Razorpay HTTP 401 Unauthorized: Invalid API Key or Secret")
                    raise ValueError("Razorpay API Unauthorized: Invalid API credentials")

                # Rate Limit (HTTP 429) or Transient Server Error (HTTP 5xx): Retry with exponential backoff
                if response.status_code == 429 or response.status_code >= 500:
                    attempt += 1
                    if attempt > self.max_retries:
                        logger.error(f"Razorpay API request failed after {self.max_retries} retries with status {response.status_code}")
                        response.raise_for_status()

                    backoff_delay = self.retry_backoff_factor * (2 ** (attempt - 1))
                    logger.warning(
                        f"Razorpay API returned status {response.status_code} for reference '{request.reference_id}'. "
                        f"Retrying attempt {attempt}/{self.max_retries} in {backoff_delay:.2f}s..."
                    )
                    await asyncio.sleep(backoff_delay)
                    continue

                # Any other unexpected HTTP status
                response.raise_for_status()

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    logger.error(f"Razorpay API network timeout/connection error after {self.max_retries} retries: {exc}")
                    raise TimeoutError(f"Razorpay API network timeout: {exc}") from exc

                backoff_delay = self.retry_backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    f"Razorpay API network exception for reference '{request.reference_id}': {exc}. "
                    f"Retrying attempt {attempt}/{self.max_retries} in {backoff_delay:.2f}s..."
                )
                await asyncio.sleep(backoff_delay)

        raise TimeoutError("Razorpay API request failed: Exceeded maximum retries")

    async def execute_action(self, transaction: Any, request: Any) -> Dict[str, Any]:
        """High-level ActionExecutor delegate method for executing recovery interventions.

        Args:
            transaction: Transaction domain model instance.
            request: ActionExecutionRequest payload.

        Returns:
            Dictionary payload matching ActionExecutor delegate protocol.
        """
        short_tx_id = str(transaction.id)[:12]
        cycle = getattr(transaction, "recovery_cycle", 1)
        reference_id = f"RAI-{short_tx_id}-{cycle}"

        # Authoritative Decimal monetary conversion to integer minor units (paise)
        amount_in_paise = convert_to_minor_units(
            amount=transaction.amount,
            currency=getattr(transaction, "currency", "INR") or "INR",
        )

        # Build Payment Link request payload
        notes_dict = {
            "merchant_id": str(request.merchant_id),
            "transaction_id": str(transaction.id),
            "logical_operation_key": f"{request.merchant_id}:{transaction.id}:{cycle}:{request.action_type}",
            "recovery_cycle": str(cycle),
        }

        pl_request = PaymentLinkCreateRequest(
            amount=amount_in_paise,
            currency=getattr(transaction, "currency", "INR") or "INR",
            description=f"RecoverAI payment link for transaction {short_tx_id}",
            reference_id=reference_id,
            notes=notes_dict,
        )

        effective_mode = request.mode_override or getattr(transaction, "mode", "REAL_TEST")
        pl_response = await self.create_payment_link(pl_request, mode=effective_mode)

        return {
            "success": True,
            "execution_status": "SUCCESS",
            "external_resource_id": pl_response.id,
            "razorpay_payment_link_id": pl_response.id,
            "razorpay_reference_id": pl_response.reference_id,
            "short_url": pl_response.short_url,
            "raw_response": pl_response.model_dump(),
        }

    async def fetch_payment_link(
        self,
        payment_link_id: str,
        mode: str = "REAL_TEST",
    ) -> Dict[str, Any]:
        """Fetch status and details of a Payment Link via Razorpay REST API (GET /v1/payment_links/{id}) or SIMULATION.

        Args:
            payment_link_id: Razorpay Payment Link ID (e.g. "plink_123456").
            mode: Operational mode ("REAL_TEST" vs "SIMULATION").

        Returns:
            Dictionary containing payment link entity attributes including 'status'.

        Raises:
            ValueError: On HTTP 400/404 Bad Request or invalid link ID.
            httpx.HTTPStatusError: On non-retryable HTTP errors.
            TimeoutError / httpx.RequestError: On network timeouts or connection failures.
        """
        # 1. SIMULATION Mode: Deterministic synthetic payment link lookup
        if mode == "SIMULATION":
            logger.info(f"SIMULATION mode: Fetching synthetic payment link '{payment_link_id}'")
            if "paid" in payment_link_id.lower() or "success" in payment_link_id.lower():
                status = "paid"
                amount_paid = 100000
            elif "expired" in payment_link_id.lower():
                status = "expired"
                amount_paid = 0
            elif "cancelled" in payment_link_id.lower() or "failed" in payment_link_id.lower():
                status = "cancelled"
                amount_paid = 0
            else:
                status = "created"
                amount_paid = 0

            return {
                "id": payment_link_id,
                "entity": "payment_link",
                "status": status,
                "amount": 100000,
                "amount_paid": amount_paid,
                "currency": "INR",
                "reference_id": f"RAI-ref-{payment_link_id[:8]}",
            }

        # 2. REAL_TEST Mode: Execute authenticated HTTPS API request against Razorpay Test Mode
        url = f"{self.base_url}/v1/payment_links/{payment_link_id}"
        auth = (self._key_id, self._key_secret)

        attempt = 0
        while attempt <= self.max_retries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        url,
                        auth=auth,
                        headers={"Content-Type": "application/json"},
                    )

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (400, 404):
                    err_json = response.json() if response.content else {}
                    err_detail = err_json.get("error", {}).get("description", f"Status {response.status_code}")
                    logger.error(f"Razorpay HTTP {response.status_code}: {err_detail}")
                    raise ValueError(f"Razorpay Payment Link not found: {err_detail}")

                if response.status_code == 401:
                    logger.error("Razorpay HTTP 401 Unauthorized: Invalid API Key or Secret")
                    raise ValueError("Razorpay API Unauthorized: Invalid API credentials")

                if response.status_code == 429 or response.status_code >= 500:
                    attempt += 1
                    if attempt > self.max_retries:
                        logger.error(f"Razorpay GET payment link failed after {self.max_retries} retries with status {response.status_code}")
                        response.raise_for_status()

                    backoff_delay = self.retry_backoff_factor * (2 ** (attempt - 1))
                    logger.warning(
                        f"Razorpay API GET returned status {response.status_code} for payment link '{payment_link_id}'. "
                        f"Retrying attempt {attempt}/{self.max_retries} in {backoff_delay:.2f}s..."
                    )
                    await asyncio.sleep(backoff_delay)
                    continue

                response.raise_for_status()

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    logger.error(f"Razorpay API network timeout during GET payment link after {self.max_retries} retries: {exc}")
                    raise TimeoutError(f"Razorpay API network timeout: {exc}") from exc

                backoff_delay = self.retry_backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    f"Razorpay GET network exception for link '{payment_link_id}': {exc}. "
                    f"Retrying attempt {attempt}/{self.max_retries} in {backoff_delay:.2f}s..."
                )
                await asyncio.sleep(backoff_delay)

        raise TimeoutError("Razorpay API GET request failed: Exceeded maximum retries")

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes,
        signature: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify official Razorpay webhook HMAC SHA-256 signature using raw body bytes.

        Args:
            raw_body: Exact, unmodified bytes of the incoming HTTP POST request body.
            signature: Signature string from X-Razorpay-Signature header.
            secret: Webhook signing secret (defaults to settings.RAZORPAY_WEBHOOK_SECRET).

        Returns:
            True if signature is authentic, False otherwise.
        """
        webhook_secret = secret or settings.RAZORPAY_WEBHOOK_SECRET
        if not webhook_secret or not signature or not raw_body:
            return False

        computed_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)
