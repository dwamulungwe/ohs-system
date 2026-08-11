from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveActionPriority, CorrectiveActionSourceType
from app.models.incident import IncidentSeverity
from app.models.site import Site
from app.models.sio import (
    SIOObservationNature,
    SIOStatus,
    SIOUrgency,
    SafetyImprovementObservation,
)
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.hazard import HazardCreate
from app.schemas.incident import IncidentCreate
from app.schemas.sio import SIOCreate, SIOEscalationOptions, SIOUpdate
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.hazard_service import create_hazard
from app.services.incident_service import create_incident
from app.services.query_utils import paginate


class SIOServiceError(Exception):
    pass


class SIONotFoundError(SIOServiceError):
    pass


class SIOSiteNotFoundError(SIOServiceError):
    pass


class SIOUserNotFoundError(SIOServiceError):
    pass


class SIODuplicateError(SIOServiceError):
    pass


class SIOLinkAlreadyExistsError(SIOServiceError):
    pass


class SIOEscalationValidationError(SIOServiceError):
    pass


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise SIOSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise SIOUserNotFoundError(f"User {user_id} was not found")


def _validate_references(db: Session, data: dict) -> None:
    if data.get("site_id") is not None:
        _ensure_site_exists(db, data["site_id"])
    _ensure_user_exists(db, data.get("responsible_hs_officer_user_id"))
    _ensure_user_exists(db, data.get("responsible_person_user_id"))


def list_sios(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    department: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[SIOStatus] = None,
    observation_nature: Optional[SIOObservationNature] = None,
    urgency: Optional[SIOUrgency] = None,
    category: Optional[str] = None,
    incident_classification: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
) -> dict:
    statement: Select[tuple[SafetyImprovementObservation]] = select(SafetyImprovementObservation)
    filters = (
        (site_id, SafetyImprovementObservation.site_id),
        (department, SafetyImprovementObservation.department),
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
    if date_from is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date >= date_from)
    if date_to is not None:
        statement = statement.where(SafetyImprovementObservation.observation_date <= date_to)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                SafetyImprovementObservation.description.ilike(term),
                SafetyImprovementObservation.department.ilike(term),
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


def create_sio(
    db: Session,
    sio_in: SIOCreate,
    *,
    actor_id: Optional[int],
) -> SafetyImprovementObservation:
    data = sio_in.model_dump()
    _validate_references(db, data)
    sio = SafetyImprovementObservation(**data, created_by_user_id=actor_id)
    db.add(sio)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SIODuplicateError("An SIO with this source system and external reference already exists") from exc
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="sio.create",
        resource_type="sio",
        resource_id=sio.id,
        details={"site_id": sio.site_id, "source_system": sio.source_system},
    )
    return sio


def update_sio(
    db: Session,
    sio: SafetyImprovementObservation,
    sio_in: SIOUpdate,
    *,
    actor_id: Optional[int],
) -> SafetyImprovementObservation:
    data = sio_in.model_dump(exclude_unset=True)
    _validate_references(db, data)
    for field, value in data.items():
        setattr(sio, field, value)
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


def _default_title(sio: SafetyImprovementObservation) -> str:
    label = sio.category or sio.incident_classification or sio.observation_nature.value
    return f"SIO #{sio.id}: {label}"[:200]


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
    db.add(sio)
    db.commit()
    db.refresh(sio)
    write_audit_log(
        db,
        actor_id=actor_id,
        action=f"sio.{field.replace('linked_', '').replace('_id', '')}.create",
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
            owner_user_id=sio.responsible_person_user_id,
            due_date=options.due_date if options else None,
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
    due_date = options.due_date if options and options.due_date else date.today() + timedelta(days=30)
    action = create_corrective_action(
        db,
        CorrectiveActionCreate(
            site_id=sio.site_id,
            title=options.title if options and options.title else _default_title(sio),
            description=sio.description,
            source_type=CorrectiveActionSourceType.sio,
            source_id=sio.id,
            priority=_corrective_priority(sio.urgency),
            due_date=due_date,
            assigned_to_user_id=sio.responsible_person_user_id,
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
    subquery = statement.subquery()
    total = db.scalar(select(func.count()).select_from(subquery)) or 0

    def count_where(*conditions) -> int:
        return db.scalar(select(func.count()).select_from(subquery).where(*conditions)) or 0

    nature = subquery.c.observation_nature
    status = subquery.c.status
    urgency = subquery.c.urgency

    site_rows = db.execute(
        select(Site.name, func.count())
        .select_from(subquery.join(Site, Site.id == subquery.c.site_id))
        .group_by(Site.name)
    ).all()

    def distribution(column) -> dict[str, int]:
        rows = db.execute(select(column, func.count()).select_from(subquery).group_by(column)).all()
        return {str(value or "Unspecified"): count for value, count in rows}

    trend_rows = db.execute(
        select(subquery.c.observation_date).where(subquery.c.observation_date.is_not(None))
    ).all()
    trend: dict[str, int] = {}
    for (observed_on,) in trend_rows:
        month = observed_on.strftime("%Y-%m")
        trend[month] = trend.get(month, 0) + 1

    return {
        "total_observations": total,
        "positive_observations": count_where(nature == SIOObservationNature.positive),
        "negative_observations": count_where(nature == SIOObservationNature.negative),
        "open_unassigned_observations": count_where(
            status.in_([SIOStatus.open, SIOStatus.unassigned])
        ),
        "urgent_high_priority_observations": count_where(
            urgency.in_([SIOUrgency.urgent, SIOUrgency.high])
        ),
        "observations_by_site": {name: count for name, count in site_rows},
        "observations_by_category": distribution(subquery.c.category),
        "observations_by_source": distribution(subquery.c.source_type),
        "observations_by_department": distribution(subquery.c.department),
        "observation_trend_by_month": dict(sorted(trend.items())),
    }
