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
    investigation_team: list[str] = Field(default_factory=list)
    witness_statements: list[WitnessStatement] = Field(default_factory=list)
    immediate_causes: list[str] = Field(default_factory=list)
    underlying_causes: list[str] = Field(default_factory=list)
    root_cause: Optional[str] = None
    five_whys: list[str] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    status: IncidentInvestigationStatus = IncidentInvestigationStatus.draft
    target_completion_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class IncidentInvestigationCreate(IncidentInvestigationBase):
    pass


class IncidentInvestigationUpdate(BaseModel):
    investigation_lead_user_id: Optional[int] = None
    investigation_team: Optional[list[str]] = None
    witness_statements: Optional[list[WitnessStatement]] = None
    immediate_causes: Optional[list[str]] = None
    underlying_causes: Optional[list[str]] = None
    root_cause: Optional[str] = None
    five_whys: Optional[list[str]] = None
    contributing_factors: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    status: Optional[IncidentInvestigationStatus] = None
    target_completion_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class IncidentInvestigationRead(IncidentInvestigationBase):
    id: int
    site_id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentInvestigationListRead(PaginatedResponse[IncidentInvestigationRead]):
    pass
