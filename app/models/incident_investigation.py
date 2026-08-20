from typing import Optional
import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin


class IncidentInvestigationStatus(str, enum.Enum):
    not_required = "not_required"
    assigned = "assigned"
    draft = "draft"
    in_progress = "in_progress"
    pending_review = "pending_review"
    completed = "completed"
    # Historical workflow values.
    pending_approval = "pending_approval"
    approved = "approved"
    closed = "closed"


class IncidentInvestigation(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_investigations"
    __table_args__ = (UniqueConstraint("incident_id", name="uq_incident_investigations_incident_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    investigation_lead_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    investigation_team: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    witness_statements: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    immediate_causes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    underlying_causes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    five_whys: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    contributing_factors: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    organisational_factors: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_reviewed: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    persons_interviewed: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    scene_inspection: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    documents_reviewed: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    equipment_involved: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    status: Mapped[IncidentInvestigationStatus] = mapped_column(
        Enum(IncidentInvestigationStatus),
        default=IncidentInvestigationStatus.draft,
        index=True,
        nullable=False,
    )
    target_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    investigation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    incident: Mapped["Incident"] = relationship(lazy="selectin")
    site: Mapped["Site"] = relationship(lazy="selectin")
    investigation_lead: Mapped[Optional["User"]] = relationship(
        foreign_keys=[investigation_lead_user_id],
        lazy="selectin",
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[approved_by_user_id],
        lazy="selectin",
    )
    assigned_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_by_user_id], lazy="selectin"
    )

    @property
    def due_date(self):
        return self.target_completion_date

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.target_completion_date
            and self.target_completion_date < date.today()
            and self.status not in {
                IncidentInvestigationStatus.not_required,
                IncidentInvestigationStatus.completed,
                IncidentInvestigationStatus.approved,
                IncidentInvestigationStatus.closed,
            }
        )
