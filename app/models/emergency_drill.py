import enum
from datetime import date

from sqlalchemy import JSON, Date, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class EmergencyDrillStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    overdue = "overdue"
    archived = "archived"


class EmergencyDrillRecord(TimestampMixin, Base):
    __tablename__ = "emergency_drills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    emergency_type: Mapped[str] = mapped_column(String(120), nullable=False)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    drill_date: Mapped[date] = mapped_column(Date, nullable=False)
    participants: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    attendance_records: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues_found: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    corrective_actions: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    next_drill_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EmergencyDrillStatus] = mapped_column(
        Enum(EmergencyDrillStatus),
        default=EmergencyDrillStatus.scheduled,
        index=True,
        nullable=False,
    )
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
