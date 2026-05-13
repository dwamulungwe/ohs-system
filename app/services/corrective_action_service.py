from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.corrective_action import (
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.inspection import Inspection
from app.models.site import Site
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate, CorrectiveActionUpdate
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify_action_pending_verification
from app.services.query_utils import apply_overdue_status, paginate


class CorrectiveActionServiceError(Exception):
    pass


class CorrectiveActionNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionSiteNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionUserNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionSourceNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionInvalidSourceError(CorrectiveActionServiceError):
    pass


COMPLETION_STATUSES = {CorrectiveActionStatus.pending_verification, CorrectiveActionStatus.closed}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise CorrectiveActionSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise CorrectiveActionUserNotFoundError(f"User {user_id} was not found")


def _validate_source(
    db: Session,
    *,
    source_type: CorrectiveActionSourceType,
    source_id: Optional[int],
) -> None:
    if source_type == CorrectiveActionSourceType.manual:
        return
    if source_id is None:
        raise CorrectiveActionInvalidSourceError("Source id is required for non-manual corrective actions")

    model_by_source = {
        CorrectiveActionSourceType.incident: Incident,
        CorrectiveActionSourceType.hazard: Hazard,
        CorrectiveActionSourceType.inspection: Inspection,
    }
    model = model_by_source[source_type]
    if db.get(model, source_id) is None:
        raise CorrectiveActionSourceNotFoundError(f"{source_type.value} {source_id} was not found")


def _apply_status_timestamps(
    data: dict,
    *,
    previous_status: Optional[CorrectiveActionStatus] = None,
    existing_completed_at: Optional[datetime] = None,
    existing_verified_at: Optional[datetime] = None,
    effective_verified_by_user_id: Optional[int] = None,
) -> None:
    status = data.get("status", previous_status or CorrectiveActionStatus.open)
    status_changed = previous_status is None or status != previous_status

    if status_changed and status in COMPLETION_STATUSES and data.get("completed_at") is None:
        data["completed_at"] = existing_completed_at or _now()

    verified_by_user_id = data.get("verified_by_user_id", effective_verified_by_user_id)
    if (
        status_changed
        and status == CorrectiveActionStatus.closed
        and verified_by_user_id is not None
        and data.get("verified_at") is None
    ):
        data["verified_at"] = existing_verified_at or _now()


def _dump_json_items(data: dict) -> None:
    if "closure_evidence_metadata" in data and data["closure_evidence_metadata"] is not None:
        data["closure_evidence_metadata"] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data["closure_evidence_metadata"]
        ]


def list_corrective_actions(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[CorrectiveActionStatus] = None,
    priority: Optional[CorrectiveActionPriority] = None,
    site_id: Optional[int] = None,
    assigned_to_user_id: Optional[int] = None,
    source_type: Optional[CorrectiveActionSourceType] = None,
) -> dict:
    statement: Select[tuple[CorrectiveAction]] = select(CorrectiveAction)
    if status is not None:
        statement = statement.where(CorrectiveAction.status == status)
    if priority is not None:
        statement = statement.where(CorrectiveAction.priority == priority)
    if site_id is not None:
        statement = statement.where(CorrectiveAction.site_id == site_id)
    if assigned_to_user_id is not None:
        statement = statement.where(CorrectiveAction.assigned_to_user_id == assigned_to_user_id)
    if source_type is not None:
        statement = statement.where(CorrectiveAction.source_type == source_type)

    statement = statement.order_by(CorrectiveAction.due_date.asc(), CorrectiveAction.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_corrective_action(db: Session, action_id: int) -> CorrectiveAction:
    action = db.get(CorrectiveAction, action_id)
    if action is None:
        raise CorrectiveActionNotFoundError(f"Corrective action {action_id} was not found")
    return action


def create_corrective_action(
    db: Session,
    action_in: CorrectiveActionCreate,
    *,
    current_user_id: Optional[int],
) -> CorrectiveAction:
    data = action_in.model_dump()
    _dump_json_items(data)
    if data.get("created_by_user_id") is None:
        data["created_by_user_id"] = current_user_id

    _ensure_site_exists(db, data["site_id"])
    _ensure_user_exists(db, data.get("assigned_to_user_id"))
    _ensure_user_exists(db, data.get("created_by_user_id"))
    _ensure_user_exists(db, data.get("verified_by_user_id"))
    _validate_source(db, source_type=data["source_type"], source_id=data.get("source_id"))
    apply_overdue_status(data)
    _apply_status_timestamps(data)

    action = CorrectiveAction(**data)
    db.add(action)
    db.commit()
    db.refresh(action)
    write_audit_log(
        db,
        actor_id=current_user_id,
        action="corrective_action.create",
        resource_type="corrective_action",
        resource_id=action.id,
        details={"status": action.status.value, "priority": action.priority.value},
    )
    return action


def update_corrective_action(
    db: Session,
    action: CorrectiveAction,
    action_in: CorrectiveActionUpdate,
    *,
    actor_id: Optional[int] = None,
) -> CorrectiveAction:
    update_data = action_in.model_dump(exclude_unset=True)
    _dump_json_items(update_data)

    effective_source_type = update_data.get("source_type", action.source_type)
    effective_source_id = update_data.get("source_id", action.source_id)
    effective_status = update_data.get("status", action.status)
    effective_due_date = update_data.get("due_date", action.due_date)
    effective_verified_by_user_id = update_data.get("verified_by_user_id", action.verified_by_user_id)

    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    for user_field in ("assigned_to_user_id", "created_by_user_id", "verified_by_user_id"):
        if user_field in update_data:
            _ensure_user_exists(db, update_data[user_field])

    _validate_source(db, source_type=effective_source_type, source_id=effective_source_id)

    status_payload = {
        "status": effective_status,
        "due_date": effective_due_date,
        "completed_at": update_data.get("completed_at", action.completed_at),
        "verified_by_user_id": effective_verified_by_user_id,
        "verified_at": update_data.get("verified_at", action.verified_at),
    }
    previous_status = action.status
    apply_overdue_status(status_payload)
    update_data["status"] = status_payload["status"]
    _apply_status_timestamps(
        update_data,
        previous_status=action.status,
        existing_completed_at=action.completed_at,
        existing_verified_at=action.verified_at,
        effective_verified_by_user_id=effective_verified_by_user_id,
    )

    for field, value in update_data.items():
        setattr(action, field, value)

    db.add(action)
    db.commit()
    db.refresh(action)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="corrective_action.update",
        resource_type="corrective_action",
        resource_id=action.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    if "status" in update_data and action.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="corrective_action.status_transition",
            resource_type="corrective_action",
            resource_id=action.id,
            details={"from": previous_status.value, "to": action.status.value},
        )
    if action.status == CorrectiveActionStatus.pending_verification and previous_status != CorrectiveActionStatus.pending_verification:
        notify_action_pending_verification(db, action)
    return action
