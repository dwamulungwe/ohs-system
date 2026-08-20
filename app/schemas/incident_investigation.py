from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident_investigation import IncidentInvestigationStatus
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class WitnessStatement(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1)


class IncidentInvestigationBase(BaseModel):
    incident_id: int
    investigation_lead_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    investigation_team: list[str] = Field(default_factory=list)
    witness_statements: list[WitnessStatement] = Field(default_factory=list)
    immediate_causes: list[str] = Field(default_factory=list)
    underlying_causes: list[str] = Field(default_factory=list)
    root_cause: Optional[str] = None
    five_whys: list[str] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    organisational_factors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    scope: Optional[str] = None
    objectives: Optional[str] = None
    evidence_reviewed: list[dict] = Field(default_factory=list)
    persons_interviewed: list[dict] = Field(default_factory=list)
    scene_inspection: dict = Field(default_factory=dict)
    documents_reviewed: list[dict] = Field(default_factory=list)
    equipment_involved: list[dict] = Field(default_factory=list)
    status: IncidentInvestigationStatus = IncidentInvestigationStatus.draft
    target_completion_date: Optional[date] = None
    investigation_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class IncidentInvestigationCreate(IncidentInvestigationBase):
    pass


class IncidentInvestigationUpdate(BaseModel):
    investigation_lead_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    investigation_team: Optional[list[str]] = None
    witness_statements: Optional[list[WitnessStatement]] = None
    immediate_causes: Optional[list[str]] = None
    underlying_causes: Optional[list[str]] = None
    root_cause: Optional[str] = None
    five_whys: Optional[list[str]] = None
    contributing_factors: Optional[list[str]] = None
    organisational_factors: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    scope: Optional[str] = None
    objectives: Optional[str] = None
    evidence_reviewed: Optional[list[dict]] = None
    persons_interviewed: Optional[list[dict]] = None
    scene_inspection: Optional[dict] = None
    documents_reviewed: Optional[list[dict]] = None
    equipment_involved: Optional[list[dict]] = None
    status: Optional[IncidentInvestigationStatus] = None
    target_completion_date: Optional[date] = None
    investigation_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class IncidentInvestigationRead(IncidentInvestigationBase):
    id: int
    site_id: int
    due_date: Optional[date] = None
    is_overdue: bool = False
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentInvestigationListRead(PaginatedResponse[IncidentInvestigationRead]):
    pass
