from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class MedicalSurveillanceStatus(str, enum.Enum):
    due = "due"
    completed = "completed"
    overdue = "overdue"


class MedicalClearanceStatus(str, enum.Enum):
    pending = "pending"
    cleared = "cleared"
    restricted = "restricted"
    not_cleared = "not_cleared"


class FitnessOutcome(str, enum.Enum):
    fit = "fit"
    fit_with_restrictions = "fit_with_restrictions"
    temporarily_unfit = "temporarily_unfit"
    permanently_unfit = "permanently_unfit"
    pending_further_assessment = "pending_further_assessment"
    not_applicable = "not_applicable"


class SurveillanceComplianceStatus(str, enum.Enum):
    compliant = "compliant"
    due_soon = "due_soon"
    overdue = "overdue"
    non_compliant = "non_compliant"
    pending_assessment = "pending_assessment"
    not_applicable = "not_applicable"


class MedicalAppointmentStatus(str, enum.Enum):
    not_scheduled = "not_scheduled"
    scheduled = "scheduled"
    completed = "completed"
    missed = "missed"
    cancelled = "cancelled"
    rescheduled = "rescheduled"


class WorkRestrictionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    superseded = "superseded"
    removed = "removed"


class OccupationalIllnessStatus(str, enum.Enum):
    suspected = "suspected"
    under_assessment = "under_assessment"
    confirmed = "confirmed"
    monitoring = "monitoring"
    resolved = "resolved"
    closed = "closed"


class ConfidentialityClassification(str, enum.Enum):
    operational = "operational"
    restricted_medical = "restricted_medical"
    highly_confidential = "highly_confidential"


class CertificateRenewalStatus(str, enum.Enum):
    current = "current"
    renewal_due = "renewal_due"
    renewal_scheduled = "renewal_scheduled"
    renewed = "renewed"
    expired = "expired"


class SurveillanceProgramme(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "medical_surveillance_programmes"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_medical_programmes_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    default_frequency_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validity_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reminder_windows: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=lambda: [90, 60, 30, 7], nullable=False)
    provider_requirements: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    certificate_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    risk_exposure_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidentiality_classification: Mapped[ConfidentialityClassification] = mapped_column(
        Enum(ConfidentialityClassification, native_enum=False, length=40),
        default=ConfidentialityClassification.restricted_medical, nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OccupationalExposureType(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "occupational_exposure_types"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_exposure_types_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_risk_level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SurveillanceRequirement(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "medical_surveillance_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("medical_surveillance_programmes.id", ondelete="RESTRICT"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True)
    hazard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hazards.id", ondelete="SET NULL"), index=True, nullable=True)
    exposure_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("occupational_exposure_types.id", ondelete="SET NULL"), index=True, nullable=True)
    jsa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_safety_analyses.id", ondelete="SET NULL"), index=True, nullable=True)
    ppe_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_items.id", ondelete="SET NULL"), index=True, nullable=True)
    task_activity: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contractor_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    frequency_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validity_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    programme: Mapped[SurveillanceProgramme] = relationship(lazy="selectin")


class MedicalProvider(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "medical_providers"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_medical_providers_org_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    facility_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    services: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    preferred_programme_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MedicalSurveillanceRecord(OrganisationOwnedMixin, TimestampMixin, Base):
    """The original worker surveillance record, evolved in place for compatibility."""

    __tablename__ = "medical_surveillance_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    programme_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_programmes.id", ondelete="SET NULL"), index=True, nullable=True)
    requirement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_requirements.id", ondelete="SET NULL"), index=True, nullable=True)
    surveillance_type: Mapped[str] = mapped_column(String(120), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MedicalSurveillanceStatus] = mapped_column(Enum(MedicalSurveillanceStatus), default=MedicalSurveillanceStatus.due, index=True, nullable=False)
    compliance_status: Mapped[SurveillanceComplianceStatus] = mapped_column(
        Enum(SurveillanceComplianceStatus, native_enum=False, length=40),
        default=SurveillanceComplianceStatus.pending_assessment, index=True, nullable=False,
    )
    fitness_outcome: Mapped[Optional[FitnessOutcome]] = mapped_column(Enum(FitnessOutcome, native_enum=False, length=40), index=True, nullable=True)
    results_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medical_clearance_status: Mapped[MedicalClearanceStatus] = mapped_column(Enum(MedicalClearanceStatus), default=MedicalClearanceStatus.pending, nullable=False)
    next_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    recurrence_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    attachments_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)

    employee: Mapped["User"] = relationship(foreign_keys=[employee_user_id], lazy="selectin")
    site: Mapped[Optional["Site"]] = relationship(lazy="selectin")
    programme: Mapped[Optional[SurveillanceProgramme]] = relationship(lazy="selectin")

    @property
    def programme_name(self) -> Optional[str]:
        return self.programme.name if self.programme else None


class MedicalAppointment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "medical_appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    surveillance_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_records.id", ondelete="SET NULL"), index=True, nullable=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("medical_surveillance_programmes.id", ondelete="RESTRICT"), index=True, nullable=False)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_providers.id", ondelete="SET NULL"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    appointment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[MedicalAppointmentStatus] = mapped_column(
        Enum(MedicalAppointmentStatus, native_enum=False, length=40),
        default=MedicalAppointmentStatus.not_scheduled, index=True, nullable=False,
    )
    rescheduled_from_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_appointments.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attendance_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MedicalAssessment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "medical_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    surveillance_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_records.id", ondelete="SET NULL"), index=True, nullable=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("medical_surveillance_programmes.id", ondelete="RESTRICT"), index=True, nullable=False)
    appointment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_appointments.id", ondelete="SET NULL"), index=True, nullable=True)
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), index=True, nullable=True)
    return_to_work_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_return_to_work.id", ondelete="SET NULL"), index=True, nullable=True)
    assessment_type: Mapped[str] = mapped_column(String(120), nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_providers.id", ondelete="SET NULL"), index=True, nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    clinician_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    facility_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    certificate_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    fitness_outcome: Mapped[FitnessOutcome] = mapped_column(Enum(FitnessOutcome, native_enum=False, length=40), index=True, nullable=False)
    operational_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    confidential_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clinical_results: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class FitnessCertificate(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "fitness_certificates"
    __table_args__ = (UniqueConstraint("organisation_id", "certificate_number", name="uq_fitness_certificates_org_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    assessment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_assessments.id", ondelete="SET NULL"), index=True, nullable=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("medical_surveillance_programmes.id", ondelete="RESTRICT"), index=True, nullable=False)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_providers.id", ondelete="SET NULL"), nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    fitness_outcome: Mapped[FitnessOutcome] = mapped_column(Enum(FitnessOutcome, native_enum=False, length=40), nullable=False)
    operational_restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    certificate_file_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    renewal_status: Mapped[CertificateRenewalStatus] = mapped_column(
        Enum(CertificateRenewalStatus, native_enum=False, length=40),
        default=CertificateRenewalStatus.current, index=True, nullable=False,
    )
    replaced_by_certificate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fitness_certificates.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class WorkRestriction(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "work_restrictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    source_assessment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_assessments.id", ondelete="SET NULL"), index=True, nullable=True)
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), index=True, nullable=True)
    return_to_work_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_return_to_work.id", ondelete="SET NULL"), index=True, nullable=True)
    restriction_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    permanent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prohibited_activities: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    hours_shift_restriction: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lifting_limit_kg: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ppe_requirement: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    status: Mapped[WorkRestrictionStatus] = mapped_column(
        Enum(WorkRestrictionStatus, native_enum=False, length=40),
        default=WorkRestrictionStatus.active, index=True, nullable=False,
    )
    authorised_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    supersedes_restriction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_restrictions.id", ondelete="SET NULL"), index=True, nullable=True)
    removed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WorkerExposureAssignment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "worker_exposure_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    exposure_type_id: Mapped[int] = mapped_column(ForeignKey("occupational_exposure_types.id", ondelete="RESTRICT"), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    hazard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hazards.id", ondelete="SET NULL"), index=True, nullable=True)
    jsa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_safety_analyses.id", ondelete="SET NULL"), index=True, nullable=True)
    source_type: Mapped[str] = mapped_column(String(60), default="explicit", nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    triggered_programme_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OccupationalIllnessCase(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "occupational_illness_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    illness_category: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    status: Mapped[OccupationalIllnessStatus] = mapped_column(
        Enum(OccupationalIllnessStatus, native_enum=False, length=40),
        default=OccupationalIllnessStatus.suspected, index=True, nullable=False,
    )
    date_identified: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    symptoms_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosis_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exposure_assignment_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    related_incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), index=True, nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_providers.id", ondelete="SET NULL"), nullable=True)
    clinician_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    regulator_notification_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regulator_notification_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    work_restriction_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    unified_action_ids: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidential_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ClinicEncounter(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "occupational_clinic_encounters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    worker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    encounter_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    encountered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_providers.id", ondelete="SET NULL"), nullable=True)
    operational_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidential_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    related_incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    assessment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_assessments.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class MedicalReminderDelivery(OrganisationOwnedMixin, Base):
    __tablename__ = "medical_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "entity_type", "entity_id", "recipient_user_id",
            "milestone_key", "due_date_snapshot", name="uq_medical_reminder_delivery",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    milestone_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    due_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
