from typing import Optional
import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Float, Integer, JSON, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class TrainingType(str, enum.Enum):
    induction = "induction"
    toolbox_talk = "toolbox_talk"
    safety_training = "safety_training"
    equipment_training = "equipment_training"
    emergency_response = "emergency_response"
    compliance_training = "compliance_training"
    other = "other"


class TrainingStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"
    expired = "expired"
    cancelled = "cancelled"


class ComplianceAcknowledgementStatus(str, enum.Enum):
    assigned = "assigned"
    acknowledged = "acknowledged"
    overdue = "overdue"
    superseded = "superseded"


class TrainingRecord(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_courses.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    training_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[TrainingStatus] = mapped_column(Enum(TrainingStatus), default=TrainingStatus.assigned, index=True, nullable=False)
    certificate_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_user_id], lazy="selectin")
    assigned_by: Mapped["User"] = relationship(foreign_keys=[assigned_by_user_id], lazy="selectin")
    course: Mapped[Optional["TrainingCourse"]] = relationship(lazy="selectin")


class ComplianceAcknowledgement(OrganisationOwnedMixin, Base):
    __tablename__ = "compliance_acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ComplianceAcknowledgementStatus] = mapped_column(
        Enum(ComplianceAcknowledgementStatus),
        default=ComplianceAcknowledgementStatus.assigned,
        index=True,
        nullable=False,
    )
    document_control_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_control_records.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_user_id], lazy="selectin")
    assigned_by: Mapped["User"] = relationship(foreign_keys=[assigned_by_user_id], lazy="selectin")


class RequirementLevel(str, enum.Enum):
    mandatory = "mandatory"
    recommended = "recommended"


class AssignmentPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class AssignmentStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"
    overdue = "overdue"
    cancelled = "cancelled"


class TrainingSessionStatus(str, enum.Enum):
    planned = "planned"
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class DeliveryMode(str, enum.Enum):
    classroom = "classroom"
    practical = "practical"
    online = "online"
    toolbox = "toolbox"
    blended = "blended"


class AttendanceStatus(str, enum.Enum):
    invited = "invited"
    attended = "attended"
    absent = "absent"
    partially_attended = "partially_attended"
    excused = "excused"


class AssessmentType(str, enum.Enum):
    theory = "theory"
    practical = "practical"
    observation = "observation"
    oral = "oral"
    competency_check = "competency_check"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class CompetencyAwardStatus(str, enum.Enum):
    competent = "competent"
    conditionally_competent = "conditionally_competent"
    expired = "expired"
    suspended = "suspended"
    revoked = "revoked"
    pending_assessment = "pending_assessment"


class AuthorizationStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    expired = "expired"
    suspended = "suspended"
    revoked = "revoked"


class TrainingRequestStatus(str, enum.Enum):
    requested = "requested"
    reviewed = "reviewed"
    approved = "approved"
    assigned = "assigned"
    rejected = "rejected"


class EligibilityStatus(str, enum.Enum):
    eligible = "eligible"
    eligible_with_restrictions = "eligible_with_restrictions"
    not_eligible = "not_eligible"
    insufficient_data = "insufficient_data"


class TrainingCourse(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_courses"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_training_courses_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    training_type: Mapped[TrainingType] = mapped_column(Enum(TrainingType, native_enum=False, length=40), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    provider_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assessment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    passing_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    certificate_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_validity_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    refresher_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_refresher_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    practical_component_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_clearance_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_programme_codes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    ppe_prerequisite_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ppe_item_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    reminder_windows: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=lambda: [90, 60, 30, 7], nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Competency(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "competencies"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_competencies_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    evidence_requirements: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    assessment_rules: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    validity_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    renewal_rules: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    medical_prerequisite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_programme_codes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    ppe_prerequisite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ppe_item_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    supervisor_approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_experience_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CourseCompetencyMapping(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "course_competency_mappings"
    __table_args__ = (UniqueConstraint("organisation_id", "course_id", "competency_id", name="uq_course_competency_mapping"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id", ondelete="CASCADE"), index=True, nullable=False)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"), index=True, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    contribution_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_sufficient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    course: Mapped[TrainingCourse] = relationship(lazy="selectin")
    competency: Mapped[Competency] = relationship(lazy="selectin")


class TrainingRequirement(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_courses.id", ondelete="CASCADE"), index=True, nullable=True)
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"), index=True, nullable=True)
    authorization_type: Mapped[Optional[str]] = mapped_column(String(160), index=True, nullable=True)
    level: Mapped[RequirementLevel] = mapped_column(Enum(RequirementLevel, native_enum=False, length=20), default=RequirementLevel.mandatory, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True)
    task_activity: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    hazard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hazards.id", ondelete="SET NULL"), index=True, nullable=True)
    jsa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_safety_analyses.id", ondelete="SET NULL"), index=True, nullable=True)
    permit_type: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    equipment_category: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    contractor_category: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    ppe_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_items.id", ondelete="SET NULL"), index=True, nullable=True)
    medical_programme_codes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    mandatory_certificate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assessment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refresher_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    course: Mapped[Optional[TrainingCourse]] = relationship(lazy="selectin")
    competency: Mapped[Optional[Competency]] = relationship(lazy="selectin")


class ContractorWorker(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "contractor_workers"
    __table_args__ = (UniqueConstraint("organisation_id", "contractor_id", "external_reference", name="uq_contractor_worker_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id", ondelete="CASCADE"), index=True, nullable=False)
    external_reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    medical_clearance_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    medical_clearance_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ppe_compliant: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TrainingAssignment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    team: Mapped[Optional[str]] = mapped_column(String(160), index=True, nullable=True)
    contractor_group: Mapped[Optional[str]] = mapped_column(String(160), index=True, nullable=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    priority: Mapped[AssignmentPriority] = mapped_column(Enum(AssignmentPriority, native_enum=False, length=20), default=AssignmentPriority.normal, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False, index=True)
    requirement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_requirements.id", ondelete="SET NULL"), index=True, nullable=True)
    training_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_records.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(Enum(AssignmentStatus, native_enum=False, length=30), default=AssignmentStatus.assigned, nullable=False, index=True)
    refresher_for_assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_assignments.id", ondelete="SET NULL"), index=True, nullable=True)
    course: Mapped[TrainingCourse] = relationship(lazy="selectin")
    assigned_user: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_user_id], lazy="selectin")


class TrainingSession(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id", ondelete="RESTRICT"), index=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trainer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    delivery_mode: Mapped[DeliveryMode] = mapped_column(Enum(DeliveryMode, native_enum=False, length=30), nullable=False)
    status: Mapped[TrainingSessionStatus] = mapped_column(Enum(TrainingSessionStatus, native_enum=False, length=30), default=TrainingSessionStatus.planned, nullable=False, index=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    course: Mapped[TrainingCourse] = relationship(lazy="selectin")


class TrainingAttendance(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_attendance"
    __table_args__ = (
        UniqueConstraint("organisation_id", "session_id", "worker_user_id", name="uq_attendance_session_worker"),
        UniqueConstraint("organisation_id", "session_id", "contractor_worker_id", name="uq_attendance_session_contractor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_assignments.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus, native_enum=False, length=30), default=AttendanceStatus.invited, nullable=False, index=True)
    attendance_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attendance_recorded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    minutes_attended: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TrainingAssessment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    training_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_records.id", ondelete="SET NULL"), index=True, nullable=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_assignments.id", ondelete="SET NULL"), index=True, nullable=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_sessions.id", ondelete="SET NULL"), index=True, nullable=True)
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_courses.id", ondelete="SET NULL"), index=True, nullable=True)
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competencies.id", ondelete="SET NULL"), index=True, nullable=True)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    assessment_type: Mapped[AssessmentType] = mapped_column(Enum(AssessmentType, native_enum=False, length=30), nullable=False, index=True)
    assessor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    assessment_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    competency_demonstrated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    reassessment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reassessment_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)


class TrainingCertificate(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_certificates"
    __table_args__ = (UniqueConstraint("organisation_id", "certificate_number", name="uq_training_certificates_org_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_courses.id", ondelete="SET NULL"), index=True, nullable=True)
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competencies.id", ondelete="SET NULL"), index=True, nullable=True)
    training_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_records.id", ondelete="SET NULL"), index=True, nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    certificate_file_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus, native_enum=False, length=30), default=VerificationStatus.pending, nullable=False, index=True)
    verification_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verified_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_snapshot: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)


class CompetencyAward(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "competency_awards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="RESTRICT"), index=True, nullable=False)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    awarded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evidence: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    status: Mapped[CompetencyAwardStatus] = mapped_column(Enum(CompetencyAwardStatus, native_enum=False, length=40), default=CompetencyAwardStatus.pending_assessment, nullable=False, index=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements_snapshot: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    source_award_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competency_awards.id", ondelete="SET NULL"), index=True, nullable=True)
    competency: Mapped[Competency] = relationship(lazy="selectin")


class CompetencyStatusEvent(OrganisationOwnedMixin, Base):
    __tablename__ = "competency_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    competency_award_id: Mapped[int] = mapped_column(ForeignKey("competency_awards.id", ondelete="CASCADE"), index=True, nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class WorkAuthorization(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "work_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    authorization_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competencies.id", ondelete="SET NULL"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    task_activity: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    equipment_category: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    status: Mapped[AuthorizationStatus] = mapped_column(Enum(AuthorizationStatus, native_enum=False, length=30), default=AuthorizationStatus.pending, nullable=False, index=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    prerequisites_snapshot: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    restrictions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    supersedes_authorization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_authorizations.id", ondelete="SET NULL"), index=True, nullable=True)


class TrainingRequest(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id", ondelete="RESTRICT"), index=True, nullable=False)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    requested_for_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    contractor_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractor_workers.id", ondelete="CASCADE"), index=True, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[AssignmentPriority] = mapped_column(Enum(AssignmentPriority, native_enum=False, length=20), default=AssignmentPriority.normal, nullable=False)
    status: Mapped[TrainingRequestStatus] = mapped_column(Enum(TrainingRequestStatus, native_enum=False, length=30), default=TrainingRequestStatus.requested, nullable=False, index=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resulting_assignment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_assignments.id", ondelete="SET NULL"), index=True, nullable=True)


class TrainingReminderDelivery(OrganisationOwnedMixin, Base):
    __tablename__ = "training_reminder_deliveries"
    __table_args__ = (UniqueConstraint("organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_training_reminder_delivery"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    milestone_key: Mapped[str] = mapped_column(String(80), nullable=False)
    due_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TrainingDeficiencyLink(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "training_deficiency_links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    deficiency_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_entity_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    source_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    worker_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("competencies.id", ondelete="SET NULL"), index=True, nullable=True)
    training_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_records.id", ondelete="SET NULL"), index=True, nullable=True)
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=True)
    corrective_action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("corrective_actions.id", ondelete="SET NULL"), index=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
