import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class JSAStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    expired = "expired"
    archived = "archived"


class ResidualRiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class JobSafetyAnalysis(TimestampMixin, Base):
    __tablename__ = "job_safety_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    department_or_area: Mapped[str] = mapped_column(String(200), nullable=False)
    job_steps: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    hazards: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    controls: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    ppe_required: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    residual_risk_level: Mapped[ResidualRiskLevel] = mapped_column(
        Enum(ResidualRiskLevel),
        default=ResidualRiskLevel.medium,
        nullable=False,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[JSAStatus] = mapped_column(
        Enum(JSAStatus),
        default=JSAStatus.draft,
        index=True,
        nullable=False,
    )
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    approved_by: Mapped["User | None"] = relationship(lazy="selectin")
