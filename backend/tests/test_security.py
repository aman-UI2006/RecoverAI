"""
RecoverAI - Step 26 Security Test Suite

Comprehensive test suite verifying JWT authentication, API key authentication, RBAC authorization,
authoritative merchant tenant isolation, header-spoofing prevention, and token management.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.domain import Merchant, Customer, Transaction, Policy
from backend.app.schemas.auth import RoleEnum, AuthenticatedIdentity

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create isolated in-memory SQLite DB for security tests."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def unauth_client(db_session: AsyncSession):
    """Unauthenticated HTTP client for testing 401 unauthorized errors."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def security_test_data(db_session: AsyncSession):
    """Seed DB with multi-tenant data for security tests."""
    session = db_session

    m_a_id = "m_alpha_123"
    m_b_id = "m_beta_456"

    m_a = Merchant(id=m_a_id, name="Merchant Alpha", email="alpha@test.com", industry="ECOM")
    m_b = Merchant(id=m_b_id, name="Merchant Beta", email="beta@test.com", industry="SAAS")
    session.add_all([m_a, m_b])
    await session.flush()

    c_a = Customer(id=str(uuid.uuid4()), merchant_id=m_a_id, email="ca@test.com", name="Cust A")
    c_b = Customer(id=str(uuid.uuid4()), merchant_id=m_b_id, email="cb@test.com", name="Cust B")
    session.add_all([c_a, c_b])
    await session.flush()

    tx_a = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_a_id,
        customer_id=c_a.id,
        amount=Decimal("1000.00"),
        currency="INR",
        status="FAILED",
        scenario_type="CARD_AUTHENTICATION_FAILED",
        mode="SIMULATION",
    )
    tx_b = Transaction(
        id=str(uuid.uuid4()),
        merchant_id=m_b_id,
        customer_id=c_b.id,
        amount=Decimal("2000.00"),
        currency="INR",
        status="FAILED",
        scenario_type="PAYMENT_LINK_EXPIRED",
        mode="SIMULATION",
    )
    session.add_all([tx_a, tx_b])

    pol_a = Policy(id=str(uuid.uuid4()), merchant_id=m_a_id, policy_version="v1.0")
    pol_b = Policy(id=str(uuid.uuid4()), merchant_id=m_b_id, policy_version="v1.0")
    session.add_all([pol_a, pol_b])

    await session.commit()

    return {
        "m_a_id": m_a_id,
        "m_b_id": m_b_id,
        "tx_a_id": tx_a.id,
        "tx_b_id": tx_b.id,
        "pol_a_id": pol_a.id,
        "pol_b_id": pol_b.id,
    }


# =====================================================================
# 1. UTILITY & PASSWORD HASHING TESTS
# =====================================================================

def test_1_password_hashing():
    """1. Password hashing and verification functions."""
    raw = "MySecretPass123!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_2_jwt_encode_decode():
    """2. JWT creation and decoding helpers."""
    token = create_access_token(
        data={"sub": "usr_test_123", "role": RoleEnum.ROLE_MERCHANT.value, "merchant_id": "m_test_999"},
        expires_delta=timedelta(minutes=10)
    )
    payload = decode_access_token(token)
    assert payload.sub == "usr_test_123"
    assert payload.role == RoleEnum.ROLE_MERCHANT.value
    assert payload.merchant_id == "m_test_999"


# =====================================================================
# 2. AUTHENTICATION ENDPOINT TESTS (LOGIN & GET ME)
# =====================================================================

@pytest.mark.asyncio
async def test_3_login_success(unauth_client):
    """3. Successful login returns JWT access token."""
    res = await unauth_client.post(
        "/api/v1/auth/login",
        json={"username": "merchant_alpha", "password": "secret123"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == RoleEnum.ROLE_MERCHANT.value
    assert data["merchant_id"] == "m_alpha_123"


@pytest.mark.asyncio
async def test_4_login_invalid_password(unauth_client):
    """4. Login with invalid password returns 401 Unauthorized."""
    res = await unauth_client.post(
        "/api/v1/auth/login",
        json={"username": "merchant_alpha", "password": "wrongpassword"}
    )
    assert res.status_code == 401
    assert res.json()["error"] is True


@pytest.mark.asyncio
async def test_5_login_unknown_user(unauth_client):
    """5. Login with non-existent username returns 401 Unauthorized."""
    res = await unauth_client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user", "password": "secret123"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_6_get_me_jwt(unauth_client):
    """6. GET /auth/me with Bearer token returns current identity."""
    token = create_access_token({
        "sub": "usr_alpha_1",
        "merchant_id": "m_alpha_123",
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    headers = {"Authorization": f"Bearer {token}"}
    res = await unauth_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "usr_alpha_1"
    assert data["merchant_id"] == "m_alpha_123"
    assert data["role"] == RoleEnum.ROLE_MERCHANT.value
    assert data["auth_type"] == "jwt"


@pytest.mark.asyncio
async def test_7_get_me_api_key(unauth_client):
    """7. GET /auth/me with X-API-Key header returns identity."""
    headers = {"X-API-Key": "key_merchant_alpha_123"}
    res = await unauth_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["merchant_id"] == "m_alpha_123"
    assert data["auth_type"] == "api_key"


# =====================================================================
# 3. AUTHENTICATION ENFORCEMENT & ERROR SCENARIOS
# =====================================================================

@pytest.mark.asyncio
async def test_8_missing_authentication(unauth_client):
    """8. Unauthenticated request to protected endpoint returns HTTP 401."""
    res = await unauth_client.get("/api/v1/transactions")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_9_invalid_jwt_signature(unauth_client):
    """9. JWT token with tampered signature returns HTTP 401."""
    token = create_access_token({"sub": "user1", "role": "ROLE_ADMIN"})
    tampered_token = token[:-5] + "XXXXX"
    res = await unauth_client.get(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_10_expired_jwt_token(unauth_client):
    """10. Expired JWT token returns HTTP 401."""
    token = create_access_token(
        data={"sub": "user1", "role": "ROLE_ADMIN"},
        expires_delta=timedelta(seconds=-10)
    )
    res = await unauth_client.get(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_11_invalid_api_key(unauth_client):
    """11. Invalid X-API-Key header returns HTTP 401."""
    res = await unauth_client.get(
        "/api/v1/transactions",
        headers={"X-API-Key": "invalid_api_key_string"}
    )
    assert res.status_code == 401


# =====================================================================
# 4. RBAC ROLE AUTHORIZATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_12_rbac_admin_allowed_evaluations(unauth_client, security_test_data):
    """12. ROLE_ADMIN can access /evaluations endpoint."""
    admin_token = create_access_token({"sub": "admin1", "role": RoleEnum.ROLE_ADMIN.value})
    res = await unauth_client.get(
        "/api/v1/evaluations",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_13_rbac_merchant_forbidden_evaluations(unauth_client):
    """13. ROLE_MERCHANT attempting to access /evaluations returns HTTP 403."""
    merchant_token = create_access_token({
        "sub": "m_user_1",
        "merchant_id": "m_alpha_123",
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    res = await unauth_client.get(
        "/api/v1/evaluations",
        headers={"Authorization": f"Bearer {merchant_token}"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_14_rbac_reviewer_forbidden_evaluations(unauth_client):
    """14. ROLE_HUMAN_REVIEWER attempting to access /evaluations returns HTTP 403."""
    reviewer_token = create_access_token({
        "sub": "rev_1",
        "role": RoleEnum.ROLE_HUMAN_REVIEWER.value
    })
    res = await unauth_client.get(
        "/api/v1/evaluations",
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_15_rbac_reviewer_allowed_queue(unauth_client):
    """15. ROLE_HUMAN_REVIEWER can access /human-review/queue."""
    reviewer_token = create_access_token({
        "sub": "rev_1",
        "role": RoleEnum.ROLE_HUMAN_REVIEWER.value
    })
    res = await unauth_client.get(
        "/api/v1/human-review/queue",
        headers={"Authorization": f"Bearer {reviewer_token}"}
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_16_rbac_merchant_forbidden_queue(unauth_client):
    """16. ROLE_MERCHANT accessing /human-review/queue returns HTTP 403."""
    merchant_token = create_access_token({
        "sub": "m_user_1",
        "merchant_id": "m_alpha_123",
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    res = await unauth_client.get(
        "/api/v1/human-review/queue",
        headers={"Authorization": f"Bearer {merchant_token}"}
    )
    assert res.status_code == 403


# =====================================================================
# 5. MULTI-TENANT ISOLATION & HEADER SPOOFING PREVENTION
# =====================================================================

@pytest.mark.asyncio
async def test_17_cross_tenant_isolation_transaction_detail(unauth_client, security_test_data):
    """17. Merchant A JWT cannot access Merchant B transaction detail (returns 404)."""
    m_a_token = create_access_token({
        "sub": "user_a",
        "merchant_id": security_test_data["m_a_id"],
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    tx_b_id = security_test_data["tx_b_id"]

    res = await unauth_client.get(
        f"/api/v1/transactions/{tx_b_id}",
        headers={"Authorization": f"Bearer {m_a_token}"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_18_header_spoofing_prevention(unauth_client, security_test_data):
    """18. X-Merchant-ID header spoofing attempt is ignored when JWT identity is present."""
    m_a_token = create_access_token({
        "sub": "user_a",
        "merchant_id": security_test_data["m_a_id"],
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    tx_b_id = security_test_data["tx_b_id"]

    # Client passes Merchant A JWT but tries to spoof X-Merchant-ID header to Merchant B
    headers = {
        "Authorization": f"Bearer {m_a_token}",
        "X-Merchant-ID": security_test_data["m_b_id"]
    }
    res = await unauth_client.get(f"/api/v1/transactions/{tx_b_id}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_19_cross_tenant_policy_patch_isolation(unauth_client, security_test_data):
    """19. Merchant A JWT cannot PATCH Merchant B policy (returns 404)."""
    m_a_token = create_access_token({
        "sub": "user_a",
        "merchant_id": security_test_data["m_a_id"],
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    pol_b_id = security_test_data["pol_b_id"]

    res = await unauth_client.patch(
        f"/api/v1/policies/{pol_b_id}",
        json={"cooldown_hours": 12},
        headers={"Authorization": f"Bearer {m_a_token}"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_20_cross_tenant_audit_verification_isolation(unauth_client, security_test_data):
    """20. Merchant A JWT cannot verify Merchant B transaction audit chain (returns 404)."""
    m_a_token = create_access_token({
        "sub": "user_a",
        "merchant_id": security_test_data["m_a_id"],
        "role": RoleEnum.ROLE_MERCHANT.value
    })
    tx_b_id = security_test_data["tx_b_id"]

    res = await unauth_client.get(
        f"/api/v1/audit/verify?transaction_id={tx_b_id}",
        headers={"Authorization": f"Bearer {m_a_token}"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_21_admin_global_tenant_access(unauth_client, security_test_data):
    """21. ROLE_ADMIN can query transactions for any merchant scope."""
    admin_token = create_access_token({"sub": "admin1", "role": RoleEnum.ROLE_ADMIN.value})
    tx_b_id = security_test_data["tx_b_id"]

    res = await unauth_client.get(
        f"/api/v1/transactions/{tx_b_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    assert res.json()["id"] == tx_b_id
