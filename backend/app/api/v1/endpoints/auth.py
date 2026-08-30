from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.config import settings
from backend.app.core.security import create_access_token, get_current_identity
from backend.app.schemas.auth import LoginRequest, Token, AuthenticatedIdentity, RoleEnum

router = APIRouter()

# Mock user credentials store for testing/demo authentication
MOCK_USERS = {
    "admin": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", # "secret123"
        "plain_password": "secret123",
        "user_id": "usr_admin_001",
        "merchant_id": None,
        "role": RoleEnum.ROLE_ADMIN.value
    },
    "merchant_alpha": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "plain_password": "secret123",
        "user_id": "usr_merchant_alpha",
        "merchant_id": "m_alpha_123",
        "role": RoleEnum.ROLE_MERCHANT.value
    },
    "merchant_beta": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "plain_password": "secret123",
        "user_id": "usr_merchant_beta",
        "merchant_id": "m_beta_456",
        "role": RoleEnum.ROLE_MERCHANT.value
    },
    "reviewer": {
        "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "plain_password": "secret123",
        "user_id": "usr_reviewer_001",
        "merchant_id": None,
        "role": RoleEnum.ROLE_HUMAN_REVIEWER.value
    }
}


@router.post("/login", response_model=Token, summary="User Authentication & Token Issuance")
async def login(payload: LoginRequest) -> Token:
    """
    Authenticate credentials and issue signed JWT access token.
    """
    username = payload.username
    user_record = MOCK_USERS.get(username)

    if not user_record or payload.password != user_record["plain_password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    assigned_role = user_record["role"]
    merchant_id = payload.merchant_id or user_record["merchant_id"]

    token_data = {
        "sub": user_record["user_id"],
        "role": assigned_role,
        "merchant_id": merchant_id
    }

    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=assigned_role,
        merchant_id=merchant_id
    )


@router.get("/me", response_model=AuthenticatedIdentity, summary="Retrieve Current Identity Scope")
async def get_me(
    identity: AuthenticatedIdentity = Depends(get_current_identity)
) -> AuthenticatedIdentity:
    """
    Returns current authenticated identity payload.
    """
    return identity
