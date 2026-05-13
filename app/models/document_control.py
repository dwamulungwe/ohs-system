from typing import Optional
import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class DocumentType(str, enum.Enum):
    policy = "policy"
    sop = "sop"
    procedure = "procedure"
    form = "form"


class DocumentStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    expired = "expired"
    archived = "archived"


class DocumentControlRecord(TimestampMixin, Base):
    __tablename__ = "document_control_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType),
        index=True,
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        default=DocumentStatus.draft,
        index=True,
        nullable=False,
    )
    acknowledgement_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    acknowledgement_user_ids: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    supersedes_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_control_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    attachments_metadata: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id],
        lazy="selectin",
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[approved_by_user_id],
        lazy="selectin",
    )
    supersedes_document: Mapped[Optional["DocumentControlRecord"]] = relationship(
        remote_side="DocumentControlRecord.id",
        lazy="selectin",
    )
