from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.safety_communication import SafetyCommunication, SafetyCommunicationStatus, SafetyCommunicationType
from app.models.user import User
from app.schemas.safety_communication import (
    SafetyCommunicationCreate,
    SafetyCommunicationListRead,
    SafetyCommunicationRead,
    SafetyCommunicationUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope
from app.services.safety_communication_service import (
    SafetyCommunicationNotFoundError,
    SafetyCommunicationSiteNotFoundError,
    create_safety_communication,
    get_safety_communication,
    list_safety_communications,
    update_safety_communication,
)

router = APIRouter()


@router.get("", response_model=SafetyCommunicationListRead)
def read_safety_communications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    communication_type: SafetyCommunicationType | None = None,
    communication_status: SafetyCommunicationStatus | None = Query(default=None, alias="status"),
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.SAFETY_COMMUNICATIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_safety_communications(
        db,
        skip=skip,
        limit=limit,
        communication_type=communication_type,
        communication_status=communication_status,
        site_id=site_id,
    )


@router.post("", response_model=SafetyCommunicationRead, status_code=status.HTTP_201_CREATED)
def create_safety_communication_record(
    communication_in: SafetyCommunicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyCommunication:
    ensure_permission(current_user, Permission.SAFETY_COMMUNICATIONS_CREATE)
    communication_in = communication_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, communication_in.site_id)}
    )
    try:
        return create_safety_communication(db, communication_in, actor_id=current_user.id)
    except SafetyCommunicationSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")


@router.get("/{communication_id}", response_model=SafetyCommunicationRead)
def read_safety_communication_record(
    communication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyCommunication:
    ensure_permission(current_user, Permission.SAFETY_COMMUNICATIONS_VIEW)
    try:
        communication = get_safety_communication(db, communication_id)
        ensure_site_access(current_user, communication.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.safety_communication, communication)
    except SafetyCommunicationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety communication not found")


@router.patch("/{communication_id}", response_model=SafetyCommunicationRead)
def patch_safety_communication_record(
    communication_id: int,
    communication_in: SafetyCommunicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SafetyCommunication:
    ensure_permission(current_user, Permission.SAFETY_COMMUNICATIONS_EDIT)
    try:
        communication = get_safety_communication(db, communication_id)
        ensure_site_access(current_user, communication.site_id)
        if communication_in.site_id is not None:
            communication_in = communication_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, communication_in.site_id)}
            )
        return update_safety_communication(db, communication, communication_in, actor_id=current_user.id)
    except SafetyCommunicationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety communication not found")
    except SafetyCommunicationSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
