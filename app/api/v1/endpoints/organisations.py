from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.organisation import OrganisationFeature, OrganisationSettings
from app.models.user import User
from app.schemas.organisation import (
    OrganisationCreate,
    OrganisationFeatureRead,
    OrganisationFeaturesUpdate,
    OrganisationRead,
    OrganisationSettingsRead,
    OrganisationSettingsUpdate,
    OrganisationUpdate,
)
from app.services.organisation_service import (
    create_organisation_record,
    get_organisation,
    list_organisations,
    switch_to_platform_target,
    update_organisation,
    update_organisation_settings,
)
from app.services.rbac import Permission, ensure_permission
from app.services.tenancy import MODULE_KEYS

router = APIRouter()


def _ensure_platform_admin(user: User) -> None:
    if not user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator access required")


def _target_organisation(db: Session, organisation_id: int):
    organisation = get_organisation(db, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return organisation


@router.get("", response_model=list[OrganisationRead])
def read_organisations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _ensure_platform_admin(current_user)
    return list_organisations(db)


@router.post("", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
def create_organisation(
    organisation_in: OrganisationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_platform_admin(current_user)
    try:
        return create_organisation_record(db, organisation_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organisation code or slug already exists")


@router.get("/{organisation_id}", response_model=OrganisationRead)
def read_organisation(
    organisation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_platform_admin(current_user)
    return _target_organisation(db, organisation_id)


@router.patch("/{organisation_id}", response_model=OrganisationRead)
def patch_organisation(
    organisation_id: int,
    organisation_in: OrganisationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_platform_admin(current_user)
    organisation = _target_organisation(db, organisation_id)
    try:
        return update_organisation(db, organisation, organisation_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organisation code or slug already exists")


@router.get("/{organisation_id}/features", response_model=list[OrganisationFeatureRead])
def read_features(
    organisation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_platform_admin(current_user)
    _target_organisation(db, organisation_id)
    switch_to_platform_target(db, organisation_id)
    return list(db.scalars(select(OrganisationFeature).order_by(OrganisationFeature.key)).all())


@router.patch("/{organisation_id}/features", response_model=list[OrganisationFeatureRead])
def patch_features(
    organisation_id: int,
    features_in: OrganisationFeaturesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_platform_admin(current_user)
    _target_organisation(db, organisation_id)
    unknown = {item.key for item in features_in.features}.difference(MODULE_KEYS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown module keys: {', '.join(sorted(unknown))}",
        )
    switch_to_platform_target(db, organisation_id)
    existing = {
        item.key: item for item in db.scalars(select(OrganisationFeature)).all()
    }
    for update in features_in.features:
        feature = existing.get(update.key)
        if feature is None:
            feature = OrganisationFeature(key=update.key, is_enabled=update.is_enabled)
            db.add(feature)
            existing[update.key] = feature
        else:
            feature.is_enabled = update.is_enabled
        if update.configuration is not None:
            feature.configuration = update.configuration
    db.commit()
    return list(db.scalars(select(OrganisationFeature).order_by(OrganisationFeature.key)).all())


@router.get("/{organisation_id}/settings", response_model=OrganisationSettingsRead)
def read_settings(
    organisation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organisation_id != organisation_id:
        _ensure_platform_admin(current_user)
    else:
        ensure_permission(current_user, Permission.USERS_MANAGE)
    _target_organisation(db, organisation_id)
    switch_to_platform_target(db, organisation_id)
    settings = db.scalar(
        select(OrganisationSettings).where(OrganisationSettings.organisation_id == organisation_id)
    )
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation settings not found")
    return settings


@router.patch("/{organisation_id}/settings", response_model=OrganisationSettingsRead)
def patch_settings(
    organisation_id: int,
    settings_in: OrganisationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.organisation_id != organisation_id:
        _ensure_platform_admin(current_user)
    else:
        ensure_permission(current_user, Permission.USERS_MANAGE)
    _target_organisation(db, organisation_id)
    switch_to_platform_target(db, organisation_id)
    settings = db.scalar(
        select(OrganisationSettings).where(OrganisationSettings.organisation_id == organisation_id)
    )
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation settings not found")
    return update_organisation_settings(db, settings, settings_in)
