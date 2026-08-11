from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin


class ImportJobStatus(str, enum.Enum):
    previewed = "previewed"
    processing = "processing"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class ImportRowStatus(str, enum.Enum):
    valid = "valid"
    unresolved_site = "unresolved_site"
    duplicate = "duplicate"
    invalid = "invalid"
    imported = "imported"
    failed = "failed"


class DataImportJob(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "data_import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    importer_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus), default=ImportJobStatus.previewed, index=True, nullable=False
    )
    is_dry_run: Mapped[bool] = mapped_column(default=True, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    successful_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    validation_messages: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    report: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    created_by: Mapped[Optional["User"]] = relationship(lazy="selectin")
    rows: Mapped[list["DataImportRow"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )


class DataImportRow(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "data_import_rows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("data_import_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    external_reference_id: Mapped[Optional[str]] = mapped_column(String(160), index=True, nullable=True)
    source_site_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    resolved_site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[ImportRowStatus] = mapped_column(Enum(ImportRowStatus), index=True, nullable=False)
    raw_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    normalized_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    messages: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON), default=list, nullable=False
    )
    imported_sio_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("safety_improvement_observations.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped[DataImportJob] = relationship(back_populates="rows")
    resolved_site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    imported_sio: Mapped[Optional["SafetyImprovementObservation"]] = relationship(lazy="selectin")
