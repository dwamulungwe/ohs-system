from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.training import ComplianceAcknowledgementStatus, TrainingStatus, TrainingType
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class TrainingRecordBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    training_type: TrainingType
    site_id: int | None = None
    assigned_to_user_id: int
    assigned_by_user_id: int | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
    expiry_date: date | None = None
    status: TrainingStatus = TrainingStatus.assigned
    certificate_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    notes: str | None = None


class TrainingRecordCreate(TrainingRecordBase):
    pass


class TrainingRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    training_type: TrainingType | None = None
    site_id: int | None = None
    assigned_to_user_id: int | None = None
    assigned_by_user_id: int | None = None
    due_date: date | None = None
    completed_at: datetime | None = None
    expiry_date: date | None = None
    status: TrainingStatus | None = None
    certificate_metadata: list[AttachmentMetadata] | None = None
    notes: str | None = None


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
    site_id: int | None = None
    document_control_id: int | None = None
    assigned_to_user_id: int
    assigned_by_user_id: int | None = None
    assigned_at: datetime | None = None
    acknowledged_at: datetime | None = None
    status: ComplianceAcknowledgementStatus = ComplianceAcknowledgementStatus.assigned
    notes: str | None = None


class ComplianceAcknowledgementCreate(ComplianceAcknowledgementBase):
    pass


class ComplianceAcknowledgementUpdate(BaseModel):
    document_title: str | None = Field(default=None, min_length=2, max_length=200)
    document_type: str | None = Field(default=None, min_length=2, max_length=120)
    version: str | None = Field(default=None, min_length=1, max_length=80)
    site_id: int | None = None
    document_control_id: int | None = None
    assigned_to_user_id: int | None = None
    assigned_by_user_id: int | None = None
    assigned_at: datetime | None = None
    acknowledged_at: datetime | None = None
    status: ComplianceAcknowledgementStatus | None = None
    notes: str | None = None


class ComplianceAcknowledgementRead(ComplianceAcknowledgementBase):
    id: int
    assigned_by_user_id: int
    assigned_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ComplianceAcknowledgementListRead(PaginatedResponse[ComplianceAcknowledgementRead]):
    pass
