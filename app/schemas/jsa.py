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
    approved_by_user_id: int | None = None
    approved_at: datetime | None = None
    status: JSAStatus = JSAStatus.draft
    review_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class JSACreate(JSABase):
    pass


class JSAUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    site_id: int | None = None
    department_or_area: str | None = Field(default=None, min_length=2, max_length=200)
    job_steps: list[str] | None = None
    hazards: list[str] | None = None
    controls: list[str] | None = None
    ppe_required: list[str] | None = None
    residual_risk_level: ResidualRiskLevel | None = None
    approved_by_user_id: int | None = None
    approved_at: datetime | None = None
    status: JSAStatus | None = None
    review_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class JSARead(JSABase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JSAListRead(PaginatedResponse[JSARead]):
    pass
