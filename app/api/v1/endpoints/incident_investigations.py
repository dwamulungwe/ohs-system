from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.user import User
from app.schemas.incident_investigation import (
    IncidentInvestigationCreate,
    IncidentInvestigationListRead,
    IncidentInvestigationRead,
    IncidentInvestigationUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.incident_investigation_service import (
    IncidentInvestigationNotFoundError,
    IncidentInvestigationValidationError,
    create_incident_investigation,
    get_incident_investigation,
    list_incident_investigations,
    update_incident_investigation,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=IncidentInvestigationListRead)
def read_investigations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[IncidentInvestigationStatus] = None,
    site_id: Optional[int] = None,
    incident_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.INVESTIGATIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_incident_investigations(
        db,
        skip=skip,
        limit=limit,
        status=status,
        site_id=site_id,
        incident_id=incident_id,
    )


@router.post("", response_model=IncidentInvestigationRead, status_code=status.HTTP_201_CREATED)
def create_investigation(
    investigation_in: IncidentInvestigationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentInvestigation:
    ensure_permission(current_user, Permission.INVESTIGATIONS_CREATE)
    if investigation_in.status in {IncidentInvestigationStatus.approved, IncidentInvestigationStatus.closed}:
        ensure_permission(current_user, Permission.INVESTIGATIONS_APPROVE)
    try:
        return create_incident_investigation(db, investigation_in, actor_id=current_user.id)
    except IncidentInvestigationValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{investigation_id}", response_model=IncidentInvestigationRead)
def read_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentInvestigation:
    ensure_permission(current_user, Permission.INVESTIGATIONS_VIEW)
    try:
        investigation = get_incident_investigation(db, investigation_id)
        ensure_site_access(current_user, investigation.site_id)
        return hydrate_entity_attachments(
            db,
            AttachmentEntityType.incident_investigation,
            investigation,
        )
    except IncidentInvestigationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident investigation not found")


@router.patch("/{investigation_id}", response_model=IncidentInvestigationRead)
def patch_investigation(
    investigation_id: int,
    investigation_in: IncidentInvestigationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentInvestigation:
    ensure_permission(current_user, Permission.INVESTIGATIONS_EDIT)
    try:
        investigation = get_incident_investigation(db, investigation_id)
        ensure_site_access(current_user, investigation.site_id)
        next_status = investigation_in.status or investigation.status
        if next_status in {IncidentInvestigationStatus.approved, IncidentInvestigationStatus.closed}:
            ensure_permission(current_user, Permission.INVESTIGATIONS_APPROVE)
        return update_incident_investigation(db, investigation, investigation_in, actor_id=current_user.id)
    except IncidentInvestigationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident investigation not found")
    except IncidentInvestigationValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
