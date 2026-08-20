from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.incident import (
    Incident,
    IncidentActivity,
    IncidentClassification,
    IncidentReferenceSequence,
    IncidentSeverity,
    IncidentStatus,
    RegulatoryNotificationStatus,
)
from app.models.organisation import OrganisationSettings
from app.models.site import Site
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentUpdate
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify_critical_incident
from app.services.query_utils import paginate
from app.services.tenancy import current_organisation_id


PLATFORM_CLASSIFICATIONS = {
    "near_miss", "first_aid_injury", "medical_treatment_injury", "restricted_work_case",
    "lost_time_injury", "occupational_illness", "fatality", "property_damage",
    "environmental_incident", "vehicle_incident", "fire_explosion", "security_incident",
    "dangerous_occurrence", "other",
}

TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.draft: {IncidentStatus.reported, IncidentStatus.cancelled},
    IncidentStatus.reported: {IncidentStatus.triaged, IncidentStatus.under_investigation, IncidentStatus.cancelled},
    IncidentStatus.triaged: {IncidentStatus.under_investigation, IncidentStatus.actions_open, IncidentStatus.pending_closure, IncidentStatus.cancelled},
    IncidentStatus.under_investigation: {IncidentStatus.actions_open, IncidentStatus.pending_closure, IncidentStatus.cancelled},
    IncidentStatus.actions_open: {IncidentStatus.pending_closure, IncidentStatus.under_investigation},
    IncidentStatus.pending_closure: {IncidentStatus.closed, IncidentStatus.under_investigation, IncidentStatus.actions_open},
    IncidentStatus.closed: {IncidentStatus.reopened},
    IncidentStatus.reopened: {IncidentStatus.under_investigation, IncidentStatus.actions_open, IncidentStatus.pending_closure},
    # Historical transition compatibility.
    IncidentStatus.open: {IncidentStatus.investigating, IncidentStatus.resolved, IncidentStatus.closed, IncidentStatus.triaged, IncidentStatus.under_investigation},
    IncidentStatus.investigating: {IncidentStatus.resolved, IncidentStatus.closed, IncidentStatus.actions_open, IncidentStatus.pending_closure},
    IncidentStatus.resolved: {IncidentStatus.closed, IncidentStatus.reopened, IncidentStatus.pending_closure},
    IncidentStatus.cancelled: set(),
}


class IncidentServiceError(Exception):
    pass


class IncidentNotFoundError(IncidentServiceError):
    pass


class IncidentSiteNotFoundError(IncidentServiceError):
    pass


class IncidentValidationError(IncidentServiceError):
    pass


class IncidentTransitionError(IncidentServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def incident_settings(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    defaults = {
        "reference_prefix": "INC",
        "default_investigation_due_days": 14,
        "closure_verification_required": True,
        "require_lessons_learned": True,
        "require_medical_follow_up_completion": True,
        "independent_closure_verifier": True,
        "closure_require_investigation_for": ["high", "critical"],
        "action_closure_requirement": "critical_closed",
        "regulator_reminder_days": [7, 3, 1],
        "investigation_reminder_days": [7, 3, 1],
        "recordable_classifications": [
            "medical_treatment_injury", "restricted_work_case", "lost_time_injury",
            "occupational_illness", "fatality",
        ],
    }
    configured = dict(settings.incident_configuration or {}) if settings else {}
    if settings:
        configured.setdefault("reference_prefix", (settings.numbering_prefixes or {}).get("incident", "INC"))
    return {**defaults, **configured}


def _reference_prefix(db: Session) -> str:
    raw = incident_settings(db).get("reference_prefix", "INC")
    value = "".join(character for character in str(raw).upper() if character.isalnum() or character == "-")
    return value.strip("-")[:20] or "INC"


def _next_reference(db: Session, *, year: int) -> str:
    organisation_id = current_organisation_id(db)
    prefix = _reference_prefix(db)
    stem = f"{prefix}-{year}-"
    for _attempt in range(8):
        sequence = db.scalar(
            select(IncidentReferenceSequence)
            .where(IncidentReferenceSequence.year == year)
            .with_for_update()
        )
        if sequence is None:
            try:
                with db.begin_nested():
                    suffixes = []
                    for reference in db.scalars(select(Incident.incident_reference).where(Incident.incident_reference.like(f"{stem}%"))):
                        suffix = str(reference or "")[len(stem):]
                        if suffix.isdigit():
                            suffixes.append(int(suffix))
                    value = max(suffixes, default=0) + 1
                    sequence = IncidentReferenceSequence(
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
        return f"{stem}{value:06d}"
    raise IncidentServiceError("Unable to allocate a unique incident reference")


def _ensure_site_exists(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise IncidentSiteNotFoundError(f"Site {site_id} was not found")
    return site


def _validate_references(db: Session, data: dict) -> None:
    if data.get("department_id") is not None and db.get(Department, data["department_id"]) is None:
        raise IncidentValidationError("Department not found")
    for field in ("supervisor_user_id", "responsible_hs_officer_user_id"):
        if data.get(field) is not None and db.get(User, data[field]) is None:
            raise IncidentValidationError(f"{field.replace('_', ' ').title()} not found")


def _validate_classification(db: Session, code: str) -> Optional[IncidentClassification]:
    classification = db.scalar(select(IncidentClassification).where(IncidentClassification.code == code))
    if classification is not None and not classification.is_active:
        raise IncidentValidationError("Incident classification is inactive")
    if classification is None and code not in PLATFORM_CLASSIFICATIONS:
        # Custom values are accepted only once configured in the tenant catalogue.
        raise IncidentValidationError("Incident classification is not configured")
    return classification


def add_activity(
    db: Session, incident: Incident, event_type: str, summary: str, *,
    actor_id: Optional[int] = None, metadata: Optional[dict] = None,
) -> IncidentActivity:
    activity = IncidentActivity(
        incident_id=incident.id, actor_user_id=actor_id, event_type=event_type,
        summary=summary, event_metadata=metadata or {},
    )
    db.add(activity)
    db.flush()
    return activity


def list_incidents(
    db: Session, *, skip: int = 0, limit: int = 100,
    status: Optional[IncidentStatus] = None, severity: Optional[IncidentSeverity] = None,
    site_id: Optional[int] = None, department_id: Optional[int] = None,
    incident_type: Optional[str] = None, regulator_status: Optional[RegulatoryNotificationStatus] = None,
    responsible_investigator_user_id: Optional[int] = None, open_only: Optional[bool] = None,
    reported_by_user_id: Optional[int] = None, closure_verifier_user_id: Optional[int] = None,
    critical_open: bool = False,
) -> dict:
    statement: Select[tuple[Incident]] = select(Incident)
    if status is not None:
        statement = statement.where(Incident.status == status)
    if severity is not None:
        statement = statement.where(Incident.severity == severity)
    if site_id is not None:
        statement = statement.where(Incident.site_id == site_id)
    if department_id is not None:
        statement = statement.where(Incident.department_id == department_id)
    if incident_type is not None:
        statement = statement.where(Incident.incident_type == incident_type)
    if regulator_status is not None:
        statement = statement.where(Incident.regulator_notification_status == regulator_status)
    if responsible_investigator_user_id is not None:
        from app.models.incident_investigation import IncidentInvestigation
        statement = statement.join(IncidentInvestigation).where(
            IncidentInvestigation.investigation_lead_user_id == responsible_investigator_user_id
        )
    if reported_by_user_id is not None:
        statement = statement.where(Incident.reported_by_id == reported_by_user_id)
    if closure_verifier_user_id is not None:
        statement = statement.where(
            Incident.closure_verifier_user_id == closure_verifier_user_id,
            Incident.closure_requested.is_(True),
        )
    if critical_open:
        statement = statement.where(
            Incident.severity == IncidentSeverity.critical,
            Incident.status.notin_([IncidentStatus.closed, IncidentStatus.cancelled]),
        )
    if open_only is True:
        statement = statement.where(Incident.status.notin_([IncidentStatus.closed, IncidentStatus.cancelled]))
    elif open_only is False:
        statement = statement.where(Incident.status == IncidentStatus.closed)
    statement = statement.order_by(Incident.occurred_at.desc(), Incident.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_incident(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise IncidentNotFoundError(f"Incident {incident_id} was not found")
    return incident


def create_incident(db: Session, incident_in: IncidentCreate, *, reported_by_id: Optional[int]) -> Incident:
    _ensure_site_exists(db, incident_in.site_id)
    data = incident_in.model_dump(exclude_none=True)
    _validate_references(db, data)
    classification = _validate_classification(db, data.get("incident_type", "other"))
    data["reported_at"] = data.get("reported_at") or _now()
    data["incident_reference"] = _next_reference(db, year=data["occurred_at"].year)
    if classification and classification.is_recordable:
        data["is_recordable"] = True
    if data.get("incident_type") in incident_settings(db).get("recordable_classifications", []):
        data["is_recordable"] = True
    if data.get("is_lost_time") or data.get("incident_type") == "lost_time_injury":
        data["is_lost_time"] = True
        data["is_recordable"] = True
    if data.get("regulator_notification_required") and data.get("regulator_notification_status") == RegulatoryNotificationStatus.not_required:
        data["regulator_notification_status"] = RegulatoryNotificationStatus.required
    incident = Incident(**data, reported_by_id=reported_by_id)
    if incident.status == IncidentStatus.closed:
        incident.closed_at = _now()
        incident.closed_by_user_id = reported_by_id
    db.add(incident)
    db.flush()
    add_activity(db, incident, "incident_created", f"Incident {incident.incident_reference} reported.", actor_id=reported_by_id)
    db.commit()
    db.refresh(incident)
    write_audit_log(
        db, actor_id=reported_by_id, action="incident.create", resource_type="incident",
        resource_id=incident.id,
        details={"reference": incident.incident_reference, "status": incident.status.value, "severity": incident.severity.value},
    )
    notify_critical_incident(db, incident)
    return incident


def validate_transition(current: IncidentStatus, target: IncidentStatus) -> None:
    if current == target:
        return
    if target not in TRANSITIONS.get(current, set()):
        raise IncidentTransitionError(f"Invalid incident transition from {current.value} to {target.value}")


def update_incident(db: Session, incident: Incident, incident_in: IncidentUpdate, *, actor_id: Optional[int] = None) -> Incident:
    data = incident_in.model_dump(exclude_unset=True)
    if "site_id" in data:
        _ensure_site_exists(db, data["site_id"])
    _validate_references(db, data)
    if data.get("incident_type"):
        classification = _validate_classification(db, data["incident_type"])
        if classification and classification.is_recordable:
            data["is_recordable"] = True
    if data.get("is_lost_time") or data.get("incident_type") == "lost_time_injury":
        data["is_lost_time"] = True
        data["is_recordable"] = True
    previous_status = incident.status
    previous_severity = incident.severity
    previous_type = incident.incident_type
    if data.get("status") is not None:
        validate_transition(previous_status, data["status"])
    for field, value in data.items():
        setattr(incident, field, value)
    if incident.status == IncidentStatus.closed:
        incident.closed_at = incident.closed_at or _now()
        incident.closed_by_user_id = incident.closed_by_user_id or actor_id
        incident.closure_requested = False
    add_activity(db, incident, "incident_updated", "Incident details updated.", actor_id=actor_id, metadata={"updated_fields": sorted(data)})
    if incident.incident_type != previous_type:
        add_activity(db, incident, "classification_changed", f"Classification changed from {previous_type} to {incident.incident_type}.", actor_id=actor_id, metadata={"from": previous_type, "to": incident.incident_type})
    if incident.severity != previous_severity:
        add_activity(db, incident, "severity_changed", f"Severity changed from {previous_severity.value} to {incident.severity.value}.", actor_id=actor_id, metadata={"from": previous_severity.value, "to": incident.severity.value})
    if incident.status != previous_status:
        add_activity(db, incident, "status_transition", f"Status changed from {previous_status.value} to {incident.status.value}.", actor_id=actor_id)
    db.add(incident)
    db.commit()
    db.refresh(incident)
    write_audit_log(db, actor_id=actor_id, action="incident.update", resource_type="incident", resource_id=incident.id, details={"updated_fields": sorted(data)})
    if incident.status != previous_status:
        write_audit_log(db, actor_id=actor_id, action="incident.status_transition", resource_type="incident", resource_id=incident.id, details={"from": previous_status.value, "to": incident.status.value})
    if incident.severity == IncidentSeverity.critical and previous_severity != IncidentSeverity.critical:
        notify_critical_incident(db, incident)
    return incident
