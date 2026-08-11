from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.sio import SIOObservationNature, SIOStatus, SIOUrgency, SafetyImprovementObservation
from app.models.user import User
from app.schemas.sio import SIOCreate, SIOEscalationOptions, SIOListRead, SIORead, SIOUpdate
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope
from app.services.sio_service import (
    SIODuplicateError,
    SIOEscalationValidationError,
    SIOLinkAlreadyExistsError,
    SIONotFoundError,
    SIOSiteNotFoundError,
    SIOUserNotFoundError,
    create_linked_corrective_action,
    create_linked_hazard,
    create_linked_incident,
    create_sio,
    get_sio,
    list_sios,
    update_sio,
)

router = APIRouter()


def _not_found(exc: Exception) -> HTTPException:
    if isinstance(exc, SIOSiteNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    if isinstance(exc, SIOUserNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIO not found")


@router.get("", response_model=SIOListRead)
def read_sios(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None,
    department: Optional[str] = None,
    source_type: Optional[str] = None,
    sio_status: Optional[SIOStatus] = Query(default=None, alias="status"),
    observation_nature: Optional[SIOObservationNature] = None,
    urgency: Optional[SIOUrgency] = None,
    category: Optional[str] = None,
    incident_classification: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_sios(
        db,
        skip=skip,
        limit=limit,
        site_id=site_id,
        department=department,
        source_type=source_type,
        status=sio_status,
        observation_nature=observation_nature,
        urgency=urgency,
        category=category,
        incident_classification=incident_classification,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


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
    except (SIOSiteNotFoundError, SIOUserNotFoundError) as exc:
        raise _not_found(exc)
    except SIODuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/{sio_id}", response_model=SIORead)
def read_sio_record(
    sio_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_VIEW)
    try:
        sio = get_sio(db, sio_id)
        ensure_site_access(current_user, sio.site_id)
        return sio
    except SIONotFoundError as exc:
        raise _not_found(exc)


@router.patch("/{sio_id}", response_model=SIORead)
def patch_sio_record(
    sio_id: int,
    sio_in: SIOUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyImprovementObservation:
    ensure_permission(current_user, Permission.SIOS_EDIT)
    try:
        sio = get_sio(db, sio_id)
        ensure_site_access(current_user, sio.site_id)
        if sio_in.site_id is not None:
            sio_in = sio_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, sio_in.site_id)}
            )
        return update_sio(db, sio, sio_in, actor_id=current_user.id)
    except (SIONotFoundError, SIOSiteNotFoundError, SIOUserNotFoundError) as exc:
        raise _not_found(exc)


def _get_scoped_sio(db: Session, current_user: User, sio_id: int) -> SafetyImprovementObservation:
    try:
        sio = get_sio(db, sio_id)
    except SIONotFoundError as exc:
        raise _not_found(exc)
    ensure_site_access(current_user, sio.site_id)
    return sio


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


@router.post(
    "/{sio_id}/create-corrective-action",
    response_model=SIORead,
    status_code=status.HTTP_201_CREATED,
)
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
