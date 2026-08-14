from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.corrective_action import (
    ActionExtensionRequest,
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.user import User
from app.schemas.corrective_action import (
    ActionActivityRead,
    ActionAssignmentDecision,
    ActionAssignmentRequest,
    ActionBulkExportRequest,
    ActionBulkRequest,
    ActionBulkResult,
    ActionCommentCreate,
    ActionCommentRead,
    ActionCompletionRequest,
    ActionDashboardRead,
    ActionExtensionCreate,
    ActionExtensionDecision,
    ActionExtensionRead,
    ActionProgressUpdate,
    ActionReasonRequest,
    ActionTaskCreate,
    ActionTaskRead,
    ActionTaskUpdate,
    ActionTransitionRequest,
    ActionVerificationRequest,
    CorrectiveActionCreate,
    CorrectiveActionListRead,
    CorrectiveActionRead,
    CorrectiveActionUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.corrective_action_service import (
    CorrectiveActionAssignmentError,
    CorrectiveActionDepartmentNotFoundError,
    CorrectiveActionExtensionError,
    CorrectiveActionInvalidSourceError,
    CorrectiveActionNotFoundError,
    CorrectiveActionServiceError,
    CorrectiveActionSiteNotFoundError,
    CorrectiveActionSourceNotFoundError,
    CorrectiveActionTaskError,
    CorrectiveActionTransitionError,
    CorrectiveActionUserNotFoundError,
    CorrectiveActionVerificationError,
    accept_action_assignment,
    add_action_comment,
    assign_action,
    bulk_update_actions,
    create_action_task,
    create_corrective_action as create_corrective_action_record,
    decide_action_extension,
    decline_action_assignment,
    get_action_dashboard,
    get_action_task,
    get_corrective_action as get_corrective_action_record,
    list_action_activity,
    list_action_comments,
    list_corrective_actions as list_corrective_action_records,
    reopen_action,
    request_action_completion,
    request_action_extension,
    transition_action,
    update_action_progress,
    update_action_task,
    update_corrective_action as update_corrective_action_record,
    verify_action_completion,
)
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    is_site_scoped,
    resolve_site_scope,
)


router = APIRouter()
SELF_SERVICE_ACTION_FIELDS = {
    "description",
    "acceptance_criteria",
    "expected_outcome",
    "progress_percent",
    "progress_notes",
    "started_at",
    "completion_notes",
    "closure_notes",
    "closure_evidence_metadata",
}


def _workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CorrectiveActionSiteNotFoundError):
        return HTTPException(status_code=404, detail="Site not found")
    if isinstance(exc, CorrectiveActionUserNotFoundError):
        return HTTPException(status_code=404, detail="Referenced user not found")
    if isinstance(exc, CorrectiveActionDepartmentNotFoundError):
        return HTTPException(status_code=404, detail="Department not found")
    if isinstance(exc, CorrectiveActionSourceNotFoundError):
        return HTTPException(status_code=404, detail="Source record not found")
    if isinstance(exc, CorrectiveActionNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CorrectiveActionInvalidSourceError):
        return HTTPException(status_code=422, detail="Invalid source reference")
    if isinstance(exc, CorrectiveActionExtensionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


def _ensure_action_access(current_user: User, action: CorrectiveAction) -> None:
    if action.site_id is not None:
        ensure_site_access(current_user, action.site_id)
    if not is_site_scoped(current_user) or has_permission(
        current_user, Permission.CORRECTIVE_ACTIONS_EDIT
    ):
        return
    contributor_ids = {item.user_id for item in action.contributors}
    if current_user.id in {action.owner_user_id, action.created_by_user_id} or current_user.id in contributor_ids:
        return
    if current_user.department_id and current_user.department_id in {
        action.department_id,
        action.responsible_department_id,
    }:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this action")


def _get_scoped_action(db: Session, current_user: User, action_id: int) -> CorrectiveAction:
    try:
        action = get_corrective_action_record(db, action_id)
    except CorrectiveActionNotFoundError:
        raise HTTPException(status_code=404, detail="Corrective action not found")
    _ensure_action_access(current_user, action)
    return action


def _ensure_owner_or_manager(current_user: User, action: CorrectiveAction) -> None:
    if has_permission(current_user, Permission.CORRECTIVE_ACTIONS_EDIT):
        return
    if has_permission(current_user, Permission.CORRECTIVE_ACTIONS_SELF_UPDATE) and action.owner_user_id == current_user.id:
        return
    raise HTTPException(status_code=403, detail="Not authorized to manage this action")


@router.get("", response_model=CorrectiveActionListRead)
def list_corrective_actions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    action_status: Optional[CorrectiveActionStatus] = Query(default=None, alias="status"),
    priority: Optional[CorrectiveActionPriority] = None,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    responsible_department_id: Optional[int] = None,
    assigned_to_user_id: Optional[int] = None,
    assigned_by_user_id: Optional[int] = None,
    verifier_user_id: Optional[int] = None,
    source_type: Optional[CorrectiveActionSourceType] = None,
    overdue: Optional[bool] = None,
    due_soon_days: Optional[int] = Query(default=None, ge=0, le=365),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    age_bucket: Optional[str] = None,
    extension_count: Optional[int] = Query(default=None, ge=0),
    reopened: Optional[bool] = None,
    awaiting_verification: Optional[bool] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    queue: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_corrective_action_records(
        db,
        skip=skip,
        limit=limit,
        status=action_status,
        priority=priority,
        site_id=site_id,
        department_id=department_id,
        responsible_department_id=responsible_department_id,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=assigned_by_user_id,
        verifier_user_id=verifier_user_id,
        source_type=source_type,
        overdue=overdue,
        due_soon_days=due_soon_days,
        date_from=date_from,
        date_to=date_to,
        age_bucket=age_bucket,
        extension_count=extension_count,
        reopened=reopened,
        awaiting_verification=awaiting_verification,
        search=search,
        queue=queue,
        current_user=current_user,
    )


@router.post("", response_model=CorrectiveActionRead, status_code=status.HTTP_201_CREATED)
def create_corrective_action(
    action_in: CorrectiveActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_CREATE)
    if action_in.lifecycle_status == CorrectiveActionStatus.closed:
        ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY)
    if is_site_scoped(current_user) or action_in.site_id is not None:
        action_in = action_in.model_copy(update={"site_id": resolve_site_scope(current_user, action_in.site_id)})
    try:
        return create_corrective_action_record(db, action_in, current_user_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.get("/dashboard", response_model=ActionDashboardRead)
def action_dashboard(
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW_ANALYTICS)
    site_id = resolve_site_scope(current_user, site_id)
    return get_action_dashboard(db, site_id=site_id, date_from=date_from, date_to=date_to)


def _bulk_records(db: Session, current_user: User, ids: list[int]) -> list[CorrectiveAction]:
    unique_ids = list(dict.fromkeys(ids))
    records = list(db.scalars(select(CorrectiveAction).where(CorrectiveAction.id.in_(unique_ids))).unique().all())
    if len(records) != len(unique_ids):
        raise HTTPException(status_code=404, detail="One or more actions were not found in the current organisation")
    for action in records:
        _ensure_action_access(current_user, action)
    return records


@router.post("/bulk", response_model=ActionBulkResult)
def bulk_actions(
    request: ActionBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_BULK)
    records = _bulk_records(db, current_user, request.action_ids)
    try:
        updated = bulk_update_actions(db, records, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        db.rollback()
        raise _workflow_error(exc)
    return {"updated_ids": [item.id for item in updated], "count": len(updated)}


@router.post("/bulk/export")
def export_selected_actions(
    request: ActionBulkExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    records = _bulk_records(db, current_user, request.action_ids)
    stream = StringIO()
    headers = ["action_reference", "title", "source_type", "site", "responsible_department", "owner", "priority", "lifecycle_status", "progress_percent", "original_due_date", "current_due_date", "age_days", "days_overdue", "number_of_extensions"]
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    for action in records:
        writer.writerow([action.action_reference, action.title, action.source_type.value, action.site_name, action.responsible_department_name, action.owner_name, action.priority.value, action.lifecycle_status.value, action.progress_percent, action.original_due_date, action.current_due_date, action.age_days, action.days_overdue, action.number_of_extensions])
    return Response(content=stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="actions-selected.csv"'})


@router.get("/{action_id}", response_model=CorrectiveActionRead)
def get_corrective_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    action = _get_scoped_action(db, current_user, action_id)
    return hydrate_entity_attachments(db, AttachmentEntityType.corrective_action, action)


@router.patch("/{action_id}", response_model=CorrectiveActionRead)
def patch_corrective_action(
    action_id: int,
    action_in: CorrectiveActionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    action = _get_scoped_action(db, current_user, action_id)
    update_fields = action_in.model_fields_set
    if has_permission(current_user, Permission.CORRECTIVE_ACTIONS_EDIT):
        pass
    elif has_permission(current_user, Permission.CORRECTIVE_ACTIONS_SELF_UPDATE) and action.owner_user_id == current_user.id:
        if not update_fields.issubset(SELF_SERVICE_ACTION_FIELDS):
            raise HTTPException(status_code=403, detail="Not authorized to change those action fields")
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    target = action_in.lifecycle_status if "lifecycle_status" in update_fields or "status" in update_fields else None
    if target == CorrectiveActionStatus.closed:
        ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY)
    if action_in.site_id is not None:
        action_in = action_in.model_copy(update={"site_id": resolve_site_scope(current_user, action_in.site_id)})
    try:
        return update_corrective_action_record(db, action, action_in, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/assign", response_model=CorrectiveActionRead)
def assign_action_record(action_id: int, request: ActionAssignmentRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_EDIT)
    action = _get_scoped_action(db, current_user, action_id)
    try:
        return assign_action(db, action, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/assignment/accept", response_model=CorrectiveActionRead)
def accept_assignment(action_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    action = _get_scoped_action(db, current_user, action_id)
    try:
        return accept_action_assignment(db, action, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/assignment/decline", response_model=CorrectiveActionRead)
def decline_assignment(action_id: int, request: ActionAssignmentDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=422, detail="A decline reason is required")
    action = _get_scoped_action(db, current_user, action_id)
    try:
        return decline_action_assignment(db, action, actor_id=current_user.id, reason=request.reason.strip())
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/transition", response_model=CorrectiveActionRead)
def transition_action_record(action_id: int, request: ActionTransitionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    _ensure_owner_or_manager(current_user, action)
    try:
        return transition_action(db, action, target_status=request.lifecycle_status, actor_id=current_user.id, reason=request.reason)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.patch("/{action_id}/progress", response_model=CorrectiveActionRead)
def patch_progress(action_id: int, request: ActionProgressUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    _ensure_owner_or_manager(current_user, action)
    try:
        return update_action_progress(db, action, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/tasks", response_model=ActionTaskRead, status_code=201)
def create_task(action_id: int, request: ActionTaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    _ensure_owner_or_manager(current_user, action)
    try:
        return create_action_task(db, action, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.patch("/{action_id}/tasks/{task_id}", response_model=ActionTaskRead)
def patch_task(action_id: int, task_id: int, request: ActionTaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    try:
        task = get_action_task(db, action, task_id)
        if task.owner_user_id != current_user.id:
            _ensure_owner_or_manager(current_user, action)
        return update_action_task(db, action, task, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.get("/{action_id}/comments", response_model=list[ActionCommentRead])
def get_comments(action_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    _get_scoped_action(db, current_user, action_id)
    return list_action_comments(db, action_id)


@router.post("/{action_id}/comments", response_model=ActionCommentRead, status_code=201)
def create_comment(action_id: int, request: ActionCommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    action = _get_scoped_action(db, current_user, action_id)
    return add_action_comment(db, action, request, actor_id=current_user.id)


@router.get("/{action_id}/activity", response_model=list[ActionActivityRead])
def get_activity(action_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    _get_scoped_action(db, current_user, action_id)
    return list_action_activity(db, action_id)


@router.post("/{action_id}/request-completion", response_model=CorrectiveActionRead)
def request_completion(action_id: int, request: ActionCompletionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    _ensure_owner_or_manager(current_user, action)
    try:
        return request_action_completion(db, action, actor_id=current_user.id, completion_notes=request.completion_notes)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/verify", response_model=CorrectiveActionRead)
def verify_completion(action_id: int, request: ActionVerificationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY)
    action = _get_scoped_action(db, current_user, action_id)
    try:
        return verify_action_completion(db, action, actor_id=current_user.id, approved=request.approved, notes=request.notes)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/reopen", response_model=CorrectiveActionRead)
def reopen_action_record(action_id: int, request: ActionReasonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY)
    action = _get_scoped_action(db, current_user, action_id)
    try:
        return reopen_action(db, action, actor_id=current_user.id, reason=request.reason)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.get("/{action_id}/extensions", response_model=list[ActionExtensionRead])
def get_extensions(action_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    action = _get_scoped_action(db, current_user, action_id)
    return action.extensions


@router.post("/{action_id}/extensions", response_model=ActionExtensionRead, status_code=201)
def create_extension_request(action_id: int, request: ActionExtensionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    action = _get_scoped_action(db, current_user, action_id)
    _ensure_owner_or_manager(current_user, action)
    try:
        return request_action_extension(db, action, request, actor_id=current_user.id)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)


@router.post("/{action_id}/extensions/{extension_id}/decision", response_model=ActionExtensionRead)
def decide_extension_request(action_id: int, extension_id: int, request: ActionExtensionDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_MANAGE_EXTENSIONS)
    action = _get_scoped_action(db, current_user, action_id)
    extension = db.get(ActionExtensionRequest, extension_id)
    if extension is None or extension.action_id != action.id:
        raise HTTPException(status_code=404, detail="Extension request not found")
    try:
        return decide_action_extension(db, action, extension, actor_id=current_user.id, approved=request.approved, decision_notes=request.decision_notes)
    except CorrectiveActionServiceError as exc:
        raise _workflow_error(exc)
