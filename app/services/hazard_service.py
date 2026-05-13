from typing import Optional
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.incident import Incident
from app.models.site import Site
from app.models.user import User
from app.schemas.hazard import HazardCreate, HazardUpdate
from app.services.audit_service import write_audit_log
from app.services.notification_service import notify_critical_hazard
from app.services.query_utils import paginate


class HazardServiceError(Exception):
    pass


class HazardNotFoundError(HazardServiceError):
    pass


class HazardSiteNotFoundError(HazardServiceError):
    pass


class HazardOwnerNotFoundError(HazardServiceError):
    pass


class HazardIncidentNotFoundError(HazardServiceError):
    pass


def calculate_risk_score(likelihood: int, impact: int) -> int:
    return likelihood * impact


def derive_risk_level(risk_score: int) -> HazardRiskLevel:
    if risk_score <= 4:
        return HazardRiskLevel.low
    if risk_score <= 9:
        return HazardRiskLevel.medium
    if risk_score <= 15:
        return HazardRiskLevel.high
    return HazardRiskLevel.critical


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise HazardSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_owner_exists(db: Session, owner_user_id: Optional[int]) -> None:
    if owner_user_id is not None and db.get(User, owner_user_id) is None:
        raise HazardOwnerNotFoundError(f"User {owner_user_id} was not found")


def _ensure_incident_exists(db: Session, incident_id: Optional[int]) -> None:
    if incident_id is not None and db.get(Incident, incident_id) is None:
        raise HazardIncidentNotFoundError(f"Incident {incident_id} was not found")


def _validate_references(
    db: Session,
    *,
    site_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
    incident_id: Optional[int] = None,
) -> None:
    if site_id is not None:
        _ensure_site_exists(db, site_id)
    _ensure_owner_exists(db, owner_user_id)
    _ensure_incident_exists(db, incident_id)


def list_hazards(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[HazardStatus] = None,
    risk_level: Optional[HazardRiskLevel] = None,
    site_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[Hazard]] = select(Hazard)
    if status is not None:
        statement = statement.where(Hazard.status == status)
    if risk_level is not None:
        statement = statement.where(Hazard.risk_level == risk_level)
    if site_id is not None:
        statement = statement.where(Hazard.site_id == site_id)
    if owner_user_id is not None:
        statement = statement.where(Hazard.owner_user_id == owner_user_id)

    statement = statement.order_by(Hazard.risk_score.desc(), Hazard.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_hazard(db: Session, hazard_id: int) -> Hazard:
    hazard = db.get(Hazard, hazard_id)
    if hazard is None:
        raise HazardNotFoundError(f"Hazard {hazard_id} was not found")
    return hazard


def create_hazard(db: Session, hazard_in: HazardCreate, *, reported_by_id: Optional[int]) -> Hazard:
    _validate_references(
        db,
        site_id=hazard_in.site_id,
        owner_user_id=hazard_in.owner_user_id,
        incident_id=hazard_in.incident_id,
    )
    risk_score = calculate_risk_score(hazard_in.likelihood, hazard_in.impact)
    hazard = Hazard(
        **hazard_in.model_dump(),
        risk_score=risk_score,
        risk_level=derive_risk_level(risk_score),
        reported_by_id=reported_by_id,
    )
    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    write_audit_log(
        db,
        actor_id=reported_by_id,
        action="hazard.create",
        resource_type="hazard",
        resource_id=hazard.id,
        details={"status": hazard.status.value, "risk_level": hazard.risk_level.value},
    )
    notify_critical_hazard(db, hazard)
    return hazard


def update_hazard(db: Session, hazard: Hazard, hazard_in: HazardUpdate, *, actor_id: Optional[int] = None) -> Hazard:
    update_data = hazard_in.model_dump(exclude_unset=True)
    _validate_references(
        db,
        site_id=update_data.get("site_id"),
        owner_user_id=update_data.get("owner_user_id"),
        incident_id=update_data.get("incident_id"),
    )

    previous_status = hazard.status
    previous_risk_level = hazard.risk_level
    for field, value in update_data.items():
        setattr(hazard, field, value)

    if "likelihood" in update_data or "impact" in update_data:
        hazard.risk_score = calculate_risk_score(hazard.likelihood, hazard.impact)
        hazard.risk_level = derive_risk_level(hazard.risk_score)

    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="hazard.update",
        resource_type="hazard",
        resource_id=hazard.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    if "status" in update_data and hazard.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="hazard.status_transition",
            resource_type="hazard",
            resource_id=hazard.id,
            details={"from": previous_status.value, "to": hazard.status.value},
        )
    if hazard.risk_level == HazardRiskLevel.critical and previous_risk_level != HazardRiskLevel.critical:
        notify_critical_hazard(db, hazard)
    return hazard
