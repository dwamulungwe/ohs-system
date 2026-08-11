from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class SIOObservationNature(str, enum.Enum):
    positive = "positive"
    negative = "negative"


class SIOStatus(str, enum.Enum):
    unassigned = "unassigned"
    assigned_to_responsible_person = "assigned_to_responsible_person"
    assigned_to_action_tracker = "assigned_to_action_tracker"
    complete = "complete"
    no_action_required = "no_action_required"
    open = "open"


class SIOUrgency(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"
    not_applicable = "not_applicable"


class SafetyImprovementObservation(TimestampMixin, Base):
    __tablename__ = "safety_improvement_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "external_reference_id",
            name="uq_sios_source_external_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    external_reference_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    observation_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    department: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
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
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    responsible_hs_officer_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    responsible_hs_officer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    urgency: Mapped[Optional[SIOUrgency]] = mapped_column(Enum(SIOUrgency), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    responsible_person_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    responsible_person_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    responsible_hs_officer: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_hs_officer_user_id], lazy="selectin"
    )
    responsible_person: Mapped[Optional["User"]] = relationship(
        foreign_keys=[responsible_person_user_id], lazy="selectin"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id], lazy="selectin"
    )
    linked_hazard: Mapped[Optional["Hazard"]] = relationship(lazy="selectin")
    linked_incident: Mapped[Optional["Incident"]] = relationship(lazy="selectin")
    linked_corrective_action: Mapped[Optional["CorrectiveAction"]] = relationship(lazy="selectin")
