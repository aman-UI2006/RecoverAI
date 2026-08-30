import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Callable
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from backend.app.core.config import settings
from backend.app.schemas.auth import AuthenticatedIdentity, RoleEnum, TokenPayload

# Password Hashing Context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# Security Schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)

# Mock API Key Store for Verification (maps API Key string -> (user_id, merchant_id, role))
MOCK_API_KEYS = {
    "key_admin_secret_999": ("admin_user_01", None, RoleEnum.ROLE_ADMIN.value),
    "key_merchant_alpha_123": ("merchant_user_1", "m_alpha_123", RoleEnum.ROLE_MERCHANT.value),
    "key_merchant_beta_456": ("merchant_user_2", "m_beta_456", RoleEnum.ROLE_MERCHANT.value),
    "key_reviewer_789": ("reviewer_user_1", None, RoleEnum.ROLE_HUMAN_REVIEWER.value),
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt password hash."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate signed JWT access token.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp())
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate signed JWT access token.
    Raises HTTPException 401 on invalid or expired token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject identifier",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenPayload(
            sub=sub,
            merchant_id=payload.get("merchant_id"),
            role=payload.get("role", RoleEnum.ROLE_MERCHANT.value),
            exp=payload.get("exp"),
            iat=payload.get("iat")
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials / invalid token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_identity(
    token_auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key_auth: Optional[str] = Security(api_key_scheme)
) -> AuthenticatedIdentity:
    """
    Authenticates incoming request using Bearer JWT or API Key header.
    Authoritative identity dependency.
    """
    # 1. Try JWT Bearer Token first
    if token_auth and token_auth.credentials:
        payload = decode_access_token(token_auth.credentials)
        return AuthenticatedIdentity(
            user_id=payload.sub,
            merchant_id=payload.merchant_id,
            role=payload.role,
            auth_type="jwt"
        )
    
    # 2. Try API Key Header second
    if api_key_auth:
        if api_key_auth in MOCK_API_KEYS:
            user_id, merchant_id, role = MOCK_API_KEYS[api_key_auth]
            return AuthenticatedIdentity(
                user_id=user_id,
                merchant_id=merchant_id,
                role=role,
                auth_type="api_key"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Neither credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials missing (Bearer token or X-API-Key required)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_merchant(
    identity: AuthenticatedIdentity = Depends(get_current_identity)
) -> Optional[str]:
    """
    Authoritative tenant dependency resolving merchant_id from authenticated identity.
    Client-supplied headers or query parameters cannot override identity.merchant_id.
    """
    if identity.role == RoleEnum.ROLE_ADMIN.value:
        # Admin can access any merchant scope or global view
        return identity.merchant_id
    
    if identity.merchant_id:
        return identity.merchant_id

    # If role is merchant but missing merchant_id
    if identity.role == RoleEnum.ROLE_MERCHANT.value and not identity.merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant role account lacks associated merchant tenant ID"
        )
    
    return None


def require_role(allowed_roles: List[RoleEnum]) -> Callable:
    """
    Dependency generator enforcing Role-Based Access Control (RBAC).
    """
    allowed_values = [r.value for r in allowed_roles]

    async def role_checker(
        identity: AuthenticatedIdentity = Depends(get_current_identity)
    ) -> AuthenticatedIdentity:
        # ROLE_ADMIN always possesses elevated access across roles
        if identity.role == RoleEnum.ROLE_ADMIN.value:
            return identity
        
        if identity.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action forbidden: Role '{identity.role}' does not have required permissions"
            )
        return identity

    return role_checker
