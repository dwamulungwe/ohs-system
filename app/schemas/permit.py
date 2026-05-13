from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.permit import PermitStatus, PermitType
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class GasTestResult(BaseModel):
    test_name: str = Field(min_length=1, max_length=120)
    result: str = Field(min_length=1, max_length=120)
    tested_at: Optional[datetime] = None
    tested_by: Optional[str] = Field(default=None, max_length=120)


class PermitBase(BaseModel):
    permit_number: str = Field(min_length=2, max_length=80)
    permit_type: PermitType
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    site_id: int
    area_location: str = Field(min_length=2, max_length=255)
    requested_by_user_id: int
    issued_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    assigned_team_or_contractor: Optional[str] = Field(default=None, max_length=255)
    start_datetime: datetime
    end_datetime: datetime
    status: PermitStatus = PermitStatus.draft
    risk_summary: Optional[str] = None
    precautions_required: list[str] = Field(default_factory=list)
    ppe_required: list[str] = Field(default_factory=list)
    isolation_required: bool = False
    gas_test_required: bool = False
    gas_test_results: list[GasTestResult] = Field(default_factory=list)
    emergency_controls: list[str] = Field(default_factory=list)
    closure_notes: Optional[str] = None
    closed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class PermitCreate(PermitBase):
    pass


class PermitUpdate(BaseModel):
    permit_number: Optional[str] = Field(default=None, min_length=2, max_length=80)
    permit_type: Optional[PermitType] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    site_id: Optional[int] = None
    area_location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    requested_by_user_id: Optional[int] = None
    issued_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    assigned_team_or_contractor: Optional[str] = Field(default=None, max_length=255)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional[PermitStatus] = None
    risk_summary: Optional[str] = None
    precautions_required: Optional[list[str]] = None
    ppe_required: Optional[list[str]] = None
    isolation_required: Optional[bool] = None
    gas_test_required: Optional[bool] = None
    gas_test_results: Optional[list[GasTestResult]] = None
    emergency_controls: Optional[list[str]] = None
    closure_notes: Optional[str] = None
    closed_at: Optional[datetime] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class PermitRead(PermitBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermitListRead(PaginatedResponse[PermitRead]):
    pass
