import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class LegalComplianceStatus(str, enum.Enum):
    compliant = "compliant"
    partial = "partial"
    non_compliant = "non_compliant"
    not_applicable = "not_applicable"
    pending_review = "pending_review"


class LegalComplianceItem(TimestampMixin, Base):
    __tablename__ = "legal_compliance_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    regulatory_body: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    requirement_summary: Mapped[str] = mapped_column(Text, nullable=False)
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    compliance_status: Mapped[LegalComplianceStatus] = mapped_column(
        Enum(LegalComplianceStatus),
        default=LegalComplianceStatus.pending_review,
        index=True,
        nullable=False,
    )
    review_frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site | None"] = relationship(lazy="selectin")
    owner: Mapped["User"] = relationship(lazy="selectin")
