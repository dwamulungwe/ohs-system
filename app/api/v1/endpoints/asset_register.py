from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.asset_register import AssetConditionStatus, AssetRegisterItem, AssetType
from app.models.attachment import AttachmentEntityType
from app.models.user import User
from app.schemas.asset_register import (
    AssetRegisterCreate,
    AssetRegisterListRead,
    AssetRegisterRead,
    AssetRegisterUpdate,
)
from app.services.asset_register_service import (
    AssetRegisterNotFoundError,
    AssetRegisterValidationError,
    create_asset,
    get_asset,
    list_assets,
    update_asset,
)
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope

router = APIRouter()


@router.get("", response_model=AssetRegisterListRead)
def read_assets(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    site_id: Optional[int] = None,
    asset_type: Optional[AssetType] = None,
    condition_status: Optional[AssetConditionStatus] = None,
    assigned_to_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.ASSETS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_assets(
        db,
        skip=skip,
        limit=limit,
        site_id=site_id,
        asset_type=asset_type,
        condition_status=condition_status,
        assigned_to_user_id=assigned_to_user_id,
    )


@router.post("", response_model=AssetRegisterRead, status_code=status.HTTP_201_CREATED)
def create_asset_record(
    asset_in: AssetRegisterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetRegisterItem:
    ensure_permission(current_user, Permission.ASSETS_CREATE)
    asset_in = asset_in.model_copy(update={"site_id": resolve_site_scope(current_user, asset_in.site_id)})
    try:
        return create_asset(db, asset_in, actor_id=current_user.id)
    except AssetRegisterValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{asset_id}", response_model=AssetRegisterRead)
def read_asset_record(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetRegisterItem:
    ensure_permission(current_user, Permission.ASSETS_VIEW)
    try:
        asset = get_asset(db, asset_id)
        ensure_site_access(current_user, asset.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.asset_register, asset)
    except AssetRegisterNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset register item not found")


@router.patch("/{asset_id}", response_model=AssetRegisterRead)
def patch_asset_record(
    asset_id: int,
    asset_in: AssetRegisterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetRegisterItem:
    ensure_permission(current_user, Permission.ASSETS_EDIT)
    try:
        asset = get_asset(db, asset_id)
        ensure_site_access(current_user, asset.site_id)
        if asset_in.site_id is not None:
            asset_in = asset_in.model_copy(update={"site_id": resolve_site_scope(current_user, asset_in.site_id)})
        return update_asset(db, asset, asset_in, actor_id=current_user.id)
    except AssetRegisterNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset register item not found")
    except AssetRegisterValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=detail)
