from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification_delivery import (
    NotificationDeliveryChannel,
    NotificationDeliveryStatus,
)
from app.schemas.common import PaginatedResponse


class NotificationDeliveryRead(BaseModel):
    id: int
    notification_id: int
    recipient_user_id: int
    channel: NotificationDeliveryChannel
    destination: Optional[str] = None
    provider: Optional[str] = None
    status: NotificationDeliveryStatus
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryListRead(PaginatedResponse[NotificationDeliveryRead]):
    pass
