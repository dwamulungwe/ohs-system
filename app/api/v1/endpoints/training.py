from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.training import ComplianceAcknowledgementStatus, TrainingStatus, TrainingType
from app.models.user import User
from app.schemas.training import (
    ComplianceAcknowledgementCreate,
    ComplianceAcknowledgementListRead,
    ComplianceAcknowledgementRead,
    ComplianceAcknowledgementUpdate,
    TrainingRecordCreate,
    TrainingRecordListRead,
    TrainingRecordRead,
    TrainingRecordUpdate,
)
from app.services.training_service import (
    ComplianceAcknowledgementNotFoundError,
    TrainingRecordNotFoundError,
    TrainingSiteNotFoundError,
    TrainingUserNotFoundError,
    create_compliance_acknowledgement,
    create_training_record,
    get_compliance_acknowledgement,
    get_training_record,
    list_compliance_acknowledgements,
    list_training_records,
    update_compliance_acknowledgement,
    update_training_record,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    resolve_site_scope,
)

router = APIRouter()
TRAINING_SELF_UPDATE_FIELDS = {"completed_at", "status", "certificate_metadata", "notes"}
COMPLIANCE_SELF_UPDATE_FIELDS = {"acknowledged_at", "status", "notes"}


@router.get("/training", response_model=TrainingRecordListRead)
def list_training(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[TrainingStatus] = None,
    training_type: Optional[TrainingType] = None,
    site_id: Optional[int] = None,
    assigned_to_user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if has_permission(current_user, Permission.TRAINING_VIEW_ALL):
        site_id = resolve_site_scope(current_user, site_id)
    elif has_permission(current_user, Permission.TRAINING_SELF_VIEW):
        site_id = resolve_site_scope(current_user, site_id)
        if assigned_to_user_id is not None and assigned_to_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        assigned_to_user_id = current_user.id
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return list_training_records(
        db,
        skip=skip,
        limit=limit,
        status=status,
        training_type=training_type,
        site_id=site_id,
        assigned_to_user_id=assigned_to_user_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/training", response_model=TrainingRecordRead, status_code=status.HTTP_201_CREATED)
def create_training(
    training_in: TrainingRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.TRAINING_MANAGE)
    if training_in.site_id is not None:
        training_in = training_in.model_copy(
            update={"site_id": resolve_site_scope(current_user, training_in.site_id)}
        )
    try:
        return create_training_record(db, training_in, current_user_id=current_user.id)
    except TrainingSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except TrainingUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")


@router.get("/training/{training_id}", response_model=TrainingRecordRead)
def get_training(
    training_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        record = get_training_record(db, training_id)
        if has_permission(current_user, Permission.TRAINING_VIEW_ALL):
            ensure_site_access(current_user, record.site_id)
        elif has_permission(current_user, Permission.TRAINING_SELF_VIEW):
            if record.assigned_to_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return hydrate_entity_attachments(db, AttachmentEntityType.training, record)
    except TrainingRecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training record not found")


@router.patch("/training/{training_id}", response_model=TrainingRecordRead)
def patch_training(
    training_id: int,
    training_in: TrainingRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        record = get_training_record(db, training_id)
        update_data = training_in.model_dump(exclude_unset=True)
        if has_permission(current_user, Permission.TRAINING_MANAGE):
            ensure_site_access(current_user, record.site_id)
        elif has_permission(current_user, Permission.TRAINING_SELF_UPDATE):
            if record.assigned_to_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if not set(update_data).issubset(TRAINING_SELF_UPDATE_FIELDS):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return update_training_record(db, record, training_in)
    except TrainingRecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training record not found")
    except TrainingSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except TrainingUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")


@router.get("/compliance-acknowledgements", response_model=ComplianceAcknowledgementListRead)
def list_acknowledgements(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[ComplianceAcknowledgementStatus] = None,
    document_type: Optional[str] = None,
    site_id: Optional[int] = None,
    assigned_to_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if has_permission(current_user, Permission.COMPLIANCE_VIEW_ALL):
        site_id = resolve_site_scope(current_user, site_id)
    elif has_permission(current_user, Permission.COMPLIANCE_SELF_VIEW):
        site_id = resolve_site_scope(current_user, site_id)
        if assigned_to_user_id is not None and assigned_to_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        assigned_to_user_id = current_user.id
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    return list_compliance_acknowledgements(
        db,
        skip=skip,
        limit=limit,
        status=status,
        document_type=document_type,
        site_id=site_id,
        assigned_to_user_id=assigned_to_user_id,
    )


@router.post("/compliance-acknowledgements", response_model=ComplianceAcknowledgementRead, status_code=status.HTTP_201_CREATED)
def create_acknowledgement(
    acknowledgement_in: ComplianceAcknowledgementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.COMPLIANCE_MANAGE)
    if acknowledgement_in.site_id is not None:
        acknowledgement_in = acknowledgement_in.model_copy(
            update={"site_id": resolve_site_scope(current_user, acknowledgement_in.site_id)}
        )
    try:
        return create_compliance_acknowledgement(db, acknowledgement_in, current_user_id=current_user.id)
    except TrainingSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except TrainingUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")


@router.get("/compliance-acknowledgements/{acknowledgement_id}", response_model=ComplianceAcknowledgementRead)
def get_acknowledgement(
    acknowledgement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        acknowledgement = get_compliance_acknowledgement(db, acknowledgement_id)
        if has_permission(current_user, Permission.COMPLIANCE_VIEW_ALL):
            ensure_site_access(current_user, acknowledgement.site_id)
        elif has_permission(current_user, Permission.COMPLIANCE_SELF_VIEW):
            if acknowledgement.assigned_to_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return hydrate_entity_attachments(
            db,
            AttachmentEntityType.compliance_acknowledgement,
            acknowledgement,
        )
    except ComplianceAcknowledgementNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance acknowledgement not found")


@router.patch("/compliance-acknowledgements/{acknowledgement_id}", response_model=ComplianceAcknowledgementRead)
def patch_acknowledgement(
    acknowledgement_id: int,
    acknowledgement_in: ComplianceAcknowledgementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        acknowledgement = get_compliance_acknowledgement(db, acknowledgement_id)
        update_data = acknowledgement_in.model_dump(exclude_unset=True)
        if has_permission(current_user, Permission.COMPLIANCE_MANAGE):
            ensure_site_access(current_user, acknowledgement.site_id)
        elif has_permission(current_user, Permission.COMPLIANCE_SELF_UPDATE):
            if acknowledgement.assigned_to_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if not set(update_data).issubset(COMPLIANCE_SELF_UPDATE_FIELDS):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return update_compliance_acknowledgement(db, acknowledgement, acknowledgement_in)
    except ComplianceAcknowledgementNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance acknowledgement not found")
    except TrainingSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except TrainingUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
