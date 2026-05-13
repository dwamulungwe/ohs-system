from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.safety_communication import SafetyCommunicationStatus, SafetyCommunicationType
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class SafetyCommunicationBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    communication_type: SafetyCommunicationType
    status: SafetyCommunicationStatus = SafetyCommunicationStatus.draft
    summary: str = Field(min_length=2)
    details: Optional[str] = None
    audience: Optional[str] = Field(default=None, max_length=200)
    requires_acknowledgement: bool = False
    issued_at: datetime
    expires_at: Optional[datetime] = None
    owner_user_id: Optional[int] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.expires_at is not None and self.expires_at < self.issued_at:
            raise ValueError("Expiry must be after the issue date")
        return self


class SafetyCommunicationCreate(SafetyCommunicationBase):
    pass


class SafetyCommunicationUpdate(BaseModel):
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    communication_type: Optional[SafetyCommunicationType] = None
    status: Optional[SafetyCommunicationStatus] = None
    summary: Optional[str] = Field(default=None, min_length=2)
    details: Optional[str] = None
    audience: Optional[str] = Field(default=None, max_length=200)
    requires_acknowledgement: Optional[bool] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    owner_user_id: Optional[int] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class SafetyCommunicationRead(SafetyCommunicationBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafetyCommunicationListRead(PaginatedResponse[SafetyCommunicationRead]):
    pass
