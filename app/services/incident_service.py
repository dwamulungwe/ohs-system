from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.site import Site
from app.schemas.incident import IncidentCreate, IncidentUpdate
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify_critical_incident
from app.services.query_utils import paginate


class IncidentServiceError(Exception):
    pass


class IncidentNotFoundError(IncidentServiceError):
    pass


class IncidentSiteNotFoundError(IncidentServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise IncidentSiteNotFoundError(f"Site {site_id} was not found")


def list_incidents(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    site_id: int | None = None,
) -> dict:
    statement: Select[tuple[Incident]] = select(Incident)
    if status is not None:
        statement = statement.where(Incident.status == status)
    if severity is not None:
        statement = statement.where(Incident.severity == severity)
    if site_id is not None:
        statement = statement.where(Incident.site_id == site_id)

    statement = statement.order_by(Incident.occurred_at.desc(), Incident.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_incident(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise IncidentNotFoundError(f"Incident {incident_id} was not found")
    return incident


def create_incident(db: Session, incident_in: IncidentCreate, *, reported_by_id: int | None) -> Incident:
    _ensure_site_exists(db, incident_in.site_id)
    incident_data = incident_in.model_dump()
    if incident_data.get("is_lost_time"):
        incident_data["is_recordable"] = True
    if incident_data.get("status") == IncidentStatus.closed:
        incident_data["closed_at"] = _now()
        incident_data["closed_by_user_id"] = reported_by_id
        incident_data["closure_requested"] = False
    incident = Incident(
        **incident_data,
        reported_by_id=reported_by_id,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    write_audit_log(
        db,
        actor_id=reported_by_id,
        action="incident.create",
        resource_type="incident",
        resource_id=incident.id,
        details={"status": incident.status.value, "severity": incident.severity.value},
    )
    notify_critical_incident(db, incident)
    return incident


def update_incident(db: Session, incident: Incident, incident_in: IncidentUpdate, *, actor_id: int | None = None) -> Incident:
    update_data = incident_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    if update_data.get("is_lost_time"):
        update_data["is_recordable"] = True

    previous_status = incident.status
    previous_severity = incident.severity
    for field, value in update_data.items():
        setattr(incident, field, value)

    if "status" in update_data and incident.status == IncidentStatus.closed:
        incident.closed_at = incident.closed_at or _now()
        incident.closed_by_user_id = incident.closed_by_user_id or actor_id
        incident.closure_requested = False

    db.add(incident)
    db.commit()
    db.refresh(incident)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="incident.update",
        resource_type="incident",
        resource_id=incident.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    if "status" in update_data and incident.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="incident.status_transition",
            resource_type="incident",
            resource_id=incident.id,
            details={"from": previous_status.value, "to": incident.status.value},
        )
    if incident.severity == IncidentSeverity.critical and previous_severity != IncidentSeverity.critical:
        notify_critical_incident(db, incident)
    return incident
