from typing import Optional
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
    source_id: Optional[int] = None
    priority: CorrectiveActionPriority = CorrectiveActionPriority.medium
    status: CorrectiveActionStatus = CorrectiveActionStatus.open
    due_date: Optional[date] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closure_notes: Optional[str] = None
    closure_evidence_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    verification_notes: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None


class CorrectiveActionCreate(CorrectiveActionBase):
    pass


class CorrectiveActionUpdate(BaseModel):
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    source_type: Optional[CorrectiveActionSourceType] = None
    source_id: Optional[int] = None
    priority: Optional[CorrectiveActionPriority] = None
    status: Optional[CorrectiveActionStatus] = None
    due_date: Optional[date] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closure_notes: Optional[str] = None
    closure_evidence_metadata: Optional[list[AttachmentMetadata]] = None
    verification_notes: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None


class CorrectiveActionRead(CorrectiveActionBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionListRead(PaginatedResponse[CorrectiveActionRead]):
    pass
