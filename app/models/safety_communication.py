import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class SafetyCommunicationType(str, enum.Enum):
    toolbox_talk = "toolbox_talk"
    safety_alert = "safety_alert"
    poster = "poster"
    signage = "signage"
    campaign = "campaign"


class SafetyCommunicationStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class SafetyCommunication(TimestampMixin, Base):
    __tablename__ = "safety_communications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    communication_type: Mapped[SafetyCommunicationType] = mapped_column(
        Enum(SafetyCommunicationType),
        index=True,
        nullable=False,
    )
    status: Mapped[SafetyCommunicationStatus] = mapped_column(
        Enum(SafetyCommunicationStatus),
        default=SafetyCommunicationStatus.draft,
        index=True,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requires_acknowledgement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    owner: Mapped["User | None"] = relationship(lazy="selectin")
