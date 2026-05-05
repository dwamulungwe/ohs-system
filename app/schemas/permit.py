from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.permit import PermitStatus, PermitType
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class GasTestResult(BaseModel):
    test_name: str = Field(min_length=1, max_length=120)
    result: str = Field(min_length=1, max_length=120)
    tested_at: datetime | None = None
    tested_by: str | None = Field(default=None, max_length=120)


class PermitBase(BaseModel):
    permit_number: str = Field(min_length=2, max_length=80)
    permit_type: PermitType
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    site_id: int
    area_location: str = Field(min_length=2, max_length=255)
    requested_by_user_id: int
    issued_by_user_id: int | None = None
    approved_by_user_id: int | None = None
    assigned_team_or_contractor: str | None = Field(default=None, max_length=255)
    start_datetime: datetime
    end_datetime: datetime
    status: PermitStatus = PermitStatus.draft
    risk_summary: str | None = None
    precautions_required: list[str] = Field(default_factory=list)
    ppe_required: list[str] = Field(default_factory=list)
    isolation_required: bool = False
    gas_test_required: bool = False
    gas_test_results: list[GasTestResult] = Field(default_factory=list)
    emergency_controls: list[str] = Field(default_factory=list)
    closure_notes: str | None = None
    closed_at: datetime | None = None
    approved_at: datetime | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class PermitCreate(PermitBase):
    pass


class PermitUpdate(BaseModel):
    permit_number: str | None = Field(default=None, min_length=2, max_length=80)
    permit_type: PermitType | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=2)
    site_id: int | None = None
    area_location: str | None = Field(default=None, min_length=2, max_length=255)
    requested_by_user_id: int | None = None
    issued_by_user_id: int | None = None
    approved_by_user_id: int | None = None
    assigned_team_or_contractor: str | None = Field(default=None, max_length=255)
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: PermitStatus | None = None
    risk_summary: str | None = None
    precautions_required: list[str] | None = None
    ppe_required: list[str] | None = None
    isolation_required: bool | None = None
    gas_test_required: bool | None = None
    gas_test_results: list[GasTestResult] | None = None
    emergency_controls: list[str] | None = None
    closure_notes: str | None = None
    closed_at: datetime | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class PermitRead(PermitBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermitListRead(PaginatedResponse[PermitRead]):
    pass
