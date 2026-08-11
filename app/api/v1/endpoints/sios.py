from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.sio import SIOObservationNature, SIOStatus, SIOUrgency, SafetyImprovementObservation
from app.models.user import User
from app.schemas.sio import (
    SIOActivityRead,
    SIOAssignmentDecision,
    SIOAssignmentRequest,
    SIOBulkExportRequest,
    SIOBulkRequest,
    SIOBulkResult,
    SIOClosureRequest,
    SIOCommentCreate,
    SIOCommentRead,
    SIOCreate,
    SIOEscalationOptions,
    SIOInvestigationUpdate,
    SIOListRead,
    SIORead,
    SIOReasonRequest,
    SIOTransitionRequest,
    SIOUpdate,
    SIOVerificationRequest,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope
from app.services.sio_service import (
    SIOAssignmentError,
    SIODepartmentNotFoundError,
    SIODuplicateError,
    SIOEscalationValidationError,
    SIOLinkAlreadyExistsError,
    SIONotFoundError,
    SIOServiceError,
    SIOSiteNotFoundError,
    SIOTransitionError,
    SIOUserNotFoundError,
    accept_sio_assignment,
    add_sio_comment,
    assign_sio,
    bulk_update_sios,
    create_linked_corrective_action,
    create_linked_hazard,
    create_linked_incident,
    create_sio,
    decline_sio_assignment,
    get_sio,
    list_sio_activity,
    list_sio_comments,
    list_sios,
    mark_sio_no_action_required,
    reopen_sio,
    request_sio_closure,
    transition_sio,
    update_sio,
    update_sio_investigation,
    verify_sio_closure,
)

router = APIRouter()


def _not_found(exc: Exception) -> HTTPException:
    if isinstance(exc, SIOSiteNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    if isinstance(exc, SIOUserNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    if isinstance(exc, SIODepartmentNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced department not found")
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIO not found")


def _workflow_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _get_scoped_sio(db: Session, current_user: User, sio_id: int) -> SafetyImprovementObservation:
    try:
        sio = get_sio(db, sio_id)
    except SIONotFoundError as exc:
        raise _not_found(exc)
    ensure_site_access(current_user, sio.site_id)
    return sio


def _can_manage_own_workflow(current_user: User, sio: SafetyImprovementObservation) -> bool:
    return sio.responsible_user_id == current_user.id


def _ensure_workflow_access(current_user: User, sio: SafetyImprovementObservation) -> None:
    if has_permission(current_user, Permission.SIOS_EDIT) or _can_manage_own_workflow(current_user, sio):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this SIO workflow")


@router.get("", response_model=SIOListRead)
def read_sios(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None,
    department: Optional[str] = None,
    department_id: Optional[int] = None,
    responsible_department_id: Optional[int] = None,
    responsible_user_id: Optional[int] = None,
    source_type: Optional[str] = None,
    sio_status: Optional[SIOStatus] = Query(default=None, alias="status"),
    observation_nature: Optional[SIOObservationNature] = None,
    urgency: Optional[SIOUrgency] = None,
    category: Optional[str] = None,
    incident_classification: Optional[str] = None,
    overdue: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    view: Optional[str] = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    if view == "awaiting_my_verification":
        ensure_permission(current_user, Permission.SIOS_VERIFY)
    site_id = resolve_site_scope(current_user, site_id)
    try:
        return list_sios(
            db,
            skip=skip,
            limit=limit,
            site_id=site_id,
            department=department,
            department_id=department_id,
            responsible_department_id=responsible_department_id,
            responsible_user_id=responsible_user_id,
            source_type=source_type,
            status=sio_status,
            observation_nature=observation_nature,
            urgency=urgency,
            category=category,
            incident_classification=incident_classification,
            overdue=overdue,
            date_from=date_from,
            date_to=date_to,
            search=search,
            view=view,
            current_user_id=current_user.id,
        )
    except SIOServiceError as exc:
        raise _workflow_error(exc)


@router.post("", response_model=SIORead, status_code=status.HTTP_201_CREATED)
def create_sio_record(
    sio_in: SIOCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_CREATE)
    sio_in = sio_in.model_copy(update={"site_id": resolve_site_scope(current_user, sio_in.site_id)})
    try:
        return create_sio(db, sio_in, actor_id=current_user.id)
    except (SIOSiteNotFoundError, SIOUserNotFoundError, SIODepartmentNotFoundError) as exc:
        raise _not_found(exc)
    except SIODuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _bulk_records(
    db: Session, current_user: User, sio_ids: list[int]
) -> list[SafetyImprovementObservation]:
    unique_ids = list(dict.fromkeys(sio_ids))
    records = list(
        db.scalars(
            select(SafetyImprovementObservation).where(
                SafetyImprovementObservation.id.in_(unique_ids)
            )
        ).all()
    )
    if len(records) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more SIO records were not found in the current organisation",
        )
    for sio in records:
        ensure_site_access(current_user, sio.site_id)
    return records


@router.post("/bulk", response_model=SIOBulkResult)
def bulk_update_sio_records(
    request: SIOBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    records = _bulk_records(db, current_user, request.sio_ids)
    try:
        updated = bulk_update_sios(db, records, request, actor_id=current_user.id)
    except (SIOServiceError, SIOTransitionError, SIOAssignmentError, SIOUserNotFoundError, SIODepartmentNotFoundError) as exc:
        raise _workflow_error(exc)
    return {"updated_ids": [item.id for item in updated], "count": len(updated)}


SIO_EXPORT_HEADERS = (
    "reference_number",
    "external_reference_id",
    "observation_date",
    "site_id",
    "department",
    "department_id",
    "responsible_department",
    "responsible_department_id",
    "responsible_user_id",
    "responsible_person_name",
    "source_type",
    "category",
    "observation_nature",
    "urgency",
    "status",
    "due_date",
    "age_days",
    "days_overdue",
    "investigation_required",
    "investigator_user_id",
    "immediate_cause",
    "underlying_cause",
    "root_cause",
    "investigation_summary",
    "lessons_learned",
    "closure_requested_at",
    "closure_notes",
    "verified_by_user_id",
    "verified_at",
    "verification_notes",
    "closed_at",
)


def _sio_csv(records: list[SafetyImprovementObservation]) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(SIO_EXPORT_HEADERS)
    for sio in records:
        writer.writerow(
            [
                getattr(value, "value", value).isoformat()
                if isinstance(value := getattr(sio, field), (date,))
                else getattr(value, "value", value)
                for field in SIO_EXPORT_HEADERS
            ]
        )
    return stream.getvalue()


@router.post("/bulk/export")
def export_selected_sios(
    request: SIOBulkExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    records = _bulk_records(db, current_user, request.sio_ids)
    return Response(
        content=_sio_csv(records),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sios-selected.csv"'},
    )


@router.get("/{sio_id}", response_model=SIORead)
def read_sio_record(
    sio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    return _get_scoped_sio(db, current_user, sio_id)


@router.patch("/{sio_id}", response_model=SIORead)
def patch_sio_record(
    sio_id: int,
    sio_in: SIOUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    sio = _get_scoped_sio(db, current_user, sio_id)
    if sio_in.site_id is not None:
        sio_in = sio_in.model_copy(update={"site_id": resolve_site_scope(current_user, sio_in.site_id)})
    try:
        return update_sio(db, sio, sio_in, actor_id=current_user.id)
    except (SIOSiteNotFoundError, SIOUserNotFoundError, SIODepartmentNotFoundError) as exc:
        raise _not_found(exc)
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/assign", response_model=SIORead)
def assign_sio_record(
    sio_id: int,
    request: SIOAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return assign_sio(db, sio, request, actor_id=current_user.id)
    except (SIOUserNotFoundError, SIODepartmentNotFoundError) as exc:
        raise _not_found(exc)


@router.post("/{sio_id}/assignment/accept", response_model=SIORead)
def accept_assignment(
    sio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return accept_sio_assignment(db, sio, actor_id=current_user.id)
    except SIOAssignmentError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/assignment/decline", response_model=SIORead)
def decline_assignment(
    sio_id: int,
    request: SIOAssignmentDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=422, detail="A decline reason is required")
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return decline_sio_assignment(db, sio, actor_id=current_user.id, reason=request.reason.strip())
    except SIOAssignmentError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/transition", response_model=SIORead)
def transition_sio_record(
    sio_id: int,
    request: SIOTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    sio = _get_scoped_sio(db, current_user, sio_id)
    _ensure_workflow_access(current_user, sio)
    try:
        return transition_sio(
            db,
            sio,
            target_status=request.status,
            actor_id=current_user.id,
            reason=request.reason,
        )
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


@router.patch("/{sio_id}/investigation", response_model=SIORead)
def patch_investigation(
    sio_id: int,
    request: SIOInvestigationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    sio = _get_scoped_sio(db, current_user, sio_id)
    if not has_permission(current_user, Permission.SIOS_EDIT) and sio.investigator_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this investigation")
    try:
        return update_sio_investigation(db, sio, request, actor_id=current_user.id)
    except SIOUserNotFoundError as exc:
        raise _not_found(exc)


@router.get("/{sio_id}/comments", response_model=list[SIOCommentRead])
def read_comments(
    sio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    _get_scoped_sio(db, current_user, sio_id)
    return list_sio_comments(db, sio_id)


@router.post("/{sio_id}/comments", response_model=SIOCommentRead, status_code=201)
def create_comment(
    sio_id: int,
    request: SIOCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.SIOS_VIEW)
    sio = _get_scoped_sio(db, current_user, sio_id)
    return add_sio_comment(db, sio, request, actor_id=current_user.id)


@router.get("/{sio_id}/activity", response_model=list[SIOActivityRead])
def read_activity(
    sio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    _get_scoped_sio(db, current_user, sio_id)
    return list_sio_activity(db, sio_id)


@router.post("/{sio_id}/request-closure", response_model=SIORead)
def request_closure(
    sio_id: int,
    request: SIOClosureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    sio = _get_scoped_sio(db, current_user, sio_id)
    _ensure_workflow_access(current_user, sio)
    try:
        return request_sio_closure(db, sio, actor_id=current_user.id, notes=request.notes)
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/verify", response_model=SIORead)
def verify_closure(
    sio_id: int,
    request: SIOVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VERIFY)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return verify_sio_closure(
            db,
            sio,
            actor_id=current_user.id,
            approved=request.approved,
            notes=request.notes,
        )
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/no-action-required", response_model=SIORead)
def no_action_required(
    sio_id: int,
    request: SIOReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VERIFY)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return mark_sio_no_action_required(db, sio, actor_id=current_user.id, reason=request.reason)
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


@router.post("/{sio_id}/reopen", response_model=SIORead)
def reopen_sio_record(
    sio_id: int,
    request: SIOReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VERIFY)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return reopen_sio(db, sio, actor_id=current_user.id, reason=request.reason)
    except SIOTransitionError as exc:
        raise _workflow_error(exc)


def _link_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SIOLinkAlreadyExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post("/{sio_id}/create-hazard", response_model=SIORead, status_code=status.HTTP_201_CREATED)
def create_hazard_from_sio(
    sio_id: int,
    options: Optional[SIOEscalationOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    ensure_permission(current_user, Permission.HAZARDS_CREATE)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return create_linked_hazard(db, sio, actor_id=current_user.id, options=options)
    except (SIOLinkAlreadyExistsError, SIOEscalationValidationError) as exc:
        raise _link_error(exc)


@router.post("/{sio_id}/create-incident", response_model=SIORead, status_code=status.HTTP_201_CREATED)
def create_incident_from_sio(
    sio_id: int,
    options: Optional[SIOEscalationOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    ensure_permission(current_user, Permission.INCIDENTS_CREATE)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return create_linked_incident(db, sio, actor_id=current_user.id, options=options)
    except (SIOLinkAlreadyExistsError, SIOEscalationValidationError) as exc:
        raise _link_error(exc)


@router.post("/{sio_id}/create-corrective-action", response_model=SIORead, status_code=status.HTTP_201_CREATED)
def create_corrective_action_from_sio(
    sio_id: int,
    options: Optional[SIOEscalationOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_CREATE)
    sio = _get_scoped_sio(db, current_user, sio_id)
    try:
        return create_linked_corrective_action(db, sio, actor_id=current_user.id, options=options)
    except (SIOLinkAlreadyExistsError, SIOEscalationValidationError) as exc:
        raise _link_error(exc)
