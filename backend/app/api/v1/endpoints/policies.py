"""
RecoverAI - Policies REST API Endpoint Controller (Step 25 & Step 26)

Provides GET /api/v1/policies, GET /api/v1/policies/{policy_id}, and PATCH /api/v1/policies/{policy_id}
for inspecting and updating merchant policy rules with strict partial update semantics, RBAC, and tenant isolation.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_identity, require_role
from backend.app.schemas.auth import AuthenticatedIdentity, RoleEnum
from backend.app.models.domain import Policy
from backend.app.schemas.policy import PolicyResponse, PolicyUpdatePayload

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=List[PolicyResponse])
async def list_policies(
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    List merchant policies with authenticated merchant_id filter.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    stmt = select(Policy).order_by(Policy.created_at.desc())
    if effective_merchant_id:
        stmt = stmt.where(Policy.merchant_id == effective_merchant_id)

    policy_rows = (await session.execute(stmt)).scalars().all()
    return [PolicyResponse.model_validate(p) for p in policy_rows]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve specific merchant policy by ID. Enforces cross-tenant 404 behavior.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    stmt = select(Policy).where(Policy.id == policy_id)
    policy = (await session.execute(stmt)).scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' was not found.",
        )

    if effective_merchant_id and policy.merchant_id and policy.merchant_id != effective_merchant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' was not found.",
        )

    return PolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdatePayload,
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN, RoleEnum.ROLE_MERCHANT])),
    session: AsyncSession = Depends(get_db),
):
    """
    Partially update policy guardrail settings while preserving unspecified fields and policy versioning.
    Enforces cross-tenant 404 behavior.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    stmt = select(Policy).where(Policy.id == policy_id)
    policy = (await session.execute(stmt)).scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' was not found.",
        )

    if effective_merchant_id and policy.merchant_id and policy.merchant_id != effective_merchant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' was not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    for field_name, new_val in update_data.items():
        if hasattr(policy, field_name) and new_val is not None:
            setattr(policy, field_name, new_val)

    await session.commit()
    await session.refresh(policy)

    return PolicyResponse.model_validate(policy)
