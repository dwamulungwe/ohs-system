from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.contractor import ContractorInductionStatus, ContractorOnboardingStatus, ContractorRecord
from app.models.user import User
from app.schemas.contractor import ContractorCreate, ContractorListRead, ContractorRead, ContractorUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.contractor_service import (
    ContractorNotFoundError,
    ContractorValidationError,
    create_contractor,
    get_contractor,
    list_contractors,
    update_contractor,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope

router = APIRouter()


@router.get("", response_model=ContractorListRead)
def read_contractors(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None,
    approved_for_work: Optional[bool] = None,
    onboarding_status: Optional[ContractorOnboardingStatus] = None,
    induction_status: Optional[ContractorInductionStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.CONTRACTORS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_contractors(
        db,
        skip=skip,
        limit=limit,
        site_id=site_id,
        approved_for_work=approved_for_work,
        onboarding_status=onboarding_status,
        induction_status=induction_status,
    )


@router.post("", response_model=ContractorRead, status_code=status.HTTP_201_CREATED)
def create_contractor_record(
    contractor_in: ContractorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractorRecord:
    ensure_permission(current_user, Permission.CONTRACTORS_CREATE)
    contractor_in = contractor_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, contractor_in.site_id)}
    )
    if contractor_in.approved_for_work:
        ensure_permission(current_user, Permission.CONTRACTORS_APPROVE)
    try:
        return create_contractor(db, contractor_in, actor_id=current_user.id)
    except ContractorValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{contractor_id}", response_model=ContractorRead)
def read_contractor_record(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractorRecord:
    ensure_permission(current_user, Permission.CONTRACTORS_VIEW)
    try:
        contractor = get_contractor(db, contractor_id)
        ensure_site_access(current_user, contractor.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.contractor, contractor)
    except ContractorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")


@router.patch("/{contractor_id}", response_model=ContractorRead)
def patch_contractor_record(
    contractor_id: int,
    contractor_in: ContractorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractorRecord:
    ensure_permission(current_user, Permission.CONTRACTORS_EDIT)
    try:
        contractor = get_contractor(db, contractor_id)
        ensure_site_access(current_user, contractor.site_id)
        if contractor_in.site_id is not None:
            contractor_in = contractor_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, contractor_in.site_id)}
            )
        if contractor_in.approved_for_work:
            ensure_permission(current_user, Permission.CONTRACTORS_APPROVE)
        return update_contractor(db, contractor, contractor_in, actor_id=current_user.id)
    except ContractorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
    except ContractorValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
