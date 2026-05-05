from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.medical_surveillance import MedicalSurveillanceStatus
from app.models.user import User
from app.schemas.medical_surveillance import (
    MedicalSurveillanceCreate,
    MedicalSurveillanceListRead,
    MedicalSurveillanceRead,
    MedicalSurveillanceUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.medical_surveillance_service import (
    MedicalSurveillanceNotFoundError,
    MedicalSurveillanceValidationError,
    create_medical_surveillance_record,
    get_medical_surveillance_record,
    list_medical_surveillance_records,
    update_medical_surveillance_record,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=MedicalSurveillanceListRead)
def read_medical_surveillance_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: MedicalSurveillanceStatus | None = None,
    site_id: int | None = None,
    employee_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_medical_surveillance_records(
        db,
        skip=skip,
        limit=limit,
        status=status,
        site_id=site_id,
        employee_user_id=employee_user_id,
    )


@router.post("", response_model=MedicalSurveillanceRead, status_code=status.HTTP_201_CREATED)
def create_medical_surveillance_entry(
    record_in: MedicalSurveillanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.MEDICAL_SURVEILLANCE_CREATE)
    if record_in.site_id is not None:
        record_in = record_in.model_copy(
            update={"site_id": resolve_site_scope(current_user, record_in.site_id)}
        )
    try:
        return create_medical_surveillance_record(db, record_in, actor_id=current_user.id)
    except MedicalSurveillanceValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{record_id}", response_model=MedicalSurveillanceRead)
def read_medical_surveillance_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW)
    try:
        record = get_medical_surveillance_record(db, record_id)
        ensure_site_access(current_user, record.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.medical_surveillance, record)
    except MedicalSurveillanceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical surveillance record not found")


@router.patch("/{record_id}", response_model=MedicalSurveillanceRead)
def patch_medical_surveillance_record(
    record_id: int,
    record_in: MedicalSurveillanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.MEDICAL_SURVEILLANCE_EDIT)
    try:
        record = get_medical_surveillance_record(db, record_id)
        ensure_site_access(current_user, record.site_id)
        if record_in.site_id is not None:
            record_in = record_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, record_in.site_id)}
            )
        return update_medical_surveillance_record(db, record, record_in, actor_id=current_user.id)
    except MedicalSurveillanceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical surveillance record not found")
    except MedicalSurveillanceValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
