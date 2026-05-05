from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.hazard import HazardRiskLevel, HazardStatus
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class HazardBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    existing_controls: list[str] = Field(default_factory=list)
    additional_controls: list[str] = Field(default_factory=list)
    owner_user_id: int | None = None
    due_date: date | None = None
    review_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    incident_id: int | None = None


class HazardCreate(HazardBase):
    status: HazardStatus = HazardStatus.open


class HazardUpdate(BaseModel):
    site_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=2)
    likelihood: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    status: HazardStatus | None = None
    existing_controls: list[str] | None = None
    additional_controls: list[str] | None = None
    owner_user_id: int | None = None
    due_date: date | None = None
    review_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None
    incident_id: int | None = None


class HazardRead(HazardBase):
    id: int
    risk_score: int
    risk_level: HazardRiskLevel
    status: HazardStatus
    reported_by_id: int | None = None
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HazardListRead(PaginatedResponse[HazardRead]):
    pass
