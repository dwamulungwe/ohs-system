from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.emergency_drill import EmergencyDrillStatus
from app.models.user import User
from app.schemas.emergency_drill import (
    EmergencyDrillCreate,
    EmergencyDrillListRead,
    EmergencyDrillRead,
    EmergencyDrillUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.emergency_drill_service import (
    EmergencyDrillNotFoundError,
    EmergencyDrillValidationError,
    create_emergency_drill,
    get_emergency_drill,
    list_emergency_drills,
    update_emergency_drill,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=EmergencyDrillListRead)
def read_emergency_drills(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: EmergencyDrillStatus | None = None,
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.EMERGENCY_DRILLS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_emergency_drills(db, skip=skip, limit=limit, status=status, site_id=site_id)


@router.post("", response_model=EmergencyDrillRead, status_code=status.HTTP_201_CREATED)
def create_emergency_drill_record(
    drill_in: EmergencyDrillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.EMERGENCY_DRILLS_CREATE)
    drill_in = drill_in.model_copy(update={"site_id": resolve_site_scope(current_user, drill_in.site_id)})
    try:
        return create_emergency_drill(db, drill_in, actor_id=current_user.id)
    except EmergencyDrillValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{drill_id}", response_model=EmergencyDrillRead)
def read_emergency_drill_record(
    drill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.EMERGENCY_DRILLS_VIEW)
    try:
        drill = get_emergency_drill(db, drill_id)
        ensure_site_access(current_user, drill.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.emergency_drill, drill)
    except EmergencyDrillNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency drill not found")


@router.patch("/{drill_id}", response_model=EmergencyDrillRead)
def patch_emergency_drill_record(
    drill_id: int,
    drill_in: EmergencyDrillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.EMERGENCY_DRILLS_EDIT)
    try:
        drill = get_emergency_drill(db, drill_id)
        ensure_site_access(current_user, drill.site_id)
        if drill_in.site_id is not None:
            drill_in = drill_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, drill_in.site_id)}
            )
        return update_emergency_drill(db, drill, drill_in, actor_id=current_user.id)
    except EmergencyDrillNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency drill not found")
    except EmergencyDrillValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
