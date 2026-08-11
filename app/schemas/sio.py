from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.sio import (
    SIOAssignmentStatus,
    SIOObservationNature,
    SIOStatus,
    SIOUrgency,
)
from app.schemas.common import PaginatedResponse


class SIOBase(BaseModel):
    external_reference_id: Optional[str] = Field(default=None, max_length=160)
    source_system: Optional[str] = Field(default=None, max_length=120)
    observation_date: Optional[date] = None
    department: str = Field(min_length=1, max_length=200)
    department_id: Optional[int] = None
    source_type: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=2)
    incident_classification: Optional[str] = Field(default=None, max_length=200)
    status: SIOStatus = SIOStatus.unassigned
    observation_nature: SIOObservationNature
    responsible_department: Optional[str] = Field(default=None, max_length=200)
    responsible_department_id: Optional[int] = None
    site_id: int
    responsible_hs_officer_user_id: Optional[int] = None
    responsible_hs_officer_name: Optional[str] = Field(default=None, max_length=255)
    urgency: Optional[SIOUrgency] = None
    category: Optional[str] = Field(default=None, max_length=255)
    responsible_person_user_id: Optional[int] = None
    responsible_person_name: Optional[str] = Field(default=None, max_length=255)
    responsible_user_id: Optional[int] = None
    due_date: Optional[date] = None
    property_damage: Optional[str] = Field(default=None, max_length=255)
    source_created_at: Optional[datetime] = None
    source_created_by: Optional[str] = Field(default=None, max_length=255)
    source_modified_by: Optional[str] = Field(default=None, max_length=255)
    source_path: Optional[str] = None
    legacy_metadata: Optional[dict] = None


class SIOCreate(SIOBase):
    pass


class SIOUpdate(BaseModel):
    observation_date: Optional[date] = None
    department: Optional[str] = Field(default=None, min_length=1, max_length=200)
    department_id: Optional[int] = None
    source_type: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    incident_classification: Optional[str] = Field(default=None, max_length=200)
    status: Optional[SIOStatus] = None
    observation_nature: Optional[SIOObservationNature] = None
    responsible_department: Optional[str] = Field(default=None, max_length=200)
    responsible_department_id: Optional[int] = None
    site_id: Optional[int] = None
    responsible_hs_officer_user_id: Optional[int] = None
    responsible_hs_officer_name: Optional[str] = Field(default=None, max_length=255)
    urgency: Optional[SIOUrgency] = None
    category: Optional[str] = Field(default=None, max_length=255)
    responsible_person_user_id: Optional[int] = None
    responsible_person_name: Optional[str] = Field(default=None, max_length=255)
    responsible_user_id: Optional[int] = None
    due_date: Optional[date] = None
    property_damage: Optional[str] = Field(default=None, max_length=255)


class SIORead(SIOBase):
    id: int
    organisation_id: int
    reference_number: str
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    assignment_status: SIOAssignmentStatus
    assignment_decline_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    investigation_required: bool
    investigator_user_id: Optional[int] = None
    investigation_started_at: Optional[datetime] = None
    investigation_completed_at: Optional[datetime] = None
    immediate_cause: Optional[str] = None
    underlying_cause: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: list = Field(default_factory=list)
    investigation_summary: Optional[str] = None
    lessons_learned: Optional[str] = None
    closure_requested_by_user_id: Optional[int] = None
    closure_requested_at: Optional[datetime] = None
    closure_notes: Optional[str] = None
    verified_by_user_id: Optional[int] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    no_action_reason: Optional[str] = None
    reopened_by_user_id: Optional[int] = None
    reopened_at: Optional[datetime] = None
    reopen_reason: Optional[str] = None
    age_days: int
    days_until_due: Optional[int] = None
    days_overdue: int
    is_overdue: bool
    created_by_user_id: Optional[int] = None
    linked_hazard_id: Optional[int] = None
    linked_incident_id: Optional[int] = None
    linked_corrective_action_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SIOListRead(PaginatedResponse[SIORead]):
    pass


class SIOEscalationOptions(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    due_date: Optional[date] = None


class SIOAssignmentRequest(BaseModel):
    responsible_user_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_responsibility(self):
        if self.responsible_user_id is None and self.responsible_department_id is None:
            raise ValueError("A responsible user or department is required")
        return self


class SIOAssignmentDecision(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class SIOTransitionRequest(BaseModel):
    status: SIOStatus
    reason: Optional[str] = Field(default=None, max_length=2000)


class SIOInvestigationUpdate(BaseModel):
    investigation_required: Optional[bool] = None
    investigator_user_id: Optional[int] = None
    investigation_started_at: Optional[datetime] = None
    investigation_completed_at: Optional[datetime] = None
    immediate_cause: Optional[str] = None
    underlying_cause: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: Optional[list] = None
    investigation_summary: Optional[str] = None
    lessons_learned: Optional[str] = None


class SIOCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class SIOCommentRead(BaseModel):
    id: int
    sio_id: int
    author_user_id: Optional[int] = None
    author_name: Optional[str] = None
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SIOActivityRead(BaseModel):
    id: int
    sio_id: int
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    event_type: str
    message: str
    event_metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SIOClosureRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=10000)


class SIOVerificationRequest(BaseModel):
    approved: bool = True
    notes: str = Field(min_length=1, max_length=10000)


class SIOReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=10000)


class SIOBulkRequest(BaseModel):
    sio_ids: list[int] = Field(min_length=1, max_length=500)
    operation: Literal["assign", "set_due_date", "transition"]
    responsible_user_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    due_date: Optional[date] = None
    status: Optional[SIOStatus] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class SIOBulkResult(BaseModel):
    updated_ids: list[int]
    count: int


class SIOBulkExportRequest(BaseModel):
    sio_ids: list[int] = Field(min_length=1, max_length=500)


class SIOAnalyticsRead(BaseModel):
    total_observations: int
    positive_observations: int
    negative_observations: int
    open_observations: int
    unassigned_observations: int
    in_progress_observations: int
    overdue_observations: int
    pending_verification_observations: int
    urgent_high_priority_observations: int
    closed_this_period: int
    average_closure_days: float
    observations_by_site: dict[str, int]
    observations_by_category: dict[str, int]
    observations_by_source: dict[str, int]
    observations_by_department: dict[str, int]
    observations_by_responsible_department: dict[str, int]
    observations_by_responsible_user: dict[str, int]
    observations_by_urgency: dict[str, int]
    observations_by_status: dict[str, int]
    observation_trend_by_month: dict[str, int]
    created_vs_closed_trend: dict[str, dict[str, int]]
    oldest_open_sios: list[dict]
    most_overdue_sios: list[dict]
    departments_with_highest_open_backlog: dict[str, int]
    responsible_users_with_overdue_sios: dict[str, int]
    recurring_categories: dict[str, int]
    # Compatibility fields retained for existing dashboard consumers.
    open_unassigned_observations: int
