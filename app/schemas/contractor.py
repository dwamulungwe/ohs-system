from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.contractor import (
    ContractorComplianceDocumentsStatus,
    ContractorInductionStatus,
    ContractorOnboardingStatus,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class ContractorBase(BaseModel):
    contractor_name: str = Field(min_length=2, max_length=200)
    contact_person: str = Field(min_length=2, max_length=200)
    contact_email: str = Field(min_length=3, max_length=255)
    contact_phone: str = Field(min_length=2, max_length=80)
    site_id: int
    work_scope: str = Field(min_length=2)
    onboarding_status: ContractorOnboardingStatus = ContractorOnboardingStatus.pending
    induction_status: ContractorInductionStatus = ContractorInductionStatus.pending
    insurance_expiry_date: date | None = None
    compliance_documents_status: ContractorComplianceDocumentsStatus = (
        ContractorComplianceDocumentsStatus.incomplete
    )
    approved_for_work: bool = False
    notes: str | None = None
    documents_expiry_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class ContractorCreate(ContractorBase):
    pass


class ContractorUpdate(BaseModel):
    contractor_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, min_length=2, max_length=200)
    contact_email: str | None = Field(default=None, min_length=3, max_length=255)
    contact_phone: str | None = Field(default=None, min_length=2, max_length=80)
    site_id: int | None = None
    work_scope: str | None = Field(default=None, min_length=2)
    onboarding_status: ContractorOnboardingStatus | None = None
    induction_status: ContractorInductionStatus | None = None
    insurance_expiry_date: date | None = None
    compliance_documents_status: ContractorComplianceDocumentsStatus | None = None
    approved_for_work: bool | None = None
    notes: str | None = None
    documents_expiry_date: date | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class ContractorRead(ContractorBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractorListRead(PaginatedResponse[ContractorRead]):
    pass
