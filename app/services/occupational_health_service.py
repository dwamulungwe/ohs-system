from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction, CorrectiveActionSourceType
from app.models.incident import Incident, IncidentPerson, IncidentReturnToWork, ReturnToWorkStatus
from app.models.medical_surveillance import (
    CertificateRenewalStatus,
    ClinicEncounter,
    FitnessCertificate,
    FitnessOutcome,
    MedicalAppointment,
    MedicalAppointmentStatus,
    MedicalAssessment,
    MedicalProvider,
    MedicalReminderDelivery,
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
    OccupationalExposureType,
    OccupationalIllnessCase,
    OccupationalIllnessStatus,
    SurveillanceComplianceStatus,
    SurveillanceProgramme,
    SurveillanceRequirement,
    WorkerExposureAssignment,
    WorkRestriction,
    WorkRestrictionStatus,
)
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.organisation import OrganisationSettings
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.medical_surveillance import (
    ActionGenerationRequest,
    ClinicEncounterCreate,
    ClinicEncounterUpdate,
    ExposureTypeCreate,
    ExposureTypeUpdate,
    FitnessCertificateCreate,
    FitnessCertificateUpdate,
    MedicalAppointmentCreate,
    MedicalAppointmentUpdate,
    MedicalAssessmentCreate,
    MedicalProviderCreate,
    MedicalProviderUpdate,
    OccupationalIllnessCreate,
    OccupationalIllnessUpdate,
    SurveillanceProgrammeCreate,
    SurveillanceProgrammeUpdate,
    SurveillanceRequirementCreate,
    SurveillanceRequirementUpdate,
    WorkerExposureCreate,
    WorkerExposureUpdate,
    WorkRestrictionCreate,
    WorkRestrictionUpdate,
)
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.notification_service import create_notification
from app.services.query_utils import paginate
from app.services.rbac import get_normalized_role_names


class OccupationalHealthError(Exception):
    pass


class OccupationalHealthNotFound(OccupationalHealthError):
    pass


class OccupationalHealthValidation(OccupationalHealthError):
    pass


PROGRAMME_CATALOGUE = (
    ("PRE_EMPLOYMENT", "Pre-employment Medical", None, 365),
    ("PERIODIC", "Periodic Medical", 365, 365),
    ("EXIT", "Exit Medical", None, None),
    ("RETURN_TO_WORK", "Return-to-Work Assessment", None, 90),
    ("FITNESS_TO_WORK", "Fitness-to-Work", 365, 365),
    ("AUDIOMETRY", "Audiometry", 365, 365),
    ("SPIROMETRY", "Spirometry", 365, 365),
    ("VISION", "Vision Screening", 730, 730),
    ("RESPIRATORY", "Respiratory Surveillance", 365, 365),
    ("CHEMICAL", "Chemical Exposure Surveillance", 365, 365),
    ("BIOLOGICAL", "Biological Monitoring", 365, 365),
    ("MUSCULOSKELETAL", "Ergonomic / Musculoskeletal Surveillance", 365, 365),
    ("DRIVER", "Driver Medical", 365, 365),
    ("FOOD_HANDLER", "Food Handler Medical", 365, 365),
    ("WORK_AT_HEIGHT", "Working-at-Height Fitness", 365, 365),
    ("CONFINED_SPACE", "Confined-Space Fitness", 365, 365),
)

EXPOSURE_CATALOGUE = (
    ("NOISE", "Noise"), ("DUST", "Dust"), ("SILICA", "Silica"),
    ("CHEMICALS", "Chemicals"), ("BIOLOGICAL", "Biological hazards"),
    ("VIBRATION", "Vibration"), ("RADIATION", "Radiation"),
    ("HEAT", "Heat"), ("COLD", "Cold"), ("ERGONOMIC_LOAD", "Ergonomic load"),
    ("MANUAL_HANDLING", "Manual handling"),
    ("RESPIRATORY_SENSITIZERS", "Respiratory sensitizers"),
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, *, actor_id: Optional[int], action: str, resource: str, resource_id: int, fields: Optional[list[str]] = None) -> None:
    details = {"updated_fields": sorted(fields)} if fields else None
    write_audit_log(
        db, actor_id=actor_id, action=action, resource_type=resource,
        resource_id=resource_id, details=details,
    )


def _columns(record) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in inspect(record).mapper.column_attrs:
        value = getattr(record, attribute.key)
        result[attribute.key] = value.value if hasattr(value, "value") else value
    return result


def _redact(data: dict[str, Any], *, medical_detail: bool) -> dict[str, Any]:
    if medical_detail:
        return data
    for field in (
        "results_summary", "notes", "confidential_notes", "clinical_results",
        "illness_category", "diagnosis_detail", "symptoms_summary", "clinician_name",
    ):
        if field in data:
            data[field] = None if field != "clinical_results" else {}
    data.pop("certificate_file_reference", None)
    return data


def serialize(record, *, medical_detail: bool = False) -> dict[str, Any]:
    data = _redact(_columns(record), medical_detail=medical_detail)
    if isinstance(record, MedicalSurveillanceRecord):
        data["programme_name"] = record.programme.name if record.programme else None
    return data


def _get(db: Session, model, record_id: int, label: str):
    record = db.get(model, record_id)
    if record is None:
        raise OccupationalHealthNotFound(f"{label} not found")
    return record


def _exists(db: Session, model, record_id: Optional[int], label: str):
    if record_id is None:
        return None
    record = db.get(model, record_id)
    if record is None:
        raise OccupationalHealthValidation(f"{label} not found")
    return record


def _ensure_rtw_worker(db: Session, rtw: Optional[IncidentReturnToWork], worker_id: int) -> None:
    if rtw is None:
        return
    person = _exists(db, IncidentPerson, rtw.incident_person_id, "Return-to-work person")
    if person.user_id != worker_id:
        raise OccupationalHealthValidation("Return-to-work record belongs to another worker")


def _provider_is_required(db: Session) -> bool:
    return bool(_oh_config(db).get("provider_required", False))


def _commit_new(db: Session, record, *, actor_id: Optional[int], resource: str):
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OccupationalHealthValidation("A record with the same tenant-scoped identifier already exists") from exc
    db.refresh(record)
    _audit(db, actor_id=actor_id, action=f"occupational_health.{resource}.create", resource=resource, resource_id=record.id)
    return record


def _update(db: Session, record, payload, *, actor_id: Optional[int], resource: str):
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(record, field, value)
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OccupationalHealthValidation("The update conflicts with an existing record") from exc
    db.refresh(record)
    _audit(db, actor_id=actor_id, action=f"occupational_health.{resource}.update", resource=resource, resource_id=record.id, fields=list(data))
    return record


def ensure_default_catalogue(db: Session) -> None:
    existing_programmes = set(db.scalars(select(SurveillanceProgramme.code)).all())
    for code, name, frequency, validity in PROGRAMME_CATALOGUE:
        if code not in existing_programmes:
            db.add(SurveillanceProgramme(
                code=code, name=name, description=f"Standard occupational-health programme: {name}.",
                default_frequency_days=frequency, validity_period_days=validity,
                reminder_windows=[90, 60, 30, 7], evidence_required=True,
                certificate_required=True, is_system=True,
            ))
    existing_exposures = set(db.scalars(select(OccupationalExposureType.code)).all())
    for code, name in EXPOSURE_CATALOGUE:
        if code not in existing_exposures:
            db.add(OccupationalExposureType(code=code, name=name, active=True, is_system=True))
    if len(existing_programmes) < len(PROGRAMME_CATALOGUE) or len(existing_exposures) < len(EXPOSURE_CATALOGUE):
        db.commit()


def list_programmes(db: Session, *, active: Optional[bool] = None) -> list[SurveillanceProgramme]:
    ensure_default_catalogue(db)
    statement = select(SurveillanceProgramme)
    if active is not None:
        statement = statement.where(SurveillanceProgramme.active.is_(active))
    return list(db.scalars(statement.order_by(SurveillanceProgramme.name)).all())


def create_programme(db: Session, payload: SurveillanceProgrammeCreate, *, actor_id: Optional[int]):
    data = payload.model_dump()
    data["code"] = data["code"].upper()
    return _commit_new(db, SurveillanceProgramme(**data), actor_id=actor_id, resource="programme")


def update_programme(db: Session, record_id: int, payload: SurveillanceProgrammeUpdate, *, actor_id: Optional[int]):
    record = _get(db, SurveillanceProgramme, record_id, "Programme")
    if payload.code is not None:
        payload = payload.model_copy(update={"code": payload.code.upper()})
    return _update(db, record, payload, actor_id=actor_id, resource="programme")


def list_exposure_types(db: Session, *, active: Optional[bool] = None) -> list[OccupationalExposureType]:
    ensure_default_catalogue(db)
    statement = select(OccupationalExposureType)
    if active is not None:
        statement = statement.where(OccupationalExposureType.active.is_(active))
    return list(db.scalars(statement.order_by(OccupationalExposureType.name)).all())


def create_exposure_type(db: Session, payload: ExposureTypeCreate, *, actor_id: Optional[int]):
    data = payload.model_dump(); data["code"] = data["code"].upper()
    return _commit_new(db, OccupationalExposureType(**data), actor_id=actor_id, resource="exposure_type")


def update_exposure_type(db: Session, record_id: int, payload: ExposureTypeUpdate, *, actor_id: Optional[int]):
    record = _get(db, OccupationalExposureType, record_id, "Exposure type")
    if payload.code is not None:
        payload = payload.model_copy(update={"code": payload.code.upper()})
    return _update(db, record, payload, actor_id=actor_id, resource="exposure_type")


def _validate_requirement_refs(db: Session, data: dict) -> None:
    from app.models.department import Department
    from app.models.hazard import Hazard
    from app.models.jsa import JobSafetyAnalysis
    from app.models.ppe import PPEItem
    from app.models.site import Site
    _exists(db, SurveillanceProgramme, data.get("programme_id"), "Programme")
    for field, model, label in (
        ("department_id", Department, "Department"), ("site_id", Site, "Site"),
        ("hazard_id", Hazard, "Hazard"), ("exposure_type_id", OccupationalExposureType, "Exposure type"),
        ("jsa_id", JobSafetyAnalysis, "JSA"), ("ppe_item_id", PPEItem, "PPE item"),
    ):
        _exists(db, model, data.get(field), label)


def list_requirements(db: Session, *, programme_id: Optional[int] = None, site_id: Optional[int] = None, active: Optional[bool] = None) -> list[SurveillanceRequirement]:
    statement = select(SurveillanceRequirement)
    if programme_id is not None: statement = statement.where(SurveillanceRequirement.programme_id == programme_id)
    if site_id is not None: statement = statement.where(or_(SurveillanceRequirement.site_id == site_id, SurveillanceRequirement.site_id.is_(None)))
    if active is not None: statement = statement.where(SurveillanceRequirement.active.is_(active))
    return list(db.scalars(statement.order_by(SurveillanceRequirement.name)).all())


def create_requirement(db: Session, payload: SurveillanceRequirementCreate, *, actor_id: Optional[int]):
    data = payload.model_dump(); _validate_requirement_refs(db, data)
    return _commit_new(db, SurveillanceRequirement(**data), actor_id=actor_id, resource="requirement")


def update_requirement(db: Session, record_id: int, payload: SurveillanceRequirementUpdate, *, actor_id: Optional[int]):
    record = _get(db, SurveillanceRequirement, record_id, "Requirement")
    data = payload.model_dump(exclude_unset=True)
    _validate_requirement_refs(db, {**_columns(record), **data})
    return _update(db, record, payload, actor_id=actor_id, resource="requirement")


def list_providers(db: Session, *, active: Optional[bool] = None) -> list[MedicalProvider]:
    statement = select(MedicalProvider)
    if active is not None: statement = statement.where(MedicalProvider.active.is_(active))
    return list(db.scalars(statement.order_by(MedicalProvider.name)).all())


def create_provider(db: Session, payload: MedicalProviderCreate, *, actor_id: Optional[int]):
    for programme_id in payload.preferred_programme_ids:
        _exists(db, SurveillanceProgramme, programme_id, "Programme")
    return _commit_new(db, MedicalProvider(**payload.model_dump()), actor_id=actor_id, resource="provider")


def update_provider(db: Session, record_id: int, payload: MedicalProviderUpdate, *, actor_id: Optional[int]):
    record = _get(db, MedicalProvider, record_id, "Provider")
    for programme_id in payload.preferred_programme_ids or []:
        _exists(db, SurveillanceProgramme, programme_id, "Programme")
    return _update(db, record, payload, actor_id=actor_id, resource="provider")


def _scoped_statement(model, *, worker_user_id=None, site_id=None, department_id=None, status=None):
    statement = select(model)
    worker_field = getattr(model, "worker_user_id", None)
    if worker_user_id is not None and worker_field is not None: statement = statement.where(worker_field == worker_user_id)
    if site_id is not None and hasattr(model, "site_id"): statement = statement.where(model.site_id == site_id)
    if department_id is not None and hasattr(model, "department_id"): statement = statement.where(model.department_id == department_id)
    if status is not None and hasattr(model, "status"): statement = statement.where(model.status == status)
    return statement


def list_appointments(db: Session, **filters) -> list[MedicalAppointment]:
    statement = _scoped_statement(MedicalAppointment, **filters)
    return list(db.scalars(statement.order_by(MedicalAppointment.appointment_at, MedicalAppointment.id.desc())).all())


def create_appointment(db: Session, payload: MedicalAppointmentCreate, *, actor_id: Optional[int]):
    from app.models.site import Site
    data = payload.model_dump()
    worker = _exists(db, User, data["worker_user_id"], "Worker")
    _exists(db, SurveillanceProgramme, data["programme_id"], "Programme")
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    _exists(db, Site, data.get("site_id"), "Site")
    if _provider_is_required(db) and data.get("provider_id") is None:
        raise OccupationalHealthValidation("A medical provider is required by organisation settings")
    record = _exists(db, MedicalSurveillanceRecord, data.get("surveillance_record_id"), "Surveillance record")
    if record and record.employee_user_id != worker.id: raise OccupationalHealthValidation("Surveillance record belongs to another worker")
    if data.get("site_id") is None: data["site_id"] = worker.assigned_site_id
    if data.get("appointment_at") and data["status"] == MedicalAppointmentStatus.not_scheduled:
        data["status"] = MedicalAppointmentStatus.scheduled
    data["created_by_user_id"] = actor_id
    return _commit_new(db, MedicalAppointment(**data), actor_id=actor_id, resource="appointment")


def update_appointment(db: Session, record_id: int, payload: MedicalAppointmentUpdate, *, actor_id: Optional[int]):
    from app.models.site import Site
    record = _get(db, MedicalAppointment, record_id, "Appointment")
    data = payload.model_dump(exclude_unset=True)
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    _exists(db, Site, data.get("site_id"), "Site")
    if "appointment_at" in data and record.appointment_at and data["appointment_at"] != record.appointment_at:
        record.status = MedicalAppointmentStatus.rescheduled
        db.add(record); db.flush()
        clone = MedicalAppointment(
            worker_user_id=record.worker_user_id, surveillance_record_id=record.surveillance_record_id,
            programme_id=record.programme_id, provider_id=data.get("provider_id", record.provider_id),
            site_id=data.get("site_id", record.site_id), appointment_at=data["appointment_at"],
            location=data.get("location", record.location), status=MedicalAppointmentStatus.scheduled,
            rescheduled_from_id=record.id, notes=data.get("notes", record.notes), created_by_user_id=actor_id,
        )
        db.add(clone); db.commit(); db.refresh(clone)
        _audit(db, actor_id=actor_id, action="occupational_health.appointment.reschedule", resource="appointment", resource_id=clone.id)
        return clone
    if data.get("status") in {MedicalAppointmentStatus.completed, MedicalAppointmentStatus.missed}:
        record.attendance_recorded_at = _now()
    return _update(db, record, payload, actor_id=actor_id, resource="appointment")


def list_assessments(db: Session, *, worker_user_id=None, programme_id=None, site_id=None) -> list[MedicalAssessment]:
    statement = select(MedicalAssessment)
    if worker_user_id is not None: statement = statement.where(MedicalAssessment.worker_user_id == worker_user_id)
    if programme_id is not None: statement = statement.where(MedicalAssessment.programme_id == programme_id)
    if site_id is not None:
        statement = statement.join(User, User.id == MedicalAssessment.worker_user_id).where(User.assigned_site_id == site_id)
    return list(db.scalars(statement.order_by(MedicalAssessment.assessment_date.desc(), MedicalAssessment.id.desc())).all())


def _clearance(outcome: FitnessOutcome):
    from app.models.medical_surveillance import MedicalClearanceStatus
    if outcome == FitnessOutcome.fit: return MedicalClearanceStatus.cleared
    if outcome == FitnessOutcome.fit_with_restrictions: return MedicalClearanceStatus.restricted
    if outcome in {FitnessOutcome.temporarily_unfit, FitnessOutcome.permanently_unfit}: return MedicalClearanceStatus.not_cleared
    return MedicalClearanceStatus.pending


def create_assessment(db: Session, payload: MedicalAssessmentCreate, *, actor_id: Optional[int]):
    data = payload.model_dump()
    worker = _exists(db, User, data["worker_user_id"], "Worker")
    programme = _exists(db, SurveillanceProgramme, data["programme_id"], "Programme")
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    appointment = _exists(db, MedicalAppointment, data.get("appointment_id"), "Appointment")
    record = _exists(db, MedicalSurveillanceRecord, data.get("surveillance_record_id"), "Surveillance record")
    incident = _exists(db, Incident, data.get("incident_id"), "Incident")
    rtw = _exists(db, IncidentReturnToWork, data.get("return_to_work_record_id"), "Return-to-work record")
    if _provider_is_required(db) and data.get("provider_id") is None and not data.get("provider_name"):
        raise OccupationalHealthValidation("A medical provider is required by organisation settings")
    if appointment and (appointment.worker_user_id != worker.id or appointment.programme_id != programme.id):
        raise OccupationalHealthValidation("Appointment belongs to another worker or programme")
    if record and (record.employee_user_id != worker.id or (record.programme_id and record.programme_id != programme.id)):
        raise OccupationalHealthValidation("Assessment does not match the surveillance record")
    _ensure_rtw_worker(db, rtw, worker.id)
    if rtw and incident and rtw.incident_id != incident.id:
        raise OccupationalHealthValidation("Incident and return-to-work links do not match")
    if data.get("next_due_date") is None and programme.default_frequency_days:
        data["next_due_date"] = data["assessment_date"] + timedelta(days=programme.default_frequency_days)
    if data.get("expiry_date") is None and programme.validity_period_days:
        data["expiry_date"] = data["assessment_date"] + timedelta(days=programme.validity_period_days)
    data["created_by_user_id"] = actor_id
    assessment = MedicalAssessment(**data)
    db.add(assessment); db.flush()
    if record is None:
        record = MedicalSurveillanceRecord(
            employee_user_id=worker.id, site_id=worker.assigned_site_id, department_id=worker.department_id,
            programme_id=programme.id, surveillance_type=programme.name,
            due_date=data.get("next_due_date") or data.get("expiry_date") or data["assessment_date"],
            completed_at=_now(), status=MedicalSurveillanceStatus.completed,
            fitness_outcome=data["fitness_outcome"], medical_clearance_status=_clearance(data["fitness_outcome"]),
            next_due_date=data.get("next_due_date"), expiry_date=data.get("expiry_date"),
            follow_up_required=data.get("follow_up_required", False), follow_up_date=data.get("follow_up_date"),
            created_by_user_id=actor_id,
        )
        db.add(record); db.flush(); assessment.surveillance_record_id = record.id
    else:
        record.completed_at = _now(); record.status = MedicalSurveillanceStatus.completed
        record.fitness_outcome = data["fitness_outcome"]; record.medical_clearance_status = _clearance(data["fitness_outcome"])
        record.next_due_date = data.get("next_due_date"); record.expiry_date = data.get("expiry_date")
        record.follow_up_required = data.get("follow_up_required", False); record.follow_up_date = data.get("follow_up_date")
    record.compliance_status = calculate_record_compliance(record)
    if appointment:
        appointment.status = MedicalAppointmentStatus.completed; appointment.attendance_recorded_at = _now()
    if rtw:
        rtw.medical_surveillance_record_id = record.id
        rtw.clearance_received = data["fitness_outcome"] in {FitnessOutcome.fit, FitnessOutcome.fit_with_restrictions}
        rtw.restrictions = data.get("operational_restrictions")
        if data["fitness_outcome"] == FitnessOutcome.fit: rtw.status = ReturnToWorkStatus.fit_to_return
        elif data["fitness_outcome"] == FitnessOutcome.fit_with_restrictions: rtw.status = ReturnToWorkStatus.restricted_duties
        else: rtw.status = ReturnToWorkStatus.awaiting_assessment
    db.commit(); db.refresh(assessment)
    _audit(db, actor_id=actor_id, action="occupational_health.assessment.complete", resource="assessment", resource_id=assessment.id)
    return assessment


def list_certificates(db: Session, *, worker_user_id=None, programme_id=None, site_id=None) -> list[FitnessCertificate]:
    statement = select(FitnessCertificate)
    if worker_user_id is not None: statement = statement.where(FitnessCertificate.worker_user_id == worker_user_id)
    if programme_id is not None: statement = statement.where(FitnessCertificate.programme_id == programme_id)
    if site_id is not None: statement = statement.join(User, User.id == FitnessCertificate.worker_user_id).where(User.assigned_site_id == site_id)
    return list(db.scalars(statement.order_by(FitnessCertificate.expiry_date, FitnessCertificate.id.desc())).all())


def create_certificate(db: Session, payload: FitnessCertificateCreate, *, actor_id: Optional[int]):
    data = payload.model_dump(); _exists(db, User, data["worker_user_id"], "Worker")
    _exists(db, SurveillanceProgramme, data["programme_id"], "Programme")
    assessment = _exists(db, MedicalAssessment, data.get("assessment_id"), "Assessment")
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    if _provider_is_required(db) and data.get("provider_id") is None:
        raise OccupationalHealthValidation("A medical provider is required by organisation settings")
    if assessment and (assessment.worker_user_id != data["worker_user_id"] or assessment.programme_id != data["programme_id"]):
        raise OccupationalHealthValidation("Certificate assessment belongs to another worker or programme")
    data["created_by_user_id"] = actor_id
    return _commit_new(db, FitnessCertificate(**data), actor_id=actor_id, resource="certificate")


def update_certificate(db: Session, record_id: int, payload: FitnessCertificateUpdate, *, actor_id: Optional[int]):
    record = _get(db, FitnessCertificate, record_id, "Certificate")
    replacement = _exists(db, FitnessCertificate, payload.replaced_by_certificate_id, "Replacement certificate")
    if replacement and (replacement.id == record.id or replacement.worker_user_id != record.worker_user_id or replacement.programme_id != record.programme_id):
        raise OccupationalHealthValidation("Replacement certificate must be a later certificate for the same worker and programme")
    return _update(db, record, payload, actor_id=actor_id, resource="certificate")


def list_restrictions(db: Session, *, worker_user_id=None, site_id=None, status=None) -> list[WorkRestriction]:
    statement = _scoped_statement(WorkRestriction, worker_user_id=worker_user_id, status=status)
    if site_id is not None: statement = statement.join(User, User.id == WorkRestriction.worker_user_id).where(User.assigned_site_id == site_id)
    return list(db.scalars(statement.order_by(WorkRestriction.effective_from.desc(), WorkRestriction.id.desc())).all())


def create_restriction(db: Session, payload: WorkRestrictionCreate, *, actor_id: Optional[int]):
    data = payload.model_dump(); _exists(db, User, data["worker_user_id"], "Worker")
    assessment = _exists(db, MedicalAssessment, data.get("source_assessment_id"), "Assessment")
    incident = _exists(db, Incident, data.get("incident_id"), "Incident")
    rtw = _exists(db, IncidentReturnToWork, data.get("return_to_work_record_id"), "Return-to-work record")
    if assessment and assessment.worker_user_id != data["worker_user_id"]:
        raise OccupationalHealthValidation("Restriction assessment belongs to another worker")
    _ensure_rtw_worker(db, rtw, data["worker_user_id"])
    if rtw and incident and rtw.incident_id != incident.id:
        raise OccupationalHealthValidation("Incident and return-to-work links do not match")
    data["authorised_by_user_id"] = actor_id
    return _commit_new(db, WorkRestriction(**data), actor_id=actor_id, resource="restriction")


def update_restriction(db: Session, record_id: int, payload: WorkRestrictionUpdate, *, actor_id: Optional[int]):
    record = _get(db, WorkRestriction, record_id, "Restriction")
    data = payload.model_dump(exclude_unset=True)
    if set(data).issubset({"status", "removed_reason"}) and data.get("status") in {WorkRestrictionStatus.removed, WorkRestrictionStatus.expired}:
        return _update(db, record, payload, actor_id=actor_id, resource="restriction")
    record.status = WorkRestrictionStatus.superseded; db.add(record); db.flush()
    source = _columns(record)
    fields = (
        "worker_user_id", "source_assessment_id", "incident_id", "return_to_work_record_id",
        "restriction_type", "description", "effective_from", "effective_to", "permanent",
        "prohibited_activities", "hours_shift_restriction", "lifting_limit_kg", "ppe_requirement", "review_date",
    )
    clone_data = {field: source[field] for field in fields}
    clone_data.update(data); clone_data["status"] = data.get("status", WorkRestrictionStatus.active)
    clone_data["supersedes_restriction_id"] = record.id; clone_data["authorised_by_user_id"] = actor_id
    clone = WorkRestriction(**clone_data); db.add(clone); db.commit(); db.refresh(clone)
    _audit(db, actor_id=actor_id, action="occupational_health.restriction.supersede", resource="restriction", resource_id=clone.id, fields=list(data))
    return clone


def list_exposures(db: Session, *, worker_user_id=None, site_id=None, exposure_type_id=None, active_only=False) -> list[WorkerExposureAssignment]:
    statement = _scoped_statement(WorkerExposureAssignment, worker_user_id=worker_user_id, site_id=site_id)
    if exposure_type_id is not None: statement = statement.where(WorkerExposureAssignment.exposure_type_id == exposure_type_id)
    if active_only: statement = statement.where(WorkerExposureAssignment.end_date.is_(None))
    return list(db.scalars(statement.order_by(WorkerExposureAssignment.start_date.desc(), WorkerExposureAssignment.id.desc())).all())


def create_exposure(db: Session, payload: WorkerExposureCreate, *, actor_id: Optional[int]):
    from app.models.department import Department
    from app.models.hazard import Hazard
    from app.models.jsa import JobSafetyAnalysis
    from app.models.site import Site
    data = payload.model_dump(); worker = _exists(db, User, data["worker_user_id"], "Worker")
    _exists(db, OccupationalExposureType, data["exposure_type_id"], "Exposure type")
    _exists(db, Site, data.get("site_id"), "Site")
    _exists(db, Department, data.get("department_id"), "Department")
    _exists(db, Hazard, data.get("hazard_id"), "Hazard")
    _exists(db, JobSafetyAnalysis, data.get("jsa_id"), "JSA")
    for programme_id in data["triggered_programme_ids"]: _exists(db, SurveillanceProgramme, programme_id, "Programme")
    if data.get("site_id") is None: data["site_id"] = worker.assigned_site_id
    if data.get("department_id") is None: data["department_id"] = worker.department_id
    data["created_by_user_id"] = actor_id
    return _commit_new(db, WorkerExposureAssignment(**data), actor_id=actor_id, resource="exposure")


def update_exposure(db: Session, record_id: int, payload: WorkerExposureUpdate, *, actor_id: Optional[int]):
    record = _get(db, WorkerExposureAssignment, record_id, "Exposure assignment")
    if payload.end_date and payload.end_date < record.start_date: raise OccupationalHealthValidation("Exposure end cannot precede its start")
    for programme_id in payload.triggered_programme_ids or []: _exists(db, SurveillanceProgramme, programme_id, "Programme")
    return _update(db, record, payload, actor_id=actor_id, resource="exposure")


def list_illnesses(db: Session, *, worker_user_id=None, site_id=None, department_id=None, status=None) -> list[OccupationalIllnessCase]:
    statement = _scoped_statement(OccupationalIllnessCase, worker_user_id=worker_user_id, site_id=site_id, department_id=department_id, status=status)
    return list(db.scalars(statement.order_by(OccupationalIllnessCase.date_identified.desc(), OccupationalIllnessCase.id.desc())).all())


def create_illness(db: Session, payload: OccupationalIllnessCreate, *, actor_id: Optional[int]):
    from app.models.department import Department
    from app.models.site import Site
    data = payload.model_dump(); worker = _exists(db, User, data["worker_user_id"], "Worker")
    _exists(db, Site, data.get("site_id"), "Site")
    _exists(db, Department, data.get("department_id"), "Department")
    _exists(db, Incident, data.get("related_incident_id"), "Incident")
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    if data.get("site_id") is None: data["site_id"] = worker.assigned_site_id
    if data.get("department_id") is None: data["department_id"] = worker.department_id
    for exposure_id in data["exposure_assignment_ids"]:
        exposure = _exists(db, WorkerExposureAssignment, exposure_id, "Exposure assignment")
        if exposure.worker_user_id != worker.id: raise OccupationalHealthValidation("Exposure assignment belongs to another worker")
    for restriction_id in data["work_restriction_ids"]:
        restriction = _exists(db, WorkRestriction, restriction_id, "Work restriction")
        if restriction.worker_user_id != worker.id: raise OccupationalHealthValidation("Work restriction belongs to another worker")
    for action_id in data["unified_action_ids"]: _exists(db, CorrectiveAction, action_id, "Unified action")
    data["created_by_user_id"] = actor_id
    return _commit_new(db, OccupationalIllnessCase(**data), actor_id=actor_id, resource="occupational_illness")


def update_illness(db: Session, record_id: int, payload: OccupationalIllnessUpdate, *, actor_id: Optional[int]):
    record = _get(db, OccupationalIllnessCase, record_id, "Occupational illness case")
    _exists(db, MedicalProvider, payload.provider_id, "Provider")
    for exposure_id in payload.exposure_assignment_ids or []:
        exposure = _exists(db, WorkerExposureAssignment, exposure_id, "Exposure assignment")
        if exposure.worker_user_id != record.worker_user_id: raise OccupationalHealthValidation("Exposure assignment belongs to another worker")
    for restriction_id in payload.work_restriction_ids or []:
        restriction = _exists(db, WorkRestriction, restriction_id, "Work restriction")
        if restriction.worker_user_id != record.worker_user_id: raise OccupationalHealthValidation("Work restriction belongs to another worker")
    for action_id in payload.unified_action_ids or []: _exists(db, CorrectiveAction, action_id, "Unified action")
    return _update(db, record, payload, actor_id=actor_id, resource="occupational_illness")


def list_clinic_encounters(db: Session, *, worker_user_id=None, site_id=None) -> list[ClinicEncounter]:
    statement = _scoped_statement(ClinicEncounter, worker_user_id=worker_user_id, site_id=site_id)
    return list(db.scalars(statement.order_by(ClinicEncounter.encountered_at.desc(), ClinicEncounter.id.desc())).all())


def create_clinic_encounter(db: Session, payload: ClinicEncounterCreate, *, actor_id: Optional[int]):
    from app.models.site import Site
    data = payload.model_dump(); worker = _exists(db, User, data["worker_user_id"], "Worker")
    if data.get("site_id") is None: data["site_id"] = worker.assigned_site_id
    _exists(db, Site, data.get("site_id"), "Site")
    _exists(db, MedicalProvider, data.get("provider_id"), "Provider")
    _exists(db, Incident, data.get("related_incident_id"), "Incident")
    assessment = _exists(db, MedicalAssessment, data.get("assessment_id"), "Assessment")
    if assessment and assessment.worker_user_id != worker.id:
        raise OccupationalHealthValidation("Clinic encounter assessment belongs to another worker")
    data["created_by_user_id"] = actor_id
    return _commit_new(db, ClinicEncounter(**data), actor_id=actor_id, resource="clinic_encounter")


def update_clinic_encounter(db: Session, record_id: int, payload: ClinicEncounterUpdate, *, actor_id: Optional[int]):
    return _update(db, _get(db, ClinicEncounter, record_id, "Clinic encounter"), payload, actor_id=actor_id, resource="clinic_encounter")


def calculate_record_compliance(record: MedicalSurveillanceRecord, *, as_of: Optional[date] = None) -> SurveillanceComplianceStatus:
    as_of = as_of or _today()
    if record.fitness_outcome == FitnessOutcome.not_applicable: return SurveillanceComplianceStatus.not_applicable
    if record.fitness_outcome in {FitnessOutcome.temporarily_unfit, FitnessOutcome.permanently_unfit}: return SurveillanceComplianceStatus.non_compliant
    if record.fitness_outcome == FitnessOutcome.pending_further_assessment: return SurveillanceComplianceStatus.pending_assessment
    if record.follow_up_required and record.follow_up_date and record.follow_up_date < as_of: return SurveillanceComplianceStatus.non_compliant
    due = record.next_due_date or record.expiry_date or record.due_date
    if due < as_of: return SurveillanceComplianceStatus.overdue
    if record.completed_at is None: return SurveillanceComplianceStatus.pending_assessment
    if due <= as_of + timedelta(days=90): return SurveillanceComplianceStatus.due_soon
    return SurveillanceComplianceStatus.compliant


def refresh_compliance(db: Session) -> int:
    changed = 0
    for record in db.scalars(select(MedicalSurveillanceRecord)).all():
        state = calculate_record_compliance(record)
        status = MedicalSurveillanceStatus.completed if record.completed_at else MedicalSurveillanceStatus.overdue if record.due_date < _today() else MedicalSurveillanceStatus.due
        if record.compliance_status != state or record.status != status:
            record.compliance_status = state; record.status = status; db.add(record); changed += 1
    for certificate in db.scalars(select(FitnessCertificate)).all():
        next_status = CertificateRenewalStatus.expired if certificate.expiry_date < _today() else CertificateRenewalStatus.renewal_due if certificate.expiry_date <= _today() + timedelta(days=90) else certificate.renewal_status
        if certificate.renewal_status != next_status: certificate.renewal_status = next_status; db.add(certificate); changed += 1
    for restriction in db.scalars(select(WorkRestriction).where(WorkRestriction.status == WorkRestrictionStatus.active)).all():
        if restriction.effective_to and restriction.effective_to < _today(): restriction.status = WorkRestrictionStatus.expired; db.add(restriction); changed += 1
    if changed: db.commit()
    return changed


def _requirement_matches(
    requirement: SurveillanceRequirement,
    worker: User,
    exposures: list[WorkerExposureAssignment],
    ppe_item_ids: Optional[set[int]] = None,
) -> bool:
    exposure_type_ids = {item.exposure_type_id for item in exposures}
    if requirement.site_id is not None and requirement.site_id != worker.assigned_site_id: return False
    if requirement.department_id is not None and requirement.department_id != worker.department_id: return False
    if requirement.job_title and (worker.job_title or "").casefold() != requirement.job_title.casefold(): return False
    if requirement.role_name and requirement.role_name not in get_normalized_role_names(worker): return False
    if requirement.exposure_type_id is not None and requirement.exposure_type_id not in exposure_type_ids: return False
    if requirement.hazard_id is not None and requirement.hazard_id not in {item.hazard_id for item in exposures}: return False
    if requirement.jsa_id is not None and requirement.jsa_id not in {item.jsa_id for item in exposures}: return False
    if requirement.ppe_item_id is not None and requirement.ppe_item_id not in (ppe_item_ids or set()): return False
    # There is not yet a worker-task assignment table. Task-only and contractor-
    # category rules remain linkable infrastructure, but are not guessed as
    # applicable to every employee.
    trigger_values = (
        requirement.job_title, requirement.role_name, requirement.department_id,
        requirement.site_id, requirement.hazard_id, requirement.exposure_type_id,
        requirement.jsa_id, requirement.ppe_item_id,
    )
    if not any(value is not None for value in trigger_values) and (requirement.task_activity or requirement.contractor_category):
        return False
    return True


def worker_profile(db: Session, worker_id: int, *, medical_detail: bool = False) -> dict[str, Any]:
    worker = _get(db, User, worker_id, "Worker")
    exposures = list_exposures(db, worker_user_id=worker_id)
    active_exposures = [item for item in exposures if item.end_date is None or item.end_date >= _today()]
    from app.models.ppe import PPEIssue
    ppe_item_ids = {item.item_id for item in db.scalars(select(PPEIssue).where(PPEIssue.recipient_user_id == worker_id)).all() if item.active_quantity > 0}
    requirements = [item for item in db.scalars(select(SurveillanceRequirement).where(SurveillanceRequirement.active.is_(True))).all() if _requirement_matches(item, worker, active_exposures, ppe_item_ids)]
    records = list(db.scalars(select(MedicalSurveillanceRecord).where(MedicalSurveillanceRecord.employee_user_id == worker_id)).all())
    by_programme = {record.programme_id: record for record in sorted(records, key=lambda item: item.id) if record.programme_id}
    required = []
    for requirement in requirements:
        record = by_programme.get(requirement.programme_id)
        required.append({
            "requirement_id": requirement.id, "requirement_name": requirement.name,
            "programme_id": requirement.programme_id, "programme_name": requirement.programme.name,
            "mandatory": requirement.mandatory,
            "compliance_status": calculate_record_compliance(record).value if record else SurveillanceComplianceStatus.pending_assessment.value,
            "due_date": (record.next_due_date or record.expiry_date or record.due_date) if record else None,
        })
    assessments = list_assessments(db, worker_user_id=worker_id)
    appointments = list_appointments(db, worker_user_id=worker_id)
    restrictions = list_restrictions(db, worker_user_id=worker_id)
    certificates = list_certificates(db, worker_user_id=worker_id)
    illnesses = list_illnesses(db, worker_user_id=worker_id)
    rtw = list(db.scalars(
        select(IncidentReturnToWork)
        .join(IncidentPerson, IncidentReturnToWork.incident_person_id == IncidentPerson.id)
        .where(IncidentPerson.user_id == worker_id)
    ).all())
    states = Counter(item["compliance_status"] for item in required)
    states.update(calculate_record_compliance(item).value for item in records if item.programme_id not in {r["programme_id"] for r in required})
    return {
        "worker": {"id": worker.id, "full_name": worker.full_name, "job_title": worker.job_title, "site_id": worker.assigned_site_id, "department_id": worker.department_id},
        "summary": dict(states), "required_programmes": required,
        "surveillance_records": [serialize(item, medical_detail=medical_detail) for item in records],
        "assessments": [serialize(item, medical_detail=medical_detail) for item in assessments],
        "appointments": [serialize(item) for item in appointments],
        "certificates": [serialize(item, medical_detail=medical_detail) for item in certificates],
        "restrictions": [serialize(item) for item in restrictions],
        "exposures": [serialize(item) for item in exposures],
        "occupational_illness_cases": [serialize(item, medical_detail=medical_detail) for item in illnesses],
        "return_to_work": [serialize(item) for item in rtw],
    }


def dashboard(db: Session, *, site_id: Optional[int] = None, department_id: Optional[int] = None, as_of: Optional[date] = None) -> dict[str, Any]:
    as_of = as_of or _today(); refresh_compliance(db)
    statement = select(MedicalSurveillanceRecord)
    if site_id is not None: statement = statement.where(MedicalSurveillanceRecord.site_id == site_id)
    if department_id is not None: statement = statement.where(MedicalSurveillanceRecord.department_id == department_id)
    records = list(db.scalars(statement).all())
    worker_statement = select(User).where(User.is_active.is_(True))
    if site_id is not None: worker_statement = worker_statement.where(User.assigned_site_id == site_id)
    if department_id is not None: worker_statement = worker_statement.where(User.department_id == department_id)
    workers = list(db.scalars(worker_statement).all())
    worker_ids = {item.id for item in workers}
    records = [item for item in records if item.employee_user_id in worker_ids]
    appointments = [item for item in list_appointments(db, site_id=site_id) if department_id is None or item.worker_user_id in worker_ids]
    restrictions = [item for item in list_restrictions(db, site_id=site_id) if department_id is None or item.worker_user_id in worker_ids]
    certificates = [item for item in list_certificates(db, site_id=site_id) if department_id is None or item.worker_user_id in worker_ids]
    illnesses = list_illnesses(db, site_id=site_id, department_id=department_id)
    exposures = [item for item in list_exposures(db, site_id=site_id, active_only=True) if department_id is None or item.department_id == department_id]
    due = lambda record: record.next_due_date or record.expiry_date or record.due_date
    def within(days: int): return sum(as_of <= due(item) <= as_of + timedelta(days=days) for item in records)
    compliance = Counter(calculate_record_compliance(item, as_of=as_of).value for item in records)
    requirements = list(db.scalars(select(SurveillanceRequirement).where(SurveillanceRequirement.active.is_(True), SurveillanceRequirement.mandatory.is_(True))).all())
    records_by_worker_programme = {(item.employee_user_id, item.programme_id): item for item in records if item.programme_id is not None}
    required_by_worker: dict[int, set[int]] = defaultdict(set)
    from app.models.ppe import PPEIssue
    for worker in workers:
        worker_exposures = [item for item in exposures if item.worker_user_id == worker.id]
        ppe_item_ids = {item.item_id for item in db.scalars(select(PPEIssue).where(PPEIssue.recipient_user_id == worker.id)).all() if item.active_quantity > 0}
        for requirement in requirements:
            if _requirement_matches(requirement, worker, worker_exposures, ppe_item_ids):
                required_by_worker[worker.id].add(requirement.programme_id)
    for record in records:
        if record.programme_id is not None: required_by_worker[record.employee_user_id].add(record.programme_id)
    workers_requiring = {worker_id for worker_id, programme_ids in required_by_worker.items() if programme_ids}
    current_states = {SurveillanceComplianceStatus.compliant, SurveillanceComplianceStatus.due_soon}
    compliant_workers = {
        worker_id for worker_id in workers_requiring
        if all(
            (record := records_by_worker_programme.get((worker_id, programme_id))) is not None
            and calculate_record_compliance(record, as_of=as_of) in current_states
            for programme_id in required_by_worker[worker_id]
        )
    }
    missing_requirement_count = sum(
        (worker_id, programme_id) not in records_by_worker_programme
        for worker_id, programme_ids in required_by_worker.items() for programme_id in programme_ids
    )
    compliance[SurveillanceComplianceStatus.pending_assessment.value] += missing_requirement_count
    programmes: dict[str, Counter] = defaultdict(Counter)
    for item in records: programmes[item.programme_name or item.surveillance_type][calculate_record_compliance(item, as_of=as_of).value] += 1
    programme_names = {item.id: item.name for item in db.scalars(select(SurveillanceProgramme)).all()}
    for worker_id, programme_ids in required_by_worker.items():
        for programme_id in programme_ids:
            if (worker_id, programme_id) not in records_by_worker_programme:
                programmes[programme_names.get(programme_id, str(programme_id))][SurveillanceComplianceStatus.pending_assessment.value] += 1
    from app.models.incident import Incident
    active_rtw = select(IncidentReturnToWork).join(Incident, Incident.id == IncidentReturnToWork.incident_id).where(IncidentReturnToWork.review_due_date.is_not(None), IncidentReturnToWork.review_due_date <= as_of + timedelta(days=30), IncidentReturnToWork.status.notin_([ReturnToWorkStatus.not_required, ReturnToWorkStatus.returned_to_work]))
    if site_id is not None: active_rtw = active_rtw.where(Incident.site_id == site_id)
    if department_id is not None: active_rtw = active_rtw.where(Incident.department_id == department_id)
    site_breakdown: dict[str, Counter] = defaultdict(Counter)
    department_breakdown: dict[str, Counter] = defaultdict(Counter)
    for item in records:
        state = calculate_record_compliance(item, as_of=as_of).value
        site_breakdown[str(item.site_id or "unassigned")][state] += 1
        department_breakdown[str(item.department_id or "unassigned")][state] += 1
    workers_by_id = {item.id: item for item in workers}
    for worker_id, programme_ids in required_by_worker.items():
        worker = workers_by_id.get(worker_id)
        if worker is None: continue
        for programme_id in programme_ids:
            if (worker_id, programme_id) not in records_by_worker_programme:
                state = SurveillanceComplianceStatus.pending_assessment.value
                site_breakdown[str(worker.assigned_site_id or "unassigned")][state] += 1
                department_breakdown[str(worker.department_id or "unassigned")][state] += 1
    exposure_names = {item.id: item.name for item in db.scalars(select(OccupationalExposureType)).all()}
    exposure_breakdown = Counter(exposure_names.get(item.exposure_type_id, str(item.exposure_type_id)) for item in exposures)
    completed_delays = [max(0, (item.completed_at.date() - item.due_date).days) for item in records if item.completed_at]
    return {
        "workers_requiring_surveillance": len(workers_requiring),
        "compliant_workers": len(compliant_workers),
        "compliance_rate": round(len(compliant_workers) * 100 / len(workers_requiring), 2) if workers_requiring else None,
        "due_30": within(30), "due_60": within(60), "due_90": within(90),
        "overdue_assessments": compliance["overdue"],
        "pending_assessment": compliance["pending_assessment"],
        "appointments_scheduled": sum(item.status == MedicalAppointmentStatus.scheduled for item in appointments),
        "missed_appointments": sum(item.status == MedicalAppointmentStatus.missed for item in appointments),
        "expired_certificates": sum(item.expiry_date < as_of for item in certificates),
        "active_restrictions": sum(item.status == WorkRestrictionStatus.active for item in restrictions),
        "return_to_work_reviews_due": len(list(db.scalars(active_rtw).all())),
        "occupational_illness_suspected": sum(item.status in {OccupationalIllnessStatus.suspected, OccupationalIllnessStatus.under_assessment} for item in illnesses),
        "occupational_illness_confirmed": sum(item.status == OccupationalIllnessStatus.confirmed for item in illnesses),
        "average_completion_delay_days": round(sum(completed_delays) / len(completed_delays), 2) if completed_delays else None,
        "by_compliance_status": dict(compliance),
        "by_programme": [{"programme": name, **dict(counts)} for name, counts in sorted(programmes.items())],
        "by_site": [{"site_id": key, **dict(counts)} for key, counts in sorted(site_breakdown.items())],
        "by_department": [{"department_id": key, **dict(counts)} for key, counts in sorted(department_breakdown.items())],
        "by_exposure": [{"exposure": key, "active_assignments": value} for key, value in sorted(exposure_breakdown.items())],
    }


def prerequisite_status(
    db: Session,
    worker_id: int,
    *,
    programme_codes: Optional[list[str]] = None,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    _get(db, User, worker_id, "Worker")
    codes = set(programme_codes or ["CONFINED_SPACE", "DRIVER", "WORK_AT_HEIGHT", "RESPIRATORY"])
    records = list(db.scalars(select(MedicalSurveillanceRecord).where(MedicalSurveillanceRecord.employee_user_id == worker_id)).all())
    items = []
    for record in records:
        code = record.programme.code if record.programme else None
        if code in codes:
            state = calculate_record_compliance(record, as_of=as_of)
            items.append({"programme_code": code, "programme_name": record.programme.name, "status": state.value, "cleared": state in {SurveillanceComplianceStatus.compliant, SurveillanceComplianceStatus.due_soon} and record.fitness_outcome in {FitnessOutcome.fit, FitnessOutcome.fit_with_restrictions}})
    return {"worker_user_id": worker_id, "cleared": bool(items) and all(item["cleared"] for item in items), "prerequisites": items}


def _oh_config(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    return dict(getattr(settings, "occupational_health_configuration", {}) or {}) if settings else {}


def _reminder_windows(db: Session, programme: Optional[SurveillanceProgramme] = None, *, key: str = "default_reminder_windows") -> list[int]:
    if programme and programme.reminder_windows: return list(programme.reminder_windows)
    defaults = [7, 1] if key == "appointment_reminder_days" else [90, 60, 30, 7]
    return list(_oh_config(db).get(key, defaults))


def _deliver_reminder(db: Session, *, entity_type: str, entity_id: int, recipient_user_id: int, due_date: date, milestone: str, title: str, message: str, overdue: bool = False) -> bool:
    exists = db.scalar(select(MedicalReminderDelivery.id).where(
        MedicalReminderDelivery.entity_type == entity_type, MedicalReminderDelivery.entity_id == entity_id,
        MedicalReminderDelivery.recipient_user_id == recipient_user_id, MedicalReminderDelivery.milestone_key == milestone,
        MedicalReminderDelivery.due_date_snapshot == due_date,
    ))
    if exists: return False
    db.add(MedicalReminderDelivery(entity_type=entity_type, entity_id=entity_id, recipient_user_id=recipient_user_id, milestone_key=milestone, due_date_snapshot=due_date)); db.commit()
    create_notification(db, NotificationCreate(
        recipient_user_id=recipient_user_id, title=title, message=message,
        notification_type=NotificationType.medical_surveillance_overdue if overdue else NotificationType.medical_surveillance_due_soon,
        severity=NotificationSeverity.critical if overdue else NotificationSeverity.warning,
        related_entity_type=RelatedEntityType.medical_surveillance, related_entity_id=entity_id,
    ))
    return True


def generate_reminders(db: Session) -> dict[str, int]:
    today = _today(); counts = Counter(); config = _oh_config(db)
    for record in db.scalars(select(MedicalSurveillanceRecord)).all():
        if record.follow_up_required and record.follow_up_date:
            follow_up_days = (record.follow_up_date - today).days
            follow_up_window = max(_reminder_windows(db, key="appointment_reminder_days"), default=7)
            if follow_up_days <= follow_up_window and _deliver_reminder(db, entity_type="surveillance_follow_up", entity_id=record.id, recipient_user_id=record.employee_user_id, due_date=record.follow_up_date, milestone="follow_up", title="Occupational-health follow-up", message=f"An occupational-health follow-up is due by {record.follow_up_date}.", overdue=follow_up_days < 0): counts["follow_up"] += 1
        if record.completed_at and calculate_record_compliance(record) == SurveillanceComplianceStatus.compliant: continue
        due = record.next_due_date or record.expiry_date or record.due_date; days = (due - today).days
        milestone = "overdue" if days < 0 else next((f"due_{window}" for window in sorted(_reminder_windows(db, record.programme)) if days <= window), None)
        if milestone and _deliver_reminder(db, entity_type="surveillance", entity_id=record.id, recipient_user_id=record.employee_user_id, due_date=due, milestone=milestone, title="Medical surveillance overdue" if days < 0 else "Medical surveillance due", message=f"{record.surveillance_type} is {'overdue' if days < 0 else f'due by {due}' }.", overdue=days < 0): counts[milestone] += 1
    for certificate in db.scalars(select(FitnessCertificate)).all():
        days = (certificate.expiry_date - today).days
        milestone = "certificate_expired" if days < 0 else next((f"certificate_{window}" for window in sorted(_reminder_windows(db, key="certificate_expiry_reminders")) if days <= window), None)
        if milestone and _deliver_reminder(db, entity_type="certificate", entity_id=certificate.id, recipient_user_id=certificate.worker_user_id, due_date=certificate.expiry_date, milestone=milestone, title="Fitness certificate expiry", message=f"A fitness certificate is {'expired' if days < 0 else f'due to expire on {certificate.expiry_date}' }.", overdue=days < 0): counts[milestone] += 1
    for appointment in db.scalars(select(MedicalAppointment).where(MedicalAppointment.appointment_at.is_not(None))).all():
        appointment_date = appointment.appointment_at.date()
        days = (appointment_date - today).days
        if appointment.status == MedicalAppointmentStatus.scheduled and days >= 0:
            milestone = next((f"appointment_{window}" for window in sorted(_reminder_windows(db, key="appointment_reminder_days")) if days <= window), None)
            if milestone and _deliver_reminder(db, entity_type="appointment", entity_id=appointment.id, recipient_user_id=appointment.worker_user_id, due_date=appointment_date, milestone=milestone, title="Medical appointment reminder", message=f"Your occupational-health appointment is scheduled for {appointment_date}."): counts[milestone] += 1
        if appointment.status == MedicalAppointmentStatus.missed:
            missed_ids = list(db.scalars(select(MedicalAppointment.id).where(
                MedicalAppointment.worker_user_id == appointment.worker_user_id,
                MedicalAppointment.programme_id == appointment.programme_id,
                MedicalAppointment.status == MedicalAppointmentStatus.missed,
            ).order_by(MedicalAppointment.id)).all())
            missed_count = len(missed_ids)
            if _deliver_reminder(db, entity_type="appointment", entity_id=appointment.id, recipient_user_id=appointment.worker_user_id, due_date=appointment_date, milestone="missed_follow_up", title="Missed medical appointment", message="Please contact occupational health to reschedule your missed appointment.", overdue=True): counts["missed_follow_up"] += 1
            threshold = max(1, int(config.get("missed_appointment_escalation_count", 2)))
            if missed_count >= threshold and appointment.id == missed_ids[-1]:
                for manager in db.scalars(select(User).where(User.is_active.is_(True))).unique().all():
                    if get_normalized_role_names(manager).intersection({"admin", "ohs_manager", "safety_officer"}):
                        if _deliver_reminder(db, entity_type="appointment", entity_id=appointment.id, recipient_user_id=manager.id, due_date=appointment_date, milestone=f"missed_escalation_{missed_count}", title="Repeated missed occupational-health appointments", message=f"Worker #{appointment.worker_user_id} has repeated missed appointments requiring operational follow-up.", overdue=True): counts["missed_escalation"] += 1
    for restriction in db.scalars(select(WorkRestriction).where(WorkRestriction.status == WorkRestrictionStatus.active, WorkRestriction.review_date.is_not(None))).all():
        days = (restriction.review_date - today).days
        review_days = max(0, int(config.get("restriction_review_reminder_days", 30)))
        if days <= review_days and _deliver_reminder(db, entity_type="restriction", entity_id=restriction.id, recipient_user_id=restriction.worker_user_id, due_date=restriction.review_date, milestone="restriction_review", title="Work restriction review", message=f"A work restriction review is due by {restriction.review_date}.", overdue=days < 0): counts["restriction_review"] += 1
    for encounter in db.scalars(select(ClinicEncounter).where(ClinicEncounter.follow_up_required.is_(True), ClinicEncounter.follow_up_date.is_not(None))).all():
        days = (encounter.follow_up_date - today).days
        follow_up_window = max(_reminder_windows(db, key="appointment_reminder_days"), default=7)
        if days <= follow_up_window and _deliver_reminder(db, entity_type="clinic_follow_up", entity_id=encounter.id, recipient_user_id=encounter.worker_user_id, due_date=encounter.follow_up_date, milestone="follow_up", title="Clinic follow-up", message=f"An occupational clinic follow-up is due by {encounter.follow_up_date}.", overdue=days < 0): counts["clinic_follow_up"] += 1
    if config.get("return_to_work_review_required", True):
        rtw_rows = db.execute(
            select(IncidentReturnToWork, IncidentPerson.user_id)
            .join(IncidentPerson, IncidentReturnToWork.incident_person_id == IncidentPerson.id)
            .where(
                IncidentReturnToWork.review_due_date.is_not(None),
                IncidentReturnToWork.status.not_in({ReturnToWorkStatus.not_required, ReturnToWorkStatus.returned_to_work}),
                IncidentPerson.user_id.is_not(None),
            )
        ).all()
        for rtw, recipient_user_id in rtw_rows:
            days = (rtw.review_due_date - today).days
            if days <= 30 and _deliver_reminder(db, entity_type="return_to_work", entity_id=rtw.id, recipient_user_id=recipient_user_id, due_date=rtw.review_due_date, milestone="rtw_review", title="Return-to-work review", message=f"A return-to-work review is due by {rtw.review_due_date}.", overdue=days < 0): counts["rtw_review"] += 1
    return dict(counts)


def generate_action(db: Session, payload: ActionGenerationRequest, *, actor_id: Optional[int]):
    source_models = {
        "overdue_surveillance": MedicalSurveillanceRecord,
        "restriction_accommodation": WorkRestriction,
        "missed_assessments": MedicalAppointment,
        "illness_control": OccupationalIllnessCase,
    }
    source = _get(db, source_models[payload.issue_type], payload.source_id, "Occupational-health source")
    worker_id = getattr(source, "employee_user_id", None) or getattr(source, "worker_user_id", None)
    worker = _get(db, User, worker_id, "Worker")
    title = payload.title or {
        "overdue_surveillance": "Resolve overdue mandatory medical surveillance",
        "restriction_accommodation": "Resolve work restriction accommodation",
        "missed_assessments": "Address repeated missed medical assessments",
        "illness_control": "Implement occupational illness control",
    }[payload.issue_type]
    action = create_corrective_action(db, CorrectiveActionCreate(
        site_id=worker.assigned_site_id, department_id=worker.department_id,
        responsible_department_id=worker.department_id, title=title,
        description=f"Operational occupational-health issue ({payload.issue_type}); confidential medical detail is intentionally excluded.",
        acceptance_criteria="The operational health requirement is resolved and evidence is recorded by an authorised user.",
        source_type=CorrectiveActionSourceType.occupational_health,
        source_id=payload.source_id,
        source_metadata={"occupational_health_issue_type": payload.issue_type, "backlink": "/medical-surveillance"},
        priority="high", owner_user_id=payload.owner_user_id, current_due_date=payload.due_date,
    ), current_user_id=actor_id)
    _audit(db, actor_id=actor_id, action="occupational_health.action.generate", resource="occupational_health", resource_id=payload.source_id)
    return action


EXPORT_COLUMNS = {
    "compliance": ("employee_user_id", "site_id", "department_id", "surveillance_type", "compliance_status", "fitness_outcome", "due_date", "next_due_date", "expiry_date"),
    "due-overdue": ("employee_user_id", "site_id", "surveillance_type", "compliance_status", "due_date", "next_due_date"),
    "appointments": ("worker_user_id", "programme_id", "site_id", "appointment_at", "location", "status"),
    "certificates": ("worker_user_id", "programme_id", "certificate_number", "issued_date", "expiry_date", "fitness_outcome", "renewal_status"),
    "restrictions": ("worker_user_id", "restriction_type", "description", "effective_from", "effective_to", "permanent", "review_date", "status"),
    "medical-detail": ("worker_user_id", "programme_id", "assessment_type", "assessment_date", "fitness_outcome", "confidential_notes", "clinical_results"),
}


def export_csv(db: Session, export_type: str, *, site_id: Optional[int] = None, department_id: Optional[int] = None, medical_detail: bool = False) -> str:
    if export_type not in EXPORT_COLUMNS: raise OccupationalHealthValidation("Unsupported export type")
    if export_type == "medical-detail" and not medical_detail: raise OccupationalHealthValidation("Medical-detail permission is required")
    if export_type in {"compliance", "due-overdue"}:
        records = list(db.scalars(_scoped_statement(MedicalSurveillanceRecord, site_id=site_id, department_id=department_id)).all())
        if export_type == "due-overdue": records = [item for item in records if calculate_record_compliance(item) in {SurveillanceComplianceStatus.due_soon, SurveillanceComplianceStatus.overdue, SurveillanceComplianceStatus.pending_assessment}]
    elif export_type == "appointments": records = list_appointments(db, site_id=site_id)
    elif export_type == "certificates": records = list_certificates(db, site_id=site_id)
    elif export_type == "restrictions": records = list_restrictions(db, site_id=site_id)
    else: records = list_assessments(db, site_id=site_id)
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS[export_type]); writer.writeheader()
    for record in records:
        data = serialize(record, medical_detail=medical_detail)
        writer.writerow({field: data.get(field) for field in EXPORT_COLUMNS[export_type]})
    return output.getvalue()
