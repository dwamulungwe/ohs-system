from typing import Optional
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class SafetyKPIRecord(TimestampMixin, Base):
    __tablename__ = "safety_kpi_records"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "period_start",
            "period_end",
            name="uq_safety_kpi_records_site_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    hours_worked: Mapped[float] = mapped_column(Float, nullable=False)
    reporting_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    employees_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contractors_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    created_by: Mapped[Optional["User"]] = relationship(lazy="selectin")
