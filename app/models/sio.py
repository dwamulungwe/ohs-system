from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class SIOObservationNature(str, enum.Enum):
    positive = "positive"
    negative = "negative"


class SIOStatus(str, enum.Enum):
    # Historical values remain valid so imported records are never silently rewritten.
    unassigned = "unassigned"
    assigned_to_responsible_person = "assigned_to_responsible_person"
    assigned_to_action_tracker = "assigned_to_action_tracker"
    complete = "complete"
    no_action_required = "no_action_required"
    open = "open"
    # Phase 1B operational workflow values.
    assigned = "assigned"
    in_progress = "in_progress"
    pending_verification = "pending_verification"
    closed = "closed"
    reopened = "reopened"


class SIOAssignmentStatus(str, enum.Enum):
    unassigned = "unassigned"
    assigned = "assigned"
    accepted = "accepted"
    declined = "declined"
    reassigned = "reassigned"


class SIOUrgency(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"
    not_applicable = "not_applicable"


SIO_TERMINAL_STATUSES = {
    SIOStatus.complete,
    SIOStatus.closed,
    SIOStatus.no_action_required,
}


class SIOReferenceSequence(OrganisationOwnedMixin, Base):
    __tablename__ = "sio_reference_sequences"
    __table_args__ = (
        UniqueConstraint("organisation_id", "year", name="uq_sio_sequences_org_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(index=True, nullable=False)
    last_value: Mapped[int] = mapped_column(default=0, nullable=False)


class SafetyImprovementObservation(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "safety_improvement_observations"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "source_system",
            "external_reference_id",
            name="uq_sios_source_external_reference",
        ),
        UniqueConstraint(
            "organisation_id", "reference_number", name="uq_sios_org_reference_number"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reference_number: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    external_reference_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    observation_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    department: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_classification: Mapped[Optional[str]] = mapped_column(String(200), index=True, nullable=True)
    status: Mapped[SIOStatus] = mapped_column(
        Enum(SIOStatus), default=SIOStatus.unassigned, index=True, nullable=False
    )
    observation_nature: Mapped[SIOObservationNature] = mapped_column(
        Enum(SIOObservationNature), index=True, nullable=False
    )
    responsible_department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    responsible_department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    responsible_hs_officer_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    responsible_hs_officer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    urgency: Mapped[Optional[SIOUrgency]] = mapped_column(Enum(SIOUrgency), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    # Kept for historical compatibility. New workflow code mirrors this to responsible_user_id.
    responsible_person_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    responsible_person_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsible_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_status: Mapped[SIOAssignmentStatus] = mapped_column(
        Enum(SIOAssignmentStatus, native_enum=False, length=40),
        default=SIOAssignmentStatus.unassigned,
        index=True,
        nullable=False,
    )
    assignment_decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    investigation_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    investigator_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    investigation_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    investigation_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    immediate_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    underlying_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contributing_factors: Mapped[list] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    investigation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    closure_requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    closure_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    no_action_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopened_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_damage: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_modified_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legacy_metadata: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    linked_hazard_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hazards.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    linked_incident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    linked_corrective_action_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("corrective_actions.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    originating_department: Mapped[Optional["Department"]] = relationship(
        foreign_keys=[department_id], lazy="selectin"
    )
    responsible_department_record: Mapped[Optional["Department"]] = relationship(
        foreign_keys=[responsible_department_id], lazy="selectin"
    )
    responsible_hs_officer: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_hs_officer_user_id], lazy="selectin"
    )
    responsible_person: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_person_user_id], lazy="selectin"
    )
    responsible_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_user_id], lazy="selectin"
    )
    assigned_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_by_user_id], lazy="selectin"
    )
    investigator: Mapped[Optional["User"]] = relationship(
        foreign_keys=[investigator_user_id], lazy="selectin"
    )
    closure_requested_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[closure_requested_by_user_id], lazy="selectin"
    )
    verified_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[verified_by_user_id], lazy="selectin"
    )
    reopened_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reopened_by_user_id], lazy="selectin"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id], lazy="selectin"
    )
    linked_hazard: Mapped[Optional["Hazard"]] = relationship(lazy="selectin")
    linked_incident: Mapped[Optional["Incident"]] = relationship(lazy="selectin")
    linked_corrective_action: Mapped[Optional["CorrectiveAction"]] = relationship(lazy="selectin")
    activities: Mapped[list["SIOActivity"]] = relationship(
        back_populates="sio", cascade="all, delete-orphan", order_by="SIOActivity.created_at"
    )
    comments: Mapped[list["SIOComment"]] = relationship(
        back_populates="sio", cascade="all, delete-orphan", order_by="SIOComment.created_at"
    )

    @property
    def site_name(self) -> Optional[str]:
        return self.site.name if self.site else None

    @property
    def age_days(self) -> int:
        started_on = (
            self.observation_date
            or (self.source_created_at.date() if self.source_created_at else None)
            or self.created_at.date()
        )
        ended_on = self.closed_at.date() if self.closed_at else date.today()
        return max(0, (ended_on - started_on).days)

    @property
    def days_until_due(self) -> Optional[int]:
        if self.due_date is None:
            return None
        return (self.due_date - date.today()).days

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue or self.days_until_due is None:
            return 0
        return abs(self.days_until_due)

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.due_date
            and self.due_date < date.today()
            and self.status not in SIO_TERMINAL_STATUSES
        )


class SIOActivity(OrganisationOwnedMixin, Base):
    __tablename__ = "sio_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sio_id: Mapped[int] = mapped_column(
        ForeignKey("safety_improvement_observations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    sio: Mapped[SafetyImprovementObservation] = relationship(back_populates="activities")
    actor: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def actor_name(self) -> Optional[str]:
        return self.actor.full_name if self.actor else None


class SIOComment(OrganisationOwnedMixin, Base):
    __tablename__ = "sio_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sio_id: Mapped[int] = mapped_column(
        ForeignKey("safety_improvement_observations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    sio: Mapped[SafetyImprovementObservation] = relationship(back_populates="comments")
    author: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def author_name(self) -> Optional[str]:
        return self.author.full_name if self.author else None
