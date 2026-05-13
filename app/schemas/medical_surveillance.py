from typing import Optional
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
    site_id: Optional[int] = None
    surveillance_type: str = Field(min_length=2, max_length=120)
    due_date: date
    completed_at: Optional[datetime] = None
    status: MedicalSurveillanceStatus = MedicalSurveillanceStatus.due
    results_summary: Optional[str] = None
    medical_clearance_status: MedicalClearanceStatus = MedicalClearanceStatus.pending
    next_due_date: Optional[date] = None
    notes: Optional[str] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class MedicalSurveillanceCreate(MedicalSurveillanceBase):
    pass


class MedicalSurveillanceUpdate(BaseModel):
    employee_user_id: Optional[int] = None
    site_id: Optional[int] = None
    surveillance_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    status: Optional[MedicalSurveillanceStatus] = None
    results_summary: Optional[str] = None
    medical_clearance_status: Optional[MedicalClearanceStatus] = None
    next_due_date: Optional[date] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class MedicalSurveillanceRead(MedicalSurveillanceBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalSurveillanceListRead(PaginatedResponse[MedicalSurveillanceRead]):
    pass
