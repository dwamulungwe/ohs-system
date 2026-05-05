from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.jsa import JSAStatus, JobSafetyAnalysis
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.user import User
from app.schemas.jsa import JSACreate, JSAUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class JSAServiceError(Exception):
    pass


class JSANotFoundError(JSAServiceError):
    pass


class JSAValidationError(JSAServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise JSAValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise JSAValidationError("Referenced user not found")


def _apply_review_expiry(
    data: dict,
    *,
    review_date: date | None,
    existing_status: JSAStatus | None = None,
) -> None:
    current_review_date = data.get("review_date", review_date)
    status = data.get("status", existing_status)
    if current_review_date is not None and current_review_date < _today() and status == JSAStatus.approved:
        data["status"] = JSAStatus.expired


def _apply_approval(data: dict, *, actor_id: int | None, existing_approved_at: datetime | None = None) -> None:
    status = data.get("status")
    if status == JSAStatus.approved:
        data["approved_at"] = data.get("approved_at") or existing_approved_at or _now()
        if actor_id is not None:
            data["approved_by_user_id"] = actor_id


def _notify_review_dates(db: Session, jsa: JobSafetyAnalysis) -> None:
    if jsa.review_date is None or jsa.approved_by_user_id is None:
        return
    if jsa.review_date < _today():
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=jsa.approved_by_user_id,
                title="JSA review overdue",
                message=f"JSA '{jsa.title}' is overdue for review.",
                notification_type=NotificationType.jsa_review_overdue,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.jsa,
                related_entity_id=jsa.id,
            ),
        )
    elif jsa.review_date <= _today() + timedelta(days=7):
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=jsa.approved_by_user_id,
                title="JSA review due soon",
                message=f"JSA '{jsa.title}' is due for review by {jsa.review_date}.",
                notification_type=NotificationType.jsa_review_due_soon,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.jsa,
                related_entity_id=jsa.id,
            ),
        )


def _notify_pending_approval(db: Session, jsa: JobSafetyAnalysis) -> None:
    if jsa.status != JSAStatus.pending_approval or jsa.approved_by_user_id is None:
        return
    create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=jsa.approved_by_user_id,
            title="JSA pending approval",
            message=f"JSA '{jsa.title}' is pending approval.",
            notification_type=NotificationType.jsa_pending_approval,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.jsa,
            related_entity_id=jsa.id,
        ),
    )


def list_jsas(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: JSAStatus | None = None,
    site_id: int | None = None,
) -> dict:
    statement: Select[tuple[JobSafetyAnalysis]] = select(JobSafetyAnalysis)
    if status is not None:
        statement = statement.where(JobSafetyAnalysis.status == status)
    if site_id is not None:
        statement = statement.where(JobSafetyAnalysis.site_id == site_id)
    statement = statement.order_by(
        JobSafetyAnalysis.review_date.asc().nullslast(),
        JobSafetyAnalysis.id.desc(),
    )
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_jsa(db: Session, jsa_id: int) -> JobSafetyAnalysis:
    jsa = db.get(JobSafetyAnalysis, jsa_id)
    if jsa is None:
        raise JSANotFoundError("JSA not found")
    return jsa


def create_jsa(db: Session, jsa_in: JSACreate, *, actor_id: int | None) -> JobSafetyAnalysis:
    data = jsa_in.model_dump()
    _ensure_site_exists(db, data["site_id"])
    _ensure_user_exists(db, data.get("approved_by_user_id"))
    _apply_review_expiry(data, review_date=None, existing_status=data.get("status"))
    _apply_approval(data, actor_id=actor_id)
    jsa = JobSafetyAnalysis(**data)
    db.add(jsa)
    db.commit()
    db.refresh(jsa)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="jsa.create",
        resource_type="jsa",
        resource_id=jsa.id,
        details={"status": jsa.status.value},
    )
    _notify_pending_approval(db, jsa)
    _notify_review_dates(db, jsa)
    return jsa


def update_jsa(
    db: Session,
    jsa: JobSafetyAnalysis,
    jsa_in: JSAUpdate,
    *,
    actor_id: int | None,
) -> JobSafetyAnalysis:
    update_data = jsa_in.model_dump(exclude_unset=True)
    if "site_id" in update_data and update_data["site_id"] is not None:
        _ensure_site_exists(db, update_data["site_id"])
    _ensure_user_exists(db, update_data.get("approved_by_user_id"))
    previous_status = jsa.status
    _apply_review_expiry(update_data, review_date=jsa.review_date, existing_status=jsa.status)
    _apply_approval(update_data, actor_id=actor_id, existing_approved_at=jsa.approved_at)
    for field, value in update_data.items():
        setattr(jsa, field, value)
    db.add(jsa)
    db.commit()
    db.refresh(jsa)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="jsa.update",
        resource_type="jsa",
        resource_id=jsa.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    if jsa.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="jsa.status_transition",
            resource_type="jsa",
            resource_id=jsa.id,
            details={"from": previous_status.value, "to": jsa.status.value},
        )
    _notify_pending_approval(db, jsa)
    _notify_review_dates(db, jsa)
    return jsa
