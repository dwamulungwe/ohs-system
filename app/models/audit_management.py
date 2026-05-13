from typing import Optional
import enum
from datetime import date

from sqlalchemy import JSON, Date, Enum, Float, ForeignKey, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class AuditType(str, enum.Enum):
    internal = "internal"
    external = "external"
    compliance = "compliance"


class AuditStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class AuditManagementRecord(TimestampMixin, Base):
    __tablename__ = "audit_management_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    audit_type: Mapped[AuditType] = mapped_column(
        Enum(AuditType),
        index=True,
        nullable=False,
    )
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    auditor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    audit_date: Mapped[date] = mapped_column(Date, nullable=False)
    findings: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    non_conformances: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    recommendations: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus),
        default=AuditStatus.open,
        index=True,
        nullable=False,
    )
    audit_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corrective_action_ids: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    auditor: Mapped["User"] = relationship(lazy="selectin")
