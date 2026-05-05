from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.notification_delivery import (
    NotificationDeliveryChannel,
    NotificationDeliveryStatus,
)
from app.models.user import User
from app.schemas.notification_delivery import (
    NotificationDeliveryListRead,
    NotificationDeliveryRead,
)
from app.services.notification_delivery_service import (
    get_notification_delivery_log,
    list_notification_delivery_logs,
)
from app.services.rbac import Permission, ensure_permission

router = APIRouter()


@router.get("", response_model=NotificationDeliveryListRead)
def read_notification_delivery_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    notification_id: int | None = None,
    recipient_user_id: int | None = None,
    channel: NotificationDeliveryChannel | None = None,
    delivery_status: NotificationDeliveryStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.NOTIFICATION_DELIVERY_VIEW)
    return list_notification_delivery_logs(
        db,
        skip=skip,
        limit=limit,
        notification_id=notification_id,
        recipient_user_id=recipient_user_id,
        channel=channel,
        delivery_status=delivery_status,
    )


@router.get("/{log_id}", response_model=NotificationDeliveryRead)
def read_notification_delivery_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.NOTIFICATION_DELIVERY_VIEW)
    log = get_notification_delivery_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification delivery log not found")
    return log
