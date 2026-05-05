from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.emergency_drill import EmergencyDrillStatus
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class EmergencyDrillBase(BaseModel):
    emergency_type: str = Field(min_length=2, max_length=120)
    site_id: int
    drill_date: date
    participants: list[str] = Field(default_factory=list)
    attendance_records: list[dict] = Field(default_factory=list)
    outcome: str | None = None
    issues_found: list[str] = Field(default_factory=list)
    corrective_actions: list[str] = Field(default_factory=list)
    next_drill_date: date | None = None
    status: EmergencyDrillStatus = EmergencyDrillStatus.scheduled
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class EmergencyDrillCreate(EmergencyDrillBase):
    pass


class EmergencyDrillUpdate(BaseModel):
    emergency_type: str | None = Field(default=None, min_length=2, max_length=120)
    site_id: int | None = None
    drill_date: date | None = None
    participants: list[str] | None = None
    attendance_records: list[dict] | None = None
    outcome: str | None = None
    issues_found: list[str] | None = None
    corrective_actions: list[str] | None = None
    next_drill_date: date | None = None
    status: EmergencyDrillStatus | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class EmergencyDrillRead(EmergencyDrillBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmergencyDrillListRead(PaginatedResponse[EmergencyDrillRead]):
    pass
