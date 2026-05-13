from typing import Optional
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
    site_id: Optional[int] = None
    owner_user_id: int
    compliance_status: LegalComplianceStatus = LegalComplianceStatus.pending_review
    review_frequency: str = Field(min_length=2, max_length=120)
    next_review_date: Optional[date] = None
    last_reviewed_at: Optional[datetime] = None
    evidence_required: bool = False
    notes: Optional[str] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class LegalComplianceCreate(LegalComplianceBase):
    pass


class LegalComplianceUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    regulatory_body: Optional[str] = Field(default=None, min_length=2, max_length=200)
    legal_reference: Optional[str] = Field(default=None, min_length=2, max_length=200)
    requirement_summary: Optional[str] = Field(default=None, min_length=2)
    site_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    compliance_status: Optional[LegalComplianceStatus] = None
    review_frequency: Optional[str] = Field(default=None, min_length=2, max_length=120)
    next_review_date: Optional[date] = None
    last_reviewed_at: Optional[datetime] = None
    evidence_required: Optional[bool] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class LegalComplianceRead(LegalComplianceBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalComplianceListRead(PaginatedResponse[LegalComplianceRead]):
    pass
