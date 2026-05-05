from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.medical_surveillance import (
    MedicalClearanceStatus,
    MedicalSurveillanceStatus,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class MedicalSurveillanceBase(BaseModel):
    employee_user_id: int
    site_id: int | None = None
    surveillance_type: str = Field(min_length=2, max_length=120)
    due_date: date
    completed_at: datetime | None = None
    status: MedicalSurveillanceStatus = MedicalSurveillanceStatus.due
    results_summary: str | None = None
    medical_clearance_status: MedicalClearanceStatus = MedicalClearanceStatus.pending
    next_due_date: date | None = None
    notes: str | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class MedicalSurveillanceCreate(MedicalSurveillanceBase):
    pass


class MedicalSurveillanceUpdate(BaseModel):
    employee_user_id: int | None = None
    site_id: int | None = None
    surveillance_type: str | None = Field(default=None, min_length=2, max_length=120)
    due_date: date | None = None
    completed_at: datetime | None = None
    status: MedicalSurveillanceStatus | None = None
    results_summary: str | None = None
    medical_clearance_status: MedicalClearanceStatus | None = None
    next_due_date: date | None = None
    notes: str | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class MedicalSurveillanceRead(MedicalSurveillanceBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalSurveillanceListRead(PaginatedResponse[MedicalSurveillanceRead]):
    pass
