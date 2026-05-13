from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.jsa import JSAStatus, ResidualRiskLevel
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class JSABase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    site_id: int
    department_or_area: str = Field(min_length=2, max_length=200)
    job_steps: list[str] = Field(default_factory=list)
    hazards: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    ppe_required: list[str] = Field(default_factory=list)
    residual_risk_level: ResidualRiskLevel = ResidualRiskLevel.medium
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    status: JSAStatus = JSAStatus.draft
    review_date: Optional[date] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class JSACreate(JSABase):
    pass


class JSAUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    site_id: Optional[int] = None
    department_or_area: Optional[str] = Field(default=None, min_length=2, max_length=200)
    job_steps: Optional[list[str]] = None
    hazards: Optional[list[str]] = None
    controls: Optional[list[str]] = None
    ppe_required: Optional[list[str]] = None
    residual_risk_level: Optional[ResidualRiskLevel] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    status: Optional[JSAStatus] = None
    review_date: Optional[date] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class JSARead(JSABase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JSAListRead(PaginatedResponse[JSARead]):
    pass
