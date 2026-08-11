from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.role import Role
from app.schemas.organisation import OrganisationCreate, OrganisationSettingsUpdate, OrganisationUpdate
from app.services.rbac import STANDARD_ROLE_DESCRIPTIONS
from app.services.tenancy import MODULE_KEYS, set_tenant_context, unscoped_session


DEFAULT_ORGANISATION_CODE = "DEFAULT"
DEFAULT_ORGANISATION_SLUG = "ohs-default-organisation"


def create_organisation_record(
    db: Session,
    organisation_in: OrganisationCreate,
) -> Organisation:
    enabled_modules = set(organisation_in.enabled_modules or MODULE_KEYS)
    unknown = enabled_modules.difference(MODULE_KEYS)
    if unknown:
        raise ValueError(f"Unknown module keys: {', '.join(sorted(unknown))}")

    organisation = Organisation(
        **organisation_in.model_dump(exclude={"enabled_modules"}),
    )
    db.add(organisation)
    db.flush()
    with unscoped_session(db, allow_writes=True):
        db.add(OrganisationSettings(organisation_id=organisation.id))
        db.add_all(
            OrganisationFeature(
                organisation_id=organisation.id,
                key=key,
                is_enabled=key in enabled_modules,
            )
            for key in MODULE_KEYS
        )
        db.add_all(
            Role(
                organisation_id=organisation.id,
                name=name,
                description=description,
            )
            for name, description in STANDARD_ROLE_DESCRIPTIONS.items()
        )
        db.commit()
        db.refresh(organisation)
    return organisation


def ensure_default_organisation(db: Session) -> Organisation:
    with unscoped_session(db):
        organisation = db.scalar(
            select(Organisation).where(Organisation.code == DEFAULT_ORGANISATION_CODE)
        )
    if organisation is not None:
        return organisation
    return create_organisation_record(
        db,
        OrganisationCreate(
            name="OHS Default Organisation",
            code=DEFAULT_ORGANISATION_CODE,
            slug=DEFAULT_ORGANISATION_SLUG,
        ),
    )


def list_organisations(db: Session) -> list[Organisation]:
    with unscoped_session(db):
        return list(db.scalars(select(Organisation).order_by(Organisation.name)).unique().all())


def get_organisation(db: Session, organisation_id: int) -> Organisation | None:
    with unscoped_session(db):
        return db.get(Organisation, organisation_id)


def update_organisation(
    db: Session, organisation: Organisation, organisation_in: OrganisationUpdate
) -> Organisation:
    for field, value in organisation_in.model_dump(exclude_unset=True).items():
        setattr(organisation, field, value)
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


def update_organisation_settings(
    db: Session,
    settings: OrganisationSettings,
    settings_in: OrganisationSettingsUpdate,
) -> OrganisationSettings:
    for field, value in settings_in.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def switch_to_platform_target(db: Session, organisation_id: int) -> None:
    set_tenant_context(db, organisation_id, platform_admin=True)
