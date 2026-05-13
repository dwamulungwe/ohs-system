from typing import Optional
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
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
    review_date: Optional[date] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    incident_id: Optional[int] = None


class HazardCreate(HazardBase):
    status: HazardStatus = HazardStatus.open


class HazardUpdate(BaseModel):
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    impact: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[HazardStatus] = None
    existing_controls: Optional[list[str]] = None
    additional_controls: Optional[list[str]] = None
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
    review_date: Optional[date] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None
    incident_id: Optional[int] = None


class HazardRead(HazardBase):
    id: int
    risk_score: int
    risk_level: HazardRiskLevel
    status: HazardStatus
    reported_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_user_id: Optional[int] = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HazardListRead(PaginatedResponse[HazardRead]):
    pass
