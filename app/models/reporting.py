from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class ReportingPeriodType(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    custom = "custom"


class ReportingPeriodStatus(str, enum.Enum):
    draft = "draft"
    under_review = "under_review"
    approved = "approved"
    locked = "locked"
    reopened = "reopened"


class KPIDirection(str, enum.Enum):
    higher_is_better = "higher_is_better"
    lower_is_better = "lower_is_better"
    target_range = "target_range"
    informational = "informational"


class KPISnapshotStatus(str, enum.Enum):
    good = "good"
    warning = "warning"
    critical = "critical"
    informational = "informational"
    insufficient_data = "insufficient_data"


class ReportingPeriod(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "reporting_periods"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "name", "period_type", "report_version",
            name="uq_reporting_period_org_name_type_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    period_type: Mapped[ReportingPeriodType] = mapped_column(
        Enum(ReportingPeriodType, native_enum=False, length=30), index=True, nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[ReportingPeriodStatus] = mapped_column(
        Enum(ReportingPeriodStatus, native_enum=False, length=30),
        default=ReportingPeriodStatus.draft,
        index=True,
        nullable=False,
    )
    prepared_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    report_reference: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    supersedes_period_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="SET NULL"), index=True, nullable=True
    )
    restatement_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prepared_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[prepared_by_user_id], lazy="selectin"
    )
    reviewed_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reviewed_by_user_id], lazy="selectin"
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[approved_by_user_id], lazy="selectin"
    )
    reopened_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reopened_by_user_id], lazy="selectin"
    )
    supersedes_period: Mapped[Optional["ReportingPeriod"]] = relationship(
        remote_side="ReportingPeriod.id", foreign_keys=[supersedes_period_id], lazy="selectin"
    )
    snapshots: Mapped[list["KPISnapshot"]] = relationship(
        back_populates="reporting_period", cascade="all, delete-orphan", lazy="selectin"
    )
    sections: Mapped[list["ReportSection"]] = relationship(
        back_populates="reporting_period", cascade="all, delete-orphan", lazy="selectin"
    )
    lifecycle_history: Mapped[list["ReportingPeriodHistory"]] = relationship(
        back_populates="reporting_period",
        cascade="all, delete-orphan",
        order_by="ReportingPeriodHistory.created_at",
        lazy="selectin",
    )
    management_actions: Mapped[list["ManagementActionPlanItem"]] = relationship(
        back_populates="reporting_period", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def prepared_by_name(self) -> Optional[str]:
        return self.prepared_by.full_name if self.prepared_by else None

    @property
    def reviewed_by_name(self) -> Optional[str]:
        return self.reviewed_by.full_name if self.reviewed_by else None

    @property
    def approved_by_name(self) -> Optional[str]:
        return self.approved_by.full_name if self.approved_by else None


class ReportingPeriodHistory(OrganisationOwnedMixin, Base):
    __tablename__ = "reporting_period_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    reporting_period: Mapped[ReportingPeriod] = relationship(back_populates="lifecycle_history")
    actor: Mapped[Optional["User"]] = relationship(lazy="selectin")


class KPIDefinition(TimestampMixin, Base):
    """A platform or organisation KPI definition.

    Platform catalogue records have a NULL organisation_id. Tenant-owned
    records are explicitly scoped by the reporting service because this model
    intentionally supports both ownership modes.
    """

    __tablename__ = "kpi_definitions"
    __table_args__ = (
        UniqueConstraint("organisation_id", "key", "version", name="uq_kpi_definition_scope_key_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organisation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    calculation_method: Mapped[str] = mapped_column(String(120), nullable=False)
    numerator_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    denominator_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    direction: Mapped[KPIDirection] = mapped_column(
        Enum(KPIDirection, native_enum=False, length=40), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)


class OrganisationKPISetting(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "organisation_kpi_settings"
    __table_args__ = (
        UniqueConstraint("organisation_id", "kpi_key", name="uq_org_kpi_setting_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kpi_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KPITarget(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "kpi_targets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kpi_definition_id: Mapped[int] = mapped_column(
        ForeignKey("kpi_definitions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    kpi_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True
    )
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    warning_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    kpi_definition: Mapped[KPIDefinition] = relationship(lazy="selectin")


class WorkforceExposure(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "workforce_exposures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True
    )
    period_start: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    employee_headcount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contractor_headcount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    employee_hours_worked: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contractor_hours_worked: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def total_hours_worked(self) -> Optional[float]:
        if self.employee_hours_worked is None or self.contractor_hours_worked is None:
            return None
        return self.employee_hours_worked + self.contractor_hours_worked


class KPISnapshot(OrganisationOwnedMixin, Base):
    __tablename__ = "kpi_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kpi_definition_id: Mapped[int] = mapped_column(
        ForeignKey("kpi_definitions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True
    )
    kpi_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    kpi_name: Mapped[str] = mapped_column(String(180), nullable=False)
    kpi_version: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    numerator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    denominator: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[KPISnapshotStatus] = mapped_column(
        Enum(KPISnapshotStatus, native_enum=False, length=30), index=True, nullable=False
    )
    calculation_metadata: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    reporting_period: Mapped[ReportingPeriod] = relationship(back_populates="snapshots")
    kpi_definition: Mapped[KPIDefinition] = relationship(lazy="selectin")


class ReportSection(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "report_sections"
    __table_args__ = (
        UniqueConstraint("reporting_period_id", "section_key", name="uq_report_section_period_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    content: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    reporting_period: Mapped[ReportingPeriod] = relationship(back_populates="sections")


class ManagementActionPlanItem(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "management_action_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    linked_action_id: Mapped[int] = mapped_column(
        ForeignKey("corrective_actions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    priority: Mapped[str] = mapped_column(String(30), nullable=False)
    issue_summary: Mapped[str] = mapped_column(Text, nullable=False)
    management_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reporting_period: Mapped[ReportingPeriod] = relationship(back_populates="management_actions")
    linked_action: Mapped["CorrectiveAction"] = relationship(lazy="selectin")


class ReportExport(OrganisationOwnedMixin, Base):
    __tablename__ = "report_exports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporting_period_id: Mapped[int] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"), index=True, nullable=False
    )
    export_format: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
