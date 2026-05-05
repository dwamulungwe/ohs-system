from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.legal_compliance import LegalComplianceStatus
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class LegalComplianceBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    regulatory_body: str = Field(min_length=2, max_length=200)
    legal_reference: str = Field(min_length=2, max_length=200)
    requirement_summary: str = Field(min_length=2)
    site_id: int | None = None
    owner_user_id: int
    compliance_status: LegalComplianceStatus = LegalComplianceStatus.pending_review
    review_frequency: str = Field(min_length=2, max_length=120)
    next_review_date: date | None = None
    last_reviewed_at: datetime | None = None
    evidence_required: bool = False
    notes: str | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class LegalComplianceCreate(LegalComplianceBase):
    pass


class LegalComplianceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    regulatory_body: str | None = Field(default=None, min_length=2, max_length=200)
    legal_reference: str | None = Field(default=None, min_length=2, max_length=200)
    requirement_summary: str | None = Field(default=None, min_length=2)
    site_id: int | None = None
    owner_user_id: int | None = None
    compliance_status: LegalComplianceStatus | None = None
    review_frequency: str | None = Field(default=None, min_length=2, max_length=120)
    next_review_date: date | None = None
    last_reviewed_at: datetime | None = None
    evidence_required: bool | None = None
    notes: str | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class LegalComplianceRead(LegalComplianceBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalComplianceListRead(PaginatedResponse[LegalComplianceRead]):
    pass
