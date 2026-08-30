"""
RecoverAI - Audit REST API Endpoint Controller (Step 25 & Step 26)

Provides GET /api/v1/audit and GET /api/v1/audit/verify for viewing audit log records
and cryptographically validating transaction hash chain integrity via AuditTrailService with RBAC.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_identity
from backend.app.schemas.auth import AuthenticatedIdentity
from backend.app.models.domain import AuditEvent, Transaction
from backend.app.services.audit_trail_service import AuditTrailService, GENESIS_HASH
from backend.app.schemas.audit import (
    AuditEventResponse,
    AuditPaginatedResponse,
    AuditVerificationResponse,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPaginatedResponse)
async def list_audit_events(
    page: int = Query(1, ge=1, description="Page index (>=1)."),
    limit: int = Query(50, ge=1, le=100, description="Page size limit (1..100)."),
    transaction_id: Optional[str] = Query(None, description="Transaction UUID filter."),
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve read-only audit log records with pagination and RBAC multi-tenant isolation filters.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    filters = []
    if transaction_id:
        filters.append(AuditEvent.transaction_id == transaction_id)

    if effective_merchant_id:
        # Join Transaction to enforce merchant isolation
        stmt_tx_ids = select(Transaction.id).where(Transaction.merchant_id == effective_merchant_id)
        tx_ids = (await session.execute(stmt_tx_ids)).scalars().all()
        filters.append(AuditEvent.transaction_id.in_(tx_ids))

    # 1. Count matching audit records
    count_stmt = select(func.count(AuditEvent.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_count = (await session.execute(count_stmt)).scalar() or 0

    # 2. Fetch paginated audit events
    offset = (page - 1) * limit
    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if filters:
        stmt = stmt.where(and_(*filters))

    audit_rows = (await session.execute(stmt)).scalars().all()
    items = [AuditEventResponse.model_validate(row) for row in audit_rows]

    return AuditPaginatedResponse(
        total=total_count,
        page=page,
        limit=limit,
        items=items,
    )


@router.get("/verify", response_model=AuditVerificationResponse)
async def verify_audit_chain(
    transaction_id: str = Query(..., description="Transaction UUID to verify."),
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    Cryptographically verify SHA-256 hash chain integrity for a transaction via AuditTrailService.
    Read-only operation.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    # Verify transaction existence & tenant isolation
    stmt_tx = select(Transaction).where(Transaction.id == transaction_id)
    tx = (await session.execute(stmt_tx)).scalar_one_or_none()

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' was not found.",
        )

    if effective_merchant_id and tx.merchant_id != effective_merchant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' was not found.",
        )

    res = await AuditTrailService.verify_chain(session=session, transaction_id=transaction_id)

    is_valid = res.get("valid", False)
    total_events = res.get("total_events", 0)
    failed_event_id = res.get("failed_event_id")
    reason = res.get("reason")

    return AuditVerificationResponse(
        transaction_id=transaction_id,
        is_valid=is_valid,
        total_events=total_events,
        tampered_event_id=failed_event_id,
        error_message=reason,
        genesis_hash=GENESIS_HASH,
    )
