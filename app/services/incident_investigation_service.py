from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.user import User
from app.schemas.incident_investigation import IncidentInvestigationCreate, IncidentInvestigationUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class IncidentInvestigationServiceError(Exception):
    pass


class IncidentInvestigationNotFoundError(IncidentInvestigationServiceError):
    pass


class IncidentInvestigationValidationError(IncidentInvestigationServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dump_json_lists(data: dict) -> None:
    for field in ("witness_statements",):
        if field in data and data[field] is not None:
            data[field] = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in data[field]
            ]


def _ensure_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise IncidentInvestigationValidationError("Referenced user not found")


def _get_incident_or_error(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise IncidentInvestigationValidationError("Incident not found")
    return incident


def _apply_status_side_effects(
    data: dict,
    *,
    previous_status: IncidentInvestigationStatus | None = None,
    actor_id: int | None = None,
    existing_approved_at: datetime | None = None,
    existing_completed_at: datetime | None = None,
) -> None:
    status = data.get("status", previous_status or IncidentInvestigationStatus.draft)
    if status == IncidentInvestigationStatus.approved:
        data["approved_at"] = data.get("approved_at") or existing_approved_at or _now()
        data["completed_at"] = data.get("completed_at") or existing_completed_at or _now()
        if actor_id is not None:
            data["approved_by_user_id"] = actor_id
    elif status == IncidentInvestigationStatus.closed:
        data["completed_at"] = data.get("completed_at") or existing_completed_at or _now()


def _notify_pending_approval(db: Session, investigation: IncidentInvestigation) -> None:
    if (
        investigation.status != IncidentInvestigationStatus.pending_approval
        or investigation.approved_by_user_id is None
    ):
        return
    create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=investigation.approved_by_user_id,
            title="Investigation pending approval",
            message=f"Incident investigation for incident #{investigation.incident_id} is pending approval.",
            notification_type=NotificationType.investigation_pending_approval,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.incident_investigation,
            related_entity_id=investigation.id,
        ),
    )


def _notify_approved(db: Session, investigation: IncidentInvestigation) -> None:
    if (
        investigation.status != IncidentInvestigationStatus.approved
        or investigation.investigation_lead_user_id is None
    ):
        return
    create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=investigation.investigation_lead_user_id,
            title="Investigation approved",
            message=f"Incident investigation for incident #{investigation.incident_id} has been approved.",
            notification_type=NotificationType.investigation_approved,
            severity=NotificationSeverity.info,
            related_entity_type=RelatedEntityType.incident_investigation,
            related_entity_id=investigation.id,
        ),
    )


def list_incident_investigations(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: IncidentInvestigationStatus | None = None,
    site_id: int | None = None,
    incident_id: int | None = None,
) -> dict:
    statement: Select[tuple[IncidentInvestigation]] = select(IncidentInvestigation)
    if status is not None:
        statement = statement.where(IncidentInvestigation.status == status)
    if site_id is not None:
        statement = statement.where(IncidentInvestigation.site_id == site_id)
    if incident_id is not None:
        statement = statement.where(IncidentInvestigation.incident_id == incident_id)
    statement = statement.order_by(
        IncidentInvestigation.created_at.desc(),
        IncidentInvestigation.id.desc(),
    )
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_incident_investigation(db: Session, investigation_id: int) -> IncidentInvestigation:
    investigation = db.get(IncidentInvestigation, investigation_id)
    if investigation is None:
        raise IncidentInvestigationNotFoundError("Incident investigation not found")
    return investigation


def create_incident_investigation(
    db: Session,
    investigation_in: IncidentInvestigationCreate,
    *,
    actor_id: int | None,
) -> IncidentInvestigation:
    data = investigation_in.model_dump()
    _dump_json_lists(data)
    incident = _get_incident_or_error(db, data["incident_id"])
    _ensure_user_exists(db, data.get("investigation_lead_user_id"))
    _ensure_user_exists(db, data.get("approved_by_user_id"))
    existing = db.scalar(
        select(IncidentInvestigation).where(IncidentInvestigation.incident_id == data["incident_id"])
    )
    if existing is not None:
        raise IncidentInvestigationValidationError("This incident already has an investigation")
    data["site_id"] = incident.site_id
    _apply_status_side_effects(data, actor_id=actor_id)
    investigation = IncidentInvestigation(**data)
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="incident_investigation.create",
        resource_type="incident_investigation",
        resource_id=investigation.id,
        details={"incident_id": investigation.incident_id, "status": investigation.status.value},
    )
    _notify_pending_approval(db, investigation)
    _notify_approved(db, investigation)
    return investigation


def update_incident_investigation(
    db: Session,
    investigation: IncidentInvestigation,
    investigation_in: IncidentInvestigationUpdate,
    *,
    actor_id: int | None,
) -> IncidentInvestigation:
    update_data = investigation_in.model_dump(exclude_unset=True)
    _dump_json_lists(update_data)
    _ensure_user_exists(db, update_data.get("investigation_lead_user_id"))
    _ensure_user_exists(db, update_data.get("approved_by_user_id"))
    previous_status = investigation.status
    _apply_status_side_effects(
        update_data,
        previous_status=previous_status,
        actor_id=actor_id,
        existing_approved_at=investigation.approved_at,
        existing_completed_at=investigation.completed_at,
    )
    for field, value in update_data.items():
        setattr(investigation, field, value)
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="incident_investigation.update",
        resource_type="incident_investigation",
        resource_id=investigation.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    if investigation.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="incident_investigation.status_transition",
            resource_type="incident_investigation",
            resource_id=investigation.id,
            details={"from": previous_status.value, "to": investigation.status.value},
        )
    _notify_pending_approval(db, investigation)
    _notify_approved(db, investigation)
    return investigation


def incident_has_completed_investigation(db: Session, *, incident_id: int) -> bool:
    investigation = db.scalar(
        select(IncidentInvestigation).where(IncidentInvestigation.incident_id == incident_id)
    )
    if investigation is None:
        return False
    return investigation.status in {
        IncidentInvestigationStatus.approved,
        IncidentInvestigationStatus.closed,
    }
