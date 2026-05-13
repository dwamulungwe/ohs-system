from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.schemas.common import PaginatedResponse


class NotificationBase(BaseModel):
    recipient_user_id: int
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)
    notification_type: NotificationType
    severity: NotificationSeverity
    related_entity_type: RelatedEntityType
    related_entity_id: int


class NotificationCreate(NotificationBase):
    pass


class NotificationRead(NotificationBase):
    id: int
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListRead(PaginatedResponse[NotificationRead]):
    pass


class UnreadCountRead(BaseModel):
    unread_count: int


class MarkAllReadRead(BaseModel):
    updated_count: int
