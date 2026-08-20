from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.medical_surveillance import (
    CertificateRenewalStatus,
    ConfidentialityClassification,
    FitnessOutcome,
    MedicalAppointmentStatus,
    MedicalClearanceStatus,
    MedicalSurveillanceStatus,
    OccupationalIllnessStatus,
    SurveillanceComplianceStatus,
    WorkRestrictionStatus,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SurveillanceProgrammeBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = None
    active: bool = True
    default_frequency_days: Optional[int] = Field(default=None, ge=1, le=3650)
    validity_period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    reminder_windows: list[int] = Field(default_factory=lambda: [90, 60, 30, 7])
    provider_requirements: dict = Field(default_factory=dict)
    evidence_required: bool = True
    certificate_required: bool = True
    risk_exposure_trigger: Optional[str] = None
    confidentiality_classification: ConfidentialityClassification = ConfidentialityClassification.restricted_medical

    @model_validator(mode="after")
    def validate_windows(self):
        if any(value < 0 or value > 365 for value in self.reminder_windows):
            raise ValueError("Reminder windows must be between 0 and 365 days")
        self.reminder_windows = sorted(set(self.reminder_windows), reverse=True)
        return self


class SurveillanceProgrammeCreate(SurveillanceProgrammeBase):
    pass


class SurveillanceProgrammeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = None
    active: Optional[bool] = None
    default_frequency_days: Optional[int] = Field(default=None, ge=1, le=3650)
    validity_period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    reminder_windows: Optional[list[int]] = None
    provider_requirements: Optional[dict] = None
    evidence_required: Optional[bool] = None
    certificate_required: Optional[bool] = None
    risk_exposure_trigger: Optional[str] = None
    confidentiality_classification: Optional[ConfidentialityClassification] = None


class SurveillanceProgrammeRead(SurveillanceProgrammeBase, ORMModel):
    id: int
    organisation_id: int
    is_system: bool = False
    created_at: datetime
    updated_at: datetime


class ExposureTypeBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = None
    active: bool = True
    default_risk_level: Optional[str] = Field(default=None, max_length=40)


class ExposureTypeCreate(ExposureTypeBase):
    pass


class ExposureTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    code: Optional[str] = Field(default=None, min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = None
    active: Optional[bool] = None
    default_risk_level: Optional[str] = Field(default=None, max_length=40)


class ExposureTypeRead(ExposureTypeBase, ORMModel):
    id: int
    organisation_id: int
    is_system: bool = False
    created_at: datetime
    updated_at: datetime


class SurveillanceRequirementBase(BaseModel):
    programme_id: int
    name: str = Field(min_length=2, max_length=200)
    mandatory: bool = True
    active: bool = True
    job_title: Optional[str] = Field(default=None, max_length=180)
    role_name: Optional[str] = Field(default=None, max_length=80)
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    hazard_id: Optional[int] = None
    exposure_type_id: Optional[int] = None
    jsa_id: Optional[int] = None
    ppe_item_id: Optional[int] = None
    task_activity: Optional[str] = Field(default=None, max_length=255)
    contractor_category: Optional[str] = Field(default=None, max_length=120)
    frequency_days: Optional[int] = Field(default=None, ge=1, le=3650)
    validity_period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def has_trigger(self):
        fields = (
            self.job_title, self.role_name, self.department_id, self.site_id, self.hazard_id,
            self.exposure_type_id, self.jsa_id, self.ppe_item_id, self.task_activity,
            self.contractor_category,
        )
        if not any(value is not None and value != "" for value in fields):
            raise ValueError("At least one surveillance requirement trigger is required")
        return self


class SurveillanceRequirementCreate(SurveillanceRequirementBase):
    pass


class SurveillanceRequirementUpdate(BaseModel):
    programme_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    mandatory: Optional[bool] = None
    active: Optional[bool] = None
    job_title: Optional[str] = Field(default=None, max_length=180)
    role_name: Optional[str] = Field(default=None, max_length=80)
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    hazard_id: Optional[int] = None
    exposure_type_id: Optional[int] = None
    jsa_id: Optional[int] = None
    ppe_item_id: Optional[int] = None
    task_activity: Optional[str] = Field(default=None, max_length=255)
    contractor_category: Optional[str] = Field(default=None, max_length=120)
    frequency_days: Optional[int] = Field(default=None, ge=1, le=3650)
    validity_period_days: Optional[int] = Field(default=None, ge=1, le=3650)
    rationale: Optional[str] = None


class SurveillanceRequirementRead(SurveillanceRequirementBase, ORMModel):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class MedicalSurveillanceBase(BaseModel):
    employee_user_id: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    programme_id: Optional[int] = None
    requirement_id: Optional[int] = None
    surveillance_type: str = Field(min_length=2, max_length=120)
    due_date: date
    completed_at: Optional[datetime] = None
    status: MedicalSurveillanceStatus = MedicalSurveillanceStatus.due
    compliance_status: SurveillanceComplianceStatus = SurveillanceComplianceStatus.pending_assessment
    fitness_outcome: Optional[FitnessOutcome] = None
    results_summary: Optional[str] = None
    medical_clearance_status: MedicalClearanceStatus = MedicalClearanceStatus.pending
    next_due_date: Optional[date] = None
    expiry_date: Optional[date] = None
    recurrence_days: Optional[int] = Field(default=None, ge=1, le=3650)
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None
    notes: Optional[str] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class MedicalSurveillanceCreate(MedicalSurveillanceBase):
    pass


class MedicalSurveillanceUpdate(BaseModel):
    employee_user_id: Optional[int] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    programme_id: Optional[int] = None
    requirement_id: Optional[int] = None
    surveillance_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    status: Optional[MedicalSurveillanceStatus] = None
    compliance_status: Optional[SurveillanceComplianceStatus] = None
    fitness_outcome: Optional[FitnessOutcome] = None
    results_summary: Optional[str] = None
    medical_clearance_status: Optional[MedicalClearanceStatus] = None
    next_due_date: Optional[date] = None
    expiry_date: Optional[date] = None
    recurrence_days: Optional[int] = Field(default=None, ge=1, le=3650)
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[date] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class MedicalSurveillanceRead(MedicalSurveillanceBase, ORMModel):
    id: int
    organisation_id: int
    programme_name: Optional[str] = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MedicalSurveillanceListRead(PaginatedResponse[MedicalSurveillanceRead]):
    pass


class MedicalProviderBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    facility_name: Optional[str] = Field(default=None, max_length=200)
    contact_name: Optional[str] = Field(default=None, max_length=180)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = None
    services: list[str] = Field(default_factory=list)
    preferred_programme_ids: list[int] = Field(default_factory=list)
    active: bool = True


class MedicalProviderCreate(MedicalProviderBase):
    pass


class MedicalProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    facility_name: Optional[str] = Field(default=None, max_length=200)
    contact_name: Optional[str] = Field(default=None, max_length=180)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = None
    services: Optional[list[str]] = None
    preferred_programme_ids: Optional[list[int]] = None
    active: Optional[bool] = None


class MedicalAppointmentBase(BaseModel):
    worker_user_id: int
    surveillance_record_id: Optional[int] = None
    programme_id: int
    provider_id: Optional[int] = None
    site_id: Optional[int] = None
    appointment_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    status: MedicalAppointmentStatus = MedicalAppointmentStatus.not_scheduled
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None


class MedicalAppointmentCreate(MedicalAppointmentBase):
    pass


class MedicalAppointmentUpdate(BaseModel):
    provider_id: Optional[int] = None
    site_id: Optional[int] = None
    appointment_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    status: Optional[MedicalAppointmentStatus] = None
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None


class MedicalAssessmentCreate(BaseModel):
    worker_user_id: int
    surveillance_record_id: Optional[int] = None
    programme_id: int
    appointment_id: Optional[int] = None
    incident_id: Optional[int] = None
    return_to_work_record_id: Optional[int] = None
    assessment_type: str = Field(min_length=2, max_length=120)
    assessment_date: date
    provider_id: Optional[int] = None
    provider_name: Optional[str] = Field(default=None, max_length=200)
    clinician_name: Optional[str] = Field(default=None, max_length=180)
    facility_name: Optional[str] = Field(default=None, max_length=200)
    certificate_reference: Optional[str] = Field(default=None, max_length=255)
    next_due_date: Optional[date] = None
    expiry_date: Optional[date] = None
    fitness_outcome: FitnessOutcome
    operational_restrictions: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None
    confidential_notes: Optional[str] = None
    clinical_results: dict = Field(default_factory=dict)


class FitnessCertificateCreate(BaseModel):
    worker_user_id: int
    assessment_id: Optional[int] = None
    programme_id: int
    provider_id: Optional[int] = None
    certificate_number: str = Field(min_length=1, max_length=160)
    issued_date: date
    expiry_date: date
    fitness_outcome: FitnessOutcome
    operational_restrictions: Optional[str] = None
    certificate_file_reference: Optional[str] = Field(default=None, max_length=512)
    renewal_status: CertificateRenewalStatus = CertificateRenewalStatus.current

    @model_validator(mode="after")
    def valid_dates(self):
        if self.expiry_date < self.issued_date:
            raise ValueError("Certificate expiry cannot precede issue date")
        return self


class FitnessCertificateUpdate(BaseModel):
    renewal_status: Optional[CertificateRenewalStatus] = None
    replaced_by_certificate_id: Optional[int] = None


class WorkRestrictionCreate(BaseModel):
    worker_user_id: int
    source_assessment_id: Optional[int] = None
    incident_id: Optional[int] = None
    return_to_work_record_id: Optional[int] = None
    restriction_type: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2)
    effective_from: date
    effective_to: Optional[date] = None
    permanent: bool = False
    prohibited_activities: list[str] = Field(default_factory=list)
    hours_shift_restriction: Optional[str] = Field(default=None, max_length=255)
    lifting_limit_kg: Optional[int] = Field(default=None, ge=0, le=1000)
    ppe_requirement: Optional[str] = Field(default=None, max_length=255)
    review_date: Optional[date] = None
    status: WorkRestrictionStatus = WorkRestrictionStatus.active

    @model_validator(mode="after")
    def valid_lifecycle(self):
        if self.permanent:
            self.effective_to = None
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("Restriction end cannot precede its start")
        return self


class WorkRestrictionUpdate(BaseModel):
    restriction_type: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, min_length=2)
    effective_to: Optional[date] = None
    permanent: Optional[bool] = None
    prohibited_activities: Optional[list[str]] = None
    hours_shift_restriction: Optional[str] = Field(default=None, max_length=255)
    lifting_limit_kg: Optional[int] = Field(default=None, ge=0, le=1000)
    ppe_requirement: Optional[str] = Field(default=None, max_length=255)
    review_date: Optional[date] = None
    status: Optional[WorkRestrictionStatus] = None
    removed_reason: Optional[str] = None


class WorkerExposureCreate(BaseModel):
    worker_user_id: int
    exposure_type_id: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    hazard_id: Optional[int] = None
    jsa_id: Optional[int] = None
    source_type: str = Field(default="explicit", max_length=60)
    source_reference: Optional[str] = Field(default=None, max_length=255)
    risk_level: Optional[str] = Field(default=None, max_length=40)
    start_date: date
    end_date: Optional[date] = None
    triggered_programme_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Exposure end cannot precede its start")
        return self


class WorkerExposureUpdate(BaseModel):
    end_date: Optional[date] = None
    risk_level: Optional[str] = Field(default=None, max_length=40)
    triggered_programme_ids: Optional[list[int]] = None


class OccupationalIllnessCreate(BaseModel):
    worker_user_id: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    illness_category: str = Field(min_length=2, max_length=160)
    status: OccupationalIllnessStatus = OccupationalIllnessStatus.suspected
    date_identified: date
    symptoms_summary: Optional[str] = None
    diagnosis_detail: Optional[str] = None
    exposure_assignment_ids: list[int] = Field(default_factory=list)
    related_incident_id: Optional[int] = None
    provider_id: Optional[int] = None
    clinician_name: Optional[str] = Field(default=None, max_length=180)
    regulator_notification_required: bool = False
    regulator_notification_status: Optional[str] = Field(default=None, max_length=60)
    work_restriction_ids: list[int] = Field(default_factory=list)
    unified_action_ids: list[int] = Field(default_factory=list)
    outcome: Optional[str] = None
    confidential_notes: Optional[str] = None


class OccupationalIllnessUpdate(BaseModel):
    status: Optional[OccupationalIllnessStatus] = None
    symptoms_summary: Optional[str] = None
    diagnosis_detail: Optional[str] = None
    exposure_assignment_ids: Optional[list[int]] = None
    provider_id: Optional[int] = None
    clinician_name: Optional[str] = Field(default=None, max_length=180)
    regulator_notification_required: Optional[bool] = None
    regulator_notification_status: Optional[str] = Field(default=None, max_length=60)
    work_restriction_ids: Optional[list[int]] = None
    unified_action_ids: Optional[list[int]] = None
    outcome: Optional[str] = None
    confidential_notes: Optional[str] = None


class ClinicEncounterCreate(BaseModel):
    worker_user_id: int
    site_id: Optional[int] = None
    encounter_type: str = Field(min_length=2, max_length=80)
    encountered_at: datetime
    provider_id: Optional[int] = None
    operational_summary: Optional[str] = None
    confidential_notes: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None
    related_incident_id: Optional[int] = None
    assessment_id: Optional[int] = None


class ClinicEncounterUpdate(BaseModel):
    operational_summary: Optional[str] = None
    confidential_notes: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[date] = None


class ActionGenerationRequest(BaseModel):
    issue_type: str = Field(pattern=r"^(overdue_surveillance|restriction_accommodation|missed_assessments|illness_control)$")
    source_id: int
    title: Optional[str] = Field(default=None, max_length=200)
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None


class OperationalExportQuery(BaseModel):
    site_id: Optional[int] = None
    department_id: Optional[int] = None
