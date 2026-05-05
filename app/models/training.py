import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin, utcnow


class TrainingType(str, enum.Enum):
    induction = "induction"
    toolbox_talk = "toolbox_talk"
    safety_training = "safety_training"
    equipment_training = "equipment_training"
    emergency_response = "emergency_response"
    compliance_training = "compliance_training"
    other = "other"


class TrainingStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"
    expired = "expired"
    cancelled = "cancelled"


class ComplianceAcknowledgementStatus(str, enum.Enum):
    assigned = "assigned"
    acknowledged = "acknowledged"
    overdue = "overdue"
    superseded = "superseded"


class TrainingRecord(TimestampMixin, Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    training_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType), index=True, nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TrainingStatus] = mapped_column(Enum(TrainingStatus), default=TrainingStatus.assigned, index=True, nullable=False)
    certificate_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site | None"] = relationship(lazy="selectin")
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_user_id], lazy="selectin")
    assigned_by: Mapped["User"] = relationship(foreign_keys=[assigned_by_user_id], lazy="selectin")


class ComplianceAcknowledgement(Base):
    __tablename__ = "compliance_acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ComplianceAcknowledgementStatus] = mapped_column(
        Enum(ComplianceAcknowledgementStatus),
        default=ComplianceAcknowledgementStatus.assigned,
        index=True,
        nullable=False,
    )
    document_control_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_control_records.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site | None"] = relationship(lazy="selectin")
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_user_id], lazy="selectin")
    assigned_by: Mapped["User"] = relationship(foreign_keys=[assigned_by_user_id], lazy="selectin")
