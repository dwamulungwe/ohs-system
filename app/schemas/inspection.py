from typing import Optional
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
    comment: Optional[str] = None
    linked_hazard_id: Optional[int] = None
    action_required: bool = False


class InspectionBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    inspection_type: str = Field(min_length=2, max_length=120)
    area_location: str = Field(min_length=2, max_length=255)
    inspector_user_id: int
    inspection_date: datetime
    notes: Optional[str] = None
    findings_summary: Optional[str] = None
    checklist_items: list[InspectionChecklistItem] = Field(default_factory=list)
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    linked_hazard_ids: list[int] = Field(default_factory=list)


class InspectionCreate(InspectionBase):
    status: InspectionStatus = InspectionStatus.draft
    overall_result: Optional[InspectionOverallResult] = None


class InspectionUpdate(BaseModel):
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    inspection_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    area_location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    inspector_user_id: Optional[int] = None
    inspection_date: Optional[datetime] = None
    status: Optional[InspectionStatus] = None
    notes: Optional[str] = None
    findings_summary: Optional[str] = None
    overall_result: Optional[InspectionOverallResult] = None
    checklist_items: Optional[list[InspectionChecklistItem]] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None
    linked_hazard_ids: Optional[list[int]] = None


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
