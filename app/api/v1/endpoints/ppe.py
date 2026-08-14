from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.ppe import (
    PPEAsset,
    PPEInspection,
    PPEIssueStatus,
    PPELossDamageReport,
    PPEMovementType,
    PPERequest,
    PPERequestStatus,
    PPEStockLocation,
)
from app.models.contractor import ContractorRecord
from app.models.user import User
from app.schemas.ppe import (
    PPEAcknowledgementCreate,
    PPEActionLinkCreate,
    PPEAssetCreate,
    PPEAssetRead,
    PPECategoryCreate,
    PPECategoryRead,
    PPECategoryUpdate,
    PPEDashboardRead,
    PPEEmployeeProfileRead,
    PPEInspectionCreate,
    PPEInspectionRead,
    PPEInventoryListRead,
    PPEInventoryRead,
    PPEIssueCreate,
    PPEIssueListRead,
    PPEIssueRead,
    PPEItemCreate,
    PPEItemListRead,
    PPEItemRead,
    PPEItemUpdate,
    PPELossDamageCreate,
    PPELossDamageRead,
    PPELossDamageReview,
    PPEReplacementCreate,
    PPERequestCreate,
    PPERequestDecision,
    PPERequestRead,
    PPERequirementCreate,
    PPERequirementRead,
    PPERequirementUpdate,
    PPEReturnCreate,
    PPEReturnRead,
    PPEStockAdjustment,
    PPEStockLocationCreate,
    PPEStockLocationRead,
    PPEStockLocationUpdate,
    PPEStockMovementRead,
    PPEStockReceipt,
    PPEStockTransfer,
    PPEVariantCreate,
    PPEVariantRead,
    PPEVariantUpdate,
)
from app.services.ppe_service import (
    PPEInsufficientStockError,
    PPENotFoundError,
    PPEServiceError,
    PPEValidationError,
    acknowledge_issue,
    adjust_stock,
    create_asset,
    create_category,
    create_inspection,
    create_item,
    create_location,
    create_request,
    create_requirement,
    create_requirements_bulk,
    create_variant,
    dashboard,
    decide_request,
    employee_profile,
    export_ppe_csv,
    generate_ppe_reminders,
    get_issue,
    get_item,
    issue_ppe,
    link_unified_action,
    list_categories,
    list_inspections,
    list_inventory,
    list_items,
    list_issues,
    list_locations,
    list_movements,
    list_requests,
    list_requirements,
    receive_stock,
    receive_stock_bulk,
    replace_ppe,
    report_loss_damage,
    review_loss_damage,
    return_ppe,
    transfer_stock,
    update_category,
    update_item,
    update_location,
    update_requirement,
    update_variant,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope

router = APIRouter()


def _raise_service_error(exc: PPEServiceError) -> None:
    if isinstance(exc, PPENotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PPEInsufficientStockError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    raise HTTPException(status_code=code, detail=str(exc))


def _scoped_site(current_user: User, site_id: Optional[int]) -> Optional[int]:
    return resolve_site_scope(current_user, site_id)


def _ensure_employee_access(current_user: User, employee: User) -> None:
    if employee.id == current_user.id and has_permission(current_user, Permission.PPE_SELF_VIEW):
        return
    ensure_permission(current_user, Permission.PPE_VIEW)
    ensure_site_access(current_user, employee.assigned_site_id)


def _issue_site_id(db: Session, issue) -> Optional[int]:
    if issue.site_id_snapshot is not None:
        return issue.site_id_snapshot
    if issue.recipient_user_id is not None:
        recipient = db.get(User, issue.recipient_user_id)
        if recipient is not None:
            return recipient.assigned_site_id
    if issue.contractor_id is not None:
        contractor = db.get(ContractorRecord, issue.contractor_id)
        if contractor is not None:
            return contractor.site_id
    location = db.get(PPEStockLocation, issue.stock_location_id)
    return location.site_id if location else None


@router.get("/dashboard", response_model=PPEDashboardRead)
def read_dashboard(
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return dashboard(db, site_id=_scoped_site(current_user, site_id), department_id=department_id)


@router.get("/categories", response_model=list[PPECategoryRead])
def read_categories(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_permission(current_user, Permission.PPE_VIEW):
        ensure_permission(current_user, Permission.PPE_REQUEST)
    return list_categories(db, active_only=active_only)


@router.post("/categories", response_model=PPECategoryRead, status_code=status.HTTP_201_CREATED)
def add_category(payload: PPECategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return create_category(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.patch("/categories/{category_id}", response_model=PPECategoryRead)
def patch_category(category_id: int, payload: PPECategoryUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return update_category(db, category_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/catalogue", response_model=PPEItemListRead)
def read_catalogue(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    category_id: Optional[int] = None,
    active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_permission(current_user, Permission.PPE_VIEW):
        ensure_permission(current_user, Permission.PPE_REQUEST)
    return list_items(db, skip=skip, limit=limit, category_id=category_id, active=active, search=search)


@router.post("/catalogue", response_model=PPEItemRead, status_code=status.HTTP_201_CREATED)
def add_item(payload: PPEItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return create_item(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/catalogue/{item_id}", response_model=PPEItemRead)
def read_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_permission(current_user, Permission.PPE_VIEW):
        ensure_permission(current_user, Permission.PPE_REQUEST)
    try:
        return get_item(db, item_id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.patch("/catalogue/{item_id}", response_model=PPEItemRead)
def patch_item(item_id: int, payload: PPEItemUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return update_item(db, item_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/variants", response_model=PPEVariantRead, status_code=status.HTTP_201_CREATED)
def add_variant(payload: PPEVariantCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return create_variant(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.patch("/variants/{variant_id}", response_model=PPEVariantRead)
def patch_variant(variant_id: int, payload: PPEVariantUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return update_variant(db, variant_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/locations", response_model=list[PPEStockLocationRead])
def read_locations(site_id: Optional[int] = None, active_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return list_locations(db, site_id=_scoped_site(current_user, site_id), active_only=active_only)


@router.post("/locations", response_model=PPEStockLocationRead, status_code=status.HTTP_201_CREATED)
def add_location(payload: PPEStockLocationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RECEIVE)
    if payload.site_id is not None:
        payload = payload.model_copy(update={"site_id": _scoped_site(current_user, payload.site_id)})
    try:
        return create_location(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.patch("/locations/{location_id}", response_model=PPEStockLocationRead)
def patch_location(location_id: int, payload: PPEStockLocationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RECEIVE)
    try:
        return update_location(db, location_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/inventory", response_model=PPEInventoryListRead)
def read_inventory(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None, location_id: Optional[int] = None, item_id: Optional[int] = None,
    category_id: Optional[int] = None, variant_id: Optional[int] = None, low_stock: Optional[bool] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return list_inventory(db, skip=skip, limit=limit, site_id=_scoped_site(current_user, site_id), location_id=location_id, item_id=item_id, category_id=category_id, variant_id=variant_id, low_stock=low_stock)


@router.post("/inventory/receive", response_model=PPEInventoryRead)
def receive(payload: PPEStockReceipt, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RECEIVE)
    try:
        return receive_stock(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/inventory/receive/bulk", response_model=list[PPEInventoryRead])
def receive_bulk(payload: list[PPEStockReceipt], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RECEIVE)
    if not payload or len(payload) > 500:
        raise HTTPException(status_code=422, detail="Bulk receipts require between 1 and 500 rows")
    try:
        return receive_stock_bulk(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/inventory/transfer", response_model=list[PPEStockMovementRead])
def transfer(payload: PPEStockTransfer, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_TRANSFER)
    try:
        return transfer_stock(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/inventory/adjust", response_model=PPEInventoryRead)
def adjust(payload: PPEStockAdjustment, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_ADJUST)
    try:
        return adjust_stock(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/movements")
def read_movements(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500), site_id: Optional[int] = None,
    location_id: Optional[int] = None, item_id: Optional[int] = None, movement_type: Optional[PPEMovementType] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return list_movements(db, skip=skip, limit=limit, site_id=_scoped_site(current_user, site_id), location_id=location_id, item_id=item_id, movement_type=movement_type)


@router.get("/assets", response_model=list[PPEAssetRead])
def read_assets(item_id: Optional[int] = None, status_filter: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_VIEW)
    statement = select(PPEAsset)
    if item_id is not None:
        statement = statement.where(PPEAsset.item_id == item_id)
    if status_filter is not None:
        statement = statement.where(PPEAsset.status == status_filter)
    return list(db.scalars(statement.order_by(PPEAsset.asset_tag.asc())).all())


@router.post("/assets", response_model=PPEAssetRead, status_code=status.HTTP_201_CREATED)
def add_asset(payload: PPEAssetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RECEIVE)
    try:
        return create_asset(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/issues", response_model=PPEIssueListRead)
def read_issues(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None, department_id: Optional[int] = None, recipient_user_id: Optional[int] = None,
    item_id: Optional[int] = None, issue_status: Optional[PPEIssueStatus] = None,
    replacement_due_before: Optional[date] = None, inspection_due_before: Optional[date] = None, expiry_before: Optional[date] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    if not has_permission(current_user, Permission.PPE_VIEW):
        ensure_permission(current_user, Permission.PPE_SELF_VIEW)
        recipient_user_id = current_user.id
    return list_issues(db, skip=skip, limit=limit, site_id=_scoped_site(current_user, site_id), department_id=department_id, recipient_user_id=recipient_user_id, item_id=item_id, status=issue_status, replacement_due_before=replacement_due_before, inspection_due_before=inspection_due_before, expiry_before=expiry_before)


@router.post("/issues", response_model=PPEIssueRead, status_code=status.HTTP_201_CREATED)
def add_issue(payload: PPEIssueCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_ISSUE)
    if payload.recipient_user_id is not None:
        recipient = db.get(User, payload.recipient_user_id)
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient not found")
        ensure_site_access(current_user, recipient.assigned_site_id)
    try:
        return issue_ppe(
            db,
            payload,
            actor_id=current_user.id,
            allow_override=has_permission(current_user, Permission.PPE_INVENTORY_NEGATIVE_OVERRIDE),
        )
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/issues/{issue_id}", response_model=PPEIssueRead)
def read_issue(issue_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        issue = get_issue(db, issue_id)
    except PPEServiceError as exc:
        _raise_service_error(exc)
    if issue.recipient_user_id == current_user.id:
        ensure_permission(current_user, Permission.PPE_SELF_VIEW)
    else:
        ensure_permission(current_user, Permission.PPE_VIEW)
        ensure_site_access(current_user, _issue_site_id(db, issue))
    return issue


@router.post("/issues/{issue_id}/acknowledge", response_model=PPEIssueRead)
def acknowledge(issue_id: int, payload: PPEAcknowledgementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_ACKNOWLEDGE)
    try:
        return acknowledge_issue(db, issue_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/issues/{issue_id}/return", response_model=PPEReturnRead, status_code=status.HTTP_201_CREATED)
def process_return(issue_id: int, payload: PPEReturnCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_RETURN)
    try:
        return return_ppe(db, issue_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/issues/{issue_id}/loss-damage", response_model=PPELossDamageRead, status_code=status.HTTP_201_CREATED)
def report_issue_loss_damage(issue_id: int, payload: PPELossDamageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REPORT_LOSS_DAMAGE)
    issue = get_issue(db, issue_id)
    if issue.recipient_user_id != current_user.id and not has_permission(current_user, Permission.PPE_VIEW):
        raise HTTPException(status_code=403, detail="Only the recipient or a PPE manager may report this PPE")
    if issue.recipient_user_id != current_user.id:
        ensure_site_access(current_user, _issue_site_id(db, issue))
    try:
        return report_loss_damage(db, issue_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/issues/{issue_id}/replace", response_model=PPEIssueRead, status_code=status.HTTP_201_CREATED)
def replace(issue_id: int, payload: PPEReplacementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INVENTORY_ISSUE)
    try:
        return replace_ppe(db, issue_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/requirements", response_model=list[PPERequirementRead])
def read_requirements(site_id: Optional[int] = None, department_id: Optional[int] = None, role_name: Optional[str] = None, item_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return list_requirements(db, site_id=_scoped_site(current_user, site_id), department_id=department_id, role_name=role_name, item_id=item_id)


@router.post("/requirements", response_model=PPERequirementRead, status_code=status.HTTP_201_CREATED)
def add_requirement(payload: PPERequirementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    if payload.site_id is not None:
        payload = payload.model_copy(update={"site_id": _scoped_site(current_user, payload.site_id)})
    try:
        return create_requirement(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.patch("/requirements/{requirement_id}", response_model=PPERequirementRead)
def patch_requirement(requirement_id: int, payload: PPERequirementUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    try:
        return update_requirement(db, requirement_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/requirements/bulk", response_model=list[PPERequirementRead], status_code=status.HTTP_201_CREATED)
def add_requirements_bulk(payload: list[PPERequirementCreate], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUIREMENTS_MANAGE)
    if len(payload) > 500:
        raise HTTPException(status_code=422, detail="A maximum of 500 requirements may be created at once")
    created = []
    try:
        created = create_requirements_bulk(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)
    return created


@router.get("/employees/{employee_user_id}", response_model=PPEEmployeeProfileRead)
def read_employee_profile(employee_user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = db.get(User, employee_user_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    _ensure_employee_access(current_user, employee)
    return employee_profile(db, employee_user_id)


@router.get("/requests")
def read_requests(skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500), request_status: Optional[PPERequestStatus] = None, site_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.PPE_REQUEST_REVIEW):
        return list_requests(db, skip=skip, limit=limit, status=request_status, site_id=_scoped_site(current_user, site_id))
    ensure_permission(current_user, Permission.PPE_REQUEST)
    return list_requests(db, skip=skip, limit=limit, status=request_status, requester_user_id=current_user.id)


@router.post("/requests", response_model=PPERequestRead, status_code=status.HTTP_201_CREATED)
def add_request(payload: PPERequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUEST)
    recipient_id = payload.recipient_user_id or current_user.id
    if recipient_id != current_user.id:
        ensure_permission(current_user, Permission.PPE_REQUEST_REVIEW)
        recipient = db.get(User, recipient_id)
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient not found")
        ensure_site_access(current_user, recipient.assigned_site_id)
    try:
        return create_request(db, payload, requester_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/requests/{request_id}/decision", response_model=PPERequestRead)
def review_request(request_id: int, payload: PPERequestDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_REQUEST_REVIEW)
    request_record = db.scalar(select(PPERequest).where(PPERequest.id == request_id))
    if request_record is None:
        raise HTTPException(status_code=404, detail="PPE request not found")
    recipient = db.get(User, request_record.recipient_user_id)
    ensure_site_access(current_user, recipient.assigned_site_id if recipient else None)
    try:
        return decide_request(db, request_id, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.get("/inspections")
def read_inspections(skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500), site_id: Optional[int] = None, passed: Optional[bool] = None, due_before: Optional[date] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_VIEW)
    return list_inspections(db, skip=skip, limit=limit, site_id=_scoped_site(current_user, site_id), passed=passed, due_before=due_before)


@router.post("/inspections", response_model=PPEInspectionRead, status_code=status.HTTP_201_CREATED)
def add_inspection(payload: PPEInspectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_INSPECT)
    try:
        return create_inspection(db, payload, actor_id=current_user.id)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/loss-damage/{report_id}/action")
def create_loss_damage_action(report_id: int, payload: PPEActionLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_CREATE)
    report = db.get(PPELossDamageReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="PPE loss/damage report not found")
    issue = get_issue(db, report.issue_id)
    return link_unified_action(db, report, payload, actor_id=current_user.id, site_id=None if issue is None else (db.get(User, issue.recipient_user_id).assigned_site_id if issue.recipient_user_id and db.get(User, issue.recipient_user_id) else None))


@router.post("/loss-damage/{report_id}/review", response_model=PPELossDamageRead)
def review_report(report_id: int, payload: PPELossDamageReview, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_VIEW)
    try:
        return review_loss_damage(db, report_id, actor_id=current_user.id, notes=payload.review_notes)
    except PPEServiceError as exc:
        _raise_service_error(exc)


@router.post("/reminders/run")
def run_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_CONFIGURE)
    return generate_ppe_reminders(db)


@router.get("/exports/{report}")
def export_report(report: str, site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.PPE_EXPORT)
    try:
        content = export_ppe_csv(db, report, site_id=_scoped_site(current_user, site_id), department_id=department_id)
    except PPEServiceError as exc:
        _raise_service_error(exc)
    filename = f"ppe-{report}-{date.today().isoformat()}.csv"
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
