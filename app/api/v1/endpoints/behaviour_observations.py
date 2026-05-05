from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.behaviour_observation import (
    BehaviourObservation,
    BehaviourObservationStatus,
    BehaviourObservationType,
)
from app.models.user import User
from app.schemas.behaviour_observation import (
    BehaviourObservationCreate,
    BehaviourObservationListRead,
    BehaviourObservationRead,
    BehaviourObservationUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.behaviour_observation_service import (
    BehaviourObservationNotFoundError,
    BehaviourObservationSiteNotFoundError,
    create_behaviour_observation,
    get_behaviour_observation,
    list_behaviour_observations,
    update_behaviour_observation,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=BehaviourObservationListRead)
def read_behaviour_observations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    observation_type: BehaviourObservationType | None = None,
    observation_status: BehaviourObservationStatus | None = Query(default=None, alias="status"),
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.BEHAVIOUR_OBSERVATIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_behaviour_observations(
        db,
        skip=skip,
        limit=limit,
        observation_type=observation_type,
        observation_status=observation_status,
        site_id=site_id,
    )


@router.post("", response_model=BehaviourObservationRead, status_code=status.HTTP_201_CREATED)
def create_behaviour_observation_record(
    observation_in: BehaviourObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BehaviourObservation:
    ensure_permission(current_user, Permission.BEHAVIOUR_OBSERVATIONS_CREATE)
    observation_in = observation_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, observation_in.site_id)}
    )
    try:
        return create_behaviour_observation(db, observation_in, actor_id=current_user.id)
    except BehaviourObservationSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")


@router.get("/{observation_id}", response_model=BehaviourObservationRead)
def read_behaviour_observation_record(
    observation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BehaviourObservation:
    ensure_permission(current_user, Permission.BEHAVIOUR_OBSERVATIONS_VIEW)
    try:
        observation = get_behaviour_observation(db, observation_id)
        ensure_site_access(current_user, observation.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.behaviour_observation, observation)
    except BehaviourObservationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Behaviour observation not found")


@router.patch("/{observation_id}", response_model=BehaviourObservationRead)
def patch_behaviour_observation_record(
    observation_id: int,
    observation_in: BehaviourObservationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BehaviourObservation:
    ensure_permission(current_user, Permission.BEHAVIOUR_OBSERVATIONS_EDIT)
    try:
        observation = get_behaviour_observation(db, observation_id)
        ensure_site_access(current_user, observation.site_id)
        if observation_in.site_id is not None:
            observation_in = observation_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, observation_in.site_id)}
            )
        return update_behaviour_observation(db, observation, observation_in, actor_id=current_user.id)
    except BehaviourObservationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Behaviour observation not found")
    except BehaviourObservationSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
