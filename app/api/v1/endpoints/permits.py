from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.permit import PermitStatus, PermitType
from app.models.user import User
from app.schemas.permit import PermitCreate, PermitListRead, PermitRead, PermitUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import (
    Permission,
    ensure_permission,
    ensure_site_access,
    has_permission,
    resolve_site_scope,
)
from app.services.permit_service import (
    PermitNotFoundError,
    PermitSiteNotFoundError,
    PermitUserNotFoundError,
    PermitValidationError,
    create_permit,
    get_permit,
    list_permits,
    update_permit,
)

router = APIRouter()
REQUESTER_PERMIT_STATUSES = {PermitStatus.draft, PermitStatus.pending_approval, PermitStatus.cancelled}


@router.get("", response_model=PermitListRead)
def list_permit_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[PermitStatus] = None,
    permit_type: Optional[PermitType] = None,
    site_id: Optional[int] = None,
    requested_by_user_id: Optional[int] = None,
    issued_by_user_id: Optional[int] = None,
    approved_by_user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.PERMITS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_permits(
        db,
        skip=skip,
        limit=limit,
        status=status,
        permit_type=permit_type,
        site_id=site_id,
        requested_by_user_id=requested_by_user_id,
        issued_by_user_id=issued_by_user_id,
        approved_by_user_id=approved_by_user_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=PermitRead, status_code=status.HTTP_201_CREATED)
def create_permit_record(
    permit_in: PermitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.PERMITS_REQUEST)
    update_data = {"site_id": resolve_site_scope(current_user, permit_in.site_id)}

    if not has_permission(current_user, Permission.PERMITS_MANAGE):
        if permit_in.status not in {PermitStatus.draft, PermitStatus.pending_approval}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to approve or activate permits")
        if permit_in.issued_by_user_id is not None or permit_in.approved_by_user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to assign permit approvers")
        update_data["requested_by_user_id"] = current_user.id
    elif not has_permission(current_user, Permission.PERMITS_APPROVE):
        if permit_in.status == PermitStatus.approved or permit_in.approved_by_user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to approve permits")

    permit_in = permit_in.model_copy(update=update_data)
    try:
        return create_permit(db, permit_in)
    except PermitSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except PermitUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    except PermitValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{permit_id}", response_model=PermitRead)
def get_permit_record(
    permit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.PERMITS_VIEW)
    try:
        permit = get_permit(db, permit_id)
        ensure_site_access(current_user, permit.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.permit, permit)
    except PermitNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permit not found")


@router.patch("/{permit_id}", response_model=PermitRead)
def patch_permit_record(
    permit_id: int,
    permit_in: PermitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        permit = get_permit(db, permit_id)
        ensure_site_access(current_user, permit.site_id)
        update_data = permit_in.model_dump(exclude_unset=True)

        if has_permission(current_user, Permission.PERMITS_APPROVE):
            pass
        elif has_permission(current_user, Permission.PERMITS_MANAGE):
            if update_data.get("status") == PermitStatus.approved or "approved_by_user_id" in update_data:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to approve permits")
        else:
            if permit.requested_by_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            if (
                "approved_by_user_id" in update_data
                or "issued_by_user_id" in update_data
                or "requested_by_user_id" in update_data
                or "site_id" in update_data
            ):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
            next_status = update_data.get("status", permit.status)
            if next_status not in REQUESTER_PERMIT_STATUSES:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to approve or close permits")
        return update_permit(db, permit, permit_in)
    except PermitNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permit not found")
    except PermitSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except PermitUserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced user not found")
    except PermitValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
