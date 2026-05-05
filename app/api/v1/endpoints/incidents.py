from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentListRead, IncidentRead, IncidentUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    resolve_site_scope,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentSiteNotFoundError,
    create_incident as create_incident_record,
    get_incident as get_incident_record,
    list_incidents as list_incident_records,
    update_incident as update_incident_record,
)
from app.services.incident_investigation_service import incident_has_completed_investigation

router = APIRouter()
MANAGER_INCIDENT_STATUSES = {IncidentStatus.resolved, IncidentStatus.closed}


@router.get("", response_model=IncidentListRead)
def list_incidents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    severity: IncidentSeverity | None = None,
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_incident_records(
        db,
        skip=skip,
        limit=limit,
        status=incident_status,
        severity=severity,
        site_id=site_id,
    )


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    incident_in: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_CREATE)
    if incident_in.status in MANAGER_INCIDENT_STATUSES and not has_permission(
        current_user,
        Permission.INCIDENTS_CLOSE,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to close incidents")

    incident_in = incident_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, incident_in.site_id)}
    )
    try:
        return create_incident_record(db, incident_in, reported_by_id=current_user.id)
    except IncidentSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    try:
        incident = get_incident_record(db, incident_id)
        ensure_site_access(current_user, incident.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.incident, incident)
    except IncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")


@router.patch("/{incident_id}", response_model=IncidentRead)
def patch_incident(
    incident_id: int,
    incident_in: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_EDIT)
    try:
        incident = get_incident_record(db, incident_id)
        ensure_site_access(current_user, incident.site_id)
        next_status = incident_in.status or incident.status
        if next_status in MANAGER_INCIDENT_STATUSES and not has_permission(
            current_user,
            Permission.INCIDENTS_CLOSE,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to close incidents",
            )
        if (
            next_status == IncidentStatus.closed
            and incident.severity in {IncidentSeverity.high, IncidentSeverity.critical}
            and not incident_has_completed_investigation(db, incident_id=incident.id)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="High and critical incidents require a completed investigation before closure",
            )
        return update_incident_record(db, incident, incident_in, actor_id=current_user.id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    except IncidentSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
