import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import utcnow


class AttachmentEntityType(str, enum.Enum):
    incident = "incident"
    hazard = "hazard"
    inspection = "inspection"
    corrective_action = "corrective_action"
    permit = "permit"
    training = "training"
    compliance_acknowledgement = "compliance_acknowledgement"
    safety_communication = "safety_communication"
    behaviour_observation = "behaviour_observation"
    incident_investigation = "incident_investigation"
    legal_compliance = "legal_compliance"
    jsa = "jsa"
    contractor = "contractor"
    asset_register = "asset_register"
    medical_surveillance = "medical_surveillance"
    emergency_drill = "emergency_drill"
    document_control = "document_control"
    audit_management = "audit_management"


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[AttachmentEntityType] = mapped_column(
        Enum(AttachmentEntityType),
        index=True,
        nullable=False,
    )
    entity_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    uploaded_by: Mapped["User | None"] = relationship(lazy="selectin")
