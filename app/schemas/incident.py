from typing import Optional
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
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    occurred_at: Optional[datetime] = None
    is_recordable: Optional[bool] = None
    is_lost_time: Optional[bool] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class IncidentRead(IncidentBase):
    id: int
    status: IncidentStatus
    reported_by_id: Optional[int] = None
    is_recordable: bool = False
    is_lost_time: bool = False
    closure_requested: bool = False
    closed_at: Optional[datetime] = None
    closed_by_user_id: Optional[int] = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentListRead(PaginatedResponse[IncidentRead]):
    pass
