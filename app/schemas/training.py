from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.training import ComplianceAcknowledgementStatus, TrainingStatus, TrainingType
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class TrainingRecordBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    training_type: TrainingType
    site_id: Optional[int] = None
    assigned_to_user_id: int
    assigned_by_user_id: Optional[int] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: TrainingStatus = TrainingStatus.assigned
    certificate_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    notes: Optional[str] = None


class TrainingRecordCreate(TrainingRecordBase):
    pass


class TrainingRecordUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    training_type: Optional[TrainingType] = None
    site_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: Optional[TrainingStatus] = None
    certificate_metadata: Optional[list[AttachmentMetadata]] = None
    notes: Optional[str] = None


class TrainingRecordRead(TrainingRecordBase):
    id: int
    assigned_by_user_id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRecordListRead(PaginatedResponse[TrainingRecordRead]):
    pass


class ComplianceAcknowledgementBase(BaseModel):
    document_title: str = Field(min_length=2, max_length=200)
    document_type: str = Field(min_length=2, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    site_id: Optional[int] = None
    document_control_id: Optional[int] = None
    assigned_to_user_id: int
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    status: ComplianceAcknowledgementStatus = ComplianceAcknowledgementStatus.assigned
    notes: Optional[str] = None


class ComplianceAcknowledgementCreate(ComplianceAcknowledgementBase):
    pass


class ComplianceAcknowledgementUpdate(BaseModel):
    document_title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    document_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    version: Optional[str] = Field(default=None, min_length=1, max_length=80)
    site_id: Optional[int] = None
    document_control_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    status: Optional[ComplianceAcknowledgementStatus] = None
    notes: Optional[str] = None


class ComplianceAcknowledgementRead(ComplianceAcknowledgementBase):
    id: int
    assigned_by_user_id: int
    assigned_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ComplianceAcknowledgementListRead(PaginatedResponse[ComplianceAcknowledgementRead]):
    pass
