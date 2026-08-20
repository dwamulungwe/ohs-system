from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentRead
from app.models.training import ComplianceAcknowledgementStatus, TrainingStatus, TrainingType
from app.models.training import (
    AssignmentPriority,
    AssignmentStatus,
    AssessmentType,
    AttendanceStatus,
    AuthorizationStatus,
    CompetencyAwardStatus,
    DeliveryMode,
    RequirementLevel,
    TrainingRequestStatus,
    TrainingSessionStatus,
    VerificationStatus,
)
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class TrainingRecordBase(BaseModel):
    course_id: Optional[int] = None
    title: str = Field(min_length=2, max_length=200)
    training_type: TrainingType
    site_id: Optional[int] = None
    assigned_to_user_id: int
    assigned_by_user_id: Optional[int] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: TrainingStatus = TrainingStatus.assigned
    certificate_metadata: list[AttachmentMetadata] = Field(default_factory=list)
    notes: Optional[str] = None


class TrainingRecordCreate(TrainingRecordBase):
    pass


class TrainingRecordUpdate(BaseModel):
    course_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    training_type: Optional[TrainingType] = None
    site_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    expiry_date: Optional[date] = None
    status: Optional[TrainingStatus] = None
    certificate_metadata: Optional[list[AttachmentMetadata]] = None
    notes: Optional[str] = None


class TrainingRecordRead(TrainingRecordBase):
    id: int
    assigned_by_user_id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingRecordListRead(PaginatedResponse[TrainingRecordRead]):
    pass


class ComplianceAcknowledgementBase(BaseModel):
    document_title: str = Field(min_length=2, max_length=200)
    document_type: str = Field(min_length=2, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    site_id: Optional[int] = None
    document_control_id: Optional[int] = None
    assigned_to_user_id: int
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    status: ComplianceAcknowledgementStatus = ComplianceAcknowledgementStatus.assigned
    notes: Optional[str] = None


class ComplianceAcknowledgementCreate(ComplianceAcknowledgementBase):
    pass


class ComplianceAcknowledgementUpdate(BaseModel):
    document_title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    document_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    version: Optional[str] = Field(default=None, min_length=1, max_length=80)
    site_id: Optional[int] = None
    document_control_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    assigned_by_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    status: Optional[ComplianceAcknowledgementStatus] = None
    notes: Optional[str] = None


class ComplianceAcknowledgementRead(ComplianceAcknowledgementBase):
    id: int
    assigned_by_user_id: int
    assigned_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ComplianceAcknowledgementListRead(PaginatedResponse[ComplianceAcknowledgementRead]):
    pass


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TrainingCourseBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=80)
    description: Optional[str] = None
    category: str = Field(min_length=2, max_length=120)
    training_type: TrainingType
    active: bool = True
    provider_required: bool = False
    assessment_required: bool = False
    passing_score: Optional[float] = Field(default=None, ge=0, le=100)
    certificate_required: bool = False
    default_validity_period_days: Optional[int] = Field(default=None, gt=0)
    refresher_required: bool = False
    default_refresher_interval_days: Optional[int] = Field(default=None, gt=0)
    practical_component_required: bool = False
    medical_clearance_required: bool = False
    medical_programme_codes: list[str] = Field(default_factory=list)
    ppe_prerequisite_required: bool = False
    ppe_item_ids: list[int] = Field(default_factory=list)
    reminder_windows: list[int] = Field(default_factory=lambda: [90, 60, 30, 7])


class TrainingCourseCreate(TrainingCourseBase):
    pass


class TrainingCourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    code: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = None
    category: Optional[str] = None
    training_type: Optional[TrainingType] = None
    active: Optional[bool] = None
    provider_required: Optional[bool] = None
    assessment_required: Optional[bool] = None
    passing_score: Optional[float] = Field(default=None, ge=0, le=100)
    certificate_required: Optional[bool] = None
    default_validity_period_days: Optional[int] = Field(default=None, gt=0)
    refresher_required: Optional[bool] = None
    default_refresher_interval_days: Optional[int] = Field(default=None, gt=0)
    practical_component_required: Optional[bool] = None
    medical_clearance_required: Optional[bool] = None
    medical_programme_codes: Optional[list[str]] = None
    ppe_prerequisite_required: Optional[bool] = None
    ppe_item_ids: Optional[list[int]] = None
    reminder_windows: Optional[list[int]] = None


class TrainingCourseRead(TrainingCourseBase, ORMModel):
    id: int
    organisation_id: int
    is_system: bool = False
    created_at: datetime
    updated_at: datetime


class CompetencyBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=80)
    description: Optional[str] = None
    category: str = Field(min_length=2, max_length=120)
    active: bool = True
    evidence_requirements: list[str] = Field(default_factory=list)
    assessment_rules: dict = Field(default_factory=dict)
    validity_period_days: Optional[int] = Field(default=None, gt=0)
    renewal_rules: dict = Field(default_factory=dict)
    medical_prerequisite: bool = False
    medical_programme_codes: list[str] = Field(default_factory=list)
    ppe_prerequisite: bool = False
    ppe_item_ids: list[int] = Field(default_factory=list)
    supervisor_approval_required: bool = False
    minimum_experience_days: Optional[int] = Field(default=None, ge=0)


class CompetencyCreate(CompetencyBase):
    pass


class CompetencyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    code: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None
    evidence_requirements: Optional[list[str]] = None
    assessment_rules: Optional[dict] = None
    validity_period_days: Optional[int] = Field(default=None, gt=0)
    renewal_rules: Optional[dict] = None
    medical_prerequisite: Optional[bool] = None
    medical_programme_codes: Optional[list[str]] = None
    ppe_prerequisite: Optional[bool] = None
    ppe_item_ids: Optional[list[int]] = None
    supervisor_approval_required: Optional[bool] = None
    minimum_experience_days: Optional[int] = Field(default=None, ge=0)


class CompetencyRead(CompetencyBase, ORMModel):
    id: int
    organisation_id: int
    is_system: bool = False
    created_at: datetime
    updated_at: datetime


class CourseCompetencyMappingCreate(BaseModel):
    course_id: int
    competency_id: int
    required: bool = True
    contribution_weight: Optional[float] = Field(default=None, ge=0)
    completion_sufficient: bool = False
    sequence: int = Field(default=0, ge=0)


class CourseCompetencyMappingRead(CourseCompetencyMappingCreate, ORMModel):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class TrainingRequirementBase(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    course_id: Optional[int] = None
    competency_id: Optional[int] = None
    authorization_type: Optional[str] = Field(default=None, max_length=160)
    level: RequirementLevel = RequirementLevel.mandatory
    active: bool = True
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    task_activity: Optional[str] = None
    hazard_id: Optional[int] = None
    jsa_id: Optional[int] = None
    permit_type: Optional[str] = None
    equipment_category: Optional[str] = None
    contractor_category: Optional[str] = None
    ppe_item_id: Optional[int] = None
    medical_programme_codes: list[str] = Field(default_factory=list)
    mandatory_certificate: bool = False
    assessment_required: bool = False
    refresher_interval_days: Optional[int] = Field(default=None, gt=0)
    rationale: Optional[str] = None
    is_critical: bool = False


class TrainingRequirementCreate(TrainingRequirementBase):
    pass


class TrainingRequirementUpdate(BaseModel):
    name: Optional[str] = None
    course_id: Optional[int] = None
    competency_id: Optional[int] = None
    authorization_type: Optional[str] = None
    level: Optional[RequirementLevel] = None
    active: Optional[bool] = None
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    task_activity: Optional[str] = None
    hazard_id: Optional[int] = None
    jsa_id: Optional[int] = None
    permit_type: Optional[str] = None
    equipment_category: Optional[str] = None
    contractor_category: Optional[str] = None
    ppe_item_id: Optional[int] = None
    medical_programme_codes: Optional[list[str]] = None
    mandatory_certificate: Optional[bool] = None
    assessment_required: Optional[bool] = None
    refresher_interval_days: Optional[int] = Field(default=None, gt=0)
    rationale: Optional[str] = None
    is_critical: Optional[bool] = None


class TrainingRequirementRead(TrainingRequirementBase, ORMModel):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class ContractorWorkerCreate(BaseModel):
    contractor_id: int
    external_reference: str = Field(min_length=1, max_length=120)
    full_name: str = Field(min_length=2, max_length=200)
    email: Optional[str] = None
    job_title: Optional[str] = None
    category: Optional[str] = None
    site_id: Optional[int] = None
    active: bool = True
    medical_clearance_status: Optional[str] = None
    medical_clearance_expiry: Optional[date] = None
    ppe_compliant: Optional[bool] = None
    notes: Optional[str] = None


class ContractorWorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    job_title: Optional[str] = None
    category: Optional[str] = None
    site_id: Optional[int] = None
    active: Optional[bool] = None
    medical_clearance_status: Optional[str] = None
    medical_clearance_expiry: Optional[date] = None
    ppe_compliant: Optional[bool] = None
    notes: Optional[str] = None


class ContractorWorkerRead(ContractorWorkerCreate, ORMModel):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class TrainingAssignmentCreate(BaseModel):
    course_id: int
    assigned_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    team: Optional[str] = None
    contractor_group: Optional[str] = None
    due_date: Optional[date] = None
    priority: AssignmentPriority = AssignmentPriority.normal
    mandatory: bool = True
    reason: Optional[str] = None
    source: str = "manual"
    requirement_id: Optional[int] = None
    refresher_for_assignment_id: Optional[int] = None


class BulkTrainingAssignmentCreate(BaseModel):
    course_id: int
    user_ids: list[int] = Field(default_factory=list)
    contractor_worker_ids: list[int] = Field(default_factory=list)
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    due_date: Optional[date] = None
    priority: AssignmentPriority = AssignmentPriority.normal
    mandatory: bool = True
    reason: Optional[str] = None
    source: str = "bulk"
    requirement_id: Optional[int] = None


class TrainingAssignmentUpdate(BaseModel):
    due_date: Optional[date] = None
    priority: Optional[AssignmentPriority] = None
    mandatory: Optional[bool] = None
    reason: Optional[str] = None
    status: Optional[AssignmentStatus] = None


class TrainingAssignmentRead(TrainingAssignmentCreate, ORMModel):
    id: int
    organisation_id: int
    assigned_by_user_id: Optional[int] = None
    assigned_at: datetime
    training_record_id: Optional[int] = None
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime


class TrainingSessionCreate(BaseModel):
    course_id: int
    starts_at: datetime
    ends_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    trainer_user_id: Optional[int] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = Field(default=None, gt=0)
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    delivery_mode: DeliveryMode
    status: TrainingSessionStatus = TrainingSessionStatus.planned
    attachments_metadata: list[dict] = Field(default_factory=list)
    notes: Optional[str] = None


class TrainingSessionUpdate(BaseModel):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    trainer_user_id: Optional[int] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = Field(default=None, gt=0)
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    delivery_mode: Optional[DeliveryMode] = None
    status: Optional[TrainingSessionStatus] = None
    attachments_metadata: Optional[list[dict]] = None
    notes: Optional[str] = None


class TrainingSessionRead(TrainingSessionCreate, ORMModel):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class TrainingAttendanceCreate(BaseModel):
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    assignment_id: Optional[int] = None
    status: AttendanceStatus = AttendanceStatus.invited
    minutes_attended: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class TrainingAttendanceRead(TrainingAttendanceCreate, ORMModel):
    id: int
    organisation_id: int
    session_id: int
    attendance_recorded_at: Optional[datetime] = None
    attendance_recorded_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class TrainingAssessmentCreate(BaseModel):
    training_record_id: Optional[int] = None
    assignment_id: Optional[int] = None
    session_id: Optional[int] = None
    course_id: Optional[int] = None
    competency_id: Optional[int] = None
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    assessment_type: AssessmentType
    assessment_date: date
    score: Optional[float] = Field(default=None, ge=0, le=100)
    passed: bool
    competency_demonstrated: bool = False
    comments: Optional[str] = None
    evidence: list[dict] = Field(default_factory=list)
    reassessment_required: bool = False
    reassessment_due_date: Optional[date] = None


class TrainingAssessmentRead(TrainingAssessmentCreate, ORMModel):
    id: int
    organisation_id: int
    assessor_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class TrainingCertificateCreate(BaseModel):
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    course_id: Optional[int] = None
    competency_id: Optional[int] = None
    training_record_id: Optional[int] = None
    certificate_number: str = Field(min_length=1, max_length=160)
    issue_date: date
    expiry_date: Optional[date] = None
    provider: Optional[str] = None
    certificate_file_reference: Optional[str] = None
    metadata_snapshot: dict = Field(default_factory=dict)


class CertificateVerification(BaseModel):
    verification_status: VerificationStatus
    verification_date: Optional[date] = None
    notes: Optional[str] = None


class TrainingCertificateRead(TrainingCertificateCreate, ORMModel):
    id: int
    organisation_id: int
    verification_status: VerificationStatus
    verification_date: Optional[date] = None
    verified_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CompetencyAwardCreate(BaseModel):
    competency_id: int
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    achieved_at: Optional[datetime] = None
    valid_until: Optional[date] = None
    evidence: list[dict] = Field(default_factory=list)
    status: CompetencyAwardStatus = CompetencyAwardStatus.competent
    conditions: Optional[str] = None
    source_award_id: Optional[int] = None
    override_requirements: bool = False


class CompetencyAwardRead(BaseModel):
    id: int
    organisation_id: int
    competency_id: int
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    achieved_at: datetime
    valid_until: Optional[date] = None
    awarded_by_user_id: Optional[int] = None
    evidence: list[dict]
    status: CompetencyAwardStatus
    conditions: Optional[str] = None
    requirements_snapshot: dict
    source_award_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CompetencyStatusChange(BaseModel):
    status: CompetencyAwardStatus
    reason: str = Field(min_length=2)
    review_date: Optional[date] = None


class WorkAuthorizationCreate(BaseModel):
    authorization_type: str = Field(min_length=2, max_length=160)
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    competency_id: Optional[int] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    task_activity: Optional[str] = None
    equipment_category: Optional[str] = None
    valid_from: date
    valid_until: Optional[date] = None
    status: AuthorizationStatus = AuthorizationStatus.pending
    restrictions: list[str] = Field(default_factory=list)
    reason: Optional[str] = None
    review_date: Optional[date] = None
    supersedes_authorization_id: Optional[int] = None
    override_requirements: bool = False


class WorkAuthorizationUpdate(BaseModel):
    status: Optional[AuthorizationStatus] = None
    valid_until: Optional[date] = None
    restrictions: Optional[list[str]] = None
    reason: Optional[str] = None
    review_date: Optional[date] = None


class WorkAuthorizationRead(BaseModel):
    id: int
    organisation_id: int
    authorization_type: str
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    competency_id: Optional[int] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    task_activity: Optional[str] = None
    equipment_category: Optional[str] = None
    issued_at: datetime
    valid_from: date
    valid_until: Optional[date] = None
    status: AuthorizationStatus
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    prerequisites_snapshot: dict
    restrictions: list[str]
    reason: Optional[str] = None
    review_date: Optional[date] = None
    supersedes_authorization_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TrainingRequestCreate(BaseModel):
    course_id: int
    requested_for_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    reason: str = Field(min_length=2)
    urgency: AssignmentPriority = AssignmentPriority.normal


class TrainingRequestDecision(BaseModel):
    status: TrainingRequestStatus
    decision_notes: Optional[str] = None
    due_date: Optional[date] = None


class TrainingRequestRead(TrainingRequestCreate, ORMModel):
    id: int
    organisation_id: int
    requester_user_id: int
    status: TrainingRequestStatus
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    resulting_assignment_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class EligibilityQuery(BaseModel):
    worker_user_id: Optional[int] = None
    contractor_worker_id: Optional[int] = None
    task_activity: Optional[str] = None
    authorization_type: Optional[str] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    jsa_id: Optional[int] = None
    permit_type: Optional[str] = None
    equipment_category: Optional[str] = None
    as_of: Optional[date] = None
    include_authorization_requirement: bool = True


class ActionGenerationRequest(BaseModel):
    issue_type: str
    source_id: int
    worker_user_id: Optional[int] = None
    owner_user_id: int
    due_date: date
    title: Optional[str] = None


class DeficiencyLinkCreate(BaseModel):
    deficiency_type: str
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[int] = None
    worker_user_id: Optional[int] = None
    competency_id: Optional[int] = None
    training_record_id: Optional[int] = None
    incident_id: Optional[int] = None
    corrective_action_id: Optional[int] = None
    notes: Optional[str] = None
