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
    destination: str | None = None
    provider: str | None = None
    status: NotificationDeliveryStatus
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryListRead(PaginatedResponse[NotificationDeliveryRead]):
    pass
