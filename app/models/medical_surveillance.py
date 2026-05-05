import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class MedicalSurveillanceStatus(str, enum.Enum):
    due = "due"
    completed = "completed"
    overdue = "overdue"


class MedicalClearanceStatus(str, enum.Enum):
    pending = "pending"
    cleared = "cleared"
    restricted = "restricted"
    not_cleared = "not_cleared"


class MedicalSurveillanceRecord(TimestampMixin, Base):
    __tablename__ = "medical_surveillance_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    surveillance_type: Mapped[str] = mapped_column(String(120), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MedicalSurveillanceStatus] = mapped_column(
        Enum(MedicalSurveillanceStatus),
        default=MedicalSurveillanceStatus.due,
        index=True,
        nullable=False,
    )
    results_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_clearance_status: Mapped[MedicalClearanceStatus] = mapped_column(
        Enum(MedicalClearanceStatus),
        default=MedicalClearanceStatus.pending,
        nullable=False,
    )
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    employee: Mapped["User"] = relationship(lazy="selectin")
    site: Mapped["Site | None"] = relationship(lazy="selectin")
