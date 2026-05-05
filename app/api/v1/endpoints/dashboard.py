from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardActionsRead,
    DashboardApprovalsRead,
    DashboardComplianceRead,
    DashboardManagementSummaryRead,
    DashboardOverviewRead,
    DashboardPermitsRead,
    DashboardRiskRead,
    DashboardSiteSummaryRead,
    DashboardTrendsRead,
)
from app.services.rbac import Permission, ensure_permission, resolve_site_scope
from app.services.dashboard_service import (
    get_dashboard_actions,
    get_dashboard_approvals,
    get_dashboard_compliance,
    get_dashboard_management_summary,
    get_dashboard_overview,
    get_dashboard_permits,
    get_dashboard_risk,
    get_dashboard_trends,
    get_site_summaries,
)

router = APIRouter()


@router.get("/overview", response_model=DashboardOverviewRead)
def read_dashboard_overview(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_overview(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/sites", response_model=list[DashboardSiteSummaryRead])
def read_dashboard_sites(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_site_summaries(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/trends", response_model=DashboardTrendsRead)
def read_dashboard_trends(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_trends(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/risk", response_model=DashboardRiskRead)
def read_dashboard_risk(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_risk(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/actions", response_model=DashboardActionsRead)
def read_dashboard_actions(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_actions(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/compliance", response_model=DashboardComplianceRead)
def read_dashboard_compliance(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_compliance(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/permits", response_model=DashboardPermitsRead)
def read_dashboard_permits(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_permits(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/approvals", response_model=DashboardApprovalsRead)
def read_dashboard_approvals(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_approvals(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/management-summary", response_model=DashboardManagementSummaryRead)
def read_dashboard_management_summary(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DASHBOARD_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return get_dashboard_management_summary(db, site_id=site_id, date_from=date_from, date_to=date_to)
