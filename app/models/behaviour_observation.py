import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class BehaviourObservationType(str, enum.Enum):
    unsafe_act = "unsafe_act"
    positive_observation = "positive_observation"
    conduct_issue = "conduct_issue"
    event_safety_observation = "event_safety_observation"


class BehaviourObservationStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    actioned = "actioned"
    closed = "closed"


class BehaviourObservationSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class BehaviourObservation(TimestampMixin, Base):
    __tablename__ = "behaviour_observations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    observation_type: Mapped[BehaviourObservationType] = mapped_column(
        Enum(BehaviourObservationType),
        index=True,
        nullable=False,
    )
    status: Mapped[BehaviourObservationStatus] = mapped_column(
        Enum(BehaviourObservationStatus),
        default=BehaviourObservationStatus.open,
        index=True,
        nullable=False,
    )
    severity: Mapped[BehaviourObservationSeverity] = mapped_column(
        Enum(BehaviourObservationSeverity),
        default=BehaviourObservationSeverity.medium,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    person_involved_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    observed_by: Mapped["User | None"] = relationship(foreign_keys=[observed_by_user_id], lazy="selectin")
    closed_by: Mapped["User | None"] = relationship(foreign_keys=[closed_by_user_id], lazy="selectin")
