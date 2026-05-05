from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.user import User
from app.schemas.legal_compliance import (
    LegalComplianceCreate,
    LegalComplianceListRead,
    LegalComplianceRead,
    LegalComplianceUpdate,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.legal_compliance_service import (
    LegalComplianceNotFoundError,
    LegalComplianceValidationError,
    create_legal_compliance_item,
    get_legal_compliance_item,
    list_legal_compliance_items,
    update_legal_compliance_item,
)
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=LegalComplianceListRead)
def read_legal_compliance(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    compliance_status: LegalComplianceStatus | None = Query(default=None, alias="status"),
    site_id: int | None = None,
    owner_user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.LEGAL_COMPLIANCE_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_legal_compliance_items(
        db,
        skip=skip,
        limit=limit,
        compliance_status=compliance_status,
        site_id=site_id,
        owner_user_id=owner_user_id,
    )


@router.post("", response_model=LegalComplianceRead, status_code=status.HTTP_201_CREATED)
def create_legal_item(
    item_in: LegalComplianceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalComplianceItem:
    ensure_permission(current_user, Permission.LEGAL_COMPLIANCE_CREATE)
    if item_in.site_id is not None:
        item_in = item_in.model_copy(update={"site_id": resolve_site_scope(current_user, item_in.site_id)})
    try:
        return create_legal_compliance_item(db, item_in, actor_id=current_user.id)
    except LegalComplianceValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{item_id}", response_model=LegalComplianceRead)
def read_legal_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalComplianceItem:
    ensure_permission(current_user, Permission.LEGAL_COMPLIANCE_VIEW)
    try:
        item = get_legal_compliance_item(db, item_id)
        ensure_site_access(current_user, item.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.legal_compliance, item)
    except LegalComplianceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal compliance item not found")


@router.patch("/{item_id}", response_model=LegalComplianceRead)
def patch_legal_item(
    item_id: int,
    item_in: LegalComplianceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalComplianceItem:
    ensure_permission(current_user, Permission.LEGAL_COMPLIANCE_EDIT)
    try:
        item = get_legal_compliance_item(db, item_id)
        ensure_site_access(current_user, item.site_id)
        if item_in.site_id is not None:
            item_in = item_in.model_copy(update={"site_id": resolve_site_scope(current_user, item_in.site_id)})
        return update_legal_compliance_item(db, item, item_in, actor_id=current_user.id)
    except LegalComplianceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal compliance item not found")
    except LegalComplianceValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
