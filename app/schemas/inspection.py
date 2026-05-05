import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.inspection import InspectionOverallResult, InspectionStatus
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class InspectionChecklistItemResult(str, enum.Enum):
    compliant = "compliant"
    non_compliant = "non_compliant"
    observation = "observation"
    not_applicable = "not_applicable"


class InspectionChecklistItem(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    result: InspectionChecklistItemResult
    comment: str | None = None
    linked_hazard_id: int | None = None
    action_required: bool = False


class InspectionBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    inspection_type: str = Field(min_length=2, max_length=120)
    area_location: str = Field(min_length=2, max_length=255)
    inspector_user_id: int
    inspection_date: datetime
    notes: str | None = None
    findings_summary: str | None = None
    checklist_items: list[InspectionChecklistItem] = Field(default_factory=list)
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    linked_hazard_ids: list[int] = Field(default_factory=list)


class InspectionCreate(InspectionBase):
    status: InspectionStatus = InspectionStatus.draft
    overall_result: InspectionOverallResult | None = None


class InspectionUpdate(BaseModel):
    site_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    inspection_type: str | None = Field(default=None, min_length=2, max_length=120)
    area_location: str | None = Field(default=None, min_length=2, max_length=255)
    inspector_user_id: int | None = None
    inspection_date: datetime | None = None
    status: InspectionStatus | None = None
    notes: str | None = None
    findings_summary: str | None = None
    overall_result: InspectionOverallResult | None = None
    checklist_items: list[InspectionChecklistItem] | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None
    linked_hazard_ids: list[int] | None = None


class InspectionRead(InspectionBase):
    id: int
    status: InspectionStatus
    overall_result: InspectionOverallResult
    number_of_non_conformities: int
    number_of_observations: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InspectionListRead(PaginatedResponse[InspectionRead]):
    pass
