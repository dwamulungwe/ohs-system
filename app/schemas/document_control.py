from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document_control import DocumentStatus, DocumentType
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class DocumentControlBase(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    document_type: DocumentType
    version: str = Field(min_length=1, max_length=80)
    site_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: DocumentStatus = DocumentStatus.draft
    acknowledgement_required: bool = False
    acknowledgement_user_ids: list[int] = Field(default_factory=list)
    supersedes_document_id: Optional[int] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class DocumentControlCreate(DocumentControlBase):
    pass


class DocumentControlUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    document_type: Optional[DocumentType] = None
    version: Optional[str] = Field(default=None, min_length=1, max_length=80)
    site_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: Optional[DocumentStatus] = None
    acknowledgement_required: Optional[bool] = None
    acknowledgement_user_ids: Optional[list[int]] = None
    supersedes_document_id: Optional[int] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class DocumentControlRead(DocumentControlBase):
    id: int
    created_by_user_id: Optional[int] = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentControlListRead(PaginatedResponse[DocumentControlRead]):
    pass
