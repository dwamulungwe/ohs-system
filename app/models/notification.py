from typing import Optional
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, utcnow


class NotificationType(str, enum.Enum):
    sio_assigned = "sio_assigned"
    sio_reassigned = "sio_reassigned"
    sio_assignment_declined = "sio_assignment_declined"
    sio_due_soon = "sio_due_soon"
    sio_overdue = "sio_overdue"
    sio_closure_requested = "sio_closure_requested"
    sio_verification_required = "sio_verification_required"
    sio_reopened = "sio_reopened"
    sio_urgent_high = "sio_urgent_high"
    corrective_action_due_soon = "corrective_action_due_soon"
    corrective_action_overdue = "corrective_action_overdue"
    action_assigned = "action_assigned"
    action_reassigned = "action_reassigned"
    action_declined = "action_declined"
    action_due_soon = "action_due_soon"
    action_overdue = "action_overdue"
    action_escalation = "action_escalation"
    action_extension_requested = "action_extension_requested"
    action_extension_approved = "action_extension_approved"
    action_extension_rejected = "action_extension_rejected"
    action_completion_requested = "action_completion_requested"
    action_verification_requested = "action_verification_requested"
    action_verification_rejected = "action_verification_rejected"
    action_closed = "action_closed"
    action_reopened = "action_reopened"
    action_recurring_generated = "action_recurring_generated"
    critical_hazard_created = "critical_hazard_created"
    critical_incident_created = "critical_incident_created"
    inspection_assigned = "inspection_assigned"
    inspection_due_soon = "inspection_due_soon"
    action_pending_verification = "action_pending_verification"
    training_overdue = "training_overdue"
    training_expired = "training_expired"
    compliance_acknowledgement_overdue = "compliance_acknowledgement_overdue"
    permit_pending_approval = "permit_pending_approval"
    permit_nearing_expiry = "permit_nearing_expiry"
    permit_expired = "permit_expired"
    approval_requested = "approval_requested"
    approval_approved = "approval_approved"
    approval_rejected = "approval_rejected"
    investigation_pending_approval = "investigation_pending_approval"
    investigation_approved = "investigation_approved"
    investigator_assigned = "investigator_assigned"
    investigation_due = "investigation_due"
    investigation_overdue = "investigation_overdue"
    regulator_notification_due = "regulator_notification_due"
    regulator_notification_overdue = "regulator_notification_overdue"
    incident_closure_requested = "incident_closure_requested"
    incident_closure_verification = "incident_closure_verification"
    incident_closure_rejected = "incident_closure_rejected"
    incident_closed = "incident_closed"
    incident_reopened = "incident_reopened"
    return_to_work_review_due = "return_to_work_review_due"
    legal_compliance_due_soon = "legal_compliance_due_soon"
    legal_compliance_overdue = "legal_compliance_overdue"
    jsa_pending_approval = "jsa_pending_approval"
    jsa_review_due_soon = "jsa_review_due_soon"
    jsa_review_overdue = "jsa_review_overdue"
    contractor_insurance_due_soon = "contractor_insurance_due_soon"
    contractor_insurance_overdue = "contractor_insurance_overdue"
    contractor_documents_due_soon = "contractor_documents_due_soon"
    contractor_documents_overdue = "contractor_documents_overdue"
    asset_inspection_due_soon = "asset_inspection_due_soon"
    asset_inspection_overdue = "asset_inspection_overdue"
    asset_defective = "asset_defective"
    medical_surveillance_due_soon = "medical_surveillance_due_soon"
    medical_surveillance_overdue = "medical_surveillance_overdue"
    emergency_drill_due_soon = "emergency_drill_due_soon"
    emergency_drill_overdue = "emergency_drill_overdue"
    document_pending_approval = "document_pending_approval"
    document_due_soon = "document_due_soon"
    document_expired = "document_expired"
    audit_open = "audit_open"
    ppe_request_submitted = "ppe_request_submitted"
    ppe_request_approved = "ppe_request_approved"
    ppe_request_rejected = "ppe_request_rejected"
    ppe_issued = "ppe_issued"
    ppe_replacement_due = "ppe_replacement_due"
    ppe_replacement_overdue = "ppe_replacement_overdue"
    ppe_inspection_due = "ppe_inspection_due"
    ppe_inspection_overdue = "ppe_inspection_overdue"
    ppe_expiring = "ppe_expiring"
    ppe_low_stock = "ppe_low_stock"
    ppe_critical_failure = "ppe_critical_failure"
    ppe_loss_damage_review = "ppe_loss_damage_review"


class NotificationSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class RelatedEntityType(str, enum.Enum):
    sio = "sio"
    incident = "incident"
    hazard = "hazard"
    inspection = "inspection"
    corrective_action = "corrective_action"
    training_record = "training_record"
    compliance_acknowledgement = "compliance_acknowledgement"
    permit = "permit"
    incident_investigation = "incident_investigation"
    legal_compliance = "legal_compliance"
    jsa = "jsa"
    contractor = "contractor"
    asset_register = "asset_register"
    medical_surveillance = "medical_surveillance"
    emergency_drill = "emergency_drill"
    document_control = "document_control"
    audit_management = "audit_management"
    ppe_item = "ppe_item"
    ppe_issue = "ppe_issue"
    ppe_request = "ppe_request"
    ppe_inspection = "ppe_inspection"
    ppe_loss_damage = "ppe_loss_damage"


class Notification(OrganisationOwnedMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), index=True, nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(Enum(NotificationSeverity), index=True, nullable=False)
    related_entity_type: Mapped[RelatedEntityType] = mapped_column(Enum(RelatedEntityType), index=True, nullable=False)
    related_entity_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    recipient: Mapped["User"] = relationship(lazy="selectin")
