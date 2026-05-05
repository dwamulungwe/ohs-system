from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.training import (
    ComplianceAcknowledgement,
    ComplianceAcknowledgementStatus,
    TrainingRecord,
    TrainingStatus,
    TrainingType,
)
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.schemas.training import (
    ComplianceAcknowledgementCreate,
    ComplianceAcknowledgementUpdate,
    TrainingRecordCreate,
    TrainingRecordUpdate,
)
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate


class TrainingServiceError(Exception):
    pass


class TrainingRecordNotFoundError(TrainingServiceError):
    pass


class ComplianceAcknowledgementNotFoundError(TrainingServiceError):
    pass


class TrainingSiteNotFoundError(TrainingServiceError):
    pass


class TrainingUserNotFoundError(TrainingServiceError):
    pass


COMPLIANCE_OVERDUE_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_site_exists(db: Session, site_id: int | None) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise TrainingSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise TrainingUserNotFoundError(f"User {user_id} was not found")


def _dump_certificate_metadata(data: dict) -> None:
    if "certificate_metadata" in data and data["certificate_metadata"] is not None:
        data["certificate_metadata"] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data["certificate_metadata"]
        ]


def derive_training_status(data: dict) -> None:
    status = data.get("status", TrainingStatus.assigned)
    completed_at = data.get("completed_at")
    due_date = data.get("due_date")
    expiry_date = data.get("expiry_date")
    today = date.today()

    if status == TrainingStatus.cancelled:
        return
    if completed_at is not None and expiry_date is not None and expiry_date < today:
        data["status"] = TrainingStatus.expired
        return
    if completed_at is not None and status in {TrainingStatus.assigned, TrainingStatus.in_progress, TrainingStatus.overdue}:
        data["status"] = TrainingStatus.completed
        return
    if due_date is not None and due_date < today and status not in {TrainingStatus.completed, TrainingStatus.expired}:
        data["status"] = TrainingStatus.overdue


def derive_compliance_status(data: dict, *, overdue_days: int = COMPLIANCE_OVERDUE_DAYS) -> None:
    status = data.get("status", ComplianceAcknowledgementStatus.assigned)
    acknowledged_at = data.get("acknowledged_at")
    assigned_at = data.get("assigned_at") or _now()
    if status == ComplianceAcknowledgementStatus.superseded:
        return
    if acknowledged_at is not None:
        data["status"] = ComplianceAcknowledgementStatus.acknowledged
        return
    if assigned_at <= _now() - timedelta(days=overdue_days):
        data["status"] = ComplianceAcknowledgementStatus.overdue


def list_training_records(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: TrainingStatus | None = None,
    training_type: TrainingType | None = None,
    site_id: int | None = None,
    assigned_to_user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    statement: Select[tuple[TrainingRecord]] = select(TrainingRecord)
    if status is not None:
        statement = statement.where(TrainingRecord.status == status)
    if training_type is not None:
        statement = statement.where(TrainingRecord.training_type == training_type)
    if site_id is not None:
        statement = statement.where(TrainingRecord.site_id == site_id)
    if assigned_to_user_id is not None:
        statement = statement.where(TrainingRecord.assigned_to_user_id == assigned_to_user_id)
    if date_from is not None:
        statement = statement.where(TrainingRecord.due_date >= date_from)
    if date_to is not None:
        statement = statement.where(TrainingRecord.due_date <= date_to)
    statement = statement.order_by(TrainingRecord.due_date.asc(), TrainingRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_training_record(db: Session, training_id: int) -> TrainingRecord:
    record = db.get(TrainingRecord, training_id)
    if record is None:
        raise TrainingRecordNotFoundError(f"Training record {training_id} was not found")
    return record


def create_training_record(db: Session, training_in: TrainingRecordCreate, *, current_user_id: int | None) -> TrainingRecord:
    data = training_in.model_dump()
    _dump_certificate_metadata(data)
    if data.get("assigned_by_user_id") is None:
        data["assigned_by_user_id"] = current_user_id
    _ensure_site_exists(db, data.get("site_id"))
    _ensure_user_exists(db, data.get("assigned_to_user_id"))
    _ensure_user_exists(db, data.get("assigned_by_user_id"))
    derive_training_status(data)

    record = TrainingRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_training_record(db: Session, record: TrainingRecord, training_in: TrainingRecordUpdate) -> TrainingRecord:
    update_data = training_in.model_dump(exclude_unset=True)
    _dump_certificate_metadata(update_data)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data.get("site_id"))
    for user_field in ("assigned_to_user_id", "assigned_by_user_id"):
        if user_field in update_data:
            _ensure_user_exists(db, update_data.get(user_field))

    effective_data = {
        "status": update_data.get("status", record.status),
        "completed_at": update_data.get("completed_at", record.completed_at),
        "due_date": update_data.get("due_date", record.due_date),
        "expiry_date": update_data.get("expiry_date", record.expiry_date),
    }
    derive_training_status(effective_data)
    update_data["status"] = effective_data["status"]

    for field, value in update_data.items():
        setattr(record, field, value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_compliance_acknowledgements(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: ComplianceAcknowledgementStatus | None = None,
    document_type: str | None = None,
    site_id: int | None = None,
    assigned_to_user_id: int | None = None,
) -> dict:
    statement: Select[tuple[ComplianceAcknowledgement]] = select(ComplianceAcknowledgement)
    if status is not None:
        statement = statement.where(ComplianceAcknowledgement.status == status)
    if document_type is not None:
        statement = statement.where(ComplianceAcknowledgement.document_type == document_type)
    if site_id is not None:
        statement = statement.where(ComplianceAcknowledgement.site_id == site_id)
    if assigned_to_user_id is not None:
        statement = statement.where(ComplianceAcknowledgement.assigned_to_user_id == assigned_to_user_id)
    statement = statement.order_by(ComplianceAcknowledgement.assigned_at.desc(), ComplianceAcknowledgement.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_compliance_acknowledgement(db: Session, acknowledgement_id: int) -> ComplianceAcknowledgement:
    acknowledgement = db.get(ComplianceAcknowledgement, acknowledgement_id)
    if acknowledgement is None:
        raise ComplianceAcknowledgementNotFoundError(f"Acknowledgement {acknowledgement_id} was not found")
    return acknowledgement


def create_compliance_acknowledgement(
    db: Session,
    acknowledgement_in: ComplianceAcknowledgementCreate,
    *,
    current_user_id: int | None,
) -> ComplianceAcknowledgement:
    data = acknowledgement_in.model_dump()
    if data.get("assigned_by_user_id") is None:
        data["assigned_by_user_id"] = current_user_id
    if data.get("assigned_at") is None:
        data["assigned_at"] = _now()
    _ensure_site_exists(db, data.get("site_id"))
    _ensure_user_exists(db, data.get("assigned_to_user_id"))
    _ensure_user_exists(db, data.get("assigned_by_user_id"))
    derive_compliance_status(data)

    acknowledgement = ComplianceAcknowledgement(**data)
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


def update_compliance_acknowledgement(
    db: Session,
    acknowledgement: ComplianceAcknowledgement,
    acknowledgement_in: ComplianceAcknowledgementUpdate,
) -> ComplianceAcknowledgement:
    update_data = acknowledgement_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data.get("site_id"))
    for user_field in ("assigned_to_user_id", "assigned_by_user_id"):
        if user_field in update_data:
            _ensure_user_exists(db, update_data.get(user_field))

    effective_data = {
        "status": update_data.get("status", acknowledgement.status),
        "acknowledged_at": update_data.get("acknowledged_at", acknowledgement.acknowledged_at),
        "assigned_at": update_data.get("assigned_at", acknowledgement.assigned_at),
    }
    derive_compliance_status(effective_data)
    update_data["status"] = effective_data["status"]

    for field, value in update_data.items():
        setattr(acknowledgement, field, value)
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


def generate_overdue_training_notifications(db: Session) -> list[Notification]:
    records = list(
        db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.assigned_to_user_id.is_not(None),
                TrainingRecord.status == TrainingStatus.overdue,
            )
        ).all()
    )
    notifications = []
    for record in records:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=record.assigned_to_user_id,
                title="Training overdue",
                message=f"Training '{record.title}' is overdue.",
                notification_type=NotificationType.training_overdue,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.training_record,
                related_entity_id=record.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def generate_expired_training_notifications(db: Session) -> list[Notification]:
    records = list(
        db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.assigned_to_user_id.is_not(None),
                TrainingRecord.status == TrainingStatus.expired,
            )
        ).all()
    )
    notifications = []
    for record in records:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=record.assigned_to_user_id,
                title="Training expired",
                message=f"Training '{record.title}' has expired.",
                notification_type=NotificationType.training_expired,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.training_record,
                related_entity_id=record.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def generate_overdue_compliance_acknowledgement_notifications(db: Session) -> list[Notification]:
    acknowledgements = list(
        db.scalars(
            select(ComplianceAcknowledgement).where(
                ComplianceAcknowledgement.assigned_to_user_id.is_not(None),
                ComplianceAcknowledgement.status == ComplianceAcknowledgementStatus.overdue,
            )
        ).all()
    )
    notifications = []
    for acknowledgement in acknowledgements:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=acknowledgement.assigned_to_user_id,
                title="Compliance acknowledgement overdue",
                message=f"Acknowledgement for '{acknowledgement.document_title}' is overdue.",
                notification_type=NotificationType.compliance_acknowledgement_overdue,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.compliance_acknowledgement,
                related_entity_id=acknowledgement.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications
