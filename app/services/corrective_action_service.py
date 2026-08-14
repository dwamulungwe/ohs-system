from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attachment import Attachment, AttachmentEntityType
from app.models.audit_management import AuditManagementRecord
from app.models.contractor import ContractorRecord
from app.models.corrective_action import (
    ACTION_TERMINAL_STATUSES,
    ActionActivity,
    ActionAssignmentHistory,
    ActionComment,
    ActionContributor,
    ActionExtensionDecisionStatus,
    ActionExtensionRequest,
    ActionRecurrenceFrequency,
    ActionReferenceSequence,
    ActionReminderDelivery,
    ActionTask,
    ActionTaskStatus,
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.department import Department
from app.models.document_control import DocumentControlRecord
from app.models.emergency_drill import EmergencyDrillRecord
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.inspection import Inspection
from app.models.jsa import JobSafetyAnalysis
from app.models.legal_compliance import LegalComplianceItem
from app.models.notification import (
    Notification,
    NotificationSeverity,
    NotificationType,
    RelatedEntityType,
)
from app.models.organisation import OrganisationSettings
from app.models.permit import PermitToWork
from app.models.role import Role
from app.models.site import Site
from app.models.sio import SafetyImprovementObservation
from app.models.training import TrainingRecord
from app.models.user import User
from app.schemas.corrective_action import (
    ActionAssignmentRequest,
    ActionBulkRequest,
    ActionCommentCreate,
    ActionExtensionCreate,
    ActionProgressUpdate,
    ActionTaskCreate,
    ActionTaskUpdate,
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
)
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import (
    create_notification,
    create_notification_once,
    notify_action_pending_verification,
)
from app.services.query_utils import paginate
from app.services.rbac import (
    Permission,
    ROLE_OHS_MANAGER,
    ROLE_SAFETY_OFFICER,
    ROLE_SUPERVISOR,
    has_permission,
)
from app.services.tenancy import current_organisation_id


class CorrectiveActionServiceError(Exception):
    pass


class CorrectiveActionNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionSiteNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionUserNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionDepartmentNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionSourceNotFoundError(CorrectiveActionServiceError):
    pass


class CorrectiveActionInvalidSourceError(CorrectiveActionServiceError):
    pass


class CorrectiveActionTransitionError(CorrectiveActionServiceError):
    pass


class CorrectiveActionAssignmentError(CorrectiveActionServiceError):
    pass


class CorrectiveActionTaskError(CorrectiveActionServiceError):
    pass


class CorrectiveActionExtensionError(CorrectiveActionServiceError):
    pass


class CorrectiveActionVerificationError(CorrectiveActionServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _settings(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    return dict(settings.action_workflow_configuration or {}) if settings else {}


def _notifications_enabled(db: Session) -> bool:
    settings = db.scalar(select(OrganisationSettings))
    preferences = dict(settings.notification_preferences or {}) if settings else {}
    return bool(preferences.get("action_notifications_enabled", True))


def _reference_prefix(db: Session) -> str:
    settings = db.scalar(select(OrganisationSettings))
    raw = (settings.numbering_prefixes or {}).get("action", "ACT") if settings else "ACT"
    value = "".join(character for character in str(raw).upper() if character.isalnum() or character == "-")
    return value.strip("-")[:20] or "ACT"


def _next_action_reference(db: Session, *, year: Optional[int] = None) -> str:
    organisation_id = current_organisation_id(db)
    year = year or _now().year
    prefix = _reference_prefix(db)
    reference_stem = f"{prefix}-{year}-"
    for _attempt in range(8):
        sequence = db.scalar(
            select(ActionReferenceSequence)
            .where(ActionReferenceSequence.year == year)
            .with_for_update()
        )
        if sequence is None:
            try:
                with db.begin_nested():
                    existing_suffixes = []
                    for existing_reference in db.scalars(
                        select(CorrectiveAction.action_reference).where(
                            CorrectiveAction.action_reference.like(f"{reference_stem}%")
                        )
                    ):
                        suffix = str(existing_reference or "")[len(reference_stem) :]
                        if suffix.isdigit():
                            existing_suffixes.append(int(suffix))
                    value = max(existing_suffixes, default=0) + 1
                    sequence = ActionReferenceSequence(
                        organisation_id=organisation_id, year=year, last_value=value
                    )
                    db.add(sequence)
                    db.flush()
            except IntegrityError:
                continue
        else:
            sequence.last_value += 1
            value = sequence.last_value
            db.add(sequence)
            db.flush()
        return f"{reference_stem}{value:06d}"
    raise CorrectiveActionServiceError("Unable to allocate a unique action reference")


def _ensure_site_exists(db: Session, site_id: Optional[int]) -> Optional[Site]:
    if site_id is None:
        return None
    site = db.get(Site, site_id)
    if site is None:
        raise CorrectiveActionSiteNotFoundError(f"Site {site_id} was not found")
    return site


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> Optional[User]:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        raise CorrectiveActionUserNotFoundError(f"User {user_id} was not found")
    return user


def _ensure_department_exists(db: Session, department_id: Optional[int]) -> Optional[Department]:
    if department_id is None:
        return None
    department = db.get(Department, department_id)
    if department is None:
        raise CorrectiveActionDepartmentNotFoundError(
            f"Department {department_id} was not found"
        )
    return department


SOURCE_MODELS = {
    CorrectiveActionSourceType.sio: SafetyImprovementObservation,
    CorrectiveActionSourceType.incident: Incident,
    CorrectiveActionSourceType.hazard: Hazard,
    CorrectiveActionSourceType.inspection: Inspection,
    CorrectiveActionSourceType.audit: AuditManagementRecord,
    CorrectiveActionSourceType.permit: PermitToWork,
    CorrectiveActionSourceType.jsa: JobSafetyAnalysis,
    CorrectiveActionSourceType.training: TrainingRecord,
    CorrectiveActionSourceType.compliance: LegalComplianceItem,
    CorrectiveActionSourceType.contractor: ContractorRecord,
    CorrectiveActionSourceType.emergency_drill: EmergencyDrillRecord,
    CorrectiveActionSourceType.document_control: DocumentControlRecord,
}


def _validate_source(
    db: Session, *, source_type: CorrectiveActionSourceType, source_id: Optional[int]
) -> None:
    if source_type == CorrectiveActionSourceType.manual:
        return
    model = SOURCE_MODELS.get(source_type)
    # Future modules are intentionally linkable before their domain tables
    # exist; source_metadata provides the stable backlink in that case.
    if model is None:
        return
    if source_id is None:
        raise CorrectiveActionInvalidSourceError(
            "Source id is required for this non-manual action"
        )
    if db.get(model, source_id) is None:
        raise CorrectiveActionSourceNotFoundError(
            f"{source_type.value} {source_id} was not found"
        )


def record_action_activity(
    db: Session,
    action: CorrectiveAction,
    *,
    event_type: str,
    summary: str,
    actor_id: Optional[int],
    metadata: Optional[dict] = None,
    commit: bool = False,
) -> ActionActivity:
    activity = ActionActivity(
        action_id=action.id,
        actor_user_id=actor_id,
        event_type=event_type,
        summary=summary,
        event_metadata=metadata or {},
    )
    db.add(activity)
    if commit:
        db.commit()
        db.refresh(activity)
    return activity


def _notification_recipients_for_managers(db: Session, action: CorrectiveAction) -> set[int]:
    recipients: set[int] = set()
    if action.responsible_department and action.responsible_department.manager_user_id:
        recipients.add(action.responsible_department.manager_user_id)
    statement = (
        select(User.id)
        .join(User.roles)
        .where(
            Role.name.in_([ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER]),
            User.is_active.is_(True),
        )
        .distinct()
    )
    recipients.update(db.scalars(statement).all())
    return recipients


def _send_action_notification(
    db: Session,
    action: CorrectiveAction,
    *,
    recipient_user_id: Optional[int],
    notification_type: NotificationType,
    title: str,
    message: str,
    severity: NotificationSeverity = NotificationSeverity.info,
    once: bool = False,
) -> Optional[Notification]:
    if recipient_user_id is None or action.automation_suppressed or not _notifications_enabled(db):
        return None
    payload = NotificationCreate(
        recipient_user_id=recipient_user_id,
        title=title[:200],
        message=message,
        notification_type=notification_type,
        severity=severity,
        related_entity_type=RelatedEntityType.corrective_action,
        related_entity_id=action.id,
    )
    return create_notification_once(db, payload) if once else create_notification(db, payload)


COMPATIBILITY_FIELDS = {
    "status",
    "due_date",
    "assigned_to_user_id",
    "verified_by_user_id",
    "closure_notes",
    "expected_outcome",
}


def _dump_json_items(data: dict) -> None:
    if data.get("closure_evidence_metadata") is not None:
        data["closure_evidence_metadata"] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data["closure_evidence_metadata"]
        ]


def _normalise_status(value: CorrectiveActionStatus) -> CorrectiveActionStatus:
    return CorrectiveActionStatus.in_progress if value == CorrectiveActionStatus.overdue else value


def _default_due_date(db: Session, priority: CorrectiveActionPriority) -> Optional[date]:
    configured = _settings(db).get("default_due_days_by_priority", {})
    days = configured.get(priority.value)
    return date.today() + timedelta(days=days) if isinstance(days, int) and days >= 0 else None


def _sync_contributors(db: Session, action: CorrectiveAction, user_ids: list[int]) -> None:
    unique_ids = list(dict.fromkeys(user_ids))
    for user_id in unique_ids:
        _ensure_user_exists(db, user_id)
    action.contributors[:] = [ActionContributor(user_id=user_id) for user_id in unique_ids]


def list_corrective_actions(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[CorrectiveActionStatus] = None,
    priority: Optional[CorrectiveActionPriority] = None,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    responsible_department_id: Optional[int] = None,
    assigned_to_user_id: Optional[int] = None,
    assigned_by_user_id: Optional[int] = None,
    verifier_user_id: Optional[int] = None,
    source_type: Optional[CorrectiveActionSourceType] = None,
    overdue: Optional[bool] = None,
    due_soon_days: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    age_bucket: Optional[str] = None,
    extension_count: Optional[int] = None,
    reopened: Optional[bool] = None,
    awaiting_verification: Optional[bool] = None,
    search: Optional[str] = None,
    queue: Optional[str] = None,
    current_user: Optional[User] = None,
) -> dict:
    statement: Select[tuple[CorrectiveAction]] = select(CorrectiveAction)
    today = date.today()
    if status == CorrectiveActionStatus.overdue:
        overdue = True
    elif status is not None:
        statement = statement.where(CorrectiveAction.lifecycle_status == status)
    if priority is not None:
        statement = statement.where(CorrectiveAction.priority == priority)
    if site_id is not None:
        # Employee-owned legacy/manual actions may be intentionally unscoped.
        # Keep non-null actions inside the user's resolved site while allowing
        # the later owner/contributor/department predicate to admit null-site
        # records the employee is personally entitled to see.
        if current_user is not None and not has_permission(
            current_user, Permission.CORRECTIVE_ACTIONS_EDIT
        ):
            statement = statement.where(
                or_(
                    CorrectiveAction.site_id == site_id,
                    CorrectiveAction.site_id.is_(None),
                )
            )
        else:
            statement = statement.where(CorrectiveAction.site_id == site_id)
    if department_id is not None:
        statement = statement.where(CorrectiveAction.department_id == department_id)
    if responsible_department_id is not None:
        statement = statement.where(
            CorrectiveAction.responsible_department_id == responsible_department_id
        )
    if assigned_to_user_id is not None:
        statement = statement.where(CorrectiveAction.owner_user_id == assigned_to_user_id)
    if assigned_by_user_id is not None:
        statement = statement.where(CorrectiveAction.assigned_by_user_id == assigned_by_user_id)
    if verifier_user_id is not None:
        statement = statement.where(CorrectiveAction.verifier_user_id == verifier_user_id)
    if source_type is not None:
        statement = statement.where(CorrectiveAction.source_type == source_type)
    active_clause = CorrectiveAction.lifecycle_status.notin_(list(ACTION_TERMINAL_STATUSES) + [CorrectiveActionStatus.draft])
    overdue_clause = CorrectiveAction.current_due_date < today
    if overdue is True:
        statement = statement.where(CorrectiveAction.current_due_date.is_not(None), overdue_clause, active_clause)
    elif overdue is False:
        statement = statement.where(or_(CorrectiveAction.current_due_date.is_(None), ~overdue_clause, ~active_clause))
    if due_soon_days is not None:
        statement = statement.where(
            CorrectiveAction.current_due_date >= today,
            CorrectiveAction.current_due_date <= today + timedelta(days=due_soon_days),
            active_clause,
        )
    if date_from is not None:
        statement = statement.where(CorrectiveAction.current_due_date >= date_from)
    if date_to is not None:
        statement = statement.where(CorrectiveAction.current_due_date <= date_to)
    if extension_count is not None:
        statement = statement.where(CorrectiveAction.number_of_extensions >= extension_count)
    if reopened is True:
        statement = statement.where(CorrectiveAction.reopened_at.is_not(None))
    elif reopened is False:
        statement = statement.where(CorrectiveAction.reopened_at.is_(None))
    if awaiting_verification is not None:
        verification_states = [CorrectiveActionStatus.completion_requested, CorrectiveActionStatus.pending_verification]
        statement = statement.where(
            CorrectiveAction.lifecycle_status.in_(verification_states)
            if awaiting_verification
            else CorrectiveAction.lifecycle_status.notin_(verification_states)
        )
    if search and search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                CorrectiveAction.action_reference.ilike(term),
                CorrectiveAction.title.ilike(term),
                CorrectiveAction.description.ilike(term),
            )
        )
    if age_bucket:
        now = _now()
        ranges = {
            "0-7": (0, 7),
            "8-30": (8, 30),
            "31-60": (31, 60),
            "61-90": (61, 90),
            "90+": (91, None),
        }
        if age_bucket in ranges:
            low, high = ranges[age_bucket]
            statement = statement.where(CorrectiveAction.created_at <= now - timedelta(days=low))
            if high is not None:
                statement = statement.where(CorrectiveAction.created_at >= now - timedelta(days=high + 1))
    if queue and current_user:
        if queue in {"my_actions", "assigned_to_me"}:
            statement = statement.where(CorrectiveAction.owner_user_id == current_user.id)
        elif queue == "awaiting_acceptance":
            statement = statement.where(
                CorrectiveAction.owner_user_id == current_user.id,
                CorrectiveAction.lifecycle_status == CorrectiveActionStatus.assigned,
            )
        elif queue == "my_department" and current_user.department_id:
            statement = statement.where(
                or_(
                    CorrectiveAction.department_id == current_user.department_id,
                    CorrectiveAction.responsible_department_id == current_user.department_id,
                )
            )
        elif queue == "my_team" and current_user.department_id:
            statement = statement.join(User, User.id == CorrectiveAction.owner_user_id).where(
                User.department_id == current_user.department_id
            )
        elif queue == "due_this_week":
            statement = statement.where(CorrectiveAction.current_due_date.between(today, today + timedelta(days=7)), active_clause)
        elif queue == "overdue":
            statement = statement.where(overdue_clause, active_clause)
        elif queue == "awaiting_verification":
            statement = statement.where(
                CorrectiveAction.verifier_user_id == current_user.id,
                CorrectiveAction.lifecycle_status == CorrectiveActionStatus.pending_verification,
            )
        elif queue == "recently_closed":
            statement = statement.where(CorrectiveAction.closed_at >= _now() - timedelta(days=30))
        elif queue == "reopened":
            statement = statement.where(CorrectiveAction.reopened_at.is_not(None))
    if current_user and not has_permission(current_user, Permission.CORRECTIVE_ACTIONS_EDIT):
        contributor_exists = select(ActionContributor.id).where(
            ActionContributor.action_id == CorrectiveAction.id,
            ActionContributor.user_id == current_user.id,
        ).exists()
        permitted = [
            CorrectiveAction.owner_user_id == current_user.id,
            CorrectiveAction.created_by_user_id == current_user.id,
            contributor_exists,
        ]
        if current_user.department_id:
            permitted.extend(
                [
                    CorrectiveAction.department_id == current_user.department_id,
                    CorrectiveAction.responsible_department_id == current_user.department_id,
                ]
            )
        statement = statement.where(or_(*permitted))
    statement = statement.order_by(
        CorrectiveAction.current_due_date.asc(), CorrectiveAction.id.desc()
    )
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_corrective_action(db: Session, action_id: int) -> CorrectiveAction:
    action = db.get(CorrectiveAction, action_id)
    if action is None:
        raise CorrectiveActionNotFoundError(f"Action {action_id} was not found")
    return action


def create_corrective_action(
    db: Session,
    action_in: CorrectiveActionCreate,
    *,
    current_user_id: Optional[int],
    is_import: bool = False,
) -> CorrectiveAction:
    data = action_in.model_dump(exclude=COMPATIBILITY_FIELDS | {"contributor_user_ids"})
    contributor_ids = list(action_in.contributor_user_ids)
    _dump_json_items(data)
    data["lifecycle_status"] = _normalise_status(data["lifecycle_status"])
    if data.get("created_by_user_id") is None:
        data["created_by_user_id"] = current_user_id
    if data.get("current_due_date") is None:
        data["current_due_date"] = _default_due_date(db, data["priority"])
    if data.get("original_due_date") is None:
        data["original_due_date"] = data.get("current_due_date")
    data["automation_suppressed"] = is_import
    data["action_reference"] = _next_action_reference(db)
    if data.get("recurrence_enabled") and data.get("recurrence_frequency") is None:
        recurrence_defaults = _settings(db).get("recurrence_defaults", {})
        default_frequency = recurrence_defaults.get("frequency")
        try:
            data["recurrence_frequency"] = ActionRecurrenceFrequency(default_frequency)
        except (TypeError, ValueError):
            raise CorrectiveActionServiceError(
                "recurrence_frequency is required when recurrence is enabled"
            )
        configured_interval = recurrence_defaults.get("interval")
        if isinstance(configured_interval, int) and configured_interval > 0:
            data["recurrence_interval"] = configured_interval
    if (
        data.get("recurrence_enabled")
        and data.get("next_due_date") is None
        and data.get("current_due_date") is not None
    ):
        data["next_due_date"] = _advance_due_date(
            data["current_due_date"],
            data["recurrence_frequency"],
            data["recurrence_interval"],
        )

    _ensure_site_exists(db, data.get("site_id"))
    for field in ("owner_user_id", "assigned_by_user_id", "created_by_user_id", "verifier_user_id"):
        _ensure_user_exists(db, data.get(field))
    _ensure_department_exists(db, data.get("department_id"))
    _ensure_department_exists(db, data.get("responsible_department_id"))
    _validate_source(db, source_type=data["source_type"], source_id=data.get("source_id"))

    now = _now()
    if data.get("owner_user_id") and data.get("assigned_at") is None:
        data["assigned_at"] = now
        data["assigned_by_user_id"] = data.get("assigned_by_user_id") or current_user_id
    if data["lifecycle_status"] == CorrectiveActionStatus.closed:
        data["completed_at"] = data.get("completed_at") or now
        data["verified_at"] = data.get("verified_at") or now
        data["closed_at"] = now

    action = CorrectiveAction(**data)
    db.add(action)
    db.flush()
    _sync_contributors(db, action, contributor_ids)
    if action.owner_user_id:
        db.add(
            ActionAssignmentHistory(
                action_id=action.id,
                owner_user_id=action.owner_user_id,
                assigned_by_user_id=action.assigned_by_user_id,
                assignment_type="assigned",
            )
        )
    record_action_activity(
        db,
        action,
        event_type="created" if not is_import else "imported",
        summary=f"Action {action.action_reference} created",
        actor_id=current_user_id,
        metadata={"source_type": action.source_type.value, "source_id": action.source_id},
    )
    db.commit()
    db.refresh(action)
    write_audit_log(
        db,
        actor_id=current_user_id,
        action="corrective_action.import" if is_import else "corrective_action.create",
        resource_type="corrective_action",
        resource_id=action.id,
        details={"action_reference": action.action_reference, "lifecycle_status": action.lifecycle_status.value},
    )
    if action.owner_user_id and not is_import:
        _send_action_notification(
            db,
            action,
            recipient_user_id=action.owner_user_id,
            notification_type=NotificationType.action_assigned,
            title=f"Action assigned: {action.action_reference}",
            message=action.title,
        )
    return action


WORKFLOW_TRANSITIONS: dict[CorrectiveActionStatus, set[CorrectiveActionStatus]] = {
    CorrectiveActionStatus.draft: {CorrectiveActionStatus.open, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.open: {CorrectiveActionStatus.assigned, CorrectiveActionStatus.in_progress, CorrectiveActionStatus.on_hold, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.assigned: {CorrectiveActionStatus.accepted, CorrectiveActionStatus.declined, CorrectiveActionStatus.in_progress, CorrectiveActionStatus.on_hold, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.accepted: {CorrectiveActionStatus.in_progress, CorrectiveActionStatus.on_hold, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.declined: {CorrectiveActionStatus.assigned, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.in_progress: {CorrectiveActionStatus.completion_requested, CorrectiveActionStatus.on_hold, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.completion_requested: {CorrectiveActionStatus.pending_verification, CorrectiveActionStatus.in_progress, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.pending_verification: {CorrectiveActionStatus.closed, CorrectiveActionStatus.in_progress, CorrectiveActionStatus.on_hold},
    CorrectiveActionStatus.on_hold: {CorrectiveActionStatus.in_progress, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.closed: {CorrectiveActionStatus.reopened},
    CorrectiveActionStatus.reopened: {CorrectiveActionStatus.assigned, CorrectiveActionStatus.accepted, CorrectiveActionStatus.in_progress, CorrectiveActionStatus.on_hold, CorrectiveActionStatus.cancelled},
    CorrectiveActionStatus.overdue: {CorrectiveActionStatus.in_progress},
}


def _validate_transition(current: CorrectiveActionStatus, target: CorrectiveActionStatus) -> None:
    current = _normalise_status(current)
    target = _normalise_status(target)
    if current == target:
        return
    if target not in WORKFLOW_TRANSITIONS.get(current, set()):
        raise CorrectiveActionTransitionError(
            f"Invalid action transition from {current.value} to {target.value}"
        )


def transition_action(
    db: Session,
    action: CorrectiveAction,
    *,
    target_status: CorrectiveActionStatus,
    actor_id: int,
    reason: Optional[str] = None,
) -> CorrectiveAction:
    target_status = _normalise_status(target_status)
    if target_status in {
        CorrectiveActionStatus.assigned,
        CorrectiveActionStatus.accepted,
        CorrectiveActionStatus.declined,
        CorrectiveActionStatus.completion_requested,
        CorrectiveActionStatus.pending_verification,
        CorrectiveActionStatus.closed,
        CorrectiveActionStatus.reopened,
    }:
        raise CorrectiveActionTransitionError("Use the dedicated workflow endpoint for this transition")
    if target_status == CorrectiveActionStatus.cancelled and not (reason or "").strip():
        raise CorrectiveActionTransitionError("A cancellation reason is required")
    previous = _normalise_status(action.lifecycle_status)
    _validate_transition(previous, target_status)
    action.lifecycle_status = target_status
    now = _now()
    event_type = "status_changed"
    if target_status == CorrectiveActionStatus.open:
        event_type = "opened"
    elif target_status == CorrectiveActionStatus.in_progress:
        action.started_at = action.started_at or now
        event_type = "resumed" if previous == CorrectiveActionStatus.on_hold else "started"
    elif target_status == CorrectiveActionStatus.on_hold:
        event_type = "put_on_hold"
    elif target_status == CorrectiveActionStatus.cancelled:
        action.cancelled_at = now
        action.cancellation_reason = reason
        event_type = "cancelled"
    record_action_activity(
        db,
        action,
        event_type=event_type,
        summary=reason or f"Status changed from {previous.value} to {target_status.value}",
        actor_id=actor_id,
        metadata={"from": previous.value, "to": target_status.value},
    )
    db.commit()
    db.refresh(action)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="corrective_action.status_transition",
        resource_type="corrective_action",
        resource_id=action.id,
        details={"from": previous.value, "to": target_status.value, "reason": reason},
    )
    return action


def assign_action(
    db: Session,
    action: CorrectiveAction,
    request: ActionAssignmentRequest,
    *,
    actor_id: int,
) -> CorrectiveAction:
    if action.lifecycle_status in ACTION_TERMINAL_STATUSES:
        raise CorrectiveActionAssignmentError("Closed or cancelled actions cannot be assigned")
    owner = _ensure_user_exists(db, request.owner_user_id)
    department = _ensure_department_exists(db, request.responsible_department_id)
    _ensure_user_exists(db, request.verifier_user_id)
    previous_owner_id = action.owner_user_id
    previous_status = _normalise_status(action.lifecycle_status)
    now = _now()
    for history in action.assignment_history:
        if history.ended_at is None:
            history.ended_at = now
    event_type = "reassigned" if previous_owner_id is not None else "assigned"
    action.owner_user_id = owner.id
    action.assigned_by_user_id = actor_id
    action.assigned_at = now
    action.accepted_at = None
    action.assignment_decline_reason = None
    action.lifecycle_status = CorrectiveActionStatus.assigned
    if department is not None:
        action.responsible_department_id = department.id
    if request.verifier_user_id is not None:
        action.verifier_user_id = request.verifier_user_id
    if request.current_due_date is not None:
        if (
            action.current_due_date is not None
            and request.current_due_date != action.current_due_date
            and previous_status
            not in {
                CorrectiveActionStatus.draft,
                CorrectiveActionStatus.open,
                CorrectiveActionStatus.declined,
            }
        ):
            raise CorrectiveActionExtensionError(
                "Active action due dates must use the extension workflow"
            )
        if action.original_due_date is None:
            action.original_due_date = request.current_due_date
        action.current_due_date = request.current_due_date
    db.add(
        ActionAssignmentHistory(
            action_id=action.id,
            owner_user_id=owner.id,
            assigned_by_user_id=actor_id,
            assignment_type=event_type,
            reason=request.note,
        )
    )
    record_action_activity(
        db,
        action,
        event_type=event_type,
        summary=request.note or f"Action {event_type}",
        actor_id=actor_id,
        metadata={"previous_owner_user_id": previous_owner_id, "owner_user_id": owner.id},
    )
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action=f"corrective_action.{event_type}", resource_type="corrective_action", resource_id=action.id, details={"owner_user_id": owner.id})
    _send_action_notification(
        db,
        action,
        recipient_user_id=owner.id,
        notification_type=NotificationType.action_reassigned if previous_owner_id else NotificationType.action_assigned,
        title=f"Action {event_type}: {action.action_reference}",
        message=request.note or action.title,
    )
    return action


def accept_action_assignment(db: Session, action: CorrectiveAction, *, actor_id: int) -> CorrectiveAction:
    if action.owner_user_id != actor_id:
        raise CorrectiveActionAssignmentError("Only the assigned owner may accept this action")
    if action.lifecycle_status != CorrectiveActionStatus.assigned:
        raise CorrectiveActionAssignmentError("This action is not awaiting acceptance")
    action.lifecycle_status = CorrectiveActionStatus.accepted
    action.accepted_at = _now()
    record_action_activity(db, action, event_type="accepted", summary="Assignment accepted", actor_id=actor_id)
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.assignment.accept", resource_type="corrective_action", resource_id=action.id)
    return action


def decline_action_assignment(
    db: Session, action: CorrectiveAction, *, actor_id: int, reason: str
) -> CorrectiveAction:
    if action.owner_user_id != actor_id:
        raise CorrectiveActionAssignmentError("Only the assigned owner may decline this action")
    if action.lifecycle_status != CorrectiveActionStatus.assigned:
        raise CorrectiveActionAssignmentError("This action is not awaiting an assignment decision")
    assigner_id = action.assigned_by_user_id
    previous_owner_id = action.owner_user_id
    now = _now()
    for history in action.assignment_history:
        if history.ended_at is None:
            history.ended_at = now
            history.reason = reason
    action.lifecycle_status = CorrectiveActionStatus.declined
    action.assignment_decline_reason = reason
    action.owner_user_id = None
    record_action_activity(db, action, event_type="declined", summary=reason, actor_id=actor_id, metadata={"declined_owner_user_id": previous_owner_id})
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.assignment.decline", resource_type="corrective_action", resource_id=action.id, details={"reason": reason})
    for recipient in {assigner_id}.union(_notification_recipients_for_managers(db, action)):
        _send_action_notification(db, action, recipient_user_id=recipient, notification_type=NotificationType.action_declined, title=f"Action declined: {action.action_reference}", message=reason, severity=NotificationSeverity.warning)
    return action


def update_corrective_action(
    db: Session,
    action: CorrectiveAction,
    action_in: CorrectiveActionUpdate,
    *,
    actor_id: Optional[int] = None,
) -> CorrectiveAction:
    data = action_in.model_dump(exclude_unset=True, exclude=COMPATIBILITY_FIELDS | {"contributor_user_ids"})
    contributor_ids = action_in.contributor_user_ids if "contributor_user_ids" in action_in.model_fields_set else None
    _dump_json_items(data)
    target_status = data.pop("lifecycle_status", None)
    if target_status is not None:
        target_status = _normalise_status(target_status)
    effective_source_type = data.get("source_type", action.source_type)
    effective_source_id = data.get("source_id", action.source_id)
    _validate_source(db, source_type=effective_source_type, source_id=effective_source_id)
    if "site_id" in data:
        _ensure_site_exists(db, data["site_id"])
    for field in ("owner_user_id", "assigned_by_user_id", "created_by_user_id", "verifier_user_id"):
        if field in data:
            _ensure_user_exists(db, data[field])
    for field in ("department_id", "responsible_department_id"):
        if field in data:
            _ensure_department_exists(db, data[field])
    if "current_due_date" in data and data["current_due_date"] != action.current_due_date:
        if action.lifecycle_status not in {CorrectiveActionStatus.draft, CorrectiveActionStatus.open}:
            raise CorrectiveActionExtensionError("Active action due dates must use the extension workflow")
        if action.original_due_date is None:
            action.original_due_date = data["current_due_date"]
    if "progress_percent" in data and action.tasks:
        raise CorrectiveActionTaskError("Progress is calculated from tasks for this action")
    if "owner_user_id" in data and data["owner_user_id"] != action.owner_user_id:
        if data["owner_user_id"] is None:
            raise CorrectiveActionAssignmentError("Use assignment decline or reassignment to change the owner")
        request = ActionAssignmentRequest(
            owner_user_id=data.pop("owner_user_id"),
            responsible_department_id=data.pop("responsible_department_id", action.responsible_department_id),
            verifier_user_id=data.pop("verifier_user_id", action.verifier_user_id),
            current_due_date=data.pop("current_due_date", None),
        )
        for field, value in data.items():
            setattr(action, field, value)
        return assign_action(db, action, request, actor_id=actor_id or action.created_by_user_id or 0)
    for field, value in data.items():
        setattr(action, field, value)
    if contributor_ids is not None:
        _sync_contributors(db, action, contributor_ids)
    if target_status == CorrectiveActionStatus.pending_verification:
        previous = action.lifecycle_status
        updated = request_action_completion(
            db,
            action,
            actor_id=actor_id or action.owner_user_id or action.created_by_user_id or 0,
            completion_notes=action.completion_notes or "Completion requested through legacy API",
        )
        write_audit_log(db, actor_id=actor_id, action="corrective_action.update", resource_type="corrective_action", resource_id=action.id, details={"updated_fields": sorted(data) + ["status"]})
        write_audit_log(db, actor_id=actor_id, action="corrective_action.status_transition", resource_type="corrective_action", resource_id=action.id, details={"from": previous.value, "to": updated.lifecycle_status.value})
        return updated
    if target_status == CorrectiveActionStatus.closed:
        previous = action.lifecycle_status
        updated = verify_action_completion(
            db,
            action,
            actor_id=actor_id or action.verifier_user_id or action.created_by_user_id or 0,
            approved=True,
            notes=action.verification_notes or "Verified through legacy API",
        )
        write_audit_log(db, actor_id=actor_id, action="corrective_action.update", resource_type="corrective_action", resource_id=action.id, details={"updated_fields": sorted(data) + ["status"]})
        write_audit_log(db, actor_id=actor_id, action="corrective_action.status_transition", resource_type="corrective_action", resource_id=action.id, details={"from": previous.value, "to": updated.lifecycle_status.value})
        return updated
    if target_status is not None and target_status != action.lifecycle_status:
        _validate_transition(action.lifecycle_status, target_status)
        previous = action.lifecycle_status
        action.lifecycle_status = target_status
        if target_status == CorrectiveActionStatus.in_progress:
            action.started_at = action.started_at or _now()
        record_action_activity(db, action, event_type="status_changed", summary=f"Status changed from {previous.value} to {target_status.value}", actor_id=actor_id, metadata={"from": previous.value, "to": target_status.value})
    if data or contributor_ids is not None:
        record_action_activity(db, action, event_type="updated", summary="Action details updated", actor_id=actor_id, metadata={"updated_fields": sorted(data)})
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.update", resource_type="corrective_action", resource_id=action.id, details={"updated_fields": sorted(data)})
    return action


def _sync_task_progress(action: CorrectiveAction) -> None:
    tasks = [task for task in action.tasks if task.status != ActionTaskStatus.cancelled]
    if not tasks:
        return
    completed = sum(task.status == ActionTaskStatus.completed for task in tasks)
    action.progress_percent = round(completed * 100 / len(tasks))


def create_action_task(
    db: Session, action: CorrectiveAction, request: ActionTaskCreate, *, actor_id: int
) -> ActionTask:
    if action.lifecycle_status in ACTION_TERMINAL_STATUSES:
        raise CorrectiveActionTaskError("Tasks cannot be added to a closed or cancelled action")
    _ensure_user_exists(db, request.owner_user_id)
    data = request.model_dump()
    if data["status"] == ActionTaskStatus.completed:
        data["completed_at"] = _now()
    task = ActionTask(action_id=action.id, **data)
    action.tasks.append(task)
    db.flush()
    _sync_task_progress(action)
    record_action_activity(
        db,
        action,
        event_type="task_added",
        summary=f"Task added: {task.title}",
        actor_id=actor_id,
        metadata={"task_id": task.id},
    )
    db.commit()
    db.refresh(task)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.task.create", resource_type="corrective_action", resource_id=action.id, details={"task_id": task.id})
    return task


def get_action_task(db: Session, action: CorrectiveAction, task_id: int) -> ActionTask:
    task = db.get(ActionTask, task_id)
    if task is None or task.action_id != action.id:
        raise CorrectiveActionNotFoundError(f"Task {task_id} was not found")
    return task


def update_action_task(
    db: Session,
    action: CorrectiveAction,
    task: ActionTask,
    request: ActionTaskUpdate,
    *,
    actor_id: int,
) -> ActionTask:
    data = request.model_dump(exclude_unset=True)
    if "owner_user_id" in data:
        _ensure_user_exists(db, data["owner_user_id"])
    previous_status = task.status
    for field, value in data.items():
        setattr(task, field, value)
    if task.status == ActionTaskStatus.completed and previous_status != ActionTaskStatus.completed:
        task.completed_at = _now()
    elif task.status != ActionTaskStatus.completed and previous_status == ActionTaskStatus.completed:
        task.completed_at = None
    _sync_task_progress(action)
    event_type = "task_completed" if task.status == ActionTaskStatus.completed and previous_status != task.status else "task_updated"
    record_action_activity(db, action, event_type=event_type, summary=f"Task {task.title} {event_type.replace('_', ' ')}", actor_id=actor_id, metadata={"task_id": task.id, "from": previous_status.value, "to": task.status.value})
    db.commit()
    db.refresh(task)
    write_audit_log(db, actor_id=actor_id, action=f"corrective_action.{event_type}", resource_type="corrective_action", resource_id=action.id, details={"task_id": task.id})
    return task


def update_action_progress(
    db: Session,
    action: CorrectiveAction,
    request: ActionProgressUpdate,
    *,
    actor_id: int,
) -> CorrectiveAction:
    if action.tasks:
        raise CorrectiveActionTaskError("Progress is calculated automatically from action tasks")
    action.progress_percent = request.progress_percent
    action.progress_notes = request.progress_notes
    record_action_activity(db, action, event_type="progress_updated", summary=request.progress_notes or f"Progress updated to {request.progress_percent}%", actor_id=actor_id, metadata={"progress_percent": request.progress_percent})
    db.commit()
    db.refresh(action)
    return action


def list_action_comments(db: Session, action_id: int) -> list[ActionComment]:
    return list(db.scalars(select(ActionComment).where(ActionComment.action_id == action_id).order_by(ActionComment.created_at, ActionComment.id)).all())


def add_action_comment(
    db: Session, action: CorrectiveAction, request: ActionCommentCreate, *, actor_id: int
) -> ActionComment:
    comment = ActionComment(action_id=action.id, author_user_id=actor_id, body=request.body.strip())
    db.add(comment)
    db.flush()
    record_action_activity(db, action, event_type="comment_added", summary=comment.body, actor_id=actor_id, metadata={"comment_id": comment.id})
    db.commit()
    db.refresh(comment)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.comment.create", resource_type="corrective_action", resource_id=action.id, details={"comment_id": comment.id})
    return comment


def list_action_activity(db: Session, action_id: int) -> list[ActionActivity]:
    return list(db.scalars(select(ActionActivity).where(ActionActivity.action_id == action_id).order_by(ActionActivity.created_at, ActionActivity.id)).all())


def _verification_required(db: Session, action: CorrectiveAction) -> bool:
    settings = _settings(db)
    if action.priority == CorrectiveActionPriority.low and settings.get("auto_close_low_priority", False):
        return False
    by_priority = settings.get("verification_required_by_priority", {})
    if action.priority.value in by_priority:
        return bool(by_priority[action.priority.value])
    return bool(settings.get("verification_required", True))


def _completion_evidence_required(db: Session, action: CorrectiveAction) -> bool:
    settings = _settings(db)
    by_priority = settings.get("completion_evidence_required_by_priority", {})
    return bool(by_priority.get(action.priority.value, settings.get("completion_evidence_required", False)))


def _has_completion_evidence(db: Session, action: CorrectiveAction) -> bool:
    if action.closure_evidence_metadata:
        return True
    return bool(
        db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.entity_type == AttachmentEntityType.corrective_action,
                Attachment.entity_id == action.id,
                Attachment.evidence_type.in_(["completion", "completion_evidence"]),
            )
        )
    )


def request_action_completion(
    db: Session,
    action: CorrectiveAction,
    *,
    actor_id: int,
    completion_notes: str,
) -> CorrectiveAction:
    if action.lifecycle_status in ACTION_TERMINAL_STATUSES:
        raise CorrectiveActionTransitionError("A closed or cancelled action cannot request completion")
    if action.required_incomplete_tasks:
        raise CorrectiveActionTaskError("All required tasks must be completed before requesting completion")
    if _completion_evidence_required(db, action) and not _has_completion_evidence(db, action):
        raise CorrectiveActionVerificationError("Completion evidence is required")
    previous = _normalise_status(action.lifecycle_status)
    if previous not in {
        CorrectiveActionStatus.open,
        CorrectiveActionStatus.assigned,
        CorrectiveActionStatus.accepted,
        CorrectiveActionStatus.in_progress,
        CorrectiveActionStatus.reopened,
        CorrectiveActionStatus.completion_requested,
    }:
        raise CorrectiveActionTransitionError("Action is not in a state that can request completion")
    now = _now()
    action.lifecycle_status = CorrectiveActionStatus.completion_requested
    action.completion_requested_by_user_id = actor_id
    action.completion_requested_at = now
    action.completed_at = action.completed_at or now
    action.completion_notes = completion_notes.strip()
    action.progress_percent = 100
    record_action_activity(db, action, event_type="completion_requested", summary=completion_notes.strip(), actor_id=actor_id, metadata={"previous_status": previous.value})
    generated_action = None
    if _verification_required(db, action):
        action.lifecycle_status = CorrectiveActionStatus.pending_verification
        record_action_activity(db, action, event_type="pending_verification", summary="Completion submitted for verification", actor_id=actor_id)
    else:
        action.lifecycle_status = CorrectiveActionStatus.closed
        action.closed_at = now
        record_action_activity(db, action, event_type="closed", summary="Action auto-closed under organisation settings", actor_id=actor_id, metadata={"auto_closed": True})
        generated_action = _generate_next_occurrence(db, action, actor_id=actor_id)
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.completion.request", resource_type="corrective_action", resource_id=action.id, details={"lifecycle_status": action.lifecycle_status.value})
    if action.assigned_by_user_id != actor_id:
        _send_action_notification(
            db,
            action,
            recipient_user_id=action.assigned_by_user_id,
            notification_type=NotificationType.action_completion_requested,
            title=f"Action completion requested: {action.action_reference}",
            message=completion_notes,
        )
    if action.lifecycle_status == CorrectiveActionStatus.pending_verification:
        # Reuse the established event for API compatibility; recipient routing
        # includes the configured verifier and original assigning context.
        notify_action_pending_verification(db, action)
    elif generated_action and generated_action.owner_user_id:
        _send_action_notification(
            db,
            generated_action,
            recipient_user_id=generated_action.owner_user_id,
            notification_type=NotificationType.action_recurring_generated,
            title=f"Recurring action generated: {generated_action.action_reference}",
            message=generated_action.title,
        )
    return action


def _independent_verifier_required(db: Session, action: CorrectiveAction) -> bool:
    settings = _settings(db)
    by_priority = settings.get("independent_verifier_required_by_priority", {})
    if action.priority.value in by_priority:
        return bool(by_priority[action.priority.value])
    return bool(settings.get("independent_verifier_required", False))


def verify_action_completion(
    db: Session,
    action: CorrectiveAction,
    *,
    actor_id: int,
    approved: bool,
    notes: str,
) -> CorrectiveAction:
    if action.lifecycle_status not in {CorrectiveActionStatus.pending_verification, CorrectiveActionStatus.completion_requested}:
        raise CorrectiveActionTransitionError("Action is not pending verification")
    if _independent_verifier_required(db, action) and actor_id in {
        action.owner_user_id,
        action.completion_requested_by_user_id,
        action.created_by_user_id,
    }:
        raise CorrectiveActionVerificationError("Independent verification is required; the action owner cannot self-verify")
    now = _now()
    action.verifier_user_id = actor_id
    action.verified_at = now
    action.verification_notes = notes.strip()
    generated_action = None
    if approved:
        action.lifecycle_status = CorrectiveActionStatus.closed
        action.closed_at = now
        record_action_activity(db, action, event_type="verification_approved", summary=notes.strip(), actor_id=actor_id, metadata={"approved": True})
        record_action_activity(db, action, event_type="closed", summary="Action closed after verification", actor_id=actor_id)
        generated_action = _generate_next_occurrence(db, action, actor_id=actor_id)
        notification_type = NotificationType.action_closed
    else:
        action.lifecycle_status = CorrectiveActionStatus.in_progress
        action.started_at = action.started_at or now
        record_action_activity(db, action, event_type="verification_rejected", summary=notes.strip(), actor_id=actor_id, metadata={"approved": False})
        notification_type = NotificationType.action_verification_rejected
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.verification.approve" if approved else "corrective_action.verification.reject", resource_type="corrective_action", resource_id=action.id, details={"notes": notes})
    for recipient in {action.owner_user_id, action.assigned_by_user_id}:
        _send_action_notification(db, action, recipient_user_id=recipient, notification_type=notification_type, title=f"Action {'closed' if approved else 'verification rejected'}: {action.action_reference}", message=notes, severity=NotificationSeverity.info if approved else NotificationSeverity.warning)
    if generated_action and generated_action.owner_user_id:
        _send_action_notification(
            db,
            generated_action,
            recipient_user_id=generated_action.owner_user_id,
            notification_type=NotificationType.action_recurring_generated,
            title=f"Recurring action generated: {generated_action.action_reference}",
            message=generated_action.title,
        )
    return action


def reopen_action(
    db: Session, action: CorrectiveAction, *, actor_id: int, reason: str
) -> CorrectiveAction:
    if action.lifecycle_status != CorrectiveActionStatus.closed:
        raise CorrectiveActionTransitionError("Only a closed action can be reopened")
    action.lifecycle_status = CorrectiveActionStatus.reopened
    action.reopened_by_user_id = actor_id
    action.reopened_at = _now()
    action.reopen_reason = reason.strip()
    record_action_activity(db, action, event_type="reopened", summary=reason.strip(), actor_id=actor_id, metadata={"previous_closed_at": action.closed_at.isoformat() if action.closed_at else None})
    db.commit()
    db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.reopen", resource_type="corrective_action", resource_id=action.id, details={"reason": reason})
    for recipient in {action.owner_user_id, action.assigned_by_user_id, action.verifier_user_id}:
        _send_action_notification(db, action, recipient_user_id=recipient, notification_type=NotificationType.action_reopened, title=f"Action reopened: {action.action_reference}", message=reason, severity=NotificationSeverity.warning)
    return action


def request_action_extension(
    db: Session,
    action: CorrectiveAction,
    request: ActionExtensionCreate,
    *,
    actor_id: int,
) -> ActionExtensionRequest:
    if action.lifecycle_status in ACTION_TERMINAL_STATUSES:
        raise CorrectiveActionExtensionError("Closed or cancelled actions cannot be extended")
    if action.current_due_date is None:
        raise CorrectiveActionExtensionError("The action must have a current due date")
    if request.requested_due_date <= action.current_due_date:
        raise CorrectiveActionExtensionError("The requested due date must be later than the current due date")
    if any(item.decision_status == ActionExtensionDecisionStatus.pending for item in action.extensions):
        raise CorrectiveActionExtensionError("An extension request is already pending")
    extension = ActionExtensionRequest(
        action_id=action.id,
        previous_due_date=action.current_due_date,
        requested_due_date=request.requested_due_date,
        extension_reason=request.extension_reason.strip(),
        requested_by_user_id=actor_id,
    )
    db.add(extension)
    db.flush()
    record_action_activity(db, action, event_type="extension_requested", summary=extension.extension_reason, actor_id=actor_id, metadata={"extension_request_id": extension.id, "previous_due_date": action.current_due_date.isoformat(), "requested_due_date": request.requested_due_date.isoformat()})
    db.commit()
    db.refresh(extension)
    write_audit_log(db, actor_id=actor_id, action="corrective_action.extension.request", resource_type="corrective_action", resource_id=action.id, details={"extension_request_id": extension.id})
    for recipient in _notification_recipients_for_managers(db, action).union({action.assigned_by_user_id}):
        _send_action_notification(db, action, recipient_user_id=recipient, notification_type=NotificationType.action_extension_requested, title=f"Extension requested: {action.action_reference}", message=extension.extension_reason, severity=NotificationSeverity.warning)
    return extension


def decide_action_extension(
    db: Session,
    action: CorrectiveAction,
    extension: ActionExtensionRequest,
    *,
    actor_id: int,
    approved: bool,
    decision_notes: Optional[str],
) -> ActionExtensionRequest:
    if extension.action_id != action.id:
        raise CorrectiveActionNotFoundError("Extension request was not found")
    if extension.decision_status != ActionExtensionDecisionStatus.pending:
        raise CorrectiveActionExtensionError("Extension request has already been decided")
    extension.decision_status = ActionExtensionDecisionStatus.approved if approved else ActionExtensionDecisionStatus.rejected
    extension.decided_by_user_id = actor_id
    extension.decided_at = _now()
    extension.decision_notes = decision_notes
    event_type = "extension_approved" if approved else "extension_rejected"
    if approved:
        action.current_due_date = extension.requested_due_date
        action.number_of_extensions += 1
    record_action_activity(db, action, event_type=event_type, summary=decision_notes or event_type.replace("_", " ").title(), actor_id=actor_id, metadata={"extension_request_id": extension.id, "previous_due_date": extension.previous_due_date.isoformat() if extension.previous_due_date else None, "requested_due_date": extension.requested_due_date.isoformat(), "original_due_date": action.original_due_date.isoformat() if action.original_due_date else None})
    db.commit()
    db.refresh(extension)
    write_audit_log(db, actor_id=actor_id, action=f"corrective_action.{event_type}", resource_type="corrective_action", resource_id=action.id, details={"extension_request_id": extension.id})
    _send_action_notification(db, action, recipient_user_id=extension.requested_by_user_id, notification_type=NotificationType.action_extension_approved if approved else NotificationType.action_extension_rejected, title=f"Extension {'approved' if approved else 'rejected'}: {action.action_reference}", message=decision_notes or event_type.replace("_", " "), severity=NotificationSeverity.info if approved else NotificationSeverity.warning)
    return extension


def _advance_due_date(
    value: date, frequency: ActionRecurrenceFrequency, interval: int
) -> date:
    if frequency == ActionRecurrenceFrequency.daily:
        return value + timedelta(days=interval)
    if frequency == ActionRecurrenceFrequency.weekly:
        return value + timedelta(weeks=interval)
    months = interval
    if frequency == ActionRecurrenceFrequency.quarterly:
        months *= 3
    elif frequency == ActionRecurrenceFrequency.yearly:
        months *= 12
    absolute_month = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(absolute_month, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _generate_next_occurrence(
    db: Session, action: CorrectiveAction, *, actor_id: Optional[int]
) -> Optional[CorrectiveAction]:
    if (
        not action.recurrence_enabled
        or action.recurrence_frequency is None
        or action.automation_suppressed
    ):
        return None
    existing = db.scalar(
        select(CorrectiveAction).where(
            CorrectiveAction.recurrence_parent_action_id == action.id
        )
    )
    if existing is not None:
        return existing
    base_due_date = action.current_due_date or date.today()
    next_due_date = action.next_due_date
    if next_due_date is None or next_due_date <= base_due_date:
        next_due_date = _advance_due_date(
            base_due_date, action.recurrence_frequency, action.recurrence_interval
        )
    if action.recurrence_end_date and next_due_date > action.recurrence_end_date:
        return None
    subsequent_due_date = _advance_due_date(
        next_due_date, action.recurrence_frequency, action.recurrence_interval
    )
    successor = CorrectiveAction(
        action_reference=_next_action_reference(db, year=next_due_date.year),
        site_id=action.site_id,
        department_id=action.department_id,
        responsible_department_id=action.responsible_department_id,
        title=action.title,
        description=action.description,
        acceptance_criteria=action.acceptance_criteria,
        source_type=action.source_type,
        source_id=action.source_id,
        source_metadata=dict(action.source_metadata or {}),
        priority=action.priority,
        lifecycle_status=(
            CorrectiveActionStatus.assigned
            if action.owner_user_id
            else CorrectiveActionStatus.open
        ),
        original_due_date=next_due_date,
        current_due_date=next_due_date,
        owner_user_id=action.owner_user_id,
        assigned_by_user_id=actor_id,
        assigned_at=_now() if action.owner_user_id else None,
        created_by_user_id=action.created_by_user_id,
        verifier_user_id=action.verifier_user_id,
        recurrence_enabled=True,
        recurrence_frequency=action.recurrence_frequency,
        recurrence_interval=action.recurrence_interval,
        next_due_date=subsequent_due_date,
        recurrence_end_date=action.recurrence_end_date,
        recurrence_parent_action_id=action.id,
    )
    db.add(successor)
    db.flush()
    for contributor in action.contributors:
        successor.contributors.append(ActionContributor(user_id=contributor.user_id))
    for task in action.tasks:
        if task.status == ActionTaskStatus.cancelled:
            continue
        successor.tasks.append(
            ActionTask(
                title=task.title,
                description=task.description,
                owner_user_id=task.owner_user_id,
                due_date=None,
                status=ActionTaskStatus.open,
                is_required=task.is_required,
                notes=None,
            )
        )
    if successor.owner_user_id:
        successor.assignment_history.append(
            ActionAssignmentHistory(
                owner_user_id=successor.owner_user_id,
                assigned_by_user_id=actor_id,
                assignment_type="recurrence_generated",
            )
        )
    record_action_activity(
        db,
        action,
        event_type="recurrence_generated",
        summary=f"Generated recurring action {successor.action_reference}",
        actor_id=actor_id,
        metadata={"generated_action_id": successor.id, "due_date": next_due_date.isoformat()},
    )
    record_action_activity(
        db,
        successor,
        event_type="created",
        summary=f"Recurring action generated from {action.action_reference}",
        actor_id=actor_id,
        metadata={"recurrence_parent_action_id": action.id},
    )
    return successor


def generate_action_escalations(db: Session) -> list[Notification]:
    settings = _settings(db)
    escalation = settings.get("escalation_thresholds", {})
    default_due = escalation.get("due_soon_days", [7, 3, 0])
    default_overdue = escalation.get("overdue_days", [1, 7, 14, 30])
    today = date.today()
    actions = list(
        db.scalars(
            select(CorrectiveAction).where(
                CorrectiveAction.current_due_date.is_not(None),
                CorrectiveAction.lifecycle_status.notin_(list(ACTION_TERMINAL_STATUSES)),
                CorrectiveAction.automation_suppressed.is_(False),
            )
        ).unique().all()
    )
    created: list[Notification] = []
    for action in actions:
        action_deliveries_created = 0
        priority_settings = settings.get("priority_escalation_thresholds", {}).get(
            action.priority.value, {}
        )
        due_milestones = priority_settings.get("due_soon_days", default_due)
        overdue_milestones = priority_settings.get("overdue_days", default_overdue)
        days = action.days_until_due
        if days is None:
            continue
        if days >= 0 and days in due_milestones:
            milestone_key = f"due_soon_{days}"
            notification_type = NotificationType.action_due_soon
            severity = NotificationSeverity.warning
            message = (
                f"Action is due today."
                if days == 0
                else f"Action is due in {days} day(s)."
            )
            recipients = {action.owner_user_id}
        elif days < 0 and abs(days) in overdue_milestones:
            overdue_days = abs(days)
            milestone_key = f"overdue_{overdue_days}"
            notification_type = (
                NotificationType.action_escalation
                if overdue_days >= 7
                else NotificationType.action_overdue
            )
            severity = NotificationSeverity.critical
            message = f"Action is {overdue_days} day(s) overdue."
            recipients = {action.owner_user_id}
            recipients.update(_notification_recipients_for_managers(db, action))
        else:
            continue
        for recipient_id in recipients:
            if recipient_id is None:
                continue
            exists = db.scalar(
                select(ActionReminderDelivery.id).where(
                    ActionReminderDelivery.action_id == action.id,
                    ActionReminderDelivery.recipient_user_id == recipient_id,
                    ActionReminderDelivery.milestone_key == milestone_key,
                    ActionReminderDelivery.due_date_snapshot == action.current_due_date,
                )
            )
            if exists is not None:
                continue
            delivery = ActionReminderDelivery(
                action_id=action.id,
                recipient_user_id=recipient_id,
                milestone_key=milestone_key,
                due_date_snapshot=action.current_due_date,
            )
            db.add(delivery)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                continue
            action_deliveries_created += 1
            notification = _send_action_notification(
                db,
                action,
                recipient_user_id=recipient_id,
                notification_type=notification_type,
                title=f"Action reminder: {action.action_reference}",
                message=message,
                severity=severity,
            )
            if notification is not None:
                created.append(notification)
        if action_deliveries_created:
            record_action_activity(
                db,
                action,
                event_type="escalation",
                summary=message,
                actor_id=None,
                metadata={"milestone": milestone_key},
            )
            db.commit()
    return created


def bulk_update_actions(
    db: Session,
    actions: list[CorrectiveAction],
    request: ActionBulkRequest,
    *,
    actor_id: int,
) -> list[CorrectiveAction]:
    # Validate every reference before applying any mutation so mixed selections
    # fail atomically.
    if request.operation == "assign_owner":
        if request.owner_user_id is None:
            raise CorrectiveActionAssignmentError("owner_user_id is required")
        _ensure_user_exists(db, request.owner_user_id)
    elif request.operation == "assign_department":
        if request.responsible_department_id is None:
            raise CorrectiveActionDepartmentNotFoundError("responsible_department_id is required")
        _ensure_department_exists(db, request.responsible_department_id)
    elif request.operation == "change_priority" and request.priority is None:
        raise CorrectiveActionServiceError("priority is required")
    elif request.operation == "set_due_date":
        if request.current_due_date is None:
            raise CorrectiveActionExtensionError("current_due_date is required")
        if any(action.lifecycle_status not in {CorrectiveActionStatus.draft, CorrectiveActionStatus.open} for action in actions):
            raise CorrectiveActionExtensionError("Active action due dates must use individual extension governance")
    elif request.operation == "place_on_hold":
        for action in actions:
            _validate_transition(action.lifecycle_status, CorrectiveActionStatus.on_hold)
    elif request.operation == "resume":
        for action in actions:
            _validate_transition(action.lifecycle_status, CorrectiveActionStatus.in_progress)

    now = _now()
    for action in actions:
        if request.operation == "assign_owner":
            previous_owner = action.owner_user_id
            action.owner_user_id = request.owner_user_id
            action.assigned_by_user_id = actor_id
            action.assigned_at = now
            action.accepted_at = None
            action.lifecycle_status = CorrectiveActionStatus.assigned
            action.assignment_history.append(ActionAssignmentHistory(owner_user_id=request.owner_user_id, assigned_by_user_id=actor_id, assignment_type="reassigned" if previous_owner else "assigned", reason=request.note))
            event_type = "reassigned" if previous_owner else "assigned"
        elif request.operation == "assign_department":
            action.responsible_department_id = request.responsible_department_id
            event_type = "responsible_department_changed"
        elif request.operation == "change_priority":
            action.priority = request.priority
            event_type = "priority_changed"
        elif request.operation == "set_due_date":
            action.current_due_date = request.current_due_date
            action.original_due_date = action.original_due_date or request.current_due_date
            event_type = "due_date_set"
        elif request.operation == "place_on_hold":
            action.lifecycle_status = CorrectiveActionStatus.on_hold
            event_type = "put_on_hold"
        else:
            action.lifecycle_status = CorrectiveActionStatus.in_progress
            action.started_at = action.started_at or now
            event_type = "resumed"
        record_action_activity(db, action, event_type=event_type, summary=request.note or f"Bulk operation: {request.operation}", actor_id=actor_id, metadata={"bulk": True})
    db.commit()
    for action in actions:
        db.refresh(action)
    write_audit_log(db, actor_id=actor_id, action=f"corrective_action.bulk.{request.operation}", resource_type="corrective_action", details={"action_ids": [action.id for action in actions]})
    return actions


def get_action_dashboard(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    statement = select(CorrectiveAction)
    if site_id is not None:
        statement = statement.where(CorrectiveAction.site_id == site_id)
    records = list(db.scalars(statement).unique().all())
    today = date.today()
    active = [item for item in records if item.lifecycle_status not in ACTION_TERMINAL_STATUSES]
    closed = [
        item
        for item in records
        if item.closed_at
        and (date_from is None or item.closed_at.date() >= date_from)
        and (date_to is None or item.closed_at.date() <= date_to)
    ]
    overdue = [item for item in active if item.is_overdue]
    closure_days = [max(0, (item.closed_at.date() - item.created_at.date()).days) for item in closed]

    def rate(numerator: int, denominator: int) -> float:
        return round(numerator * 100 / denominator, 2) if denominator else 0.0

    original_due_closed = [item for item in closed if item.original_due_date]
    current_due_closed = [item for item in closed if item.current_due_date]

    def breakdown(items, getter) -> dict[str, int]:
        return dict(sorted(Counter(str(getter(item) or "Unspecified") for item in items).items(), key=lambda pair: (-pair[1], pair[0])))

    def age_bucket(item: CorrectiveAction) -> str:
        age = item.age_days
        if age <= 7:
            return "0-7"
        if age <= 30:
            return "8-30"
        if age <= 60:
            return "31-60"
        if age <= 90:
            return "61-90"
        return "90+"

    def compact(item: CorrectiveAction) -> dict:
        return {
            "id": item.id,
            "action_reference": item.action_reference,
            "title": item.title,
            "site": item.site_name,
            "owner": item.owner_name,
            "priority": item.priority.value,
            "lifecycle_status": item.lifecycle_status.value,
            "current_due_date": item.current_due_date.isoformat() if item.current_due_date else None,
            "age_days": item.age_days,
            "days_overdue": item.days_overdue,
            "number_of_extensions": item.number_of_extensions,
        }

    all_verifications = [event for item in records for event in item.activities if event.event_type in {"verification_approved", "verification_rejected"}]
    rejected_verifications = [event for event in all_verifications if event.event_type == "verification_rejected"]
    reopened_records = [item for item in records if item.reopened_at is not None or any(event.event_type == "reopened" for event in item.activities)]
    pending_extensions = sum(extension.decision_status == ActionExtensionDecisionStatus.pending for item in records for extension in item.extensions)
    department_backlog = breakdown(active, lambda item: item.responsible_department_name or item.department_name)
    owner_overdue = breakdown(overdue, lambda item: item.owner_name or "Unassigned")
    source_overdue = breakdown(overdue, lambda item: item.source_type.value)
    return {
        "open_actions": len(active),
        "overdue_actions": len(overdue),
        "overdue_rate": rate(len(overdue), len(active)),
        "due_this_week": sum(bool(item.current_due_date and today <= item.current_due_date <= today + timedelta(days=7)) for item in active),
        "due_in_30_days": sum(bool(item.current_due_date and today <= item.current_due_date <= today + timedelta(days=30)) for item in active),
        "critical_high_overdue": sum(item.priority in {CorrectiveActionPriority.high, CorrectiveActionPriority.critical} for item in overdue),
        "awaiting_verification": sum(item.awaiting_verification for item in active),
        "reopened_actions": len(reopened_records),
        "pending_extension_requests": pending_extensions,
        "closed_this_period": len(closed),
        "original_due_date_on_time_closure_rate": rate(sum(item.closed_at.date() <= item.original_due_date for item in original_due_closed), len(original_due_closed)),
        "current_due_date_on_time_closure_rate": rate(sum(item.closed_at.date() <= item.current_due_date for item in current_due_closed), len(current_due_closed)),
        "average_closure_days": round(sum(closure_days) / len(closure_days), 2) if closure_days else 0.0,
        "median_closure_days": round(float(median(closure_days)), 2) if closure_days else 0.0,
        "verification_rejection_rate": rate(len(rejected_verifications), len(all_verifications)),
        "multiple_extension_actions": sum(item.number_of_extensions > 1 for item in records),
        "overdue_30_plus": sum(item.days_overdue >= 30 for item in overdue),
        "overdue_60_plus": sum(item.days_overdue >= 60 for item in overdue),
        "overdue_90_plus": sum(item.days_overdue >= 90 for item in overdue),
        "by_site": breakdown(active, lambda item: item.site_name),
        "by_department": breakdown(active, lambda item: item.department_name),
        "by_responsible_department": breakdown(active, lambda item: item.responsible_department_name),
        "by_owner": breakdown(active, lambda item: item.owner_name or "Unassigned"),
        "by_manager": breakdown(active, lambda item: item.assigned_by_name),
        "by_source": breakdown(active, lambda item: item.source_type.value),
        "by_priority": breakdown(active, lambda item: item.priority.value),
        "by_status": breakdown(active, lambda item: item.lifecycle_status.value),
        "by_age_bucket": breakdown(active, age_bucket),
        "oldest_open_actions": [compact(item) for item in sorted(active, key=lambda item: (-item.age_days, item.id))[:10]],
        "most_overdue_actions": [compact(item) for item in sorted(overdue, key=lambda item: (-item.days_overdue, item.id))[:10]],
        "repeated_extension_actions": [compact(item) for item in sorted((item for item in records if item.number_of_extensions > 1), key=lambda item: (-item.number_of_extensions, item.id))[:10]],
        "departments_with_highest_backlog": department_backlog,
        "owners_with_overdue_actions": owner_overdue,
        "sources_generating_most_overdue_actions": source_overdue,
    }
