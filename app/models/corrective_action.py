import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class CorrectiveActionPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CorrectiveActionStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    pending_verification = "pending_verification"
    closed = "closed"
    overdue = "overdue"
    cancelled = "cancelled"


class CorrectiveActionSourceType(str, enum.Enum):
    incident = "incident"
    hazard = "hazard"
    inspection = "inspection"
    manual = "manual"


class CorrectiveAction(TimestampMixin, Base):
    __tablename__ = "corrective_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[CorrectiveActionSourceType] = mapped_column(
        Enum(CorrectiveActionSourceType),
        default=CorrectiveActionSourceType.manual,
        nullable=False,
    )
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[CorrectiveActionPriority] = mapped_column(
        Enum(CorrectiveActionPriority),
        default=CorrectiveActionPriority.medium,
        nullable=False,
    )
    status: Mapped[CorrectiveActionStatus] = mapped_column(
        Enum(CorrectiveActionStatus),
        default=CorrectiveActionStatus.open,
        nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closure_evidence_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    verified_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    site: Mapped["Site"] = relationship(lazy="selectin")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_user_id], lazy="selectin")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id], lazy="selectin")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id], lazy="selectin")
