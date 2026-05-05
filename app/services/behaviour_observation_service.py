from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.attachment import AttachmentEntityType
from app.models.behaviour_observation import (
    BehaviourObservation,
    BehaviourObservationStatus,
    BehaviourObservationType,
)
from app.models.site import Site
from app.schemas.behaviour_observation import BehaviourObservationCreate, BehaviourObservationUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.audit_service import write_audit_log
from app.services.query_utils import paginate


class BehaviourObservationServiceError(Exception):
    pass


class BehaviourObservationNotFoundError(BehaviourObservationServiceError):
    pass


class BehaviourObservationSiteNotFoundError(BehaviourObservationServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise BehaviourObservationSiteNotFoundError(f"Site {site_id} was not found")


def list_behaviour_observations(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    observation_type: BehaviourObservationType | None = None,
    observation_status: BehaviourObservationStatus | None = None,
    site_id: int | None = None,
) -> dict:
    statement: Select[tuple[BehaviourObservation]] = select(BehaviourObservation)
    if observation_type is not None:
        statement = statement.where(BehaviourObservation.observation_type == observation_type)
    if observation_status is not None:
        statement = statement.where(BehaviourObservation.status == observation_status)
    if site_id is not None:
        statement = statement.where(BehaviourObservation.site_id == site_id)
    statement = statement.order_by(BehaviourObservation.observed_at.desc(), BehaviourObservation.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_behaviour_observation(db: Session, observation_id: int) -> BehaviourObservation:
    observation = db.get(BehaviourObservation, observation_id)
    if observation is None:
        raise BehaviourObservationNotFoundError(f"Behaviour observation {observation_id} was not found")
    return observation


def create_behaviour_observation(
    db: Session,
    observation_in: BehaviourObservationCreate,
    *,
    actor_id: int | None,
) -> BehaviourObservation:
    _ensure_site_exists(db, observation_in.site_id)
    data = observation_in.model_dump()
    if data["status"] == BehaviourObservationStatus.closed:
        data["closed_at"] = _now()
        data["closed_by_user_id"] = actor_id
    observation = BehaviourObservation(**data, observed_by_user_id=actor_id)
    db.add(observation)
    db.commit()
    db.refresh(observation)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="behaviour_observation.create",
        resource_type="behaviour_observation",
        resource_id=observation.id,
        details={"observation_type": observation.observation_type.value},
    )
    return hydrate_entity_attachments(db, AttachmentEntityType.behaviour_observation, observation)


def update_behaviour_observation(
    db: Session,
    observation: BehaviourObservation,
    observation_in: BehaviourObservationUpdate,
    *,
    actor_id: int | None,
) -> BehaviourObservation:
    update_data = observation_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])

    next_status = update_data.get("status", observation.status)
    for field, value in update_data.items():
        setattr(observation, field, value)

    if next_status == BehaviourObservationStatus.closed:
        observation.closed_at = observation.closed_at or _now()
        observation.closed_by_user_id = observation.closed_by_user_id or actor_id
    elif "status" in update_data:
        observation.closed_at = None
        observation.closed_by_user_id = None

    db.add(observation)
    db.commit()
    db.refresh(observation)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="behaviour_observation.update",
        resource_type="behaviour_observation",
        resource_id=observation.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    return hydrate_entity_attachments(db, AttachmentEntityType.behaviour_observation, observation)
