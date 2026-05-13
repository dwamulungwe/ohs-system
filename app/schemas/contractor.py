from typing import Optional
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
    insurance_expiry_date: Optional[date] = None
    compliance_documents_status: ContractorComplianceDocumentsStatus = (
        ContractorComplianceDocumentsStatus.incomplete
    )
    approved_for_work: bool = False
    notes: Optional[str] = None
    documents_expiry_date: Optional[date] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class ContractorCreate(ContractorBase):
    pass


class ContractorUpdate(BaseModel):
    contractor_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    contact_person: Optional[str] = Field(default=None, min_length=2, max_length=200)
    contact_email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    contact_phone: Optional[str] = Field(default=None, min_length=2, max_length=80)
    site_id: Optional[int] = None
    work_scope: Optional[str] = Field(default=None, min_length=2)
    onboarding_status: Optional[ContractorOnboardingStatus] = None
    induction_status: Optional[ContractorInductionStatus] = None
    insurance_expiry_date: Optional[date] = None
    compliance_documents_status: Optional[ContractorComplianceDocumentsStatus] = None
    approved_for_work: Optional[bool] = None
    notes: Optional[str] = None
    documents_expiry_date: Optional[date] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class ContractorRead(ContractorBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractorListRead(PaginatedResponse[ContractorRead]):
    pass
