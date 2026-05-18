from typing import Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import Notification, NotificationSeverity, NotificationType, RelatedEntityType
from app.models.permit import PermitStatus, PermitToWork, PermitType
from app.models.site import Site
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.schemas.permit import PermitCreate, PermitUpdate
from app.services.notification_service import create_notification_once
from app.services.query_utils import apply_date_filters, paginate


class PermitServiceError(Exception):
    pass


class PermitNotFoundError(PermitServiceError):
    pass


class PermitSiteNotFoundError(PermitServiceError):
    pass


class PermitUserNotFoundError(PermitServiceError):
    pass


class PermitValidationError(PermitServiceError):
    pass


ACTIVE_EXPIRY_STATUSES = {PermitStatus.approved, PermitStatus.active}
CLOSABLE_STATUSES = {PermitStatus.approved, PermitStatus.active, PermitStatus.suspended}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ensure_site_exists(db: Session, site_id: Optional[int]) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise PermitSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise PermitUserNotFoundError(f"User {user_id} was not found")


def _dump_json_items(data: dict) -> None:
    for field in ("gas_test_results", "attachments_metadata"):
        if field in data and data[field] is not None:
            data[field] = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in data[field]
            ]


def _validate_datetime_range(start_datetime: datetime, end_datetime: datetime) -> None:
    if start_datetime >= end_datetime:
        raise PermitValidationError("start_datetime must be before end_datetime")


def _validate_permit_type_requirements(data: dict) -> None:
    permit_type = data.get("permit_type")
    if permit_type == PermitType.hot_work and not data.get("precautions_required"):
        raise PermitValidationError("hot_work permits require precautions_required")
    if permit_type == PermitType.confined_space and data.get("gas_test_required") and not data.get("gas_test_results"):
        raise PermitValidationError("confined_space permits require gas_test_results when gas testing is required")


def _derive_expired_status(data: dict) -> None:
    status = data.get("status", PermitStatus.draft)
    end_datetime = data.get("end_datetime")
    if end_datetime is not None and _aware(end_datetime) < _now() and status in ACTIVE_EXPIRY_STATUSES:
        data["status"] = PermitStatus.expired


def _apply_approval_timestamp(
    data: dict,
    *,
    previous_status: Optional[PermitStatus] = None,
    existing_approved_at: Optional[datetime] = None,
) -> None:
    status = data.get("status", previous_status or PermitStatus.draft)
    if status == PermitStatus.approved and data.get("approved_at") is None:
        data["approved_at"] = existing_approved_at or _now()


def _validate_status_transition(previous_status: Optional[PermitStatus], next_status: PermitStatus) -> None:
    if previous_status is None:
        return
    if next_status == PermitStatus.active and previous_status != PermitStatus.approved:
        raise PermitValidationError("permit cannot become active unless it was approved")
    if next_status == PermitStatus.closed and previous_status not in CLOSABLE_STATUSES:
        raise PermitValidationError("permit cannot close unless it was approved, active, or suspended")


def list_permits(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[PermitStatus] = None,
    permit_type: Optional[PermitType] = None,
    site_id: Optional[int] = None,
    requested_by_user_id: Optional[int] = None,
    issued_by_user_id: Optional[int] = None,
    approved_by_user_id: Optional[int] = None,
    date_from=None,
    date_to=None,
) -> dict:
    statement: Select[tuple[PermitToWork]] = select(PermitToWork)
    if status is not None:
        statement = statement.where(PermitToWork.status == status)
    if permit_type is not None:
        statement = statement.where(PermitToWork.permit_type == permit_type)
    if site_id is not None:
        statement = statement.where(PermitToWork.site_id == site_id)
    if requested_by_user_id is not None:
        statement = statement.where(PermitToWork.requested_by_user_id == requested_by_user_id)
    if issued_by_user_id is not None:
        statement = statement.where(PermitToWork.issued_by_user_id == issued_by_user_id)
    if approved_by_user_id is not None:
        statement = statement.where(PermitToWork.approved_by_user_id == approved_by_user_id)
    statement = apply_date_filters(statement, PermitToWork.start_datetime, date_from=date_from, date_to=date_to)
    statement = statement.order_by(PermitToWork.start_datetime.desc(), PermitToWork.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_permit(db: Session, permit_id: int) -> PermitToWork:
    permit = db.get(PermitToWork, permit_id)
    if permit is None:
        raise PermitNotFoundError(f"Permit {permit_id} was not found")
    return permit


def create_permit(db: Session, permit_in: PermitCreate) -> PermitToWork:
    data = permit_in.model_dump()
    _dump_json_items(data)
    _ensure_site_exists(db, data.get("site_id"))
    for user_field in ("requested_by_user_id", "issued_by_user_id", "approved_by_user_id"):
        _ensure_user_exists(db, data.get(user_field))
    _validate_datetime_range(data["start_datetime"], data["end_datetime"])
    _validate_permit_type_requirements(data)
    _derive_expired_status(data)
    _apply_approval_timestamp(data)

    permit = PermitToWork(**data)
    db.add(permit)
    db.commit()
    db.refresh(permit)
    if permit.status == PermitStatus.pending_approval:
        notify_permit_pending_approval(db, permit)
    return permit


def update_permit(db: Session, permit: PermitToWork, permit_in: PermitUpdate) -> PermitToWork:
    update_data = permit_in.model_dump(exclude_unset=True)
    _dump_json_items(update_data)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data.get("site_id"))
    for user_field in ("requested_by_user_id", "issued_by_user_id", "approved_by_user_id"):
        if user_field in update_data:
            _ensure_user_exists(db, update_data.get(user_field))

    effective_data = {
        "permit_type": update_data.get("permit_type", permit.permit_type),
        "status": update_data.get("status", permit.status),
        "start_datetime": update_data.get("start_datetime", permit.start_datetime),
        "end_datetime": update_data.get("end_datetime", permit.end_datetime),
        "precautions_required": update_data.get("precautions_required", permit.precautions_required),
        "gas_test_required": update_data.get("gas_test_required", permit.gas_test_required),
        "gas_test_results": update_data.get("gas_test_results", permit.gas_test_results),
    }
    previous_status = permit.status
    _validate_datetime_range(effective_data["start_datetime"], effective_data["end_datetime"])
    _validate_status_transition(previous_status, effective_data["status"])
    _validate_permit_type_requirements(effective_data)
    _derive_expired_status(effective_data)
    update_data["status"] = effective_data["status"]
    _apply_approval_timestamp(
        update_data,
        previous_status=previous_status,
        existing_approved_at=permit.approved_at,
    )
    if update_data["status"] == PermitStatus.closed and update_data.get("closed_at") is None:
        update_data["closed_at"] = _now()

    for field, value in update_data.items():
        setattr(permit, field, value)
    db.add(permit)
    db.commit()
    db.refresh(permit)

    if permit.status == PermitStatus.pending_approval and previous_status != PermitStatus.pending_approval:
        notify_permit_pending_approval(db, permit)
    return permit


def notify_permit_pending_approval(db: Session, permit: PermitToWork) -> list[Notification]:
    if permit.status != PermitStatus.pending_approval or permit.approved_by_user_id is None:
        return []
    notification = create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=permit.approved_by_user_id,
            title="Permit pending approval",
            message=f"Permit '{permit.permit_number}' is pending approval.",
            notification_type=NotificationType.permit_pending_approval,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.permit,
            related_entity_id=permit.id,
        ),
    )
    return [notification] if notification is not None else []


def generate_permit_nearing_expiry_notifications(
    db: Session, *, days_ahead: Optional[int] = None, hours_ahead: Optional[int] = None
) -> list[Notification]:
    now = _now()
    warning_days = days_ahead if days_ahead is not None else settings.PERMIT_EXPIRY_WARNING_DAYS
    warning_delta = timedelta(hours=hours_ahead) if hours_ahead is not None else timedelta(days=warning_days)
    threshold_label = f"{warning_days} days" if hours_ahead is None else "the configured renewal threshold"
    expires_by = now + warning_delta
    permits = list(
        db.scalars(
            select(PermitToWork).where(
                PermitToWork.approved_by_user_id.is_not(None),
                PermitToWork.end_datetime >= now,
                PermitToWork.end_datetime <= expires_by,
                PermitToWork.status.in_([PermitStatus.approved, PermitStatus.active]),
            )
        ).all()
    )
    notifications = []
    for permit in permits:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=permit.approved_by_user_id,
                title="Permit renewal due soon",
                message=(
                    f"Permit renewal process should begin soon. Permit '{permit.permit_number}' "
                    f"expires within {threshold_label}."
                ),
                notification_type=NotificationType.permit_nearing_expiry,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.permit,
                related_entity_id=permit.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def generate_permit_expired_notifications(db: Session) -> list[Notification]:
    permits = list(
        db.scalars(
            select(PermitToWork).where(
                PermitToWork.approved_by_user_id.is_not(None),
                PermitToWork.end_datetime < _now(),
                PermitToWork.status.in_([PermitStatus.approved, PermitStatus.active, PermitStatus.expired]),
            )
        ).all()
    )
    notifications = []
    for permit in permits:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=permit.approved_by_user_id,
                title="Permit expired",
                message=f"Permit '{permit.permit_number}' has expired.",
                notification_type=NotificationType.permit_expired,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.permit,
                related_entity_id=permit.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications
