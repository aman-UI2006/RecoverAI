"""
RecoverAI - Transactions REST API Endpoint Controller (Step 25 & Step 26)

Provides GET /api/v1/transactions and GET /api/v1/transactions/{transaction_id}
enforcing RBAC, authenticated tenant isolation, pagination, scenario and status filters,
and full lifecycle state views without state mutation.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_identity
from backend.app.schemas.auth import AuthenticatedIdentity
from backend.app.models.domain import (
    Transaction,
    Customer,
    Diagnosis,
    RecoveryAttempt,
    RecoveryAttribution,
    AuditEvent,
)
from backend.app.schemas.transaction import (
    TransactionResponse,
    TransactionDetailResponse,
    TransactionPaginatedResponse,
    DiagnosisSummary,
    RecoveryAttemptSummary,
    RecoveryAttributionSummary,
    AuditTimelineItem,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionPaginatedResponse)
async def list_transactions(
    page: int = Query(1, ge=1, description="Page index (>=1)."),
    limit: int = Query(20, ge=1, le=100, description="Page size limit (1..100)."),
    scenario_type: Optional[str] = Query(None, description="Filter by failure scenario type."),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by transaction status."),
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    mode: Optional[str] = Query(None, description="Execution mode filter (REAL_TEST or SIMULATION)."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    List transactions with pagination, failure scenario, status filters, and RBAC tenant isolation.
    """
    # Authoritative tenant isolation: Identity merchant_id takes precedence
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    filters = []
    if effective_merchant_id:
        filters.append(Transaction.merchant_id == effective_merchant_id)
    if scenario_type:
        filters.append(Transaction.scenario_type == scenario_type)
    if status_filter:
        filters.append(Transaction.status == status_filter)
    if mode:
        filters.append(Transaction.mode == mode)

    # 1. Count total matching rows
    count_stmt = select(func.count(Transaction.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_count = (await session.execute(count_stmt)).scalar() or 0

    # 2. Fetch paginated records with deterministic ordering
    offset = (page - 1) * limit
    stmt = (
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if filters:
        stmt = stmt.where(and_(*filters))

    tx_rows = (await session.execute(stmt)).scalars().all()

    items = [TransactionResponse.model_validate(tx) for tx in tx_rows]

    return TransactionPaginatedResponse(
        total=total_count,
        page=page,
        limit=limit,
        items=items,
    )


@router.get("/{transaction_id}", response_model=TransactionDetailResponse)
async def get_transaction_detail(
    transaction_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant UUID filter for tenant isolation."),
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID", description="Tenant isolation header."),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve complete detail for a transaction including customer email, root cause diagnosis,
    recovery attempts, attributions, and audit timeline.
    Enforces cross-tenant HTTP 404 behavior.
    """
    if identity.merchant_id:
        effective_merchant_id = identity.merchant_id
    else:
        effective_merchant_id = merchant_id or x_merchant_id

    stmt = (
        select(Transaction)
        .options(
            selectinload(Transaction.customer),
            selectinload(Transaction.diagnoses),
            selectinload(Transaction.recovery_attempts),
            selectinload(Transaction.recovery_attributions),
            selectinload(Transaction.audit_events),
        )
        .where(Transaction.id == transaction_id)
    )

    result = await session.execute(stmt)
    tx = result.scalar_one_or_none()

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' was not found.",
        )

    # Enforce strict multi-tenant merchant isolation with 404 response
    if effective_merchant_id and tx.merchant_id != effective_merchant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' was not found.",
        )

    # Extract diagnosis if available
    latest_diagnosis = None
    if tx.diagnoses:
        sorted_diagnoses = sorted(tx.diagnoses, key=lambda d: d.created_at, reverse=True)
        d = sorted_diagnoses[0]
        latest_diagnosis = DiagnosisSummary.model_validate(d)

    # Extract recovery attempts
    attempts = [
        RecoveryAttemptSummary.model_validate(att)
        for att in sorted(tx.recovery_attempts, key=lambda a: a.created_at)
    ]

    # Extract recovery attributions
    attributions = [
        RecoveryAttributionSummary.model_validate(attr)
        for attr in sorted(tx.recovery_attributions, key=lambda a: a.recovery_timestamp)
    ]

    # Extract chronological audit timeline
    audit_timeline = [
        AuditTimelineItem.model_validate(evt)
        for evt in sorted(tx.audit_events, key=lambda e: e.created_at)
    ]

    base_dict = TransactionResponse.model_validate(tx).model_dump()
    base_dict["customer_email"] = tx.customer.email if tx.customer else None
    base_dict["diagnosis"] = latest_diagnosis
    base_dict["recovery_attempts"] = attempts
    base_dict["recovery_attributions"] = attributions
    base_dict["audit_timeline"] = audit_timeline

    return TransactionDetailResponse(**base_dict)
