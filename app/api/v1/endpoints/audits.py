from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.audit_management import AuditStatus, AuditType
from app.models.user import User
from app.schemas.audit_management import (
    AuditManagementCreate,
    AuditManagementListRead,
    AuditManagementRead,
    AuditManagementUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.audit_management_service import (
    AuditManagementNotFoundError,
    AuditManagementValidationError,
    create_audit,
    get_audit,
    list_audits,
    update_audit,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=AuditManagementListRead)
def read_audits(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[AuditStatus] = None,
    audit_type: Optional[AuditType] = None,
    site_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.AUDITS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_audits(db, skip=skip, limit=limit, status=status, audit_type=audit_type, site_id=site_id)


@router.post("", response_model=AuditManagementRead, status_code=status.HTTP_201_CREATED)
def create_audit_record(
    audit_in: AuditManagementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.AUDITS_CREATE)
    audit_in = audit_in.model_copy(update={"site_id": resolve_site_scope(current_user, audit_in.site_id)})
    try:
        return create_audit(db, audit_in, actor_id=current_user.id)
    except AuditManagementValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{audit_id}", response_model=AuditManagementRead)
def read_audit_record(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.AUDITS_VIEW)
    try:
        audit = get_audit(db, audit_id)
        ensure_site_access(current_user, audit.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.audit_management, audit)
    except AuditManagementNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")


@router.patch("/{audit_id}", response_model=AuditManagementRead)
def patch_audit_record(
    audit_id: int,
    audit_in: AuditManagementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.AUDITS_EDIT)
    try:
        audit = get_audit(db, audit_id)
        ensure_site_access(current_user, audit.site_id)
        if audit_in.site_id is not None:
            audit_in = audit_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, audit_in.site_id)}
            )
        return update_audit(db, audit, audit_in, actor_id=current_user.id)
    except AuditManagementNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    except AuditManagementValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
