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
    investigation_lead_user_id: int | None = None
    investigation_team: list[str] = Field(default_factory=list)
    witness_statements: list[WitnessStatement] = Field(default_factory=list)
    immediate_causes: list[str] = Field(default_factory=list)
    underlying_causes: list[str] = Field(default_factory=list)
    root_cause: str | None = None
    five_whys: list[str] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    status: IncidentInvestigationStatus = IncidentInvestigationStatus.draft
    target_completion_date: date | None = None
    completed_at: datetime | None = None
    approved_by_user_id: int | None = None
    approved_at: datetime | None = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class IncidentInvestigationCreate(IncidentInvestigationBase):
    pass


class IncidentInvestigationUpdate(BaseModel):
    investigation_lead_user_id: int | None = None
    investigation_team: list[str] | None = None
    witness_statements: list[WitnessStatement] | None = None
    immediate_causes: list[str] | None = None
    underlying_causes: list[str] | None = None
    root_cause: str | None = None
    five_whys: list[str] | None = None
    contributing_factors: list[str] | None = None
    recommendations: list[str] | None = None
    status: IncidentInvestigationStatus | None = None
    target_completion_date: date | None = None
    completed_at: datetime | None = None
    approved_by_user_id: int | None = None
    approved_at: datetime | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class IncidentInvestigationRead(IncidentInvestigationBase):
    id: int
    site_id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentInvestigationListRead(PaginatedResponse[IncidentInvestigationRead]):
    pass
