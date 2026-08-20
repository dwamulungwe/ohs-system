from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class CorrectiveActionPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CorrectiveActionStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    assigned = "assigned"
    accepted = "accepted"
    in_progress = "in_progress"
    completion_requested = "completion_requested"
    pending_verification = "pending_verification"
    closed = "closed"
    declined = "declined"
    on_hold = "on_hold"
    cancelled = "cancelled"
    reopened = "reopened"
    # Legacy only: new workflow code always derives overdue and normalises this
    # old stored/API value back to an active lifecycle state.
    overdue = "overdue"


class CorrectiveActionSourceType(str, enum.Enum):
    manual = "manual"
    sio = "sio"
    incident = "incident"
    hazard = "hazard"
    inspection = "inspection"
    audit = "audit"
    permit = "permit"
    jsa = "jsa"
    training = "training"
    compliance = "compliance"
    contractor = "contractor"
    emergency_drill = "emergency_drill"
    document_control = "document_control"
    ppe = "ppe"
    occupational_health = "occupational_health"
    fleet = "fleet"
    environmental = "environmental"
    management_of_change = "management_of_change"


class ActionTaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ActionExtensionDecisionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ActionRecurrenceFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


ACTION_TERMINAL_STATUSES = {
    CorrectiveActionStatus.closed,
    CorrectiveActionStatus.cancelled,
}


class ActionReferenceSequence(OrganisationOwnedMixin, Base):
    __tablename__ = "action_reference_sequences"
    __table_args__ = (
        UniqueConstraint("organisation_id", "year", name="uq_action_sequences_org_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(index=True, nullable=False)
    last_value: Mapped[int] = mapped_column(default=0, nullable=False)


class CorrectiveAction(OrganisationOwnedMixin, TimestampMixin, Base):
    """The platform-wide HSE/compliance action aggregate.

    Existing table and attribute names remain available as synonyms so legacy
    corrective-action links and APIs continue to work.
    """

    __tablename__ = "corrective_actions"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "action_reference", name="uq_actions_org_action_reference"
        ),
        UniqueConstraint(
            "organisation_id", "recurrence_parent_action_id", name="uq_actions_org_recurrence_parent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Production migration enforces NOT NULL after backfill. nullable=True in
    # metadata keeps legacy direct-ORM import fixtures readable; all supported
    # creation paths allocate a reference before flush.
    action_reference: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    responsible_department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[CorrectiveActionSourceType] = mapped_column(
        Enum(CorrectiveActionSourceType),
        default=CorrectiveActionSourceType.manual,
        index=True,
        nullable=False,
    )
    source_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    source_metadata: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    priority: Mapped[CorrectiveActionPriority] = mapped_column(
        Enum(CorrectiveActionPriority),
        default=CorrectiveActionPriority.medium,
        index=True,
        nullable=False,
    )
    lifecycle_status: Mapped[CorrectiveActionStatus] = mapped_column(
        "status",
        Enum(CorrectiveActionStatus),
        default=CorrectiveActionStatus.open,
        index=True,
        nullable=False,
    )
    status = synonym("lifecycle_status")

    original_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    current_due_date: Mapped[Optional[date]] = mapped_column(
        "due_date", Date, index=True, nullable=True
    )
    due_date = synonym("current_due_date")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner_user_id: Mapped[Optional[int]] = mapped_column(
        "assigned_to_user_id",
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    assigned_to_user_id = synonym("owner_user_id")
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    verifier_user_id: Mapped[Optional[int]] = mapped_column(
        "verified_by_user_id",
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    verified_by_user_id = synonym("verifier_user_id")

    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    completion_notes: Mapped[Optional[str]] = mapped_column("closure_notes", Text, nullable=True)
    closure_notes = synonym("completion_notes")
    closure_evidence_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignment_decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopened_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    number_of_extensions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    automation_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    recurrence_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_frequency: Mapped[Optional[ActionRecurrenceFrequency]] = mapped_column(
        Enum(ActionRecurrenceFrequency, native_enum=False, length=40), nullable=True
    )
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    recurrence_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recurrence_parent_action_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("corrective_actions.id", ondelete="SET NULL"), index=True, nullable=True
    )

    site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    department: Mapped[Optional["Department"]] = relationship(
        foreign_keys=[department_id], lazy="selectin"
    )
    responsible_department: Mapped[Optional["Department"]] = relationship(
        foreign_keys=[responsible_department_id], lazy="selectin"
    )
    owner: Mapped[Optional["User"]] = relationship(foreign_keys=[owner_user_id], lazy="selectin")
    assigned_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_by_user_id], lazy="selectin"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id], lazy="selectin"
    )
    verifier: Mapped[Optional["User"]] = relationship(
        foreign_keys=[verifier_user_id], lazy="selectin"
    )
    completion_requested_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[completion_requested_by_user_id], lazy="selectin"
    )
    reopened_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reopened_by_user_id], lazy="selectin"
    )
    recurrence_parent: Mapped[Optional["CorrectiveAction"]] = relationship(
        remote_side="CorrectiveAction.id", foreign_keys=[recurrence_parent_action_id], lazy="selectin"
    )
    tasks: Mapped[list["ActionTask"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", order_by="ActionTask.created_at", lazy="selectin"
    )
    contributors: Mapped[list["ActionContributor"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", lazy="selectin"
    )
    assignment_history: Mapped[list["ActionAssignmentHistory"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", order_by="ActionAssignmentHistory.created_at", lazy="selectin"
    )
    extensions: Mapped[list["ActionExtensionRequest"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", order_by="ActionExtensionRequest.requested_at", lazy="selectin"
    )
    activities: Mapped[list["ActionActivity"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", order_by="ActionActivity.created_at", lazy="selectin"
    )
    comments: Mapped[list["ActionComment"]] = relationship(
        back_populates="action", cascade="all, delete-orphan", order_by="ActionComment.created_at", lazy="selectin"
    )

    @property
    def assigned_to(self):
        return self.owner

    @property
    def verified_by(self):
        return self.verifier

    @property
    def expected_outcome(self) -> Optional[str]:
        return self.acceptance_criteria

    @property
    def age_days(self) -> int:
        ended_on = (
            self.closed_at.date()
            if self.lifecycle_status == CorrectiveActionStatus.closed and self.closed_at
            else date.today()
        )
        return max(0, (ended_on - self.created_at.date()).days)

    @property
    def days_until_due(self) -> Optional[int]:
        return None if self.current_due_date is None else (self.current_due_date - date.today()).days

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.current_due_date
            and self.current_due_date < date.today()
            and self.lifecycle_status not in ACTION_TERMINAL_STATUSES | {CorrectiveActionStatus.draft}
        )

    @property
    def days_overdue(self) -> int:
        return abs(self.days_until_due or 0) if self.is_overdue else 0

    @property
    def awaiting_verification(self) -> bool:
        return self.lifecycle_status in {
            CorrectiveActionStatus.completion_requested,
            CorrectiveActionStatus.pending_verification,
        }

    @property
    def required_incomplete_tasks(self) -> list["ActionTask"]:
        return [task for task in self.tasks if task.is_required and task.status != ActionTaskStatus.completed]

    @property
    def site_name(self) -> Optional[str]:
        return self.site.name if self.site else None

    @property
    def department_name(self) -> Optional[str]:
        return self.department.name if self.department else None

    @property
    def responsible_department_name(self) -> Optional[str]:
        return self.responsible_department.name if self.responsible_department else None

    @property
    def owner_name(self) -> Optional[str]:
        return self.owner.full_name if self.owner else None

    @property
    def assigned_by_name(self) -> Optional[str]:
        return self.assigned_by.full_name if self.assigned_by else None

    @property
    def verifier_name(self) -> Optional[str]:
        return self.verifier.full_name if self.verifier else None

    @property
    def source_backlink(self) -> Optional[str]:
        configured = (self.source_metadata or {}).get("backlink")
        if configured:
            return str(configured)
        if self.source_id is None or self.source_type == CorrectiveActionSourceType.manual:
            return None
        routes = {
            CorrectiveActionSourceType.sio: "sios",
            CorrectiveActionSourceType.incident: "incidents",
            CorrectiveActionSourceType.hazard: "hazards",
            CorrectiveActionSourceType.inspection: "inspections",
            CorrectiveActionSourceType.audit: "audits",
            CorrectiveActionSourceType.permit: "permits",
            CorrectiveActionSourceType.jsa: "jsas",
            CorrectiveActionSourceType.training: "training",
            CorrectiveActionSourceType.compliance: "legal-compliance",
            CorrectiveActionSourceType.contractor: "contractors",
            CorrectiveActionSourceType.emergency_drill: "emergency-drills",
            CorrectiveActionSourceType.document_control: "documents",
            CorrectiveActionSourceType.ppe: "ppe",
            CorrectiveActionSourceType.occupational_health: "medical-surveillance",
        }
        route = routes.get(self.source_type)
        return f"/{route}/{self.source_id}" if route else None


class ActionContributor(OrganisationOwnedMixin, Base):
    __tablename__ = "action_contributors"
    __table_args__ = (UniqueConstraint("action_id", "user_id", name="uq_action_contributors_action_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    action: Mapped[CorrectiveAction] = relationship(back_populates="contributors")
    user: Mapped["User"] = relationship(lazy="selectin")

    @property
    def user_name(self) -> str:
        return self.user.full_name


class ActionAssignmentHistory(OrganisationOwnedMixin, Base):
    __tablename__ = "action_assignment_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    assignment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action: Mapped[CorrectiveAction] = relationship(back_populates="assignment_history")
    owner: Mapped[Optional["User"]] = relationship(foreign_keys=[owner_user_id], lazy="selectin")
    assigned_by: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_by_user_id], lazy="selectin")


class ActionTask(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "action_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    status: Mapped[ActionTaskStatus] = mapped_column(Enum(ActionTaskStatus, native_enum=False, length=40), default=ActionTaskStatus.open, index=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[CorrectiveAction] = relationship(back_populates="tasks")
    owner: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def owner_name(self) -> Optional[str]:
        return self.owner.full_name if self.owner else None


class ActionExtensionRequest(OrganisationOwnedMixin, Base):
    __tablename__ = "action_extension_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    previous_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    requested_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    extension_reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    decision_status: Mapped[ActionExtensionDecisionStatus] = mapped_column(Enum(ActionExtensionDecisionStatus, native_enum=False, length=40), default=ActionExtensionDecisionStatus.pending, index=True, nullable=False)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[CorrectiveAction] = relationship(back_populates="extensions")
    requested_by: Mapped[Optional["User"]] = relationship(foreign_keys=[requested_by_user_id], lazy="selectin")
    decided_by: Mapped[Optional["User"]] = relationship(foreign_keys=[decided_by_user_id], lazy="selectin")


class ActionActivity(OrganisationOwnedMixin, Base):
    __tablename__ = "action_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    action: Mapped[CorrectiveAction] = relationship(back_populates="activities")
    actor: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def actor_name(self) -> Optional[str]:
        return self.actor.full_name if self.actor else None


class ActionComment(OrganisationOwnedMixin, Base):
    __tablename__ = "action_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    author_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    action: Mapped[CorrectiveAction] = relationship(back_populates="comments")
    author: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def author_name(self) -> Optional[str]:
        return self.author.full_name if self.author else None


class ActionReminderDelivery(OrganisationOwnedMixin, Base):
    __tablename__ = "action_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint("action_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_action_reminder_delivery"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("corrective_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    milestone_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    due_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
