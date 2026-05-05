from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction, CorrectiveActionStatus
from app.models.hazard import Hazard, HazardRiskLevel
from app.models.incident import Incident, IncidentSeverity
from app.models.notification import Notification, NotificationSeverity, NotificationType, RelatedEntityType
from app.models.role import Role
from app.models.user import User
from app.schemas.notification import NotificationCreate
from app.services.notification_delivery_service import dispatch_notification_delivery
from app.services.query_utils import is_corrective_action_overdue, paginate
from app.services.rbac import Permission, has_permission


class NotificationServiceError(Exception):
    pass


class NotificationNotFoundError(NotificationServiceError):
    pass


class NotificationRecipientNotFoundError(NotificationServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _can_manage_notifications(user: User) -> bool:
    return has_permission(user, Permission.NOTIFICATIONS_MANAGE)


def _ensure_recipient_exists(db: Session, recipient_user_id: int) -> None:
    if db.get(User, recipient_user_id) is None:
        raise NotificationRecipientNotFoundError(f"User {recipient_user_id} was not found")


def _recipient_ids(*values: int | None) -> list[int]:
    seen = set()
    recipients = []
    for value in values:
        if value is not None and value not in seen:
            seen.add(value)
            recipients.append(value)
    return recipients


def get_active_user_ids_for_roles(
    db: Session,
    *,
    role_names: list[str],
    site_id: int | None = None,
) -> list[int]:
    statement = (
        select(User.id)
        .join(User.roles)
        .where(Role.name.in_(role_names), User.is_active.is_(True))
        .distinct()
    )
    if site_id is not None:
        statement = statement.where(
            (User.assigned_site_id == site_id) | (User.assigned_site_id.is_(None))
        )
    return list(db.scalars(statement).all())


def _notification_exists(
    db: Session,
    *,
    recipient_user_id: int,
    notification_type: NotificationType,
    related_entity_type: RelatedEntityType,
    related_entity_id: int,
) -> bool:
    return (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.notification_type == notification_type,
                Notification.related_entity_type == related_entity_type,
                Notification.related_entity_id == related_entity_id,
            )
        )
        or 0
    ) > 0


def create_notification(db: Session, notification_in: NotificationCreate) -> Notification:
    _ensure_recipient_exists(db, notification_in.recipient_user_id)
    notification = Notification(**notification_in.model_dump())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    dispatch_notification_delivery(db, notification)
    return notification


def create_notification_once(db: Session, notification_in: NotificationCreate) -> Notification | None:
    if _notification_exists(
        db,
        recipient_user_id=notification_in.recipient_user_id,
        notification_type=notification_in.notification_type,
        related_entity_type=notification_in.related_entity_type,
        related_entity_id=notification_in.related_entity_id,
    ):
        return None
    return create_notification(db, notification_in)


def list_notifications(
    db: Session,
    *,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    is_read: bool | None = None,
    severity: NotificationSeverity | None = None,
    notification_type: NotificationType | None = None,
    recipient_user_id: int | None = None,
) -> dict:
    statement: Select[tuple[Notification]] = select(Notification)
    if _can_manage_notifications(current_user) and recipient_user_id is not None:
        statement = statement.where(Notification.recipient_user_id == recipient_user_id)
    elif not _can_manage_notifications(current_user):
        statement = statement.where(Notification.recipient_user_id == current_user.id)

    if is_read is not None:
        statement = statement.where(Notification.is_read == is_read)
    if severity is not None:
        statement = statement.where(Notification.severity == severity)
    if notification_type is not None:
        statement = statement.where(Notification.notification_type == notification_type)

    statement = statement.order_by(Notification.created_at.desc(), Notification.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_notification(db: Session, notification_id: int, *, current_user: User) -> Notification:
    statement = select(Notification).where(Notification.id == notification_id)
    if not _can_manage_notifications(current_user):
        statement = statement.where(Notification.recipient_user_id == current_user.id)
    notification = db.scalar(statement)
    if notification is None:
        raise NotificationNotFoundError(f"Notification {notification_id} was not found")
    return notification


def mark_notification_as_read(db: Session, notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = _now()
        db.add(notification)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_as_read(db: Session, *, current_user: User) -> int:
    notifications = list(
        db.scalars(
            select(Notification).where(
                Notification.recipient_user_id == current_user.id,
                Notification.is_read.is_(False),
            )
        ).all()
    )
    now = _now()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
        db.add(notification)
    db.commit()
    return len(notifications)


def get_unread_count(db: Session, *, current_user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ) or 0


def notify_critical_hazard(db: Session, hazard: Hazard) -> list[Notification]:
    if hazard.risk_level != HazardRiskLevel.critical:
        return []
    notifications = []
    for recipient_user_id in _recipient_ids(hazard.owner_user_id, hazard.reported_by_id):
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=recipient_user_id,
                title="Critical hazard created",
                message=f"Hazard '{hazard.title}' has been classified as critical.",
                notification_type=NotificationType.critical_hazard_created,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.hazard,
                related_entity_id=hazard.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def notify_critical_incident(db: Session, incident: Incident) -> list[Notification]:
    if incident.severity != IncidentSeverity.critical:
        return []
    notifications = []
    for recipient_user_id in _recipient_ids(incident.reported_by_id):
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=recipient_user_id,
                title="Critical incident created",
                message=f"Incident '{incident.title}' has critical severity.",
                notification_type=NotificationType.critical_incident_created,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.incident,
                related_entity_id=incident.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def notify_action_pending_verification(db: Session, action: CorrectiveAction) -> list[Notification]:
    if action.status != CorrectiveActionStatus.pending_verification:
        return []
    notifications = []
    for recipient_user_id in _recipient_ids(action.verified_by_user_id, action.created_by_user_id):
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=recipient_user_id,
                title="Corrective action pending verification",
                message=f"Corrective action '{action.title}' is pending verification.",
                notification_type=NotificationType.action_pending_verification,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.corrective_action,
                related_entity_id=action.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def generate_corrective_action_due_soon_notifications(db: Session, *, days_ahead: int = 7) -> list[Notification]:
    today = date.today()
    due_by = today + timedelta(days=days_ahead)
    actions = list(
        db.scalars(
            select(CorrectiveAction).where(
                CorrectiveAction.assigned_to_user_id.is_not(None),
                CorrectiveAction.due_date >= today,
                CorrectiveAction.due_date <= due_by,
                CorrectiveAction.status.notin_(
                    [CorrectiveActionStatus.closed, CorrectiveActionStatus.cancelled]
                ),
            )
        ).all()
    )
    notifications = []
    for action in actions:
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=action.assigned_to_user_id,
                title="Corrective action due soon",
                message=f"Corrective action '{action.title}' is due by {action.due_date}.",
                notification_type=NotificationType.corrective_action_due_soon,
                severity=NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.corrective_action,
                related_entity_id=action.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications


def generate_corrective_action_overdue_notifications(db: Session) -> list[Notification]:
    actions = list(
        db.scalars(
            select(CorrectiveAction).where(
                CorrectiveAction.assigned_to_user_id.is_not(None),
                CorrectiveAction.status.notin_(
                    [CorrectiveActionStatus.closed, CorrectiveActionStatus.cancelled]
                ),
            )
        ).all()
    )
    notifications = []
    for action in actions:
        if not is_corrective_action_overdue(action):
            continue
        notification = create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=action.assigned_to_user_id,
                title="Corrective action overdue",
                message=f"Corrective action '{action.title}' is overdue.",
                notification_type=NotificationType.corrective_action_overdue,
                severity=NotificationSeverity.critical,
                related_entity_type=RelatedEntityType.corrective_action,
                related_entity_id=action.id,
            ),
        )
        if notification is not None:
            notifications.append(notification)
    return notifications
