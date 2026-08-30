from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    ROLE_ADMIN = "ROLE_ADMIN"
    ROLE_MERCHANT = "ROLE_MERCHANT"
    ROLE_HUMAN_REVIEWER = "ROLE_HUMAN_REVIEWER"


class LoginRequest(BaseModel):
    username: str = Field(..., description="User login identifier or email")
    password: str = Field(..., description="User password")
    merchant_id: Optional[str] = Field(default=None, description="Merchant ID context if applicable")
    role: Optional[RoleEnum] = Field(default=RoleEnum.ROLE_MERCHANT, description="Requested role scope")


class Token(BaseModel):
    access_token: str = Field(..., description="JWT Bearer Access Token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token validity duration in seconds")
    role: str = Field(..., description="Assigned identity role")
    merchant_id: Optional[str] = Field(default=None, description="Scoped merchant ID")


class TokenPayload(BaseModel):
    sub: str = Field(..., description="Subject user identifier")
    merchant_id: Optional[str] = Field(default=None, description="Authoritative merchant ID")
    role: str = Field(..., description="Assigned RBAC role")
    exp: int = Field(..., description="Expiration timestamp (epoch)")
    iat: int = Field(..., description="Issued at timestamp (epoch)")


class AuthenticatedIdentity(BaseModel):
    user_id: str = Field(..., description="Authenticated user ID")
    merchant_id: Optional[str] = Field(default=None, description="Authoritative merchant tenant ID")
    role: str = Field(..., description="Active RBAC role")
    auth_type: str = Field(..., description="Authentication method (jwt or api_key)")
