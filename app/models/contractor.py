from typing import Optional
import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class ContractorOnboardingStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class ContractorInductionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    expired = "expired"


class ContractorComplianceDocumentsStatus(str, enum.Enum):
    incomplete = "incomplete"
    complete = "complete"
    expired = "expired"


class ContractorRecord(TimestampMixin, Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contractor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(80), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    work_scope: Mapped[str] = mapped_column(Text, nullable=False)
    onboarding_status: Mapped[ContractorOnboardingStatus] = mapped_column(
        Enum(ContractorOnboardingStatus),
        default=ContractorOnboardingStatus.pending,
        nullable=False,
    )
    induction_status: Mapped[ContractorInductionStatus] = mapped_column(
        Enum(ContractorInductionStatus),
        default=ContractorInductionStatus.pending,
        nullable=False,
    )
    insurance_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    compliance_documents_status: Mapped[ContractorComplianceDocumentsStatus] = mapped_column(
        Enum(ContractorComplianceDocumentsStatus),
        default=ContractorComplianceDocumentsStatus.incomplete,
        nullable=False,
    )
    approved_for_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    documents_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
