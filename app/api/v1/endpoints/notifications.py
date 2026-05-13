from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.notification import NotificationSeverity, NotificationType
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadRead,
    NotificationCreate,
    NotificationListRead,
    NotificationRead,
    UnreadCountRead,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationRecipientNotFoundError,
    create_notification,
    get_notification,
    get_unread_count,
    list_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from app.services.rbac import Permission, ensure_permission

router = APIRouter()


@router.get("", response_model=NotificationListRead)
def list_user_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    is_read: Optional[bool] = None,
    severity: Optional[NotificationSeverity] = None,
    notification_type: Optional[NotificationType] = None,
    recipient_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.NOTIFICATIONS_VIEW)
    return list_notifications(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        is_read=is_read,
        severity=severity,
        notification_type=notification_type,
        recipient_user_id=recipient_user_id,
    )


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_new_notification(
    notification_in: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.NOTIFICATIONS_MANAGE)
    try:
        return create_notification(db, notification_in)
    except NotificationRecipientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found")


@router.get("/unread-count", response_model=UnreadCountRead)
def read_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    ensure_permission(current_user, Permission.NOTIFICATIONS_VIEW)
    return {"unread_count": get_unread_count(db, current_user=current_user)}


@router.patch("/mark-all-as-read", response_model=MarkAllReadRead)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    ensure_permission(current_user, Permission.NOTIFICATIONS_VIEW)
    return {"updated_count": mark_all_notifications_as_read(db, current_user=current_user)}


@router.get("/{notification_id}", response_model=NotificationRead)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.NOTIFICATIONS_VIEW)
    try:
        return get_notification(db, notification_id, current_user=current_user)
    except NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.NOTIFICATIONS_VIEW)
    try:
        notification = get_notification(db, notification_id, current_user=current_user)
        return mark_notification_as_read(db, notification)
    except NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
