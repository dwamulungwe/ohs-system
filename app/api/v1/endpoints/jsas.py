from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.jsa import JSAStatus, JobSafetyAnalysis
from app.models.user import User
from app.schemas.jsa import JSACreate, JSAListRead, JSARead, JSAUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.jsa_service import (
    JSANotFoundError,
    JSAValidationError,
    create_jsa,
    get_jsa,
    list_jsas,
    update_jsa,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=JSAListRead)
def read_jsas(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[JSAStatus] = None,
    site_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.JSA_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_jsas(db, skip=skip, limit=limit, status=status, site_id=site_id)


@router.post("", response_model=JSARead, status_code=status.HTTP_201_CREATED)
def create_jsa_record(
    jsa_in: JSACreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobSafetyAnalysis:
    ensure_permission(current_user, Permission.JSA_CREATE)
    jsa_in = jsa_in.model_copy(update={"site_id": resolve_site_scope(current_user, jsa_in.site_id)})
    if jsa_in.status == JSAStatus.approved:
        ensure_permission(current_user, Permission.JSA_APPROVE)
    try:
        return create_jsa(db, jsa_in, actor_id=current_user.id)
    except JSAValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{jsa_id}", response_model=JSARead)
def read_jsa_record(
    jsa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobSafetyAnalysis:
    ensure_permission(current_user, Permission.JSA_VIEW)
    try:
        jsa = get_jsa(db, jsa_id)
        ensure_site_access(current_user, jsa.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.jsa, jsa)
    except JSANotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")


@router.patch("/{jsa_id}", response_model=JSARead)
def patch_jsa_record(
    jsa_id: int,
    jsa_in: JSAUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobSafetyAnalysis:
    ensure_permission(current_user, Permission.JSA_EDIT)
    try:
        jsa = get_jsa(db, jsa_id)
        ensure_site_access(current_user, jsa.site_id)
        if jsa_in.site_id is not None:
            jsa_in = jsa_in.model_copy(update={"site_id": resolve_site_scope(current_user, jsa_in.site_id)})
        if (jsa_in.status or jsa.status) == JSAStatus.approved:
            ensure_permission(current_user, Permission.JSA_APPROVE)
        return update_jsa(db, jsa, jsa_in, actor_id=current_user.id)
    except JSANotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    except JSAValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
