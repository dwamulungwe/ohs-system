import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Table, Column, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


inspection_linked_hazards = Table(
    "inspection_linked_hazards",
    Base.metadata,
    Column("inspection_id", ForeignKey("inspections.id", ondelete="CASCADE"), primary_key=True),
    Column("hazard_id", ForeignKey("hazards.id", ondelete="CASCADE"), primary_key=True),
)


class InspectionStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"
    archived = "archived"


class InspectionOverallResult(str, enum.Enum):
    compliant = "compliant"
    minor_non_conformance = "minor_non_conformance"
    major_non_conformance = "major_non_conformance"
    critical_non_conformance = "critical_non_conformance"


class Inspection(TimestampMixin, Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    area_location: Mapped[str] = mapped_column(String(255), nullable=False)
    inspection_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus),
        default=InspectionStatus.draft,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_result: Mapped[InspectionOverallResult] = mapped_column(Enum(InspectionOverallResult), nullable=False)
    number_of_non_conformities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    number_of_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checklist_items: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    inspector_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)

    site: Mapped["Site"] = relationship(lazy="selectin")
    inspector: Mapped["User"] = relationship(lazy="selectin")
    linked_hazards: Mapped[list["Hazard"]] = relationship(
        secondary=inspection_linked_hazards,
        lazy="selectin",
    )

    @property
    def linked_hazard_ids(self) -> list[int]:
        return [hazard.id for hazard in self.linked_hazards]
