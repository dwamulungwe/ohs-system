from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.incident import IncidentSeverity, IncidentStatus
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class IncidentBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    severity: IncidentSeverity
    occurred_at: datetime
    is_recordable: bool = False
    is_lost_time: bool = False
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class IncidentCreate(IncidentBase):
    status: IncidentStatus = IncidentStatus.open


class IncidentUpdate(BaseModel):
    site_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=2)
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    occurred_at: datetime | None = None
    is_recordable: bool | None = None
    is_lost_time: bool | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class IncidentRead(IncidentBase):
    id: int
    status: IncidentStatus
    reported_by_id: int | None = None
    is_recordable: bool = False
    is_lost_time: bool = False
    closure_requested: bool = False
    closed_at: datetime | None = None
    closed_by_user_id: int | None = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentListRead(PaginatedResponse[IncidentRead]):
    pass
