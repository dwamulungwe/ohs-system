from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organisation import OrganisationFeature


MODULE_KEYS = (
    "dashboard",
    "incidents",
    "incident_investigations",
    "hazards",
    "sios",
    "corrective_actions",
    "inspections",
    "audits",
    "permits",
    "jsas",
    "training",
    "compliance",
    "medical_surveillance",
    "contractors",
    "assets",
    "emergency_drills",
    "safety_communications",
    "behaviour_observations",
    "safety_kpis",
    "document_control",
    "data_imports",
    "reporting",
)

ENTITY_FEATURE_KEYS = {
    "sio": "sios",
    "incident": "incidents",
    "hazard": "hazards",
    "inspection": "inspections",
    "corrective_action": "corrective_actions",
    "permit": "permits",
    "training": "training",
    "training_record": "training",
    "compliance_acknowledgement": "compliance",
    "safety_communication": "safety_communications",
    "behaviour_observation": "behaviour_observations",
    "incident_investigation": "incident_investigations",
    "legal_compliance": "compliance",
    "jsa": "jsas",
    "contractor": "contractors",
    "asset_register": "assets",
    "medical_surveillance": "medical_surveillance",
    "emergency_drill": "emergency_drills",
    "document_control": "document_control",
    "audit_management": "audits",
}


class TenantBoundaryError(RuntimeError):
    pass


def set_tenant_context(db: Session, organisation_id: int, *, platform_admin: bool = False) -> None:
    if not organisation_id:
        raise TenantBoundaryError("An organisation context is required")
    db.info["organisation_id"] = organisation_id
    db.info["is_platform_admin"] = bool(platform_admin)


def set_user_tenant_context(db: Session, user) -> None:
    organisation_id = getattr(user, "organisation_id", None)
    if not organisation_id:
        raise TenantBoundaryError("The authenticated user is not assigned to an organisation")
    set_tenant_context(
        db,
        organisation_id,
        platform_admin=bool(getattr(user, "is_platform_admin", False)),
    )


def current_organisation_id(db: Session) -> int:
    organisation_id = db.info.get("organisation_id")
    if not organisation_id:
        raise TenantBoundaryError("An organisation context is required")
    return int(organisation_id)


@contextmanager
def unscoped_session(db: Session, *, allow_writes: bool = False) -> Iterator[None]:
    """Explicit escape hatch for authentication and platform administration only."""

    previous_read = db.info.get("bypass_tenant_filter", False)
    previous_write = db.info.get("allow_cross_tenant_writes", False)
    db.info["bypass_tenant_filter"] = True
    if allow_writes:
        db.info["allow_cross_tenant_writes"] = True
    try:
        yield
    finally:
        db.info["bypass_tenant_filter"] = previous_read
        db.info["allow_cross_tenant_writes"] = previous_write


def organisation_has_feature(db: Session, organisation_id: int, feature_key: str) -> bool:
    if feature_key not in MODULE_KEYS:
        return False
    feature = db.scalar(
        select(OrganisationFeature).where(
            OrganisationFeature.organisation_id == organisation_id,
            OrganisationFeature.key == feature_key,
        )
    )
    return bool(feature and feature.is_enabled)


def ensure_feature_enabled(db: Session, user, feature_key: str) -> None:
    if not organisation_has_feature(db, user.organisation_id, feature_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"The {feature_key} module is not enabled for this organisation",
        )


def ensure_entity_feature_enabled(db: Session, user, entity_type) -> None:
    entity_value = getattr(entity_type, "value", entity_type)
    feature_key = ENTITY_FEATURE_KEYS.get(str(entity_value))
    if feature_key:
        ensure_feature_enabled(db, user, feature_key)


def enabled_feature_keys(db: Session, organisation_id: int) -> list[str]:
    return sorted(
        db.scalars(
            select(OrganisationFeature.key).where(
                OrganisationFeature.organisation_id == organisation_id,
                OrganisationFeature.is_enabled.is_(True),
            )
        ).all()
    )


def require_feature(feature_key: str):
    from app.api.deps import get_current_user, get_db

    def dependency(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user),
    ):
        ensure_feature_enabled(db, current_user, feature_key)
        return current_user

    return dependency
