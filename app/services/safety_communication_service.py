from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.attachment import AttachmentEntityType
from app.models.safety_communication import (
    SafetyCommunication,
    SafetyCommunicationStatus,
    SafetyCommunicationType,
)
from app.models.site import Site
from app.schemas.safety_communication import SafetyCommunicationCreate, SafetyCommunicationUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.audit_service import write_audit_log
from app.services.query_utils import paginate


class SafetyCommunicationServiceError(Exception):
    pass


class SafetyCommunicationNotFoundError(SafetyCommunicationServiceError):
    pass


class SafetyCommunicationSiteNotFoundError(SafetyCommunicationServiceError):
    pass


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise SafetyCommunicationSiteNotFoundError(f"Site {site_id} was not found")


def list_safety_communications(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    communication_type: SafetyCommunicationType | None = None,
    communication_status: SafetyCommunicationStatus | None = None,
    site_id: int | None = None,
) -> dict:
    statement: Select[tuple[SafetyCommunication]] = select(SafetyCommunication)
    if communication_type is not None:
        statement = statement.where(SafetyCommunication.communication_type == communication_type)
    if communication_status is not None:
        statement = statement.where(SafetyCommunication.status == communication_status)
    if site_id is not None:
        statement = statement.where(SafetyCommunication.site_id == site_id)
    statement = statement.order_by(SafetyCommunication.issued_at.desc(), SafetyCommunication.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_safety_communication(db: Session, communication_id: int) -> SafetyCommunication:
    communication = db.get(SafetyCommunication, communication_id)
    if communication is None:
        raise SafetyCommunicationNotFoundError(f"Safety communication {communication_id} was not found")
    return communication


def create_safety_communication(
    db: Session,
    communication_in: SafetyCommunicationCreate,
    *,
    actor_id: int | None,
) -> SafetyCommunication:
    _ensure_site_exists(db, communication_in.site_id)
    communication = SafetyCommunication(**communication_in.model_dump())
    db.add(communication)
    db.commit()
    db.refresh(communication)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="safety_communication.create",
        resource_type="safety_communication",
        resource_id=communication.id,
        details={"communication_type": communication.communication_type.value},
    )
    return hydrate_entity_attachments(db, AttachmentEntityType.safety_communication, communication)


def update_safety_communication(
    db: Session,
    communication: SafetyCommunication,
    communication_in: SafetyCommunicationUpdate,
    *,
    actor_id: int | None,
) -> SafetyCommunication:
    update_data = communication_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    for field, value in update_data.items():
        setattr(communication, field, value)
    db.add(communication)
    db.commit()
    db.refresh(communication)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="safety_communication.update",
        resource_type="safety_communication",
        resource_id=communication.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    return hydrate_entity_attachments(db, AttachmentEntityType.safety_communication, communication)
