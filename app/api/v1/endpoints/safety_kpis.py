from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.safety_kpi import SafetyKPICreate, SafetyKPIListRead, SafetyKPIRead, SafetyKPIUpdate
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope
from app.services.safety_kpi_service import (
    SafetyKPIDuplicatePeriodError,
    SafetyKPINotFoundError,
    SafetyKPISiteNotFoundError,
    create_safety_kpi,
    get_safety_kpi,
    get_safety_kpi_read,
    list_safety_kpis,
    update_safety_kpi,
)

router = APIRouter()


@router.get("", response_model=SafetyKPIListRead)
def read_safety_kpis(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SAFETY_KPIS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_safety_kpis(db, skip=skip, limit=limit, site_id=site_id)


@router.post("", response_model=SafetyKPIRead, status_code=status.HTTP_201_CREATED)
def create_safety_kpi_record(
    record_in: SafetyKPICreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SAFETY_KPIS_CREATE)
    record_in = record_in.model_copy(update={"site_id": resolve_site_scope(current_user, record_in.site_id)})
    try:
        return create_safety_kpi(db, record_in, actor_id=current_user.id)
    except SafetyKPISiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except SafetyKPIDuplicatePeriodError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A KPI record already exists for that site and period")


@router.get("/{record_id}", response_model=SafetyKPIRead)
def read_safety_kpi_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SAFETY_KPIS_VIEW)
    try:
        record = get_safety_kpi(db, record_id)
        ensure_site_access(current_user, record.site_id)
        return get_safety_kpi_read(db, record_id)
    except SafetyKPINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety KPI record not found")


@router.patch("/{record_id}", response_model=SafetyKPIRead)
def patch_safety_kpi_record(
    record_id: int,
    record_in: SafetyKPIUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SAFETY_KPIS_EDIT)
    try:
        record = get_safety_kpi(db, record_id)
        ensure_site_access(current_user, record.site_id)
        if record_in.site_id is not None:
            record_in = record_in.model_copy(update={"site_id": resolve_site_scope(current_user, record_in.site_id)})
        return update_safety_kpi(db, record, record_in, actor_id=current_user.id)
    except SafetyKPINotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety KPI record not found")
    except SafetyKPISiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except SafetyKPIDuplicatePeriodError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A KPI record already exists for that site and period")
