from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.corrective_action import CorrectiveAction
from app.models.incident import Incident, IncidentInjury, IncidentLink, IncidentReturnToWork, IncidentSeverity, IncidentStatus, IncidentTreatment, RegulatoryNotificationStatus
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionRead
from app.schemas.incident import (
    ClosureDecision, ClosureRequest, EnvironmentalDetailCreate, EnvironmentalDetailRead,
    IncidentActionCreate, IncidentCauseCategoryCreate, IncidentCauseCategoryRead,
    IncidentCauseCreate, IncidentCauseRead, IncidentClassificationCreate,
    IncidentClassificationRead, IncidentCreate, IncidentDashboardRead, IncidentEventCreate,
    IncidentEventRead, IncidentFindingCreate, IncidentFindingRead, IncidentInjuryCreate,
    IncidentInjuryRead, IncidentLinkCreate, IncidentLinkRead, IncidentListRead,
    IncidentMedicalRead, IncidentPersonCreate, IncidentPersonRead, IncidentRead, IncidentTreatmentCreate,
    IncidentTreatmentRead, IncidentUpdate, IncidentWitnessCreate, IncidentWitnessRead,
    IncidentWorkspaceRead, PropertyDamageCreate, PropertyDamageRead,
    RegulatoryNotificationCreate, RegulatoryNotificationRead, ReopenRequest,
    ReturnToWorkCreate, ReturnToWorkRead, ReturnToWorkUpdate,
    VehicleDetailCreate, VehicleDetailRead,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.incident_investigation_service import incident_has_completed_investigation
from app.services.incident_management_service import (
    IncidentClosureError, IncidentManagementError, create_cause, create_cause_category,
    create_classification, create_event, create_finding, create_incident_action,
    create_injury, create_link, create_person, create_property_damage,
    create_regulatory_notification, create_return_to_work, create_treatment,
    create_witness, incident_dashboard, list_cause_categories, list_classifications,
    reopen_incident, request_closure, update_return_to_work, upsert_environmental_detail,
    upsert_vehicle_detail, verify_closure,
)
from app.services.incident_service import (
    IncidentNotFoundError, IncidentSiteNotFoundError, IncidentTransitionError,
    IncidentValidationError, create_incident as create_incident_record,
    get_incident as get_incident_record, list_incidents as list_incident_records,
    update_incident as update_incident_record,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope

router = APIRouter()
MANAGER_INCIDENT_STATUSES = {IncidentStatus.resolved, IncidentStatus.closed, IncidentStatus.cancelled}


def _management_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _incident(db: Session, current_user: User, incident_id: int) -> Incident:
    try:
        record = get_incident_record(db, incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    ensure_site_access(current_user, record.site_id)
    return record


@router.get("", response_model=IncidentListRead)
def list_incidents(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
    incident_status: Optional[IncidentStatus] = Query(default=None, alias="status"),
    severity: Optional[IncidentSeverity] = None, site_id: Optional[int] = None,
    department_id: Optional[int] = None, incident_type: Optional[str] = None,
    regulator_status: Optional[RegulatoryNotificationStatus] = None,
    responsible_investigator_user_id: Optional[int] = None, open_only: Optional[bool] = None,
    queue: Optional[str] = Query(default=None, pattern="^(reported_by_me|critical_open|awaiting_closure_verification)$"),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_incident_records(
        db, skip=skip, limit=limit, status=incident_status, severity=severity, site_id=site_id,
        department_id=department_id, incident_type=incident_type, regulator_status=regulator_status,
        responsible_investigator_user_id=responsible_investigator_user_id, open_only=open_only,
        reported_by_user_id=current_user.id if queue == "reported_by_me" else None,
        closure_verifier_user_id=current_user.id if queue == "awaiting_closure_verification" else None,
        critical_open=queue == "critical_open",
    )


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_CREATE)
    if incident_in.status in MANAGER_INCIDENT_STATUSES and not has_permission(current_user, Permission.INCIDENTS_CLOSE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to close incidents")
    incident_in = incident_in.model_copy(update={"site_id": resolve_site_scope(current_user, incident_in.site_id)})
    try:
        return create_incident_record(db, incident_in, reported_by_id=current_user.id)
    except IncidentSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except IncidentValidationError as exc:
        raise _management_error(exc)


# Static catalogue and dashboard routes must precede /{incident_id}.
@router.get("/classifications", response_model=list[IncidentClassificationRead])
def classifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    return list_classifications(db)


@router.post("/classifications", response_model=IncidentClassificationRead, status_code=201)
def add_classification(payload: IncidentClassificationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_CONFIGURE)
    try: return create_classification(db, payload)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.get("/cause-categories", response_model=list[IncidentCauseCategoryRead])
def cause_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    return list_cause_categories(db)


@router.post("/cause-categories", response_model=IncidentCauseCategoryRead, status_code=201)
def add_cause_category(payload: IncidentCauseCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_CONFIGURE)
    try: return create_cause_category(db, payload)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.get("/dashboard", response_model=IncidentDashboardRead)
def dashboard(site_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    return incident_dashboard(db, site_id=resolve_site_scope(current_user, site_id), date_from=date_from, date_to=date_to)


@router.get("/linked/{entity_type}/{entity_id}", response_model=list[IncidentRead])
def linked_incidents(entity_type: str, entity_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    if entity_type not in {"hazard", "sio", "ppe_issue", "ppe_inspection", "asset"}:
        raise HTTPException(status_code=422, detail="Unsupported linked entity type")
    records = list(db.scalars(
        select(Incident).join(IncidentLink).where(
            IncidentLink.linked_entity_type == entity_type,
            IncidentLink.linked_entity_id == entity_id,
        )
    ).unique().all())
    for record in records:
        ensure_site_access(current_user, record.site_id)
    return records


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    return hydrate_entity_attachments(db, AttachmentEntityType.incident, _incident(db, current_user, incident_id))


@router.get("/{incident_id}/workspace", response_model=IncidentWorkspaceRead)
def get_workspace(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_VIEW)
    return hydrate_entity_attachments(db, AttachmentEntityType.incident, _incident(db, current_user, incident_id))


@router.get("/{incident_id}/medical", response_model=IncidentMedicalRead)
def get_medical(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    ensure_permission(current_user, Permission.INCIDENT_MEDICAL_VIEW)
    incident = _incident(db, current_user, incident_id)
    return {
        "injuries": list(db.scalars(select(IncidentInjury).where(IncidentInjury.incident_id == incident.id)).all()),
        "treatments": list(db.scalars(select(IncidentTreatment).where(IncidentTreatment.incident_id == incident.id)).all()),
        "return_to_work_records": list(db.scalars(select(IncidentReturnToWork).where(IncidentReturnToWork.incident_id == incident.id)).all()),
    }


@router.patch("/{incident_id}", response_model=IncidentRead)
def patch_incident(incident_id: int, incident_in: IncidentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Incident:
    ensure_permission(current_user, Permission.INCIDENTS_EDIT)
    incident = _incident(db, current_user, incident_id)
    next_status = incident_in.status or incident.status
    if next_status in MANAGER_INCIDENT_STATUSES and not has_permission(current_user, Permission.INCIDENTS_CLOSE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to close incidents")
    # Preserve the legacy close API but require its historical investigation guard.
    if next_status == IncidentStatus.closed and incident.severity in {IncidentSeverity.high, IncidentSeverity.critical} and not incident_has_completed_investigation(db, incident_id=incident.id):
        raise HTTPException(status_code=422, detail="High and critical incidents require a completed investigation before closure")
    try: return update_incident_record(db, incident, incident_in, actor_id=current_user.id)
    except IncidentSiteNotFoundError: raise HTTPException(status_code=404, detail="Site not found")
    except (IncidentValidationError, IncidentTransitionError) as exc: raise _management_error(exc)


@router.post("/{incident_id}/people", response_model=IncidentPersonRead, status_code=201)
def add_person(incident_id: int, payload: IncidentPersonCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MANAGE)
    try: return create_person(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/injuries", response_model=IncidentInjuryRead, status_code=201)
def add_injury(incident_id: int, payload: IncidentInjuryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MEDICAL_MANAGE)
    try: return create_injury(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/treatments", response_model=IncidentTreatmentRead, status_code=201)
def add_treatment(incident_id: int, payload: IncidentTreatmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MEDICAL_MANAGE)
    try: return create_treatment(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/witnesses", response_model=IncidentWitnessRead, status_code=201)
def add_witness(incident_id: int, payload: IncidentWitnessCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_INVESTIGATE)
    try: return create_witness(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/events", response_model=IncidentEventRead, status_code=201)
def add_event(incident_id: int, payload: IncidentEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_INVESTIGATE)
    try: return create_event(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/causes", response_model=IncidentCauseRead, status_code=201)
def add_cause(incident_id: int, payload: IncidentCauseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_INVESTIGATE)
    try: return create_cause(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/findings", response_model=IncidentFindingRead, status_code=201)
def add_finding(incident_id: int, payload: IncidentFindingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_INVESTIGATE)
    try: return create_finding(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/actions", response_model=CorrectiveActionRead, status_code=201)
def add_action(incident_id: int, payload: IncidentActionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CorrectiveAction:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_CREATE)
    try: return create_incident_action(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except (IncidentManagementError, ValueError) as exc: raise _management_error(exc)


@router.post("/{incident_id}/regulatory", response_model=RegulatoryNotificationRead, status_code=201)
def add_regulatory(incident_id: int, payload: RegulatoryNotificationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_REGULATORY_MANAGE)
    try: return create_regulatory_notification(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/return-to-work", response_model=ReturnToWorkRead, status_code=201)
def add_return_to_work(incident_id: int, payload: ReturnToWorkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MEDICAL_MANAGE)
    try: return create_return_to_work(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.patch("/{incident_id}/return-to-work/{record_id}", response_model=ReturnToWorkRead)
def patch_return_to_work(incident_id: int, record_id: int, payload: ReturnToWorkUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MEDICAL_MANAGE)
    try: return update_return_to_work(db, _incident(db, current_user, incident_id), record_id, payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/links", response_model=IncidentLinkRead, status_code=201)
def add_link(incident_id: int, payload: IncidentLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_INVESTIGATE)
    try: return create_link(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/property-damage", response_model=PropertyDamageRead, status_code=201)
def add_property_damage(incident_id: int, payload: PropertyDamageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MANAGE)
    try: return create_property_damage(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.put("/{incident_id}/environmental", response_model=EnvironmentalDetailRead)
def put_environmental(incident_id: int, payload: EnvironmentalDetailCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MANAGE)
    try: return upsert_environmental_detail(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.put("/{incident_id}/vehicle", response_model=VehicleDetailRead)
def put_vehicle(incident_id: int, payload: VehicleDetailCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_MANAGE)
    try: return upsert_vehicle_detail(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentManagementError as exc: raise _management_error(exc)


@router.post("/{incident_id}/closure/request", response_model=IncidentRead)
def close_request(incident_id: int, payload: ClosureRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENTS_CLOSE)
    try: return request_closure(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentClosureError as exc: raise _management_error(exc)


@router.post("/{incident_id}/closure/verify", response_model=IncidentRead)
def close_verify(incident_id: int, payload: ClosureDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENT_VERIFY)
    try: return verify_closure(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentClosureError as exc: raise _management_error(exc)


@router.post("/{incident_id}/reopen", response_model=IncidentRead)
def reopen(incident_id: int, payload: ReopenRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.INCIDENTS_CLOSE)
    try: return reopen_incident(db, _incident(db, current_user, incident_id), payload, current_user.id)
    except IncidentClosureError as exc: raise _management_error(exc)
