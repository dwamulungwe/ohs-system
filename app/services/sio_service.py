from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveActionPriority, CorrectiveActionSourceType
from app.models.department import Department
from app.models.incident import IncidentSeverity
from app.models.notification import (
    Notification,
    NotificationSeverity,
    NotificationType,
    RelatedEntityType,
)
from app.models.organisation import OrganisationSettings
from app.models.site import Site
from app.models.sio import (
    SIOActivity,
    SIOAssignmentStatus,
    SIOComment,
    SIOObservationNature,
    SIOReferenceSequence,
    SIOStatus,
    SIO_TERMINAL_STATUSES,
    SIOUrgency,
    SafetyImprovementObservation,
)
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.hazard import HazardCreate
from app.schemas.incident import IncidentCreate
from app.schemas.notification import NotificationCreate
from app.schemas.sio import (
    SIOAssignmentRequest,
    SIOBulkRequest,
    SIOCommentCreate,
    SIOCreate,
    SIOEscalationOptions,
    SIOInvestigationUpdate,
    SIOUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.hazard_service import create_hazard
from app.services.incident_service import create_incident
from app.services.notification_service import (
    create_notification,
    create_notification_once,
    get_active_user_ids_for_roles,
)
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER
from app.services.tenancy import current_organisation_id


class SIOServiceError(Exception):
    pass


class SIONotFoundError(SIOServiceError):
    pass


class SIOSiteNotFoundError(SIOServiceError):
    pass


class SIOUserNotFoundError(SIOServiceError):
    pass


class SIODepartmentNotFoundError(SIOServiceError):
    pass


class SIODuplicateError(SIOServiceError):
    pass


class SIOLinkAlreadyExistsError(SIOServiceError):
    pass


class SIOEscalationValidationError(SIOServiceError):
    pass


class SIOTransitionError(SIOServiceError):
    pass


class SIOAssignmentError(SIOServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_site_exists(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise SIOSiteNotFoundError(f"Site {site_id} was not found")
    return site


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> Optional[User]:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        raise SIOUserNotFoundError(f"User {user_id} was not found")
    return user


def _ensure_department_exists(db: Session, department_id: Optional[int]) -> Optional[Department]:
    if department_id is None:
        return None
    department = db.get(Department, department_id)
    if department is None:
        raise SIODepartmentNotFoundError(f"Department {department_id} was not found")
    return department


def _validate_references(db: Session, data: dict) -> None:
    if data.get("site_id") is not None:
        _ensure_site_exists(db, data["site_id"])
    for key in (
        "responsible_hs_officer_user_id",
        "responsible_person_user_id",
        "responsible_user_id",
        "investigator_user_id",
    ):
        _ensure_user_exists(db, data.get(key))
    _ensure_department_exists(db, data.get("department_id"))
    _ensure_department_exists(db, data.get("responsible_department_id"))


def _workflow_settings(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    return dict(settings.sio_workflow_configuration or {}) if settings else {}


def _notification_settings(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    return dict(settings.notification_preferences or {}) if settings else {}


def _sio_notifications_enabled(db: Session) -> bool:
    return bool(_notification_settings(db).get("sio_notifications_enabled", True))


def _default_due_date(db: Session, urgency: Optional[SIOUrgency]) -> Optional[date]:
    if urgency is None:
        return None
    configured = _workflow_settings(db).get("default_due_days_by_urgency", {})
    days = configured.get(urgency.value)
    if not isinstance(days, int) or days < 0:
        return None
    return date.today() + timedelta(days=days)


def _reference_prefix(db: Session) -> str:
    settings = db.scalar(select(OrganisationSettings))
    prefix = (settings.numbering_prefixes or {}).get("sio", "SIO") if settings else "SIO"
    sanitized = "".join(character for character in str(prefix).upper() if character.isalnum() or character == "-")
    return sanitized.strip("-")[:20] or "SIO"


def _next_reference_number(db: Session) -> str:
    organisation_id = current_organisation_id(db)
    year = _now().year
    for _attempt in range(5):
        sequence = db.scalar(
            select(SIOReferenceSequence)
            .where(SIOReferenceSequence.year == year)
            .with_for_update()
        )
        if sequence is None:
            try:
                with db.begin_nested():
                    sequence = SIOReferenceSequence(
                        organisation_id=organisation_id,
                        year=year,
                        last_value=1,
                    )
                    db.add(sequence)
                    db.flush()
                value = 1
            except IntegrityError:
                continue
        else:
            sequence.last_value += 1
            value = sequence.last_value
            db.add(sequence)
            db.flush()
        return f"{_reference_prefix(db)}-{year}-{value:06d}"
    raise SIOServiceError("Unable to allocate a unique SIO reference number")


def record_sio_activity(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    event_type: str,
    message: str,
    actor_id: Optional[int],
    metadata: Optional[dict] = None,
    commit: bool = False,
) -> SIOActivity:
    activity = SIOActivity(
        sio_id=sio.id,
        actor_user_id=actor_id,
        event_type=event_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(activity)
    if commit:
        db.commit()
        db.refresh(activity)
    return activity


def _sync_names_and_responsibility(db: Session, data: dict) -> None:
    department = _ensure_department_exists(db, data.get("department_id"))
    if department is not None:
        data["department"] = department.name
    responsible_department = _ensure_department_exists(db, data.get("responsible_department_id"))
    if responsible_department is not None:
        data["responsible_department"] = responsible_department.name

    if "responsible_user_id" in data and data.get("responsible_user_id") is not None:
        user = _ensure_user_exists(db, data["responsible_user_id"])
        data["responsible_person_user_id"] = user.id
        data["responsible_person_name"] = user.full_name
    elif "responsible_person_user_id" in data and data.get("responsible_person_user_id") is not None:
        user = _ensure_user_exists(db, data["responsible_person_user_id"])
        data["responsible_user_id"] = user.id
        if not data.get("responsible_person_name"):
            data["responsible_person_name"] = user.full_name


def list_sios(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    department: Optional[str] = None,
    department_id: Optional[int] = None,
    responsible_department_id: Optional[int] = None,
    responsible_user_id: Optional[int] = None,
    source_type: Optional[str] = None,
    status: Optional[SIOStatus] = None,
    observation_nature: Optional[SIOObservationNature] = None,
    urgency: Optional[SIOUrgency] = None,
    category: Optional[str] = None,
    incident_classification: Optional[str] = None,
    overdue: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    view: Optional[str] = None,
    current_user_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[SafetyImprovementObservation]] = select(SafetyImprovementObservation)
    filters = (
        (site_id, SafetyImprovementObservation.site_id),
        (department, SafetyImprovementObservation.department),
        (department_id, SafetyImprovementObservation.department_id),
        (responsible_department_id, SafetyImprovementObservation.responsible_department_id),
        (responsible_user_id, SafetyImprovementObservation.responsible_user_id),
        (source_type, SafetyImprovementObservation.source_type),
        (status, SafetyImprovementObservation.status),
        (observation_nature, SafetyImprovementObservation.observation_nature),
        (urgency, SafetyImprovementObservation.urgency),
        (category, SafetyImprovementObservation.category),
        (incident_classification, SafetyImprovementObservation.incident_classification),
    )
    for value, field in filters:
        if value is not None:
            statement = statement.where(field == value)
    if overdue is True:
        statement = statement.where(
            SafetyImprovementObservation.due_date < date.today(),
            SafetyImprovementObservation.status.notin_(list(SIO_TERMINAL_STATUSES)),
        )
    elif overdue is False:
        statement = statement.where(
            or_(
                SafetyImprovementObservation.due_date.is_(None),
                SafetyImprovementObservation.due_date >= date.today(),
                SafetyImprovementObservation.status.in_(list(SIO_TERMINAL_STATUSES)),
            )
        )
    if date_from is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date >= date_from)
    if date_to is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date <= date_to)
    if view and current_user_id is not None:
        if view == "assigned_to_me":
            statement = statement.where(SafetyImprovementObservation.responsible_user_id == current_user_id)
        elif view == "reported_by_me":
            statement = statement.where(SafetyImprovementObservation.created_by_user_id == current_user_id)
        elif view == "awaiting_my_verification":
            statement = statement.where(SafetyImprovementObservation.status == SIOStatus.pending_verification)
        elif view == "overdue_assigned_to_me":
            statement = statement.where(
                SafetyImprovementObservation.responsible_user_id == current_user_id,
                SafetyImprovementObservation.due_date < date.today(),
                SafetyImprovementObservation.status.notin_(list(SIO_TERMINAL_STATUSES)),
            )
        else:
            raise SIOServiceError("Unknown SIO view preset")
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                SafetyImprovementObservation.reference_number.ilike(term),
                SafetyImprovementObservation.description.ilike(term),
                SafetyImprovementObservation.department.ilike(term),
                SafetyImprovementObservation.responsible_department.ilike(term),
                SafetyImprovementObservation.source_type.ilike(term),
                SafetyImprovementObservation.category.ilike(term),
                SafetyImprovementObservation.incident_classification.ilike(term),
                SafetyImprovementObservation.external_reference_id.ilike(term),
                SafetyImprovementObservation.responsible_person_name.ilike(term),
            )
        )
    statement = statement.order_by(
        SafetyImprovementObservation.observation_date.desc().nullslast(),
        SafetyImprovementObservation.id.desc(),
    )
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_sio(db: Session, sio_id: int) -> SafetyImprovementObservation:
    sio = db.get(SafetyImprovementObservation, sio_id)
    if sio is None:
        raise SIONotFoundError(f"SIO {sio_id} was not found")
    return sio


def _send_notification(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    recipient_user_id: Optional[int],
    notification_type: NotificationType,
    title: str,
    message: str,
    severity: NotificationSeverity = NotificationSeverity.info,
    once: bool = False,
) -> Optional[Notification]:
    if recipient_user_id is None or not _sio_notifications_enabled(db):
        return None
    payload = NotificationCreate(
        recipient_user_id=recipient_user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        severity=severity,
        related_entity_type=RelatedEntityType.sio,
        related_entity_id=sio.id,
    )
    return create_notification_once(db, payload) if once else create_notification(db, payload)


def _manager_recipient_ids(db: Session, sio: SafetyImprovementObservation) -> list[int]:
    return get_active_user_ids_for_roles(
        db,
        role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER],
        site_id=sio.site_id,
    )


def _notify_urgent_sio(db: Session, sio: SafetyImprovementObservation) -> None:
    if sio.urgency not in {SIOUrgency.high, SIOUrgency.urgent}:
        return
    recipients = set(_manager_recipient_ids(db, sio))
    if sio.responsible_hs_officer_user_id:
        recipients.add(sio.responsible_hs_officer_user_id)
    for recipient in recipients:
        _send_notification(
            db,
            sio,
            recipient_user_id=recipient,
            notification_type=NotificationType.sio_urgent_high,
            title=f"Urgent/high SIO {sio.reference_number}",
            message=sio.description[:500],
            severity=NotificationSeverity.critical,
            once=True,
        )


def create_sio(
    db: Session,
    sio_in: SIOCreate,
    *,
    actor_id: Optional[int],
    is_import: bool = False,
) -> SafetyImprovementObservation:
    data = sio_in.model_dump()
    _validate_references(db, data)
    _sync_names_and_responsibility(db, data)
    if data.get("due_date") is None:
        data["due_date"] = _default_due_date(db, data.get("urgency"))
    if data.get("responsible_user_id") is not None and not is_import:
        data["assignment_status"] = SIOAssignmentStatus.assigned
        data["assigned_by_user_id"] = actor_id
        data["assigned_at"] = _now()
        if data.get("status") in {SIOStatus.unassigned, SIOStatus.open}:
            data["status"] = SIOStatus.assigned
    sio = SafetyImprovementObservation(
        **data,
        reference_number=_next_reference_number(db),
        created_by_user_id=actor_id,
    )
    db.add(sio)
    try:
        db.flush()
        record_sio_activity(
            db,
            sio,
            event_type="imported" if is_import else "created",
            message=(
                "Historical SIO imported without workflow side effects"
                if is_import
                else "Safety improvement observation created"
            ),
            actor_id=actor_id,
            metadata={"source_system": sio.source_system} if sio.source_system else {},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SIODuplicateError(
            "An SIO with this source reference or organisation reference already exists"
        ) from exc
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.import" if is_import else "sio.create",
        resource_type="sio",
        resource_id=sio.id,
        details={"reference_number": sio.reference_number, "site_id": sio.site_id},
    )
    if not is_import:
        _notify_urgent_sio(db, sio)
        if sio.responsible_user_id:
            _send_notification(
                db,
                sio,
                recipient_user_id=sio.responsible_user_id,
                notification_type=NotificationType.sio_assigned,
                title=f"SIO assigned: {sio.reference_number}",
                message=sio.description[:500],
            )
    return sio


WORKFLOW_TRANSITIONS: dict[SIOStatus, set[SIOStatus]] = {
    SIOStatus.unassigned: {
        SIOStatus.open,
        SIOStatus.assigned,
        SIOStatus.assigned_to_responsible_person,
        SIOStatus.assigned_to_action_tracker,
        SIOStatus.complete,
    },
    SIOStatus.open: {
        SIOStatus.unassigned,
        SIOStatus.assigned,
        SIOStatus.assigned_to_responsible_person,
        SIOStatus.assigned_to_action_tracker,
        SIOStatus.in_progress,
        SIOStatus.complete,
    },
    SIOStatus.assigned: {SIOStatus.in_progress, SIOStatus.unassigned, SIOStatus.complete},
    SIOStatus.assigned_to_responsible_person: {
        SIOStatus.in_progress,
        SIOStatus.complete,
    },
    SIOStatus.assigned_to_action_tracker: {SIOStatus.in_progress, SIOStatus.complete},
    SIOStatus.in_progress: {SIOStatus.pending_verification, SIOStatus.complete},
    SIOStatus.pending_verification: {SIOStatus.in_progress, SIOStatus.closed},
    SIOStatus.complete: {SIOStatus.pending_verification, SIOStatus.reopened},
    SIOStatus.closed: {SIOStatus.reopened},
    SIOStatus.no_action_required: {SIOStatus.reopened},
    SIOStatus.reopened: {
        SIOStatus.open,
        SIOStatus.unassigned,
        SIOStatus.assigned,
        SIOStatus.in_progress,
    },
}


def _validate_transition(current: SIOStatus, target: SIOStatus, *, privileged: bool = False) -> None:
    if current == target:
        return
    if target in {SIOStatus.closed, SIOStatus.no_action_required, SIOStatus.reopened} and not privileged:
        raise SIOTransitionError("Use the dedicated verification, no-action, or reopen workflow")
    if target not in WORKFLOW_TRANSITIONS.get(current, set()):
        raise SIOTransitionError(f"Invalid SIO transition from {current.value} to {target.value}")


def update_sio(
    db: Session,
    sio: SafetyImprovementObservation,
    sio_in: SIOUpdate,
    *,
    actor_id: Optional[int],
) -> SafetyImprovementObservation:
    data = sio_in.model_dump(exclude_unset=True)
    _validate_references(db, data)
    _sync_names_and_responsibility(db, data)
    if data.get("status") is not None:
        _validate_transition(sio.status, data["status"])
    previous_status = sio.status
    previous_due_date = sio.due_date
    previous_responsible_user_id = sio.responsible_user_id
    for field, value in data.items():
        setattr(sio, field, value)
    if sio.status == SIOStatus.complete and sio.completed_at is None:
        sio.completed_at = _now()
    if "responsible_user_id" in data and data["responsible_user_id"] != previous_responsible_user_id:
        sio.responsible_person_user_id = data["responsible_user_id"]
        sio.assigned_by_user_id = actor_id
        sio.assigned_at = _now()
        sio.assignment_status = (
            SIOAssignmentStatus.reassigned
            if previous_responsible_user_id is not None
            else SIOAssignmentStatus.assigned
        )
        record_sio_activity(
            db,
            sio,
            event_type="reassigned" if previous_responsible_user_id else "assigned",
            message="SIO responsibility updated",
            actor_id=actor_id,
            metadata={
                "previous_user_id": previous_responsible_user_id,
                "responsible_user_id": sio.responsible_user_id,
            },
        )
    if sio.status != previous_status:
        record_sio_activity(
            db,
            sio,
            event_type="status_changed",
            message=f"Status changed from {previous_status.value} to {sio.status.value}",
            actor_id=actor_id,
            metadata={"from": previous_status.value, "to": sio.status.value},
        )
    if sio.due_date != previous_due_date:
        record_sio_activity(
            db,
            sio,
            event_type="due_date_changed",
            message=f"Due date changed to {sio.due_date or 'not set'}",
            actor_id=actor_id,
            metadata={
                "previous_due_date": previous_due_date.isoformat() if previous_due_date else None,
                "due_date": sio.due_date.isoformat() if sio.due_date else None,
            },
        )
    db.add(sio)
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.update",
        resource_type="sio",
        resource_id=sio.id,
        details={"updated_fields": sorted(data)},
    )
    return sio


def assign_sio(
    db: Session,
    sio: SafetyImprovementObservation,
    request: SIOAssignmentRequest,
    *,
    actor_id: int,
) -> SafetyImprovementObservation:
    user = _ensure_user_exists(db, request.responsible_user_id)
    department = _ensure_department_exists(db, request.responsible_department_id)
    previous_user_id = sio.responsible_user_id
    sio.responsible_user_id = user.id if user else None
    sio.responsible_person_user_id = user.id if user else None
    sio.responsible_person_name = user.full_name if user else sio.responsible_person_name
    sio.responsible_department_id = department.id if department else None
    sio.responsible_department = department.name if department else sio.responsible_department
    sio.assigned_by_user_id = actor_id
    sio.assigned_at = _now()
    sio.assignment_decline_reason = None
    sio.assignment_status = (
        SIOAssignmentStatus.reassigned if previous_user_id is not None else SIOAssignmentStatus.assigned
    )
    sio.status = SIOStatus.assigned
    if request.due_date is not None:
        sio.due_date = request.due_date
    event_type = "reassigned" if previous_user_id is not None else "assigned"
    record_sio_activity(
        db,
        sio,
        event_type=event_type,
        message=request.note or f"SIO {event_type}",
        actor_id=actor_id,
        metadata={
            "previous_user_id": previous_user_id,
            "responsible_user_id": sio.responsible_user_id,
            "responsible_department_id": sio.responsible_department_id,
        },
    )
    db.add(sio)
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action=f"sio.{event_type}",
        resource_type="sio",
        resource_id=sio.id,
        details={"responsible_user_id": sio.responsible_user_id},
    )
    if user:
        _send_notification(
            db,
            sio,
            recipient_user_id=user.id,
            notification_type=(
                NotificationType.sio_reassigned
                if event_type == "reassigned"
                else NotificationType.sio_assigned
            ),
            title=f"SIO {event_type}: {sio.reference_number}",
            message=request.note or sio.description[:500],
        )
    return sio


def accept_sio_assignment(
    db: Session, sio: SafetyImprovementObservation, *, actor_id: int
) -> SafetyImprovementObservation:
    if sio.responsible_user_id != actor_id:
        raise SIOAssignmentError("Only the assigned responsible user may accept this assignment")
    if sio.assignment_status not in {SIOAssignmentStatus.assigned, SIOAssignmentStatus.reassigned}:
        raise SIOAssignmentError("This SIO does not have an assignment awaiting acceptance")
    sio.assignment_status = SIOAssignmentStatus.accepted
    record_sio_activity(
        db,
        sio,
        event_type="accepted",
        message="Assignment accepted",
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.assignment.accept",
        resource_type="sio",
        resource_id=sio.id,
    )
    return sio


def decline_sio_assignment(
    db: Session, sio: SafetyImprovementObservation, *, actor_id: int, reason: str
) -> SafetyImprovementObservation:
    if sio.responsible_user_id != actor_id:
        raise SIOAssignmentError("Only the assigned responsible user may decline this assignment")
    if sio.assignment_status not in {SIOAssignmentStatus.assigned, SIOAssignmentStatus.reassigned}:
        raise SIOAssignmentError("This SIO does not have an assignment awaiting a decision")
    assigner_id = sio.assigned_by_user_id
    previous_user_id = sio.responsible_user_id
    sio.assignment_status = SIOAssignmentStatus.declined
    sio.assignment_decline_reason = reason
    sio.status = SIOStatus.unassigned
    sio.responsible_user_id = None
    sio.responsible_person_user_id = None
    record_sio_activity(
        db,
        sio,
        event_type="declined",
        message=reason,
        actor_id=actor_id,
        metadata={"declined_by_user_id": previous_user_id, "assigned_by_user_id": assigner_id},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.assignment.decline",
        resource_type="sio",
        resource_id=sio.id,
        details={"reason": reason},
    )
    recipients = set(_manager_recipient_ids(db, sio))
    if assigner_id:
        recipients.add(assigner_id)
    for recipient in recipients:
        _send_notification(
            db,
            sio,
            recipient_user_id=recipient,
            notification_type=NotificationType.sio_assignment_declined,
            title=f"SIO assignment declined: {sio.reference_number}",
            message=reason,
            severity=NotificationSeverity.warning,
        )
    return sio


def transition_sio(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    target_status: SIOStatus,
    actor_id: int,
    reason: Optional[str] = None,
) -> SafetyImprovementObservation:
    _validate_transition(sio.status, target_status)
    previous = sio.status
    sio.status = target_status
    if target_status == SIOStatus.complete and sio.completed_at is None:
        sio.completed_at = _now()
    record_sio_activity(
        db,
        sio,
        event_type="status_changed",
        message=reason or f"Status changed from {previous.value} to {target_status.value}",
        actor_id=actor_id,
        metadata={"from": previous.value, "to": target_status.value},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.status.transition",
        resource_type="sio",
        resource_id=sio.id,
        details={"from": previous.value, "to": target_status.value, "reason": reason},
    )
    return sio


def update_sio_investigation(
    db: Session,
    sio: SafetyImprovementObservation,
    request: SIOInvestigationUpdate,
    *,
    actor_id: int,
) -> SafetyImprovementObservation:
    data = request.model_dump(exclude_unset=True)
    _ensure_user_exists(db, data.get("investigator_user_id"))
    for field, value in data.items():
        setattr(sio, field, value)
    if data.get("investigation_required") and sio.investigation_started_at is None:
        sio.investigation_started_at = _now()
    record_sio_activity(
        db,
        sio,
        event_type="investigation_updated",
        message="SIO investigation updated",
        actor_id=actor_id,
        metadata={"updated_fields": sorted(data)},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.investigation.update",
        resource_type="sio",
        resource_id=sio.id,
        details={"updated_fields": sorted(data)},
    )
    return sio


def list_sio_comments(db: Session, sio_id: int) -> list[SIOComment]:
    return list(
        db.scalars(
            select(SIOComment)
            .where(SIOComment.sio_id == sio_id)
            .order_by(SIOComment.created_at.asc(), SIOComment.id.asc())
        ).all()
    )


def add_sio_comment(
    db: Session,
    sio: SafetyImprovementObservation,
    request: SIOCommentCreate,
    *,
    actor_id: int,
) -> SIOComment:
    comment = SIOComment(sio_id=sio.id, author_user_id=actor_id, body=request.body.strip())
    db.add(comment)
    db.flush()
    record_sio_activity(
        db,
        sio,
        event_type="comment_added",
        message=request.body.strip(),
        actor_id=actor_id,
        metadata={"comment_id": comment.id},
    )
    db.commit()
    db.refresh(comment)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.comment.create",
        resource_type="sio",
        resource_id=sio.id,
        details={"comment_id": comment.id},
    )
    return comment


def list_sio_activity(db: Session, sio_id: int) -> list[SIOActivity]:
    return list(
        db.scalars(
            select(SIOActivity)
            .where(SIOActivity.sio_id == sio_id)
            .order_by(SIOActivity.created_at.asc(), SIOActivity.id.asc())
        ).all()
    )


def request_sio_closure(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    actor_id: int,
    notes: str,
) -> SafetyImprovementObservation:
    if sio.status in {SIOStatus.closed, SIOStatus.no_action_required}:
        raise SIOTransitionError("A closed SIO cannot request closure")
    previous = sio.status
    sio.status = SIOStatus.pending_verification
    sio.completed_at = sio.completed_at or _now()
    sio.closure_requested_by_user_id = actor_id
    sio.closure_requested_at = _now()
    sio.closure_notes = notes
    record_sio_activity(
        db,
        sio,
        event_type="closure_requested",
        message=notes,
        actor_id=actor_id,
        metadata={"previous_status": previous.value},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.closure.request",
        resource_type="sio",
        resource_id=sio.id,
        details={"notes": notes},
    )
    for recipient in {sio.created_by_user_id, sio.assigned_by_user_id}:
        if recipient == actor_id:
            continue
        _send_notification(
            db,
            sio,
            recipient_user_id=recipient,
            notification_type=NotificationType.sio_closure_requested,
            title=f"SIO closure requested: {sio.reference_number}",
            message=notes,
            severity=NotificationSeverity.info,
            once=True,
        )
    recipients = set(_manager_recipient_ids(db, sio))
    if sio.responsible_hs_officer_user_id:
        recipients.add(sio.responsible_hs_officer_user_id)
    for recipient in recipients:
        _send_notification(
            db,
            sio,
            recipient_user_id=recipient,
            notification_type=NotificationType.sio_verification_required,
            title=f"SIO verification required: {sio.reference_number}",
            message=notes,
            severity=NotificationSeverity.warning,
            once=True,
        )
    return sio


def verify_sio_closure(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    actor_id: int,
    approved: bool,
    notes: str,
) -> SafetyImprovementObservation:
    if sio.status != SIOStatus.pending_verification:
        raise SIOTransitionError("SIO is not pending verification")
    if approved:
        sio.status = SIOStatus.closed
        sio.closed_at = _now()
        event_type = "closed"
        message = notes
    else:
        sio.status = SIOStatus.in_progress
        event_type = "verification_rejected"
        message = notes
    sio.verified_by_user_id = actor_id
    sio.verified_at = _now()
    sio.verification_notes = notes
    record_sio_activity(
        db,
        sio,
        event_type=event_type,
        message=message,
        actor_id=actor_id,
        metadata={"approved": approved},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.verification.approve" if approved else "sio.verification.reject",
        resource_type="sio",
        resource_id=sio.id,
        details={"notes": notes},
    )
    return sio


def mark_sio_no_action_required(
    db: Session, sio: SafetyImprovementObservation, *, actor_id: int, reason: str
) -> SafetyImprovementObservation:
    if sio.status == SIOStatus.closed:
        raise SIOTransitionError("Closed SIOs must be reopened before changing disposition")
    sio.status = SIOStatus.no_action_required
    sio.no_action_reason = reason
    sio.completed_at = sio.completed_at or _now()
    sio.closed_at = sio.closed_at or _now()
    record_sio_activity(
        db,
        sio,
        event_type="no_action_required",
        message=reason,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.no_action_required",
        resource_type="sio",
        resource_id=sio.id,
        details={"reason": reason},
    )
    return sio


def reopen_sio(
    db: Session, sio: SafetyImprovementObservation, *, actor_id: int, reason: str
) -> SafetyImprovementObservation:
    if sio.status not in {SIOStatus.closed, SIOStatus.complete, SIOStatus.no_action_required}:
        raise SIOTransitionError("Only completed or closed SIOs may be reopened")
    previous = sio.status
    sio.status = SIOStatus.reopened
    sio.reopened_by_user_id = actor_id
    sio.reopened_at = _now()
    sio.reopen_reason = reason
    record_sio_activity(
        db,
        sio,
        event_type="reopened",
        message=reason,
        actor_id=actor_id,
        metadata={"previous_status": previous.value},
    )
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.reopen",
        resource_type="sio",
        resource_id=sio.id,
        details={"reason": reason},
    )
    recipients = {sio.responsible_user_id, sio.created_by_user_id, sio.assigned_by_user_id}
    for recipient in recipients:
        _send_notification(
            db,
            sio,
            recipient_user_id=recipient,
            notification_type=NotificationType.sio_reopened,
            title=f"SIO reopened: {sio.reference_number}",
            message=reason,
            severity=NotificationSeverity.warning,
        )
    return sio


def bulk_update_sios(
    db: Session,
    records: list[SafetyImprovementObservation],
    request: SIOBulkRequest,
    *,
    actor_id: int,
) -> list[SafetyImprovementObservation]:
    if request.operation == "assign":
        if request.responsible_user_id is None and request.responsible_department_id is None:
            raise SIOAssignmentError("Bulk assignment requires a user or department")
        user = _ensure_user_exists(db, request.responsible_user_id)
        department = _ensure_department_exists(db, request.responsible_department_id)
        for sio in records:
            previous_user_id = sio.responsible_user_id
            sio.responsible_user_id = user.id if user else None
            sio.responsible_person_user_id = user.id if user else None
            sio.responsible_person_name = user.full_name if user else sio.responsible_person_name
            sio.responsible_department_id = department.id if department else None
            sio.responsible_department = department.name if department else sio.responsible_department
            sio.assigned_by_user_id = actor_id
            sio.assigned_at = _now()
            sio.assignment_status = (
                SIOAssignmentStatus.reassigned
                if previous_user_id is not None
                else SIOAssignmentStatus.assigned
            )
            sio.status = SIOStatus.assigned
            record_sio_activity(
                db,
                sio,
                event_type="reassigned" if previous_user_id else "assigned",
                message=request.note or "Bulk responsibility assignment",
                actor_id=actor_id,
                metadata={"responsible_user_id": sio.responsible_user_id},
            )
    elif request.operation == "set_due_date":
        if request.due_date is None:
            raise SIOServiceError("Bulk due-date update requires a due date")
        for sio in records:
            previous = sio.due_date
            sio.due_date = request.due_date
            record_sio_activity(
                db,
                sio,
                event_type="due_date_changed",
                message=request.note or f"Due date changed to {request.due_date}",
                actor_id=actor_id,
                metadata={
                    "previous_due_date": previous.isoformat() if previous else None,
                    "due_date": request.due_date.isoformat(),
                },
            )
    elif request.operation == "transition":
        if request.status is None:
            raise SIOTransitionError("Bulk transition requires a target status")
        for sio in records:
            _validate_transition(sio.status, request.status)
        for sio in records:
            previous = sio.status
            sio.status = request.status
            if request.status == SIOStatus.complete and sio.completed_at is None:
                sio.completed_at = _now()
            record_sio_activity(
                db,
                sio,
                event_type="status_changed",
                message=request.note or f"Status changed to {request.status.value}",
                actor_id=actor_id,
                metadata={"from": previous.value, "to": request.status.value},
            )
    else:
        raise SIOServiceError("Unknown bulk operation")
    db.add_all(records)
    db.commit()
    for sio in records:
        db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action=f"sio.bulk.{request.operation}",
        resource_type="sio",
        details={"sio_ids": [sio.id for sio in records]},
    )
    return records


def _default_title(sio: SafetyImprovementObservation) -> str:
    label = sio.category or sio.incident_classification or sio.observation_nature.value
    return f"{sio.reference_number}: {label}"[:200]


def _urgency_score(urgency: Optional[SIOUrgency]) -> int:
    return {
        SIOUrgency.urgent: 5,
        SIOUrgency.high: 4,
        SIOUrgency.medium: 3,
        SIOUrgency.low: 2,
        SIOUrgency.not_applicable: 1,
        None: 2,
    }[urgency]


def _incident_severity(urgency: Optional[SIOUrgency]) -> IncidentSeverity:
    return {
        SIOUrgency.urgent: IncidentSeverity.critical,
        SIOUrgency.high: IncidentSeverity.high,
        SIOUrgency.medium: IncidentSeverity.medium,
        SIOUrgency.low: IncidentSeverity.low,
        SIOUrgency.not_applicable: IncidentSeverity.low,
        None: IncidentSeverity.low,
    }[urgency]


def _corrective_priority(urgency: Optional[SIOUrgency]) -> CorrectiveActionPriority:
    return {
        SIOUrgency.urgent: CorrectiveActionPriority.critical,
        SIOUrgency.high: CorrectiveActionPriority.high,
        SIOUrgency.medium: CorrectiveActionPriority.medium,
        SIOUrgency.low: CorrectiveActionPriority.low,
        SIOUrgency.not_applicable: CorrectiveActionPriority.low,
        None: CorrectiveActionPriority.medium,
    }[urgency]


def _save_link(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    field: str,
    entity_id: int,
    actor_id: Optional[int],
) -> SafetyImprovementObservation:
    setattr(sio, field, entity_id)
    entity_name = field.replace("linked_", "").replace("_id", "")
    record_sio_activity(
        db,
        sio,
        event_type=f"{entity_name}_generated",
        message=f"Linked {entity_name.replace('_', ' ')} #{entity_id} generated",
        actor_id=actor_id,
        metadata={field: entity_id},
    )
    db.add(sio)
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action=f"sio.{entity_name}.create",
        resource_type="sio",
        resource_id=sio.id,
        details={field: entity_id},
    )
    return sio


def create_linked_hazard(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    actor_id: Optional[int],
    options: Optional[SIOEscalationOptions] = None,
) -> SafetyImprovementObservation:
    if sio.linked_hazard_id is not None:
        raise SIOLinkAlreadyExistsError("This SIO already has a linked hazard")
    score = _urgency_score(sio.urgency)
    hazard = create_hazard(
        db,
        HazardCreate(
            site_id=sio.site_id,
            title=options.title if options and options.title else _default_title(sio),
            description=sio.description,
            likelihood=score,
            impact=score,
            existing_controls=[],
            additional_controls=[],
            owner_user_id=sio.responsible_user_id,
            due_date=options.due_date if options else sio.due_date,
        ),
        reported_by_id=actor_id,
    )
    return _save_link(db, sio, field="linked_hazard_id", entity_id=hazard.id, actor_id=actor_id)


def create_linked_incident(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    actor_id: Optional[int],
    options: Optional[SIOEscalationOptions] = None,
) -> SafetyImprovementObservation:
    if sio.linked_incident_id is not None:
        raise SIOLinkAlreadyExistsError("This SIO already has a linked incident")
    if sio.observation_date is None:
        raise SIOEscalationValidationError(
            "An observation date is required before this SIO can create an incident"
        )
    incident = create_incident(
        db,
        IncidentCreate(
            site_id=sio.site_id,
            title=options.title if options and options.title else _default_title(sio),
            description=sio.description,
            severity=_incident_severity(sio.urgency),
            occurred_at=datetime.combine(sio.observation_date, time.min, tzinfo=timezone.utc),
        ),
        reported_by_id=actor_id,
    )
    return _save_link(db, sio, field="linked_incident_id", entity_id=incident.id, actor_id=actor_id)


def create_linked_corrective_action(
    db: Session,
    sio: SafetyImprovementObservation,
    *,
    actor_id: Optional[int],
    options: Optional[SIOEscalationOptions] = None,
) -> SafetyImprovementObservation:
    if sio.linked_corrective_action_id is not None:
        raise SIOLinkAlreadyExistsError("This SIO already has a linked corrective action")
    due_date = options.due_date if options and options.due_date else sio.due_date
    action = create_corrective_action(
        db,
        CorrectiveActionCreate(
            site_id=sio.site_id,
            department_id=sio.department_id,
            responsible_department_id=sio.responsible_department_id,
            title=options.title if options and options.title else _default_title(sio),
            description=sio.description,
            source_type=CorrectiveActionSourceType.sio,
            source_id=sio.id,
            priority=_corrective_priority(sio.urgency),
            due_date=due_date,
            assigned_to_user_id=sio.responsible_user_id,
        ),
        current_user_id=actor_id,
    )
    return _save_link(
        db,
        sio,
        field="linked_corrective_action_id",
        entity_id=action.id,
        actor_id=actor_id,
    )


def generate_sio_due_notifications(db: Session) -> list[Notification]:
    configuration = _workflow_settings(db)
    due_soon_days = int(configuration.get("due_soon_days", 7))
    overdue_frequency_days = max(1, int(configuration.get("overdue_reminder_frequency_days", 7)))
    manager_escalation_days = max(0, int(configuration.get("manager_escalation_after_days", 7)))
    today = date.today()
    active = list(
        db.scalars(
            select(SafetyImprovementObservation).where(
                SafetyImprovementObservation.due_date.is_not(None),
                SafetyImprovementObservation.status.notin_(list(SIO_TERMINAL_STATUSES)),
            )
        ).all()
    )
    created: list[Notification] = []
    for sio in active:
        recipients = {sio.responsible_user_id}
        if sio.due_date < today and sio.days_overdue >= manager_escalation_days:
            recipients.update(_manager_recipient_ids(db, sio))
        for recipient in recipients:
            if recipient is None:
                continue
            if sio.due_date < today:
                last = db.scalar(
                    select(Notification.created_at)
                    .where(
                        Notification.recipient_user_id == recipient,
                        Notification.notification_type == NotificationType.sio_overdue,
                        Notification.related_entity_type == RelatedEntityType.sio,
                        Notification.related_entity_id == sio.id,
                    )
                    .order_by(Notification.created_at.desc())
                    .limit(1)
                )
                if last is not None:
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if last > _now() - timedelta(days=overdue_frequency_days):
                        continue
                notification = _send_notification(
                    db,
                    sio,
                    recipient_user_id=recipient,
                    notification_type=NotificationType.sio_overdue,
                    title=f"SIO overdue: {sio.reference_number}",
                    message=f"This SIO is {sio.days_overdue} day(s) overdue.",
                    severity=NotificationSeverity.critical,
                )
            elif sio.due_date <= today + timedelta(days=due_soon_days):
                notification = _send_notification(
                    db,
                    sio,
                    recipient_user_id=recipient,
                    notification_type=NotificationType.sio_due_soon,
                    title=f"SIO due soon: {sio.reference_number}",
                    message=f"This SIO is due on {sio.due_date}.",
                    severity=NotificationSeverity.warning,
                    once=True,
                )
            else:
                notification = None
            if notification is not None:
                created.append(notification)
    return created


def get_sio_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    statement = select(SafetyImprovementObservation)
    if site_id is not None:
        statement = statement.where(SafetyImprovementObservation.site_id == site_id)
    if date_from is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date >= date_from)
    if date_to is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date <= date_to)
    records = list(db.scalars(statement).unique().all())

    def count(predicate) -> int:
        return sum(1 for item in records if predicate(item))

    def breakdown(value_getter) -> dict[str, int]:
        return dict(
            sorted(
                Counter(str(value_getter(item) or "Unspecified") for item in records).items(),
                key=lambda pair: (-pair[1], pair[0]),
            )
        )

    active = [item for item in records if item.status not in SIO_TERMINAL_STATUSES]
    closed = [item for item in records if item.closed_at is not None]
    closure_days = [item.age_days for item in closed]
    created_trend: Counter[str] = Counter()
    closed_trend: Counter[str] = Counter()
    for item in records:
        created_on = item.observation_date or (
            item.source_created_at.date() if item.source_created_at else item.created_at.date()
        )
        created_trend[created_on.strftime("%Y-%m")] += 1
        if item.closed_at:
            closed_trend[item.closed_at.strftime("%Y-%m")] += 1
    months = sorted(set(created_trend).union(closed_trend))
    created_vs_closed = {
        month: {"created": created_trend[month], "closed": closed_trend[month]}
        for month in months
    }

    by_department = breakdown(
        lambda item: item.originating_department.name
        if item.originating_department
        else item.department
    )
    by_responsible_department = breakdown(
        lambda item: item.responsible_department_record.name
        if item.responsible_department_record
        else item.responsible_department
    )
    by_responsible_user = breakdown(
        lambda item: item.responsible_user.full_name
        if item.responsible_user
        else item.responsible_person_name
    )
    open_backlog = Counter(
        (
            item.responsible_department_record.name
            if item.responsible_department_record
            else item.responsible_department
            or item.department
            or "Unspecified"
        )
        for item in active
    )
    overdue_users = Counter(
        (
            item.responsible_user.full_name
            if item.responsible_user
            else item.responsible_person_name
            or "Unassigned"
        )
        for item in records
        if item.is_overdue
    )

    def compact(item: SafetyImprovementObservation) -> dict:
        return {
            "id": item.id,
            "reference_number": item.reference_number,
            "description": item.description[:180],
            "site_id": item.site_id,
            "status": item.status.value,
            "age_days": item.age_days,
            "days_overdue": item.days_overdue,
            "due_date": item.due_date.isoformat() if item.due_date else None,
        }

    oldest = sorted(active, key=lambda item: (-item.age_days, item.id))[:5]
    most_overdue = sorted(
        (item for item in records if item.is_overdue),
        key=lambda item: (-item.days_overdue, item.id),
    )[:5]
    open_unassigned = count(
        lambda item: item.status in {SIOStatus.open, SIOStatus.unassigned}
    )
    return {
        "total_observations": len(records),
        "positive_observations": count(lambda item: item.observation_nature == SIOObservationNature.positive),
        "negative_observations": count(lambda item: item.observation_nature == SIOObservationNature.negative),
        "open_observations": len(active),
        "unassigned_observations": count(
            lambda item: item.status == SIOStatus.unassigned
            or item.assignment_status == SIOAssignmentStatus.unassigned
        ),
        "in_progress_observations": count(lambda item: item.status == SIOStatus.in_progress),
        "overdue_observations": count(lambda item: item.is_overdue),
        "pending_verification_observations": count(
            lambda item: item.status == SIOStatus.pending_verification
        ),
        "urgent_high_priority_observations": count(
            lambda item: item.urgency in {SIOUrgency.urgent, SIOUrgency.high}
        ),
        "closed_this_period": len(closed),
        "average_closure_days": round(sum(closure_days) / len(closure_days), 2) if closure_days else 0.0,
        "observations_by_site": breakdown(lambda item: item.site.name if item.site else item.site_id),
        "observations_by_category": breakdown(lambda item: item.category),
        "observations_by_source": breakdown(lambda item: item.source_type),
        "observations_by_department": by_department,
        "observations_by_responsible_department": by_responsible_department,
        "observations_by_responsible_user": by_responsible_user,
        "observations_by_urgency": breakdown(lambda item: item.urgency.value if item.urgency else None),
        "observations_by_status": breakdown(lambda item: item.status.value),
        "observation_trend_by_month": dict(sorted(created_trend.items())),
        "created_vs_closed_trend": created_vs_closed,
        "oldest_open_sios": [compact(item) for item in oldest],
        "most_overdue_sios": [compact(item) for item in most_overdue],
        "departments_with_highest_open_backlog": dict(open_backlog.most_common(10)),
        "responsible_users_with_overdue_sios": dict(overdue_users.most_common(10)),
        "recurring_categories": dict(Counter(item.category or "Unspecified" for item in records).most_common(10)),
        "open_unassigned_observations": open_unassigned,
    }
