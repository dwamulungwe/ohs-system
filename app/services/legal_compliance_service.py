from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.user import User
from app.schemas.legal_compliance import LegalComplianceCreate, LegalComplianceUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class LegalComplianceServiceError(Exception):
    pass


class LegalComplianceNotFoundError(LegalComplianceServiceError):
    pass


class LegalComplianceValidationError(LegalComplianceServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: int | None) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise LegalComplianceValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: int) -> None:
    if db.get(User, user_id) is None:
        raise LegalComplianceValidationError("Referenced user not found")


def _notify_review_dates(db: Session, item: LegalComplianceItem) -> None:
    if item.next_review_date is None:
        return
    today = _today()
    if item.next_review_date < today:
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=item.owner_user_id,
                title="Legal compliance review overdue",
                message=f"Legal compliance item '{item.title}' is overdue for review.",
                notification_type=NotificationType.legal_compliance_overdue,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.legal_compliance,
                related_entity_id=item.id,
            ),
        )
    elif item.next_review_date <= today + timedelta(days=7):
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=item.owner_user_id,
                title="Legal compliance review due soon",
                message=f"Legal compliance item '{item.title}' is due for review by {item.next_review_date}.",
                notification_type=NotificationType.legal_compliance_due_soon,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.legal_compliance,
                related_entity_id=item.id,
            ),
        )


def list_legal_compliance_items(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    compliance_status: LegalComplianceStatus | None = None,
    site_id: int | None = None,
    owner_user_id: int | None = None,
) -> dict:
    statement: Select[tuple[LegalComplianceItem]] = select(LegalComplianceItem)
    if compliance_status is not None:
        statement = statement.where(LegalComplianceItem.compliance_status == compliance_status)
    if site_id is not None:
        statement = statement.where(LegalComplianceItem.site_id == site_id)
    if owner_user_id is not None:
        statement = statement.where(LegalComplianceItem.owner_user_id == owner_user_id)
    statement = statement.order_by(
        LegalComplianceItem.next_review_date.asc().nullslast(),
        LegalComplianceItem.id.desc(),
    )
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_legal_compliance_item(db: Session, item_id: int) -> LegalComplianceItem:
    item = db.get(LegalComplianceItem, item_id)
    if item is None:
        raise LegalComplianceNotFoundError("Legal compliance item not found")
    return item


def create_legal_compliance_item(
    db: Session,
    item_in: LegalComplianceCreate,
    *,
    actor_id: int | None,
) -> LegalComplianceItem:
    data = item_in.model_dump()
    _ensure_site_exists(db, data.get("site_id"))
    _ensure_user_exists(db, data["owner_user_id"])
    item = LegalComplianceItem(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="legal_compliance.create",
        resource_type="legal_compliance",
        resource_id=item.id,
        details={"status": item.compliance_status.value},
    )
    _notify_review_dates(db, item)
    return item


def update_legal_compliance_item(
    db: Session,
    item: LegalComplianceItem,
    item_in: LegalComplianceUpdate,
    *,
    actor_id: int | None,
) -> LegalComplianceItem:
    update_data = item_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    if "owner_user_id" in update_data and update_data["owner_user_id"] is not None:
        _ensure_user_exists(db, update_data["owner_user_id"])
    for field, value in update_data.items():
        setattr(item, field, value)
    if "compliance_status" in update_data and item.compliance_status != LegalComplianceStatus.pending_review:
        item.last_reviewed_at = item.last_reviewed_at or datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="legal_compliance.update",
        resource_type="legal_compliance",
        resource_id=item.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_review_dates(db, item)
    return item
