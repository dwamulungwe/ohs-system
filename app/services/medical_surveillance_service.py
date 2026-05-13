from __future__ import annotations

from typing import Optional
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.medical_surveillance import (
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
)
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.user import User
from app.schemas.medical_surveillance import (
    MedicalSurveillanceCreate,
    MedicalSurveillanceUpdate,
)
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class MedicalSurveillanceServiceError(Exception):
    pass


class MedicalSurveillanceNotFoundError(MedicalSurveillanceServiceError):
    pass


class MedicalSurveillanceValidationError(MedicalSurveillanceServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: Optional[int]) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise MedicalSurveillanceValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise MedicalSurveillanceValidationError("Referenced employee not found")
    return user


def derive_status(data: dict) -> None:
    if data.get("completed_at") is not None:
        data["status"] = MedicalSurveillanceStatus.completed
        return
    if data.get("due_date") is not None and data["due_date"] < _today():
        data["status"] = MedicalSurveillanceStatus.overdue
        return
    data["status"] = MedicalSurveillanceStatus.due


def _notify_due_state(db: Session, record: MedicalSurveillanceRecord) -> None:
    if record.employee_user_id is None or record.status == MedicalSurveillanceStatus.completed:
        return
    today = _today()
    if record.due_date < today:
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=record.employee_user_id,
                title="Medical surveillance overdue",
                message=f"{record.surveillance_type} surveillance is overdue.",
                notification_type=NotificationType.medical_surveillance_overdue,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.medical_surveillance,
                related_entity_id=record.id,
            ),
        )
    elif record.due_date <= today + timedelta(days=7):
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=record.employee_user_id,
                title="Medical surveillance due soon",
                message=f"{record.surveillance_type} surveillance is due by {record.due_date}.",
                notification_type=NotificationType.medical_surveillance_due_soon,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.medical_surveillance,
                related_entity_id=record.id,
            ),
        )


def list_medical_surveillance_records(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[MedicalSurveillanceStatus] = None,
    site_id: Optional[int] = None,
    employee_user_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[MedicalSurveillanceRecord]] = select(MedicalSurveillanceRecord)
    if status is not None:
        statement = statement.where(MedicalSurveillanceRecord.status == status)
    if site_id is not None:
        statement = statement.where(MedicalSurveillanceRecord.site_id == site_id)
    if employee_user_id is not None:
        statement = statement.where(MedicalSurveillanceRecord.employee_user_id == employee_user_id)
    statement = statement.order_by(MedicalSurveillanceRecord.due_date.asc(), MedicalSurveillanceRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_medical_surveillance_record(db: Session, record_id: int) -> MedicalSurveillanceRecord:
    record = db.get(MedicalSurveillanceRecord, record_id)
    if record is None:
        raise MedicalSurveillanceNotFoundError("Medical surveillance record not found")
    return record


def create_medical_surveillance_record(
    db: Session,
    record_in: MedicalSurveillanceCreate,
    *,
    actor_id: Optional[int],
) -> MedicalSurveillanceRecord:
    data = record_in.model_dump()
    employee = _ensure_user_exists(db, data["employee_user_id"])
    if data.get("site_id") is None:
        data["site_id"] = employee.assigned_site_id
    _ensure_site_exists(db, data.get("site_id"))
    derive_status(data)
    record = MedicalSurveillanceRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="medical_surveillance.create",
        resource_type="medical_surveillance",
        resource_id=record.id,
        details={"status": record.status.value},
    )
    _notify_due_state(db, record)
    return record


def update_medical_surveillance_record(
    db: Session,
    record: MedicalSurveillanceRecord,
    record_in: MedicalSurveillanceUpdate,
    *,
    actor_id: Optional[int],
) -> MedicalSurveillanceRecord:
    update_data = record_in.model_dump(exclude_unset=True)
    if "employee_user_id" in update_data and update_data["employee_user_id"] is not None:
        employee = _ensure_user_exists(db, update_data["employee_user_id"])
        if "site_id" not in update_data or update_data["site_id"] is None:
            update_data["site_id"] = employee.assigned_site_id
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    effective_data = {
        "due_date": update_data.get("due_date", record.due_date),
        "completed_at": update_data.get("completed_at", record.completed_at),
    }
    derive_status(effective_data)
    update_data["status"] = effective_data["status"]
    for field, value in update_data.items():
        setattr(record, field, value)
    db.add(record)
    db.commit()
    db.refresh(record)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="medical_surveillance.update",
        resource_type="medical_surveillance",
        resource_id=record.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_due_state(db, record)
    return record


def refresh_medical_surveillance_statuses(db: Session) -> int:
    records = list(db.scalars(select(MedicalSurveillanceRecord)).all())
    updated = 0
    for record in records:
        next_status = (
            MedicalSurveillanceStatus.completed
            if record.completed_at is not None
            else MedicalSurveillanceStatus.overdue
            if record.due_date < _today()
            else MedicalSurveillanceStatus.due
        )
        if record.status != next_status:
            record.status = next_status
            db.add(record)
            updated += 1
    if updated:
        db.commit()
    return updated


def generate_medical_surveillance_notifications(db: Session) -> int:
    count = 0
    for record in db.scalars(select(MedicalSurveillanceRecord)).all():
        before = count
        notification = None
        if record.status != MedicalSurveillanceStatus.completed:
            today = _today()
            if record.due_date < today:
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=record.employee_user_id,
                        title="Medical surveillance overdue",
                        message=f"{record.surveillance_type} surveillance is overdue.",
                        notification_type=NotificationType.medical_surveillance_overdue,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.medical_surveillance,
                        related_entity_id=record.id,
                    ),
                )
            elif record.due_date <= today + timedelta(days=7):
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=record.employee_user_id,
                        title="Medical surveillance due soon",
                        message=f"{record.surveillance_type} surveillance is due by {record.due_date}.",
                        notification_type=NotificationType.medical_surveillance_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.medical_surveillance,
                        related_entity_id=record.id,
                    ),
                )
        if notification is not None:
            count = before + 1
    return count
