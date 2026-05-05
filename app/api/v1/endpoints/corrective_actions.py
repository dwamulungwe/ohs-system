from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.corrective_action import (
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.user import User
from app.schemas.corrective_action import (
    CorrectiveActionCreate,
    CorrectiveActionListRead,
    CorrectiveActionRead,
    CorrectiveActionUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    resolve_site_scope,
)
from app.services.corrective_action_service import (
    CorrectiveActionInvalidSourceError,
    CorrectiveActionNotFoundError,
    CorrectiveActionSiteNotFoundError,
    CorrectiveActionSourceNotFoundError,
    CorrectiveActionUserNotFoundError,
    create_corrective_action as create_corrective_action_record,
    get_corrective_action as get_corrective_action_record,
    list_corrective_actions as list_corrective_action_records,
    update_corrective_action as update_corrective_action_record,
)

router = APIRouter()
SELF_SERVICE_ACTION_FIELDS = {
    "status",
    "started_at",
    "completed_at",
    "closure_notes",
    "closure_evidence_metadata",
    "description",
    "due_date",
}


@router.get("", response_model=CorrectiveActionListRead)
def list_corrective_actions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    action_status: CorrectiveActionStatus | None = Query(default=None, alias="status"),
    priority: CorrectiveActionPriority | None = None,
    site_id: int | None = None,
    assigned_to_user_id: int | None = None,
    source_type: CorrectiveActionSourceType | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_corrective_action_records(
        db,
        skip=skip,
        limit=limit,
        status=action_status,
        priority=priority,
        site_id=site_id,
        assigned_to_user_id=assigned_to_user_id,
        source_type=source_type,
    )


@router.post("", response_model=CorrectiveActionRead, status_code=status.HTTP_201_CREATED)
def create_corrective_action(
    action_in: CorrectiveActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_CREATE)
    if action_in.status == CorrectiveActionStatus.closed:
        ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY)
    action_in = action_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, action_in.site_id)}
    )
    try:
        return create_corrective_action_record(db, action_in, current_user_id=current_user.id)
    except CorrectiveActionSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except CorrectiveActionUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    except CorrectiveActionSourceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source record not found")
    except CorrectiveActionInvalidSourceError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid source reference")


@router.get("/{action_id}", response_model=CorrectiveActionRead)
def get_corrective_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    ensure_permission(current_user, Permission.CORRECTIVE_ACTIONS_VIEW)
    try:
        action = get_corrective_action_record(db, action_id)
        ensure_site_access(current_user, action.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.corrective_action, action)
    except CorrectiveActionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")


@router.patch("/{action_id}", response_model=CorrectiveActionRead)
def patch_corrective_action(
    action_id: int,
    action_in: CorrectiveActionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectiveAction:
    try:
        action = get_corrective_action_record(db, action_id)
        ensure_site_access(current_user, action.site_id)
        update_data = action_in.model_dump(exclude_unset=True)

        if has_permission(current_user, Permission.CORRECTIVE_ACTIONS_VERIFY):
            pass
        elif has_permission(current_user, Permission.CORRECTIVE_ACTIONS_EDIT):
            if update_data.get("status") == CorrectiveActionStatus.closed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to verify final corrective action closure",
                )
            if any(field in update_data for field in ("verified_by_user_id", "verified_at", "verification_notes")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to verify final corrective action closure",
                )
        elif has_permission(current_user, Permission.CORRECTIVE_ACTIONS_SELF_UPDATE):
            if action.assigned_to_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only assigned corrective actions can be updated",
                )
            if not set(update_data).issubset(SELF_SERVICE_ACTION_FIELDS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to change those corrective action fields",
                )
            if update_data.get("status") == CorrectiveActionStatus.closed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Supervisors cannot verify final corrective action closure",
                )
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        return update_corrective_action_record(db, action, action_in, actor_id=current_user.id)
    except CorrectiveActionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")
    except CorrectiveActionSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except CorrectiveActionUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    except CorrectiveActionSourceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source record not found")
    except CorrectiveActionInvalidSourceError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid source reference")
