from __future__ import annotations

from typing import Optional
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.audit_management import (
    AuditManagementRecord,
    AuditStatus,
    AuditType,
)
from app.models.corrective_action import CorrectiveAction
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.user import User
from app.schemas.audit_management import AuditManagementCreate, AuditManagementUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class AuditManagementServiceError(Exception):
    pass


class AuditManagementNotFoundError(AuditManagementServiceError):
    pass


class AuditManagementValidationError(AuditManagementServiceError):
    pass


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise AuditManagementValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: int) -> None:
    if db.get(User, user_id) is None:
        raise AuditManagementValidationError("Referenced auditor not found")


def _ensure_corrective_actions_exist(db: Session, corrective_action_ids: list[int]) -> None:
    for corrective_action_id in corrective_action_ids:
        if db.get(CorrectiveAction, corrective_action_id) is None:
            raise AuditManagementValidationError(
                f"Corrective action {corrective_action_id} was not found"
            )


def _notify_open_audit(db: Session, audit: AuditManagementRecord) -> None:
    if audit.status != AuditStatus.open:
        return
    create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=audit.auditor_user_id,
            title="Audit record open",
            message=f"{audit.audit_type.value} audit scheduled on {audit.audit_date} remains open.",
            notification_type=NotificationType.audit_open,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.audit_management,
            related_entity_id=audit.id,
        ),
    )


def list_audits(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[AuditStatus] = None,
    audit_type: Optional[AuditType] = None,
    site_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[AuditManagementRecord]] = select(AuditManagementRecord)
    if status is not None:
        statement = statement.where(AuditManagementRecord.status == status)
    if audit_type is not None:
        statement = statement.where(AuditManagementRecord.audit_type == audit_type)
    if site_id is not None:
        statement = statement.where(AuditManagementRecord.site_id == site_id)
    statement = statement.order_by(AuditManagementRecord.audit_date.desc(), AuditManagementRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_audit(db: Session, audit_id: int) -> AuditManagementRecord:
    audit = db.get(AuditManagementRecord, audit_id)
    if audit is None:
        raise AuditManagementNotFoundError("Audit not found")
    return audit


def create_audit(
    db: Session,
    audit_in: AuditManagementCreate,
    *,
    actor_id: Optional[int],
) -> AuditManagementRecord:
    data = audit_in.model_dump()
    _ensure_site_exists(db, data["site_id"])
    _ensure_user_exists(db, data["auditor_user_id"])
    _ensure_corrective_actions_exist(db, data["corrective_action_ids"])
    audit = AuditManagementRecord(**data)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="audit_management.create",
        resource_type="audit_management",
        resource_id=audit.id,
        details={"status": audit.status.value},
    )
    _notify_open_audit(db, audit)
    return audit


def update_audit(
    db: Session,
    audit: AuditManagementRecord,
    audit_in: AuditManagementUpdate,
    *,
    actor_id: Optional[int],
) -> AuditManagementRecord:
    update_data = audit_in.model_dump(exclude_unset=True)
    if "site_id" in update_data and update_data["site_id"] is not None:
        _ensure_site_exists(db, update_data["site_id"])
    if "auditor_user_id" in update_data and update_data["auditor_user_id"] is not None:
        _ensure_user_exists(db, update_data["auditor_user_id"])
    if "corrective_action_ids" in update_data:
        _ensure_corrective_actions_exist(db, update_data["corrective_action_ids"])
    for field, value in update_data.items():
        setattr(audit, field, value)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="audit_management.update",
        resource_type="audit_management",
        resource_id=audit.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_open_audit(db, audit)
    return audit
