import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class PermitType(str, enum.Enum):
    hot_work = "hot_work"
    confined_space = "confined_space"
    electrical = "electrical"
    work_at_height = "work_at_height"
    excavation = "excavation"
    lifting = "lifting"
    maintenance = "maintenance"
    contractor = "contractor"


class PermitStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    active = "active"
    suspended = "suspended"
    expired = "expired"
    closed = "closed"
    cancelled = "cancelled"
    rejected = "rejected"


class PermitToWork(TimestampMixin, Base):
    __tablename__ = "permits_to_work"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    permit_number: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    permit_type: Mapped[PermitType] = mapped_column(Enum(PermitType), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    area_location: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    issued_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_team_or_contractor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[PermitStatus] = mapped_column(Enum(PermitStatus), default=PermitStatus.draft, index=True, nullable=False)
    risk_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    precautions_required: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    ppe_required: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    isolation_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    gas_test_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    gas_test_results: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    emergency_controls: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    closure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)

    site: Mapped["Site"] = relationship(lazy="selectin")
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_user_id], lazy="selectin")
    issued_by: Mapped["User | None"] = relationship(foreign_keys=[issued_by_user_id], lazy="selectin")
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id], lazy="selectin")
