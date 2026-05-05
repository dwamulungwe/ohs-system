from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notification import Notification
from app.models.notification_delivery import (
    NotificationDeliveryChannel,
    NotificationDeliveryLog,
    NotificationDeliveryStatus,
)
from app.models.user import User
from app.services.query_utils import paginate


class NotificationDeliveryServiceError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_delivery_log(
    db: Session,
    *,
    notification: Notification,
    recipient: User,
    channel: NotificationDeliveryChannel,
    destination: str | None,
    provider: str | None,
    status: NotificationDeliveryStatus,
    error_message: str | None = None,
) -> NotificationDeliveryLog:
    log = NotificationDeliveryLog(
        notification_id=notification.id,
        recipient_user_id=recipient.id,
        channel=channel,
        destination=destination,
        provider=provider,
        status=status,
        error_message=error_message,
        sent_at=_now() if status == NotificationDeliveryStatus.sent else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _send_email(destination: str, notification: Notification) -> None:
    message = EmailMessage()
    message["Subject"] = notification.title
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = destination
    message.set_content(notification.message)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
        smtp.send_message(message)


def _send_sms(destination: str, notification: Notification) -> None:
    if not settings.SMS_ENABLED:
        raise NotificationDeliveryServiceError("SMS delivery is disabled")
    if settings.SMS_PROVIDER_NAME == "noop":
        return
    raise NotificationDeliveryServiceError(
        f"Unsupported SMS provider '{settings.SMS_PROVIDER_NAME}'"
    )


def dispatch_notification_delivery(db: Session, notification: Notification) -> list[NotificationDeliveryLog]:
    recipient = db.get(User, notification.recipient_user_id)
    if recipient is None:
        return []

    logs: list[NotificationDeliveryLog] = []

    email_destination = recipient.email
    if not settings.SMTP_ENABLED:
        logs.append(
            _create_delivery_log(
                db,
                notification=notification,
                recipient=recipient,
                channel=NotificationDeliveryChannel.email,
                destination=email_destination,
                provider="smtp",
                status=NotificationDeliveryStatus.skipped,
                error_message="SMTP delivery disabled",
            )
        )
    elif not email_destination:
        logs.append(
            _create_delivery_log(
                db,
                notification=notification,
                recipient=recipient,
                channel=NotificationDeliveryChannel.email,
                destination=None,
                provider="smtp",
                status=NotificationDeliveryStatus.skipped,
                error_message="Recipient email not available",
            )
        )
    else:
        try:
            _send_email(email_destination, notification)
            logs.append(
                _create_delivery_log(
                    db,
                    notification=notification,
                    recipient=recipient,
                    channel=NotificationDeliveryChannel.email,
                    destination=email_destination,
                    provider="smtp",
                    status=NotificationDeliveryStatus.sent,
                )
            )
        except Exception as exc:
            logs.append(
                _create_delivery_log(
                    db,
                    notification=notification,
                    recipient=recipient,
                    channel=NotificationDeliveryChannel.email,
                    destination=email_destination,
                    provider="smtp",
                    status=NotificationDeliveryStatus.failed,
                    error_message=str(exc),
                )
            )

    sms_destination = recipient.phone_number
    if not settings.SMS_ENABLED:
        logs.append(
            _create_delivery_log(
                db,
                notification=notification,
                recipient=recipient,
                channel=NotificationDeliveryChannel.sms,
                destination=sms_destination,
                provider=settings.SMS_PROVIDER_NAME,
                status=NotificationDeliveryStatus.skipped,
                error_message="SMS delivery disabled",
            )
        )
    elif not sms_destination:
        logs.append(
            _create_delivery_log(
                db,
                notification=notification,
                recipient=recipient,
                channel=NotificationDeliveryChannel.sms,
                destination=None,
                provider=settings.SMS_PROVIDER_NAME,
                status=NotificationDeliveryStatus.skipped,
                error_message="Recipient phone number not available",
            )
        )
    else:
        try:
            _send_sms(sms_destination, notification)
            logs.append(
                _create_delivery_log(
                    db,
                    notification=notification,
                    recipient=recipient,
                    channel=NotificationDeliveryChannel.sms,
                    destination=sms_destination,
                    provider=settings.SMS_PROVIDER_NAME,
                    status=NotificationDeliveryStatus.sent,
                )
            )
        except Exception as exc:
            logs.append(
                _create_delivery_log(
                    db,
                    notification=notification,
                    recipient=recipient,
                    channel=NotificationDeliveryChannel.sms,
                    destination=sms_destination,
                    provider=settings.SMS_PROVIDER_NAME,
                    status=NotificationDeliveryStatus.failed,
                    error_message=str(exc),
                )
            )

    return logs


def list_notification_delivery_logs(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    notification_id: int | None = None,
    recipient_user_id: int | None = None,
    channel: NotificationDeliveryChannel | None = None,
    delivery_status: NotificationDeliveryStatus | None = None,
) -> dict:
    statement: Select[tuple[NotificationDeliveryLog]] = select(NotificationDeliveryLog)
    if notification_id is not None:
        statement = statement.where(NotificationDeliveryLog.notification_id == notification_id)
    if recipient_user_id is not None:
        statement = statement.where(NotificationDeliveryLog.recipient_user_id == recipient_user_id)
    if channel is not None:
        statement = statement.where(NotificationDeliveryLog.channel == channel)
    if delivery_status is not None:
        statement = statement.where(NotificationDeliveryLog.status == delivery_status)
    statement = statement.order_by(NotificationDeliveryLog.created_at.desc(), NotificationDeliveryLog.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_notification_delivery_log(db: Session, log_id: int) -> NotificationDeliveryLog | None:
    return db.get(NotificationDeliveryLog, log_id)
