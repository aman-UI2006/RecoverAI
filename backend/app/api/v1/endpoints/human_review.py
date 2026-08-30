"""
RecoverAI - Step 16 & Step 26: Human Review REST API Endpoints

Provides REST endpoints for fetching review items and recording reviewer decisions
(APPROVE_OVERRIDE, REJECT_PERMANENT) with RBAC role authorization and multi-tenant isolation.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_identity, require_role
from backend.app.schemas.auth import AuthenticatedIdentity, RoleEnum
from backend.app.schemas.human_review import (
    ReviewItemCreate,
    ReviewDecisionSubmit,
    HumanReviewResponse,
    HumanReviewQueueResponse,
)
from backend.app.services.human_review_service import HumanReviewService

router = APIRouter(prefix="/human-review", tags=["Human Review"])


def helper_build_review_response(review, tx) -> HumanReviewResponse:
    """Helper to convert HumanReview ORM model and Transaction ORM model into schema response."""
    return HumanReviewResponse(
        id=review.id,
        transaction_id=review.transaction_id,
        merchant_id=tx.merchant_id,
        status=review.status,
        reason=review.reason,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        notes=review.notes,
        reviewed_at=review.reviewed_at,
        created_at=review.created_at,
        amount=float(tx.amount),
        currency=tx.currency,
        scenario_type=tx.scenario_type,
        mode=tx.mode,
    )


@router.post(
    "/escalate",
    response_model=HumanReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Escalate a transaction to Human Review queue",
)
async def escalate_transaction_endpoint(
    payload: ReviewItemCreate,
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> HumanReviewResponse:
    """Escalates a transaction to the human review queue and updates state to ESCALATED."""
    effective_merchant_id = identity.merchant_id or x_merchant_id
    try:
        review_record = await HumanReviewService.escalate_transaction(
            session=db,
            transaction_id=payload.transaction_id,
            reason=payload.reason,
            merchant_id=effective_merchant_id,
            reviewer_notes=payload.reviewer_notes,
        )
        review, tx = await HumanReviewService.get_review_item(db, review_record.id, effective_merchant_id)
        return helper_build_review_response(review, tx)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/queue",
    response_model=HumanReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch pending human review items queue",
)
async def get_human_review_queue_endpoint(
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID"),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN, RoleEnum.ROLE_HUMAN_REVIEWER])),
    db: AsyncSession = Depends(get_db),
) -> HumanReviewQueueResponse:
    """Returns all pending review items, isolated by merchant_id if header is provided."""
    effective_merchant_id = identity.merchant_id or x_merchant_id
    pairs = await HumanReviewService.get_pending_reviews(session=db, merchant_id=effective_merchant_id)
    items = [helper_build_review_response(review, tx) for review, tx in pairs]
    return HumanReviewQueueResponse(items=items, count=len(items))


@router.get(
    "/items/{review_id}",
    response_model=HumanReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch a specific human review item by ID",
)
async def get_human_review_item_endpoint(
    review_id: str,
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID"),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN, RoleEnum.ROLE_HUMAN_REVIEWER])),
    db: AsyncSession = Depends(get_db),
) -> HumanReviewResponse:
    """Fetches details of a specific human review item."""
    effective_merchant_id = identity.merchant_id or x_merchant_id
    try:
        review, tx = await HumanReviewService.get_review_item(
            session=db, review_id=review_id, merchant_id=effective_merchant_id
        )
        return helper_build_review_response(review, tx)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/items/{review_id}/decision",
    response_model=HumanReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Record reviewer decision (APPROVE_OVERRIDE or REJECT_PERMANENT)",
)
async def process_reviewer_decision_endpoint(
    review_id: str,
    payload: ReviewDecisionSubmit,
    x_merchant_id: Optional[str] = Header(None, alias="X-Merchant-ID"),
    x_user_role: str = Header("ROLE_HUMAN_REVIEWER", alias="X-User-Role"),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN, RoleEnum.ROLE_HUMAN_REVIEWER])),
    db: AsyncSession = Depends(get_db),
) -> HumanReviewResponse:
    """Records reviewer decision, mutates state via StateTransitionService, and requires ROLE_HUMAN_REVIEWER role."""
    effective_merchant_id = identity.merchant_id or x_merchant_id
    effective_role = identity.role or x_user_role
    try:
        review, tx = await HumanReviewService.process_reviewer_decision(
            session=db,
            review_id=review_id,
            decision=payload.decision,
            reviewer_id=payload.reviewer_id,
            notes=payload.notes,
            merchant_id=effective_merchant_id,
            user_role=effective_role,
        )
        return helper_build_review_response(review, tx)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/auto-expire",
    status_code=status.HTTP_200_OK,
    summary="Auto-expire stale review queue items",
)
async def auto_expire_stale_reviews_endpoint(
    expiration_hours: int = Query(48, ge=1, le=720),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN])),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Auto-expires pending review queue items older than expiration_hours and sets transaction state to STOPPED."""
    expired_ids = await HumanReviewService.auto_expire_stale_reviews(
        session=db, expiration_hours=expiration_hours
    )
    return {"expired_count": len(expired_ids), "expired_review_ids": expired_ids}
