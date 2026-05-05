import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class AssetType(str, enum.Enum):
    equipment = "equipment"
    ppe = "ppe"
    emergency_equipment = "emergency_equipment"
    fire_extinguisher = "fire_extinguisher"
    first_aid_kit = "first_aid_kit"


class AssetConditionStatus(str, enum.Enum):
    good = "good"
    needs_attention = "needs_attention"
    defective = "defective"
    retired = "retired"


class AssetRegisterItem(TimestampMixin, Base):
    __tablename__ = "asset_register_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType), index=True, nullable=False)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_tag: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    inspection_frequency: Mapped[str] = mapped_column(String(120), nullable=False)
    next_inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    condition_status: Mapped[AssetConditionStatus] = mapped_column(
        Enum(AssetConditionStatus),
        default=AssetConditionStatus.good,
        index=True,
        nullable=False,
    )
    last_inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    assigned_to: Mapped["User | None"] = relationship(lazy="selectin")
