from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.reporting import ReportingPeriodHistory, ReportingPeriodStatus
from app.models.user import User
from app.schemas.reporting import (
    ComparisonRead,
    ExceptionRead,
    ForwardViewItemRead,
    KPIDefinitionCreate,
    KPIDefinitionRead,
    KPIEnablementUpdate,
    KPISnapshotRead,
    KPITargetCreate,
    KPITargetRead,
    ManagementActionPlanCreate,
    ManagementActionPlanRead,
    ReportSectionRead,
    ReportSectionUpdate,
    ReportingPeriodCreate,
    ReportingPeriodHistoryRead,
    ReportingPeriodListRead,
    ReportingPeriodRead,
    ReportingReasonRequest,
    ScorecardRead,
    SnapshotGenerationRead,
    WorkforceExposureCreate,
    WorkforceExposureListRead,
    WorkforceExposureRead,
    WorkforceExposureUpdate,
)
from app.services.rbac import Permission, ensure_permission, is_site_scoped, resolve_site_scope
from app.services.reporting_export_service import (
    build_report_pdf,
    build_report_xlsx,
    record_report_export,
)
from app.services.reporting_insights import get_forward_view, get_management_exceptions
from app.services.reporting_service import (
    ReportingConflictError,
    ReportingLockedError,
    ReportingNotFoundError,
    ReportingTransitionError,
    add_management_action,
    approve_reporting_period,
    create_kpi_definition_version,
    create_kpi_target,
    create_reporting_period,
    create_workforce_exposure,
    generate_kpi_snapshots,
    get_comparison,
    get_kpi_drilldown,
    get_reporting_period,
    get_scorecard,
    list_kpi_definitions,
    list_kpi_targets,
    list_report_sections,
    list_reporting_periods,
    list_snapshots,
    list_workforce_exposures,
    lock_reporting_period,
    reopen_reporting_period,
    review_reporting_period,
    set_kpi_enablement,
    submit_reporting_period,
    update_report_section,
    update_workforce_exposure,
)


router = APIRouter()


def _not_site_scoped(user: User) -> None:
    if is_site_scoped(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organisation-wide reporting administration is not available for site-scoped users",
        )


def _period_or_404(db: Session, period_id: int):
    try:
        return get_reporting_period(db, period_id)
    except ReportingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporting period not found")


def _raise_reporting_error(exc: Exception) -> None:
    if isinstance(exc, ReportingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ReportingConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ReportingLockedError):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    if isinstance(exc, ReportingTransitionError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


@router.get("/periods", response_model=ReportingPeriodListRead)
def read_reporting_periods(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    period_status: Optional[ReportingPeriodStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    return list_reporting_periods(db, skip=skip, limit=limit, status=period_status)


@router.post("/periods", response_model=ReportingPeriodRead, status_code=status.HTTP_201_CREATED)
def create_period(
    period_in: ReportingPeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_PREPARE)
    _not_site_scoped(current_user)
    try:
        return create_reporting_period(db, period_in, actor_id=current_user.id)
    except (ReportingConflictError, ReportingNotFoundError, ReportingLockedError, ReportingTransitionError) as exc:
        _raise_reporting_error(exc)


@router.get("/periods/{period_id}", response_model=ReportingPeriodRead)
def read_period(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    return _period_or_404(db, period_id)


@router.get("/periods/{period_id}/history", response_model=list[ReportingPeriodHistoryRead])
def read_period_history(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    period = _period_or_404(db, period_id)
    return list(db.scalars(select(ReportingPeriodHistory).where(ReportingPeriodHistory.reporting_period_id == period.id).order_by(ReportingPeriodHistory.created_at)).all())


@router.post("/periods/{period_id}/snapshots", response_model=SnapshotGenerationRead)
def generate_period_snapshots(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_PREPARE)
    _not_site_scoped(current_user)
    period = _period_or_404(db, period_id)
    try:
        return generate_kpi_snapshots(db, period, actor_id=current_user.id)
    except (ReportingConflictError, ReportingLockedError) as exc:
        _raise_reporting_error(exc)


@router.get("/periods/{period_id}/snapshots", response_model=list[KPISnapshotRead])
def read_period_snapshots(
    period_id: int,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    period = _period_or_404(db, period_id)
    return list_snapshots(db, period, site_id=site_id, department_id=department_id)


@router.get("/periods/{period_id}/scorecard", response_model=ScorecardRead)
def read_scorecard(
    period_id: int,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    return get_scorecard(db, _period_or_404(db, period_id), site_id=site_id, department_id=department_id)


@router.get("/periods/{period_id}/kpis/{kpi_key}/drilldown")
def read_kpi_drilldown(
    period_id: int,
    kpi_key: str,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    try:
        return get_kpi_drilldown(
            db,
            _period_or_404(db, period_id),
            kpi_key=kpi_key,
            site_id=site_id,
            department_id=department_id,
        )
    except ReportingNotFoundError as exc:
        _raise_reporting_error(exc)


@router.get("/periods/{period_id}/sections", response_model=list[ReportSectionRead])
def read_sections(
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    return list_report_sections(db, _period_or_404(db, period_id))


@router.patch("/periods/{period_id}/sections/{section_key}", response_model=ReportSectionRead)
def patch_section(
    period_id: int,
    section_key: str,
    section_in: ReportSectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_PREPARE)
    _not_site_scoped(current_user)
    try:
        return update_report_section(db, _period_or_404(db, period_id), section_key, content=section_in.content, actor_id=current_user.id)
    except (ReportingNotFoundError, ReportingConflictError, ReportingLockedError) as exc:
        _raise_reporting_error(exc)


@router.post("/periods/{period_id}/management-actions", response_model=ManagementActionPlanRead, status_code=status.HTTP_201_CREATED)
def create_management_action(
    period_id: int,
    item_in: ManagementActionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_PREPARE)
    _not_site_scoped(current_user)
    try:
        return add_management_action(db, _period_or_404(db, period_id), item_in, actor_id=current_user.id)
    except (ReportingNotFoundError, ReportingConflictError, ReportingLockedError) as exc:
        _raise_reporting_error(exc)


def _lifecycle_command(db: Session, period_id: int, current_user: User, permission: str, command):
    ensure_permission(current_user, permission)
    _not_site_scoped(current_user)
    try:
        return command(db, _period_or_404(db, period_id), actor_id=current_user.id)
    except (ReportingTransitionError, ReportingConflictError, ReportingLockedError) as exc:
        _raise_reporting_error(exc)


@router.post("/periods/{period_id}/submit", response_model=ReportingPeriodRead)
def submit_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _lifecycle_command(db, period_id, current_user, Permission.REPORTING_PREPARE, submit_reporting_period)


@router.post("/periods/{period_id}/review", response_model=ReportingPeriodRead)
def review_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _lifecycle_command(db, period_id, current_user, Permission.REPORTING_REVIEW, review_reporting_period)


@router.post("/periods/{period_id}/approve", response_model=ReportingPeriodRead)
def approve_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _lifecycle_command(db, period_id, current_user, Permission.REPORTING_APPROVE, approve_reporting_period)


@router.post("/periods/{period_id}/lock", response_model=ReportingPeriodRead)
def lock_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _lifecycle_command(db, period_id, current_user, Permission.REPORTING_ADMIN, lock_reporting_period)


@router.post("/periods/{period_id}/reopen", response_model=ReportingPeriodRead)
def reopen_period(
    period_id: int,
    request: ReportingReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        return reopen_reporting_period(db, _period_or_404(db, period_id), actor_id=current_user.id, reason=request.reason)
    except (ReportingTransitionError, ReportingConflictError, ReportingLockedError) as exc:
        _raise_reporting_error(exc)


@router.get("/kpi-definitions", response_model=list[KPIDefinitionRead])
def read_kpi_definitions(
    include_inactive: bool = False,
    key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    return list_kpi_definitions(db, include_inactive=include_inactive, key=key)


@router.post("/kpi-definitions", response_model=KPIDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_kpi_definition(
    definition_in: KPIDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        return create_kpi_definition_version(db, definition_in, actor_id=current_user.id)
    except ReportingConflictError as exc:
        _raise_reporting_error(exc)


@router.put("/kpi-definitions/{kpi_key}/enablement")
def update_kpi_enablement(
    kpi_key: str,
    setting_in: KPIEnablementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        setting = set_kpi_enablement(db, kpi_key=kpi_key, is_enabled=setting_in.is_enabled, actor_id=current_user.id)
        return {"kpi_key": setting.kpi_key, "is_enabled": setting.is_enabled}
    except ReportingNotFoundError as exc:
        _raise_reporting_error(exc)


@router.get("/kpi-targets", response_model=list[KPITargetRead])
def read_kpi_targets(
    kpi_key: Optional[str] = None,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    return list_kpi_targets(db, kpi_key=kpi_key, site_id=site_id, department_id=department_id)


@router.post("/kpi-targets", response_model=KPITargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    target_in: KPITargetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        return create_kpi_target(db, target_in, actor_id=current_user.id)
    except (ReportingNotFoundError, ReportingConflictError) as exc:
        _raise_reporting_error(exc)


@router.get("/workforce-exposure", response_model=WorkforceExposureListRead)
def read_workforce_exposure(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    return list_workforce_exposures(db, skip=skip, limit=limit, site_id=site_id, department_id=department_id)


@router.post("/workforce-exposure", response_model=WorkforceExposureRead, status_code=status.HTTP_201_CREATED)
def create_exposure(
    exposure_in: WorkforceExposureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        return create_workforce_exposure(db, exposure_in, actor_id=current_user.id)
    except (ReportingNotFoundError, ReportingConflictError) as exc:
        _raise_reporting_error(exc)


@router.patch("/workforce-exposure/{exposure_id}", response_model=WorkforceExposureRead)
def patch_exposure(
    exposure_id: int,
    exposure_in: WorkforceExposureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_ADMIN)
    _not_site_scoped(current_user)
    try:
        return update_workforce_exposure(db, exposure_id, exposure_in, actor_id=current_user.id)
    except ReportingNotFoundError as exc:
        _raise_reporting_error(exc)


@router.get("/forward-view", response_model=list[ForwardViewItemRead])
def read_forward_view(
    as_of: date = Query(default_factory=date.today),
    window_days: int = Query(default=90),
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    try:
        return get_forward_view(db, as_of=as_of, window_days=window_days, site_id=site_id, department_id=department_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/exceptions", response_model=list[ExceptionRead])
def read_exceptions(
    as_of: date = Query(default_factory=date.today),
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    if department_id is not None and is_site_scoped(current_user):
        _not_site_scoped(current_user)
    return get_management_exceptions(db, as_of=as_of, site_id=site_id, department_id=department_id)


@router.get("/periods/{period_id}/site-comparison", response_model=ComparisonRead)
def read_site_comparison(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    period = _period_or_404(db, period_id)
    if is_site_scoped(current_user):
        comparison = get_comparison(db, period, scope="site")
        assigned_site = resolve_site_scope(current_user)
        comparison["rows"] = [row for row in comparison["rows"] if row["scope_id"] == assigned_site]
        return comparison
    return get_comparison(db, period, scope="site")


@router.get("/periods/{period_id}/department-comparison", response_model=ComparisonRead)
def read_department_comparison(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.REPORTING_VIEW)
    _not_site_scoped(current_user)
    return get_comparison(db, _period_or_404(db, period_id), scope="department")


def _export_response(db: Session, period_id: int, current_user: User, export_format: str) -> Response:
    ensure_permission(current_user, Permission.REPORTING_EXPORT)
    _not_site_scoped(current_user)
    period = _period_or_404(db, period_id)
    reference = period.report_reference or f"HSE-MR-DRAFT-V{period.report_version}"
    if export_format == "pdf":
        content = build_report_pdf(db, period)
        media_type = "application/pdf"
        extension = "pdf"
    else:
        content = build_report_xlsx(db, period)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"
    file_name = f"{reference}.{extension}"
    record_report_export(db, period, actor_id=current_user.id, export_format=export_format, file_name=file_name, content=content)
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{file_name}"'})


@router.get("/periods/{period_id}/exports/pdf")
def export_pdf(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _export_response(db, period_id, current_user, "pdf")


@router.get("/periods/{period_id}/exports/excel")
def export_excel(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _export_response(db, period_id, current_user, "excel")
