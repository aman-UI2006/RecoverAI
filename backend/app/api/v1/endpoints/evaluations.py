"""
RecoverAI - Evaluations REST API Endpoint Controller (Step 25 & Step 26)

Provides GET /api/v1/evaluations and GET /api/v1/evaluations/{evaluation_id}
for querying historical evaluation run records with RBAC restricted to ROLE_ADMIN.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_role
from backend.app.schemas.auth import AuthenticatedIdentity, RoleEnum
from backend.app.models.domain import EvaluationRun
from backend.app.schemas.evaluation import EvaluationRunResponse, EvaluationPaginatedResponse

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("", response_model=EvaluationPaginatedResponse)
async def list_evaluations(
    page: int = Query(1, ge=1, description="Page index (>=1)."),
    limit: int = Query(20, ge=1, le=100, description="Page size limit (1..100)."),
    mode: Optional[str] = Query(None, description="Execution mode filter (REAL_TEST or SIMULATION)."),
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve historical evaluation run records with pagination and mode filtering. Admin restricted.
    """
    filters = []
    if mode:
        filters.append(EvaluationRun.mode == mode)

    # 1. Count matching evaluation runs
    count_stmt = select(func.count(EvaluationRun.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_count = (await session.execute(count_stmt)).scalar() or 0

    # 2. Fetch paginated records
    offset = (page - 1) * limit
    stmt = (
        select(EvaluationRun)
        .order_by(EvaluationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if filters:
        stmt = stmt.where(and_(*filters))

    eval_rows = (await session.execute(stmt)).scalars().all()
    items = [EvaluationRunResponse.model_validate(row) for row in eval_rows]

    return EvaluationPaginatedResponse(
        total=total_count,
        page=page,
        limit=limit,
        items=items,
    )


@router.get("/{evaluation_id}", response_model=EvaluationRunResponse)
async def get_evaluation(
    evaluation_id: str,
    identity: AuthenticatedIdentity = Depends(require_role([RoleEnum.ROLE_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve details of a specific evaluation run by ID. Admin restricted.
    """
    stmt = select(EvaluationRun).where(EvaluationRun.id == evaluation_id)
    eval_run = (await session.execute(stmt)).scalar_one_or_none()

    if not eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run with ID '{evaluation_id}' was not found.",
        )

    return EvaluationRunResponse.model_validate(eval_run)
