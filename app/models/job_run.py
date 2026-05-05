import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.common import TimestampMixin, utcnow


class JobRunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failed = "failed"


class JobRun(TimestampMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[JobRunStatus] = mapped_column(
        Enum(JobRunStatus),
        default=JobRunStatus.running,
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
