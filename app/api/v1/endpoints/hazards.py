from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.user import User
from app.schemas.hazard import HazardCreate, HazardListRead, HazardRead, HazardUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    resolve_site_scope,
)
from app.services.hazard_service import (
    HazardIncidentNotFoundError,
    HazardNotFoundError,
    HazardOwnerNotFoundError,
    HazardSiteNotFoundError,
    create_hazard as create_hazard_record,
    get_hazard as get_hazard_record,
    list_hazards as list_hazard_records,
    update_hazard as update_hazard_record,
)

router = APIRouter()
MANAGER_HAZARD_STATUSES = {HazardStatus.closed}


@router.get("", response_model=HazardListRead)
def list_hazards(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    hazard_status: HazardStatus | None = Query(default=None, alias="status"),
    risk_level: HazardRiskLevel | None = None,
    site_id: int | None = None,
    owner_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.HAZARDS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_hazard_records(
        db,
        skip=skip,
        limit=limit,
        status=hazard_status,
        risk_level=risk_level,
        site_id=site_id,
        owner_user_id=owner_user_id,
    )


@router.post("", response_model=HazardRead, status_code=status.HTTP_201_CREATED)
def create_hazard(
    hazard_in: HazardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Hazard:
    ensure_permission(current_user, Permission.HAZARDS_CREATE)
    if hazard_in.status in MANAGER_HAZARD_STATUSES and not has_permission(
        current_user,
        Permission.HAZARDS_CLOSE,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to close hazards")

    hazard_in = hazard_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, hazard_in.site_id)}
    )
    try:
        return create_hazard_record(db, hazard_in, reported_by_id=current_user.id)
    except HazardSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except HazardOwnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
    except HazardIncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked incident not found")


@router.get("/{hazard_id}", response_model=HazardRead)
def get_hazard(
    hazard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Hazard:
    ensure_permission(current_user, Permission.HAZARDS_VIEW)
    try:
        hazard = get_hazard_record(db, hazard_id)
        ensure_site_access(current_user, hazard.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.hazard, hazard)
    except HazardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard not found")


@router.patch("/{hazard_id}", response_model=HazardRead)
def patch_hazard(
    hazard_id: int,
    hazard_in: HazardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Hazard:
    ensure_permission(current_user, Permission.HAZARDS_EDIT)
    try:
        hazard = get_hazard_record(db, hazard_id)
        ensure_site_access(current_user, hazard.site_id)
        next_status = hazard_in.status or hazard.status
        if next_status in MANAGER_HAZARD_STATUSES and not has_permission(
            current_user,
            Permission.HAZARDS_CLOSE,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to close hazards",
            )
        return update_hazard_record(db, hazard, hazard_in, actor_id=current_user.id)
    except HazardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard not found")
    except HazardSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except HazardOwnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
    except HazardIncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked incident not found")
