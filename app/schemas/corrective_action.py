from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.corrective_action import (
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class CorrectiveActionBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    source_type: CorrectiveActionSourceType = CorrectiveActionSourceType.manual
    source_id: int | None = None
    priority: CorrectiveActionPriority = CorrectiveActionPriority.medium
    status: CorrectiveActionStatus = CorrectiveActionStatus.open
    due_date: date | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    closure_notes: str | None = None
    closure_evidence_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    verification_notes: str | None = None
    assigned_to_user_id: int | None = None
    created_by_user_id: int | None = None
    verified_by_user_id: int | None = None
    verified_at: datetime | None = None


class CorrectiveActionCreate(CorrectiveActionBase):
    pass


class CorrectiveActionUpdate(BaseModel):
    site_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=2)
    source_type: CorrectiveActionSourceType | None = None
    source_id: int | None = None
    priority: CorrectiveActionPriority | None = None
    status: CorrectiveActionStatus | None = None
    due_date: date | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    closure_notes: str | None = None
    closure_evidence_metadata: list[AttachmentMetadata] | None = None
    verification_notes: str | None = None
    assigned_to_user_id: int | None = None
    created_by_user_id: int | None = None
    verified_by_user_id: int | None = None
    verified_at: datetime | None = None


class CorrectiveActionRead(CorrectiveActionBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionListRead(PaginatedResponse[CorrectiveActionRead]):
    pass
