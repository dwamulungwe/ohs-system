from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.approval import ApprovalActionType, ApprovalEntityType
from app.models.attachment import AttachmentEntityType
from app.models.document_control import DocumentStatus, DocumentType
from app.models.user import User
from app.schemas.document_control import (
    DocumentControlCreate,
    DocumentControlListRead,
    DocumentControlRead,
    DocumentControlUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.document_control_service import (
    DocumentControlNotFoundError,
    DocumentControlValidationError,
    create_document,
    get_document,
    list_documents,
    update_document,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope

router = APIRouter()


@router.get("", response_model=DocumentControlListRead)
def read_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    site_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DOCUMENTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_documents(
        db,
        skip=skip,
        limit=limit,
        status=status,
        document_type=document_type,
        site_id=site_id,
    )


@router.post("", response_model=DocumentControlRead, status_code=status.HTTP_201_CREATED)
def create_document_record(
    document_in: DocumentControlCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DOCUMENTS_CREATE)
    if document_in.site_id is not None:
        document_in = document_in.model_copy(
            update={"site_id": resolve_site_scope(current_user, document_in.site_id)}
        )
    if document_in.status == DocumentStatus.approved:
        ensure_permission(current_user, Permission.DOCUMENTS_APPROVE)
    try:
        return create_document(db, document_in, actor_id=current_user.id)
    except DocumentControlValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{document_id}", response_model=DocumentControlRead)
def read_document_record(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DOCUMENTS_VIEW)
    try:
        document = get_document(db, document_id)
        ensure_site_access(current_user, document.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.document_control, document)
    except DocumentControlNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.patch("/{document_id}", response_model=DocumentControlRead)
def patch_document_record(
    document_id: int,
    document_in: DocumentControlUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DOCUMENTS_EDIT)
    try:
        document = get_document(db, document_id)
        ensure_site_access(current_user, document.site_id)
        if document_in.site_id is not None:
            document_in = document_in.model_copy(
                update={"site_id": resolve_site_scope(current_user, document_in.site_id)}
            )
        target_status = document_in.status or document.status
        if target_status == DocumentStatus.approved:
            ensure_permission(current_user, Permission.DOCUMENTS_APPROVE)
        return update_document(db, document, document_in, actor_id=current_user.id)
    except DocumentControlNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    except DocumentControlValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
