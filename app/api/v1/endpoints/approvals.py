from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.approval import ApprovalActionType, ApprovalEntityType, ApprovalStatus, ApprovalWorkflow
from app.models.user import User
from app.schemas.approval import ApprovalDecisionUpdate, ApprovalListRead, ApprovalRead, ApprovalRequestCreate
from app.services.approval_service import (
    ApprovalDuplicatePendingError,
    ApprovalEntityNotFoundError,
    ApprovalNotFoundError,
    ApprovalValidationError,
    decide_approval,
    get_approval,
    list_approvals,
    request_approval,
)

router = APIRouter()


@router.post(
    "/{entity_type}/{entity_id}/request",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_approval_request(
    entity_type: ApprovalEntityType,
    entity_id: int,
    approval_in: ApprovalRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalWorkflow:
    try:
        return request_approval(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            approval_in=approval_in,
            current_user=current_user,
        )
    except ApprovalEntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Related record not found")
    except ApprovalDuplicatePendingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ApprovalValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("", response_model=ApprovalListRead)
def list_approval_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    entity_type: ApprovalEntityType | None = None,
    entity_id: int | None = None,
    action_type: ApprovalActionType | None = None,
    approval_status: ApprovalStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return list_approvals(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        approval_status=approval_status,
    )


@router.get("/{approval_id}", response_model=ApprovalRead)
def get_approval_record(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalWorkflow:
    try:
        return get_approval(db, approval_id, current_user=current_user)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    except ApprovalEntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Related record not found")


@router.patch("/{approval_id}/decision", response_model=ApprovalRead)
def decide_approval_record(
    approval_id: int,
    decision_in: ApprovalDecisionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalWorkflow:
    try:
        return decide_approval(
            db,
            approval_id=approval_id,
            decision_in=decision_in,
            current_user=current_user,
        )
    except ApprovalNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    except ApprovalEntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Related record not found")
    except ApprovalValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
