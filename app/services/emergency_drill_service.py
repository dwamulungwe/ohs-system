from __future__ import annotations

from typing import Optional
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.emergency_drill import EmergencyDrillRecord, EmergencyDrillStatus
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.schemas.emergency_drill import EmergencyDrillCreate, EmergencyDrillUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once, get_active_user_ids_for_roles
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER


class EmergencyDrillServiceError(Exception):
    pass


class EmergencyDrillNotFoundError(EmergencyDrillServiceError):
    pass


class EmergencyDrillValidationError(EmergencyDrillServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise EmergencyDrillValidationError("Site not found")


def derive_status(data: dict) -> None:
    current_status = data.get("status", EmergencyDrillStatus.scheduled)
    if current_status == EmergencyDrillStatus.archived:
        return
    if data.get("outcome"):
        data["status"] = EmergencyDrillStatus.completed
        return
    if data.get("drill_date") is not None and data["drill_date"] < _today():
        data["status"] = EmergencyDrillStatus.overdue
        return
    data["status"] = EmergencyDrillStatus.scheduled


def _notify_due_state(db: Session, drill: EmergencyDrillRecord) -> None:
    recipients = get_active_user_ids_for_roles(
        db,
        role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER],
        site_id=drill.site_id,
    )
    today = _today()
    notification_type = None
    severity = None
    title = ""
    message = ""
    if drill.status == EmergencyDrillStatus.overdue:
        notification_type = NotificationType.emergency_drill_overdue
        severity = NotificationSeverity.critical
        title = "Emergency drill overdue"
        message = f"{drill.emergency_type} drill is overdue for site #{drill.site_id}."
    elif drill.drill_date <= today + timedelta(days=7):
        notification_type = NotificationType.emergency_drill_due_soon
        severity = NotificationSeverity.warning
        title = "Emergency drill due soon"
        message = f"{drill.emergency_type} drill is scheduled for {drill.drill_date}."
    if notification_type is None:
        return
    for recipient_user_id in recipients:
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=recipient_user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                severity=severity,
                related_entity_type=RelatedEntityType.emergency_drill,
                related_entity_id=drill.id,
            ),
        )


def list_emergency_drills(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[EmergencyDrillStatus] = None,
    site_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[EmergencyDrillRecord]] = select(EmergencyDrillRecord)
    if status is not None:
        statement = statement.where(EmergencyDrillRecord.status == status)
    if site_id is not None:
        statement = statement.where(EmergencyDrillRecord.site_id == site_id)
    statement = statement.order_by(EmergencyDrillRecord.drill_date.asc(), EmergencyDrillRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_emergency_drill(db: Session, drill_id: int) -> EmergencyDrillRecord:
    drill = db.get(EmergencyDrillRecord, drill_id)
    if drill is None:
        raise EmergencyDrillNotFoundError("Emergency drill not found")
    return drill


def create_emergency_drill(
    db: Session,
    drill_in: EmergencyDrillCreate,
    *,
    actor_id: Optional[int],
) -> EmergencyDrillRecord:
    data = drill_in.model_dump()
    _ensure_site_exists(db, data["site_id"])
    derive_status(data)
    drill = EmergencyDrillRecord(**data)
    db.add(drill)
    db.commit()
    db.refresh(drill)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="emergency_drill.create",
        resource_type="emergency_drill",
        resource_id=drill.id,
        details={"status": drill.status.value},
    )
    _notify_due_state(db, drill)
    return drill


def update_emergency_drill(
    db: Session,
    drill: EmergencyDrillRecord,
    drill_in: EmergencyDrillUpdate,
    *,
    actor_id: Optional[int],
) -> EmergencyDrillRecord:
    update_data = drill_in.model_dump(exclude_unset=True)
    if "site_id" in update_data and update_data["site_id"] is not None:
        _ensure_site_exists(db, update_data["site_id"])
    effective_data = {
        "drill_date": update_data.get("drill_date", drill.drill_date),
        "outcome": update_data.get("outcome", drill.outcome),
        "status": update_data.get("status", drill.status),
    }
    derive_status(effective_data)
    update_data["status"] = effective_data["status"]
    for field, value in update_data.items():
        setattr(drill, field, value)
    db.add(drill)
    db.commit()
    db.refresh(drill)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="emergency_drill.update",
        resource_type="emergency_drill",
        resource_id=drill.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_due_state(db, drill)
    return drill


def refresh_emergency_drill_statuses(db: Session) -> int:
    drills = list(db.scalars(select(EmergencyDrillRecord)).all())
    updated = 0
    for drill in drills:
        data = {"drill_date": drill.drill_date, "outcome": drill.outcome, "status": drill.status}
        derive_status(data)
        if drill.status != data["status"]:
            drill.status = data["status"]
            db.add(drill)
            updated += 1
    if updated:
        db.commit()
    return updated


def generate_emergency_drill_notifications(db: Session) -> int:
    count = 0
    for drill in db.scalars(select(EmergencyDrillRecord)).all():
        before = count
        recipients = get_active_user_ids_for_roles(
            db,
            role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER],
            site_id=drill.site_id,
        )
        for recipient_user_id in recipients:
            notification = None
            if drill.status == EmergencyDrillStatus.overdue:
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Emergency drill overdue",
                        message=f"{drill.emergency_type} drill is overdue for site #{drill.site_id}.",
                        notification_type=NotificationType.emergency_drill_overdue,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.emergency_drill,
                        related_entity_id=drill.id,
                    ),
                )
            elif drill.drill_date <= _today() + timedelta(days=7):
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Emergency drill due soon",
                        message=f"{drill.emergency_type} drill is scheduled for {drill.drill_date}.",
                        notification_type=NotificationType.emergency_drill_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.emergency_drill,
                        related_entity_id=drill.id,
                    ),
                )
            if notification is not None:
                count += 1
        if count < before:
            count = before
    return count
