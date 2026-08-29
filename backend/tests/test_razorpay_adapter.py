"""Step 18 — Razorpay Adapter Test Suite for RecoverAI.

Verifies Razorpay API integration, SIMULATION mode air-gap isolation,
exponential backoff retry handler, UNKNOWN result handling, security credential masking,
and HMAC SHA-256 webhook signature verification.
"""

import hmac
import hashlib
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import httpx

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import pytest_asyncio
from backend.app.core.database import Base
from backend.app.models.domain import Merchant, Customer, Transaction, current_utc_time
from backend.app.schemas.state_machine import TransactionStatus, ExecutionStatus
from backend.app.schemas.executor import ActionExecutionRequest
from backend.app.schemas.razorpay_dto import PaymentLinkCreateRequest, PaymentLinkCreateResponse
from backend.app.integrations.razorpay_adapter import RazorpayAdapter
from backend.app.services.action_executor import ActionExecutor

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for RazorpayAdapter testing."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def razorpay_adapter():
    """Fixture providing configured RazorpayAdapter instance."""
    return RazorpayAdapter(
        key_id="rzp_test_key_12345",
        key_secret="secret_67890",
        base_url="https://api.razorpay.com",
        max_retries=2,
        retry_backoff_factor=0.01,  # Fast retries for unit tests
    )


@pytest.mark.asyncio
async def test_1_create_payment_link_simulation_mode(razorpay_adapter):
    """Verify SIMULATION mode returns synthetic response without network calls."""
    req = PaymentLinkCreateRequest(
        amount=10000,
        currency="INR",
        reference_id="RAI-tx123-1",
        description="Test payment link",
    )

    res = await razorpay_adapter.create_payment_link(req, mode="SIMULATION")

    assert res.id.startswith("plink_sim_")
    assert res.short_url.startswith("https://rzp.io/i/sim_")
    assert res.amount == 10000
    assert res.currency == "INR"
    assert res.reference_id == "RAI-tx123-1"


@pytest.mark.asyncio
async def test_2_create_payment_link_real_test_success(razorpay_adapter):
    """Verify REAL_TEST mode sends authenticated POST /v1/payment_links request."""
    req = PaymentLinkCreateRequest(
        amount=25000,
        currency="INR",
        reference_id="RAI-tx456-1",
        description="Real test link",
    )

    mock_response_data = {
        "id": "plink_test_real_999",
        "entity": "payment_link",
        "short_url": "https://rzp.io/i/real_999",
        "status": "created",
        "amount": 25000,
        "amount_paid": 0,
        "currency": "INR",
        "reference_id": "RAI-tx456-1",
        "created_at": 1700000000,
        "notes": {},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        res = await razorpay_adapter.create_payment_link(req, mode="REAL_TEST")

        assert res.id == "plink_test_real_999"
        assert res.amount == 25000
        assert res.reference_id == "RAI-tx456-1"

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["auth"] == ("rzp_test_key_12345", "secret_67890")
        assert kwargs["json"]["amount"] == 25000
        assert kwargs["json"]["reference_id"] == "RAI-tx456-1"


@pytest.mark.asyncio
async def test_3_exponential_backoff_retry_on_5xx(razorpay_adapter):
    """Verify transient HTTP 500 errors trigger exponential backoff retries."""
    req = PaymentLinkCreateRequest(
        amount=15000,
        currency="INR",
        reference_id="RAI-tx789-1",
    )

    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "id": "plink_test_retry_ok",
        "entity": "payment_link",
        "short_url": "https://rzp.io/i/retry_ok",
        "status": "created",
        "amount": 15000,
        "amount_paid": 0,
        "currency": "INR",
        "reference_id": "RAI-tx789-1",
        "created_at": 1700000000,
        "notes": {},
    }

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_resp_500, mock_resp_200]

        res = await razorpay_adapter.create_payment_link(req, mode="REAL_TEST")

        assert res.id == "plink_test_retry_ok"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_4_rate_limit_429_retry(razorpay_adapter):
    """Verify HTTP 429 Rate Limit triggers backoff retry."""
    req = PaymentLinkCreateRequest(
        amount=10000,
        currency="INR",
        reference_id="RAI-tx429-1",
    )

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "id": "plink_test_429_ok",
        "entity": "payment_link",
        "short_url": "https://rzp.io/i/429_ok",
        "status": "created",
        "amount": 10000,
        "amount_paid": 0,
        "currency": "INR",
        "reference_id": "RAI-tx429-1",
        "created_at": 1700000000,
        "notes": {},
    }

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_resp_429, mock_resp_200]

        res = await razorpay_adapter.create_payment_link(req, mode="REAL_TEST")

        assert res.id == "plink_test_429_ok"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_5_http_400_bad_request_raises_exception(razorpay_adapter):
    """Verify HTTP 400 Bad Request raises ValueError without retrying."""
    req = PaymentLinkCreateRequest(
        amount=10000,
        currency="INR",
        reference_id="RAI-tx400-1",
    )

    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.content = b'{"error": {"description": "Invalid customer phone"}}'
    mock_resp_400.json.return_value = {"error": {"description": "Invalid customer phone"}}

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp_400

        with pytest.raises(ValueError, match="Invalid customer phone"):
            await razorpay_adapter.create_payment_link(req, mode="REAL_TEST")

        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_6_network_timeout_maps_to_unknown_via_action_executor(async_test_session, razorpay_adapter):
    """Verify network timeout in RazorpayAdapter triggers UNKNOWN status in ActionExecutor."""
    merchant = Merchant(
        id=f"mer_step18_{uuid4().hex[:8]}",
        name="Step 18 Merchant",
        email="mer_step18@example.com",
        industry="ECOMMERCE",
        created_at=current_utc_time(),
    )
    customer = Customer(
        id=f"cust_step18_{uuid4().hex[:8]}",
        merchant_id=merchant.id,
        email="cust_step18@example.com",
        created_at=current_utc_time(),
    )
    async_test_session.add_all([merchant, customer])

    tx = Transaction(
        id=f"tx_step18_timeout_{uuid4().hex[:8]}",
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=150.00,
        currency="INR",
        status=TransactionStatus.APPROVED.value,
        scenario_type="PAYMENT_FAILURE",
        recovery_cycle=1,
        mode="REAL_TEST",
        created_at=current_utc_time(),
    )
    async_test_session.add(tx)
    await async_test_session.commit()

    exec_req = ActionExecutionRequest(
        transaction_id=tx.id,
        merchant_id=merchant.id,
        action_type="PAYMENT_LINK",
        action_payload={},
        mode_override="REAL_TEST",
    )

    with patch.object(httpx.AsyncClient, "post", side_effect=httpx.TimeoutException("Connection timed out")):
        res = await ActionExecutor.execute(
            session=async_test_session,
            request=exec_req,
            adapter_delegate=razorpay_adapter,
        )

        assert res.execution_status == ExecutionStatus.UNKNOWN.value
        assert res.transaction_id == tx.id

        await async_test_session.refresh(tx)
        assert tx.status == TransactionStatus.EXECUTING.value


def test_7_webhook_signature_verification():
    """Verify HMAC SHA-256 webhook signature verification helper."""
    secret = "test_webhook_secret_123"
    body = b'{"event": "payment_link.paid", "payload": {}}'

    valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # Valid signature
    assert RazorpayAdapter.verify_webhook_signature(body, valid_sig, secret=secret) is True

    # Invalid signature
    assert RazorpayAdapter.verify_webhook_signature(body, "invalid_sig_hash", secret=secret) is False

    # Modified body
    modified_body = b'{"event": "payment_link.paid", "payload": {"hacked": true}}'
    assert RazorpayAdapter.verify_webhook_signature(modified_body, valid_sig, secret=secret) is False


def test_8_security_no_credential_leakage(razorpay_adapter):
    """Verify adapter string representation masks sensitive API credentials."""
    repr_str = repr(razorpay_adapter)
    assert "secret_67890" not in repr_str
    assert "rzp_te***" in repr_str or "rzp_test_k***" in repr_str or "***" in repr_str


@pytest.mark.asyncio
async def test_9_merchant_isolation_boundary(razorpay_adapter):
    """Verify execute_action creates reference_id and notes tied strictly to transaction tenant."""
    tx = MagicMock()
    tx.id = "tx_tenant_1001"
    tx.amount = 499.00
    tx.currency = "INR"
    tx.recovery_cycle = 2
    tx.mode = "SIMULATION"

    req = MagicMock()
    req.merchant_id = "mer_tenant_alpha"
    req.action_type = "PAYMENT_LINK"
    req.mode_override = "SIMULATION"

    res = await razorpay_adapter.execute_action(tx, req)

    assert res["success"] is True
    assert res["razorpay_reference_id"] == "RAI-tx_tenant_10-2"
    assert res["external_resource_id"].startswith("plink_sim_")


@pytest.mark.asyncio
async def test_10_air_gap_simulation_isolation():
    """Verify SIMULATION mode makes zero network connections even with broken endpoint/keys."""
    broken_adapter = RazorpayAdapter(
        key_id="INVALID_KEY",
        key_secret="INVALID_SECRET",
        base_url="https://nonexistent.invalid.domain",
    )

    req = PaymentLinkCreateRequest(
        amount=5000,
        currency="INR",
        reference_id="RAI-airgap-1",
    )

    # Must succeed cleanly in SIMULATION without network call or DNS resolution exception
    res = await broken_adapter.create_payment_link(req, mode="SIMULATION")

    assert res.id.startswith("plink_sim_")
    assert res.amount == 5000
