from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit_management import AuditStatus, AuditType
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class AuditManagementBase(BaseModel):
    audit_type: AuditType
    site_id: int
    auditor_user_id: int
    audit_date: date
    findings: list[str] = Field(default_factory=list)
    non_conformances: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    status: AuditStatus = AuditStatus.open
    audit_score: Optional[float] = None
    corrective_action_ids: list[int] = Field(default_factory=list)
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class AuditManagementCreate(AuditManagementBase):
    pass


class AuditManagementUpdate(BaseModel):
    audit_type: Optional[AuditType] = None
    site_id: Optional[int] = None
    auditor_user_id: Optional[int] = None
    audit_date: Optional[date] = None
    findings: Optional[list[str]] = None
    non_conformances: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    status: Optional[AuditStatus] = None
    audit_score: Optional[float] = None
    corrective_action_ids: Optional[list[int]] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class AuditManagementRead(AuditManagementBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditManagementListRead(PaginatedResponse[AuditManagementRead]):
    pass
