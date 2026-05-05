from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services.crud import create_record, get_record_or_none, list_records, update_record
from app.services.rbac import Permission, ensure_permission, ensure_site_access, is_site_scoped, resolve_site_scope

router = APIRouter()


@router.get("", response_model=list[SiteRead])
def list_sites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Site]:
    ensure_permission(current_user, Permission.SITES_READ)
    scoped_site_id = resolve_site_scope(current_user)
    if scoped_site_id is not None and is_site_scoped(current_user):
        site = get_record_or_none(db, Site, scoped_site_id)
        return [site] if site else []
    return list_records(db, Site, skip=skip, limit=limit)


@router.post("", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
def create_site(
    site_in: SiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Site:
    ensure_permission(current_user, Permission.SITES_MANAGE)
    data = site_in.model_dump()
    data["created_by_id"] = current_user.id
    return create_record(db, Site, data)


@router.get("/{site_id}", response_model=SiteRead)
def get_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Site:
    ensure_permission(current_user, Permission.SITES_READ)
    ensure_site_access(current_user, site_id)
    site = get_record_or_none(db, Site, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


@router.patch("/{site_id}", response_model=SiteRead)
def patch_site(
    site_id: int,
    site_in: SiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Site:
    ensure_permission(current_user, Permission.SITES_MANAGE)
    site = get_record_or_none(db, Site, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return update_record(db, site, site_in.model_dump(exclude_unset=True))
