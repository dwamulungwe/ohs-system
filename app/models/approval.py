from typing import Optional
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin


class ApprovalEntityType(str, enum.Enum):
    incident = "incident"
    hazard = "hazard"
    corrective_action = "corrective_action"
    permit = "permit"
    document_control = "document_control"


class ApprovalActionType(str, enum.Enum):
    incident_closure = "incident_closure"
    hazard_review = "hazard_review"
    corrective_action_verification = "corrective_action_verification"
    permit_approval = "permit_approval"
    document_approval = "document_approval"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class ApprovalWorkflow(TimestampMixin, Base):
    __tablename__ = "approval_workflows"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    entity_type: Mapped[ApprovalEntityType] = mapped_column(
        Enum(ApprovalEntityType),
        index=True,
        nullable=False,
    )

    entity_id: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
    )

    requested_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    assigned_approver_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    action_type: Mapped[ApprovalActionType] = mapped_column(
        Enum(ApprovalActionType),
        index=True,
        nullable=False,
    )

    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus),
        default=ApprovalStatus.pending,
        index=True,
        nullable=False,
    )

    request_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    decision_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    decided_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    requested_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[requested_by_user_id],
        lazy="selectin",
    )

    assigned_approver: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_approver_user_id],
        lazy="selectin",
    )

    decided_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[decided_by_user_id],
        lazy="selectin",
    )