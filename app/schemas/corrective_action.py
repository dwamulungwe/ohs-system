from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.corrective_action import (
    ActionExtensionDecisionStatus,
    ActionRecurrenceFrequency,
    ActionTaskStatus,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class CorrectiveActionBase(BaseModel):
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    acceptance_criteria: Optional[str] = Field(default=None, max_length=10000)
    expected_outcome: Optional[str] = Field(default=None, max_length=10000)
    source_type: CorrectiveActionSourceType = CorrectiveActionSourceType.manual
    source_id: Optional[int] = None
    source_metadata: dict = Field(default_factory=dict)
    priority: CorrectiveActionPriority = CorrectiveActionPriority.medium
    lifecycle_status: CorrectiveActionStatus = CorrectiveActionStatus.open
    # Legacy request/response field. lifecycle_status is authoritative.
    status: Optional[CorrectiveActionStatus] = None
    original_due_date: Optional[date] = None
    current_due_date: Optional[date] = None
    due_date: Optional[date] = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    progress_notes: Optional[str] = Field(default=None, max_length=10000)
    owner_user_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    verifier_user_id: Optional[int] = None
    verified_by_user_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    closure_notes: Optional[str] = None
    closure_evidence_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    verification_notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    recurrence_enabled: bool = False
    recurrence_frequency: Optional[ActionRecurrenceFrequency] = None
    recurrence_interval: int = Field(default=1, ge=1, le=365)
    next_due_date: Optional[date] = None
    recurrence_end_date: Optional[date] = None
    contributor_user_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def synchronise_compatibility_fields(self):
        fields = self.model_fields_set
        if "status" in fields and "lifecycle_status" not in fields and self.status is not None:
            self.lifecycle_status = self.status
        self.status = self.lifecycle_status

        if "due_date" in fields and "current_due_date" not in fields:
            self.current_due_date = self.due_date
        elif "current_due_date" in fields:
            self.due_date = self.current_due_date
        else:
            self.due_date = self.current_due_date
        if self.original_due_date is None:
            self.original_due_date = self.current_due_date

        if "assigned_to_user_id" in fields and "owner_user_id" not in fields:
            self.owner_user_id = self.assigned_to_user_id
        self.assigned_to_user_id = self.owner_user_id
        if "verified_by_user_id" in fields and "verifier_user_id" not in fields:
            self.verifier_user_id = self.verified_by_user_id
        self.verified_by_user_id = self.verifier_user_id
        if "closure_notes" in fields and "completion_notes" not in fields:
            self.completion_notes = self.closure_notes
        self.closure_notes = self.completion_notes
        if "expected_outcome" in fields and "acceptance_criteria" not in fields:
            self.acceptance_criteria = self.expected_outcome
        self.expected_outcome = self.acceptance_criteria

        return self


class CorrectiveActionCreate(CorrectiveActionBase):
    pass


class CorrectiveActionUpdate(BaseModel):
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    acceptance_criteria: Optional[str] = Field(default=None, max_length=10000)
    expected_outcome: Optional[str] = Field(default=None, max_length=10000)
    source_type: Optional[CorrectiveActionSourceType] = None
    source_id: Optional[int] = None
    source_metadata: Optional[dict] = None
    priority: Optional[CorrectiveActionPriority] = None
    lifecycle_status: Optional[CorrectiveActionStatus] = None
    status: Optional[CorrectiveActionStatus] = None
    current_due_date: Optional[date] = None
    due_date: Optional[date] = None
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)
    progress_notes: Optional[str] = Field(default=None, max_length=10000)
    owner_user_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    verifier_user_id: Optional[int] = None
    verified_by_user_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    closure_notes: Optional[str] = None
    closure_evidence_metadata: Optional[list[AttachmentMetadata]] = None
    verification_notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    recurrence_enabled: Optional[bool] = None
    recurrence_frequency: Optional[ActionRecurrenceFrequency] = None
    recurrence_interval: Optional[int] = Field(default=None, ge=1, le=365)
    next_due_date: Optional[date] = None
    recurrence_end_date: Optional[date] = None
    contributor_user_ids: Optional[list[int]] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def synchronise_alias_input(self):
        fields = self.model_fields_set
        if "status" in fields and "lifecycle_status" not in fields:
            self.lifecycle_status = self.status
        if "due_date" in fields and "current_due_date" not in fields:
            self.current_due_date = self.due_date
        if "assigned_to_user_id" in fields and "owner_user_id" not in fields:
            self.owner_user_id = self.assigned_to_user_id
        if "verified_by_user_id" in fields and "verifier_user_id" not in fields:
            self.verifier_user_id = self.verified_by_user_id
        if "closure_notes" in fields and "completion_notes" not in fields:
            self.completion_notes = self.closure_notes
        if "expected_outcome" in fields and "acceptance_criteria" not in fields:
            self.acceptance_criteria = self.expected_outcome
        return self


class ActionTaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: Optional[str] = None
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
    status: ActionTaskStatus = ActionTaskStatus.open
    is_required: bool = True
    notes: Optional[str] = Field(default=None, max_length=10000)


class ActionTaskCreate(ActionTaskBase):
    pass


class ActionTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    description: Optional[str] = None
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
    status: Optional[ActionTaskStatus] = None
    is_required: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=10000)


class ActionTaskRead(ActionTaskBase):
    id: int
    organisation_id: int
    action_id: int
    owner_name: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionContributorRead(BaseModel):
    id: int
    user_id: int
    user_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionAssignmentHistoryRead(BaseModel):
    id: int
    owner_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assignment_type: str
    reason: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ActionExtensionRead(BaseModel):
    id: int
    organisation_id: int
    action_id: int
    previous_due_date: Optional[date] = None
    requested_due_date: date
    extension_reason: str
    requested_by_user_id: Optional[int] = None
    requested_at: datetime
    decision_status: ActionExtensionDecisionStatus
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    decision_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionRead(CorrectiveActionBase):
    id: int
    organisation_id: int
    action_reference: str
    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completion_requested_at: Optional[datetime] = None
    completion_requested_by_user_id: Optional[int] = None
    closed_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    reopened_by_user_id: Optional[int] = None
    reopen_reason: Optional[str] = None
    assignment_decline_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    number_of_extensions: int = 0
    automation_suppressed: bool = False
    recurrence_parent_action_id: Optional[int] = None
    age_days: int
    days_until_due: Optional[int] = None
    is_overdue: bool
    days_overdue: int
    awaiting_verification: bool
    site_name: Optional[str] = None
    department_name: Optional[str] = None
    responsible_department_name: Optional[str] = None
    owner_name: Optional[str] = None
    assigned_by_name: Optional[str] = None
    verifier_name: Optional[str] = None
    source_backlink: Optional[str] = None
    tasks: list[ActionTaskRead] = Field(default_factory=list)
    contributors: list[ActionContributorRead] = Field(default_factory=list)
    assignment_history: list[ActionAssignmentHistoryRead] = Field(default_factory=list)
    extensions: list[ActionExtensionRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def legacy_overdue_display_status(self):
        # Old clients used status=overdue. The canonical lifecycle remains in
        # lifecycle_status and is never changed by this compatibility field.
        self.status = (
            CorrectiveActionStatus.overdue if self.is_overdue else self.lifecycle_status
        )
        return self

    model_config = ConfigDict(from_attributes=True)


class CorrectiveActionListRead(PaginatedResponse[CorrectiveActionRead]):
    pass


class ActionAssignmentRequest(BaseModel):
    owner_user_id: int
    responsible_department_id: Optional[int] = None
    verifier_user_id: Optional[int] = None
    current_due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class ActionAssignmentDecision(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class ActionTransitionRequest(BaseModel):
    lifecycle_status: CorrectiveActionStatus
    reason: Optional[str] = Field(default=None, max_length=10000)


class ActionProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)
    progress_notes: Optional[str] = Field(default=None, max_length=10000)


class ActionCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ActionCommentRead(BaseModel):
    id: int
    organisation_id: int
    action_id: int
    author_user_id: Optional[int] = None
    author_name: Optional[str] = None
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionActivityRead(BaseModel):
    id: int
    organisation_id: int
    action_id: int
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    event_type: str
    summary: str
    event_metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionCompletionRequest(BaseModel):
    completion_notes: str = Field(min_length=1, max_length=10000)


class ActionVerificationRequest(BaseModel):
    approved: bool = True
    notes: str = Field(min_length=1, max_length=10000)


class ActionReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=10000)


class ActionExtensionCreate(BaseModel):
    requested_due_date: date
    extension_reason: str = Field(min_length=1, max_length=10000)


class ActionExtensionDecision(BaseModel):
    approved: bool
    decision_notes: Optional[str] = Field(default=None, max_length=10000)


class ActionBulkRequest(BaseModel):
    action_ids: list[int] = Field(min_length=1, max_length=500)
    operation: Literal[
        "assign_owner",
        "assign_department",
        "change_priority",
        "set_due_date",
        "place_on_hold",
        "resume",
    ]
    owner_user_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    priority: Optional[CorrectiveActionPriority] = None
    current_due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class ActionBulkResult(BaseModel):
    updated_ids: list[int]
    count: int


class ActionBulkExportRequest(BaseModel):
    action_ids: list[int] = Field(min_length=1, max_length=500)


class ActionDashboardRead(BaseModel):
    open_actions: int
    overdue_actions: int
    overdue_rate: float
    due_this_week: int
    due_in_30_days: int
    critical_high_overdue: int
    awaiting_verification: int
    reopened_actions: int
    pending_extension_requests: int
    closed_this_period: int
    original_due_date_on_time_closure_rate: float
    current_due_date_on_time_closure_rate: float
    average_closure_days: float
    median_closure_days: float
    verification_rejection_rate: float
    multiple_extension_actions: int
    overdue_30_plus: int
    overdue_60_plus: int
    overdue_90_plus: int
    by_site: dict[str, int]
    by_department: dict[str, int]
    by_responsible_department: dict[str, int]
    by_owner: dict[str, int]
    by_manager: dict[str, int]
    by_source: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
    by_age_bucket: dict[str, int]
    oldest_open_actions: list[dict]
    most_overdue_actions: list[dict]
    repeated_extension_actions: list[dict]
    departments_with_highest_backlog: dict[str, int]
    owners_with_overdue_actions: dict[str, int]
    sources_generating_most_overdue_actions: dict[str, int]
