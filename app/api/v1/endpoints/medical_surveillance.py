from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.medical_surveillance import (
    MedicalAppointmentStatus,
    MedicalSurveillanceStatus,
    OccupationalIllnessStatus,
    SurveillanceComplianceStatus,
    WorkRestrictionStatus,
)
from app.models.user import User
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
    MedicalSurveillanceCreate,
    MedicalSurveillanceUpdate,
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
from app.services.medical_surveillance_service import (
    MedicalSurveillanceNotFoundError,
    MedicalSurveillanceValidationError,
    create_medical_surveillance_record,
    get_medical_surveillance_record,
    list_medical_surveillance_records,
    update_medical_surveillance_record,
)
from app.services.occupational_health_service import (
    OccupationalHealthNotFound,
    OccupationalHealthValidation,
    create_appointment,
    create_assessment,
    create_certificate,
    create_clinic_encounter,
    create_exposure,
    create_exposure_type,
    create_illness,
    create_programme,
    create_provider,
    create_requirement,
    create_restriction,
    dashboard,
    export_csv,
    generate_action,
    generate_reminders,
    list_appointments,
    list_assessments,
    list_certificates,
    list_clinic_encounters,
    list_exposure_types,
    list_exposures,
    list_illnesses,
    list_programmes,
    list_providers,
    list_requirements,
    list_restrictions,
    prerequisite_status,
    refresh_compliance,
    serialize,
    update_appointment,
    update_certificate,
    update_clinic_encounter,
    update_exposure,
    update_exposure_type,
    update_illness,
    update_programme,
    update_provider,
    update_requirement,
    update_restriction,
    worker_profile,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope

router = APIRouter()


def _detail(user: User) -> bool:
    return has_permission(user, Permission.OCCUPATIONAL_HEALTH_MEDICAL_DETAIL_VIEW)


def _manage(user: User) -> None:
    ensure_permission(user, Permission.MEDICAL_SURVEILLANCE_MANAGE)


def _medical_manage(user: User) -> None:
    ensure_permission(user, Permission.OCCUPATIONAL_HEALTH_MEDICAL_DETAIL_MANAGE)


def _compliance_access(user: User, *, worker_id: Optional[int] = None, site_id: Optional[int] = None) -> None:
    if worker_id == user.id and has_permission(user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW):
        return
    ensure_permission(user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE)
    ensure_site_access(user, site_id)


def _restriction_access(user: User, *, worker_id: Optional[int] = None, site_id: Optional[int] = None) -> None:
    if worker_id == user.id and has_permission(user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW):
        return
    ensure_permission(user, Permission.OCCUPATIONAL_HEALTH_RESTRICTIONS_VIEW)
    ensure_site_access(user, site_id)


def _ensure_worker_scope(db: Session, user: User, worker_id: Optional[int]) -> None:
    if worker_id is None or worker_id == user.id:
        return
    worker = db.get(User, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    ensure_site_access(user, worker.assigned_site_id)


def _translate_error(exc: Exception) -> HTTPException:
    message = str(exc)
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND if isinstance(exc, (OccupationalHealthNotFound, MedicalSurveillanceNotFoundError)) or "not found" in message.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )


@router.get("/dashboard")
def read_dashboard(
    site_id: Optional[int] = None, department_id: Optional[int] = None, as_of: Optional[date] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if not has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_REPORTS_VIEW):
        ensure_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE)
    site_id = resolve_site_scope(current_user, site_id)
    return dashboard(db, site_id=site_id, department_id=department_id, as_of=as_of)


@router.get("/programmes")
def read_programmes(active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _compliance_access(current_user, worker_id=current_user.id if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) else None)
    return list_programmes(db, active=active)


@router.post("/programmes", status_code=status.HTTP_201_CREATED)
def add_programme(payload: SurveillanceProgrammeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_programme(db, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/programmes/{record_id}")
def patch_programme(record_id: int, payload: SurveillanceProgrammeUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return update_programme(db, record_id, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/requirements")
def read_requirements(programme_id: Optional[int] = None, site_id: Optional[int] = None, active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _compliance_access(current_user)
    site_id = resolve_site_scope(current_user, site_id)
    return list_requirements(db, programme_id=programme_id, site_id=site_id, active=active)


@router.post("/requirements", status_code=status.HTTP_201_CREATED)
def add_requirement(payload: SurveillanceRequirementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: resolve_site_scope(current_user, payload.site_id)
    try: return create_requirement(db, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/requirements/{record_id}")
def patch_requirement(record_id: int, payload: SurveillanceRequirementUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: resolve_site_scope(current_user, payload.site_id)
    try: return update_requirement(db, record_id, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/exposure-types")
def read_exposure_types(active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _compliance_access(current_user, worker_id=current_user.id if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) else None)
    return list_exposure_types(db, active=active)


@router.post("/exposure-types", status_code=status.HTTP_201_CREATED)
def add_exposure_type(payload: ExposureTypeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_exposure_type(db, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/exposure-types/{record_id}")
def patch_exposure_type(record_id: int, payload: ExposureTypeUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return update_exposure_type(db, record_id, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/providers")
def read_providers(active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    return list_providers(db, active=active)


@router.post("/providers", status_code=status.HTTP_201_CREATED)
def add_provider(payload: MedicalProviderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_provider(db, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/providers/{record_id}")
def patch_provider(record_id: int, payload: MedicalProviderUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return update_provider(db, record_id, payload, actor_id=current_user.id)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/appointments")
def read_appointments(worker_user_id: Optional[int] = None, site_id: Optional[int] = None, status_filter: Optional[MedicalAppointmentStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id)
    _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item) for item in list_appointments(db, worker_user_id=worker_user_id, site_id=site_id, status=status_filter)]


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
def add_appointment(payload: MedicalAppointmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.notes: _medical_manage(current_user)
    if payload.site_id is not None: resolve_site_scope(current_user, payload.site_id)
    try: return serialize(create_appointment(db, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/appointments/{record_id}")
def patch_appointment(record_id: int, payload: MedicalAppointmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if "notes" in payload.model_fields_set: _medical_manage(current_user)
    try: return serialize(update_appointment(db, record_id, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/assessments")
def read_assessments(worker_user_id: Optional[int] = None, programme_id: Optional[int] = None, site_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item, medical_detail=_detail(current_user)) for item in list_assessments(db, worker_user_id=worker_user_id, programme_id=programme_id, site_id=site_id)]


@router.post("/assessments", status_code=status.HTTP_201_CREATED)
def add_assessment(payload: MedicalAssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _medical_manage(current_user)
    try: return serialize(create_assessment(db, payload, actor_id=current_user.id), medical_detail=True)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/certificates")
def read_certificates(worker_user_id: Optional[int] = None, programme_id: Optional[int] = None, site_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item, medical_detail=_detail(current_user)) for item in list_certificates(db, worker_user_id=worker_user_id, programme_id=programme_id, site_id=site_id)]


@router.post("/certificates", status_code=status.HTTP_201_CREATED)
def add_certificate(payload: FitnessCertificateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.OCCUPATIONAL_HEALTH_FITNESS_MANAGE)
    if payload.certificate_file_reference: _medical_manage(current_user)
    try: return serialize(create_certificate(db, payload, actor_id=current_user.id), medical_detail=_detail(current_user))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/certificates/{record_id}")
def patch_certificate(record_id: int, payload: FitnessCertificateUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.OCCUPATIONAL_HEALTH_FITNESS_MANAGE)
    try: return serialize(update_certificate(db, record_id, payload, actor_id=current_user.id), medical_detail=_detail(current_user))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/restrictions")
def read_restrictions(worker_user_id: Optional[int] = None, site_id: Optional[int] = None, status_filter: Optional[WorkRestrictionStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_RESTRICTIONS_VIEW): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _restriction_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item) for item in list_restrictions(db, worker_user_id=worker_user_id, site_id=site_id, status=status_filter)]


@router.post("/restrictions", status_code=status.HTTP_201_CREATED)
def add_restriction(payload: WorkRestrictionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.OCCUPATIONAL_HEALTH_FITNESS_MANAGE)
    try: return serialize(create_restriction(db, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/restrictions/{record_id}")
def patch_restriction(record_id: int, payload: WorkRestrictionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.OCCUPATIONAL_HEALTH_FITNESS_MANAGE)
    try: return serialize(update_restriction(db, record_id, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/exposures")
def read_exposures(worker_user_id: Optional[int] = None, site_id: Optional[int] = None, exposure_type_id: Optional[int] = None, active_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item) for item in list_exposures(db, worker_user_id=worker_user_id, site_id=site_id, exposure_type_id=exposure_type_id, active_only=active_only)]


@router.post("/exposures", status_code=status.HTTP_201_CREATED)
def add_exposure(payload: WorkerExposureCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: resolve_site_scope(current_user, payload.site_id)
    try: return serialize(create_exposure(db, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/exposures/{record_id}")
def patch_exposure(record_id: int, payload: WorkerExposureUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return serialize(update_exposure(db, record_id, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/occupational-illnesses")
def read_illnesses(worker_user_id: Optional[int] = None, site_id: Optional[int] = None, status_filter: Optional[OccupationalIllnessStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item, medical_detail=_detail(current_user)) for item in list_illnesses(db, worker_user_id=worker_user_id, site_id=site_id, status=status_filter)]


@router.post("/occupational-illnesses", status_code=status.HTTP_201_CREATED)
def add_illness(payload: OccupationalIllnessCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _medical_manage(current_user)
    try: return serialize(create_illness(db, payload, actor_id=current_user.id), medical_detail=True)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/occupational-illnesses/{record_id}")
def patch_illness(record_id: int, payload: OccupationalIllnessUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _medical_manage(current_user)
    try: return serialize(update_illness(db, record_id, payload, actor_id=current_user.id), medical_detail=True)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/clinic-encounters")
def read_clinic_encounters(worker_user_id: Optional[int] = None, site_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): worker_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, worker_user_id); _compliance_access(current_user, worker_id=worker_user_id, site_id=site_id)
    return [serialize(item, medical_detail=_detail(current_user)) for item in list_clinic_encounters(db, worker_user_id=worker_user_id, site_id=site_id)]


@router.post("/clinic-encounters", status_code=status.HTTP_201_CREATED)
def add_clinic_encounter(payload: ClinicEncounterCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _medical_manage(current_user)
    try: return serialize(create_clinic_encounter(db, payload, actor_id=current_user.id), medical_detail=True)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.patch("/clinic-encounters/{record_id}")
def patch_clinic_encounter(record_id: int, payload: ClinicEncounterUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _medical_manage(current_user)
    try: return serialize(update_clinic_encounter(db, record_id, payload, actor_id=current_user.id), medical_detail=True)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/workers/{worker_id}/profile")
def read_worker_profile(worker_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_worker_scope(db, current_user, worker_id); _compliance_access(current_user, worker_id=worker_id)
    try: return worker_profile(db, worker_id, medical_detail=_detail(current_user))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.get("/workers/{worker_id}/prerequisites")
def read_prerequisites(worker_id: int, programme_codes: Optional[list[str]] = Query(default=None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _ensure_worker_scope(db, current_user, worker_id); _compliance_access(current_user, worker_id=worker_id)
    try: return prerequisite_status(db, worker_id, programme_codes=programme_codes)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.post("/actions", status_code=status.HTTP_201_CREATED)
def add_action(payload: ActionGenerationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return serialize(generate_action(db, payload, actor_id=current_user.id))
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)


@router.post("/reminders/run")
def run_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user); refresh_compliance(db)
    return generate_reminders(db)


@router.get("/exports/{export_type}.csv")
def download_export(export_type: str, site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.OCCUPATIONAL_HEALTH_REPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    medical_detail = _detail(current_user)
    try: content = export_csv(db, export_type, site_id=site_id, department_id=department_id, medical_detail=medical_detail)
    except (OccupationalHealthValidation, OccupationalHealthNotFound) as exc: raise _translate_error(exc)
    from app.services.audit_service import write_audit_log
    write_audit_log(db, actor_id=current_user.id, action="occupational_health.export", resource_type="medical_export", resource_id=None, details={"export_type": export_type, "medical_detail": export_type == "medical-detail"})
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="occupational-health-{export_type}.csv"'})


# Compatibility routes for the original medical-surveillance assignment API.
@router.get("")
def read_medical_surveillance_records(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
    status_filter: Optional[MedicalSurveillanceStatus] = Query(default=None, alias="status"),
    compliance_status: Optional[SurveillanceComplianceStatus] = None,
    site_id: Optional[int] = None, department_id: Optional[int] = None,
    programme_id: Optional[int] = None, employee_user_id: Optional[int] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if has_permission(current_user, Permission.OCCUPATIONAL_HEALTH_SELF_VIEW) and not has_permission(current_user, Permission.MEDICAL_SURVEILLANCE_VIEW_COMPLIANCE): employee_user_id = current_user.id
    site_id = resolve_site_scope(current_user, site_id); _ensure_worker_scope(db, current_user, employee_user_id); _compliance_access(current_user, worker_id=employee_user_id, site_id=site_id)
    refresh_compliance(db)
    result = list_medical_surveillance_records(db, skip=skip, limit=limit, status=status_filter, site_id=site_id, employee_user_id=employee_user_id)
    items = result["items"]
    if department_id is not None: items = [item for item in items if item.department_id == department_id]
    if programme_id is not None: items = [item for item in items if item.programme_id == programme_id]
    if compliance_status is not None: items = [item for item in items if item.compliance_status == compliance_status]
    result["items"] = [serialize(item, medical_detail=_detail(current_user)) for item in items]
    result["total"] = len(items) if any(value is not None for value in (department_id, programme_id, compliance_status)) else result["total"]
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_medical_surveillance_entry(payload: MedicalSurveillanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.results_summary or payload.notes or payload.attachments_metadata: _medical_manage(current_user)
    if payload.site_id is not None: payload = payload.model_copy(update={"site_id": resolve_site_scope(current_user, payload.site_id)})
    try: return serialize(create_medical_surveillance_record(db, payload, actor_id=current_user.id), medical_detail=_detail(current_user))
    except (MedicalSurveillanceValidationError, MedicalSurveillanceNotFoundError) as exc: raise _translate_error(exc)


@router.get("/{record_id}")
def read_medical_surveillance_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        record = get_medical_surveillance_record(db, record_id)
        _compliance_access(current_user, worker_id=record.employee_user_id, site_id=record.site_id)
        return serialize(record, medical_detail=_detail(current_user))
    except (MedicalSurveillanceNotFoundError, MedicalSurveillanceValidationError) as exc: raise _translate_error(exc)


@router.patch("/{record_id}")
def patch_medical_surveillance_record(record_id: int, payload: MedicalSurveillanceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    confidential = {"results_summary", "notes", "attachments_metadata"}.intersection(payload.model_fields_set)
    if confidential: _medical_manage(current_user)
    try:
        record = get_medical_surveillance_record(db, record_id); ensure_site_access(current_user, record.site_id)
        if payload.site_id is not None: payload = payload.model_copy(update={"site_id": resolve_site_scope(current_user, payload.site_id)})
        return serialize(update_medical_surveillance_record(db, record, payload, actor_id=current_user.id), medical_detail=_detail(current_user))
    except (MedicalSurveillanceNotFoundError, MedicalSurveillanceValidationError) as exc: raise _translate_error(exc)
