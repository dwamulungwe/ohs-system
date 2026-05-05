from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.document_control import (
    DocumentControlRecord,
    DocumentStatus,
)
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.training import ComplianceAcknowledgement
from app.models.user import User
from app.schemas.document_control import DocumentControlCreate, DocumentControlUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once, get_active_user_ids_for_roles
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER


class DocumentControlServiceError(Exception):
    pass


class DocumentControlNotFoundError(DocumentControlServiceError):
    pass


class DocumentControlValidationError(DocumentControlServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: int | None) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise DocumentControlValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise DocumentControlValidationError("Referenced user not found")


def _ensure_superseded_document_exists(db: Session, document_id: int | None) -> None:
    if document_id is not None and db.get(DocumentControlRecord, document_id) is None:
        raise DocumentControlValidationError("Superseded document not found")


def derive_status(data: dict) -> None:
    status = data.get("status", DocumentStatus.draft)
    if status == DocumentStatus.archived:
        return
    if data.get("expiry_date") is not None and data["expiry_date"] < _today():
        data["status"] = DocumentStatus.expired
        return
    if status == DocumentStatus.approved and data.get("approved_at") is None:
        data["approved_at"] = datetime.now(timezone.utc)


def _approval_recipients(db: Session, *, site_id: int | None) -> list[int]:
    return get_active_user_ids_for_roles(
        db,
        role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER],
        site_id=site_id,
    )


def _notify_document_state(db: Session, document: DocumentControlRecord) -> None:
    if document.status == DocumentStatus.pending_approval:
        for recipient_user_id in _approval_recipients(db, site_id=document.site_id):
            create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=recipient_user_id,
                    title="Document pending approval",
                    message=f"Document '{document.title}' is pending approval.",
                    notification_type=NotificationType.document_pending_approval,
                    severity=NotificationSeverity.warning,
                    related_entity_type=RelatedEntityType.document_control,
                    related_entity_id=document.id,
                ),
            )
    elif document.status == DocumentStatus.expired:
        for recipient_user_id in _approval_recipients(db, site_id=document.site_id):
            create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=recipient_user_id,
                    title="Document expired",
                    message=f"Document '{document.title}' has expired.",
                    notification_type=NotificationType.document_expired,
                    severity=NotificationSeverity.critical,
                    related_entity_type=RelatedEntityType.document_control,
                    related_entity_id=document.id,
                ),
            )
    elif document.expiry_date is not None and document.expiry_date <= _today() + timedelta(days=14):
        for recipient_user_id in _approval_recipients(db, site_id=document.site_id):
            create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=recipient_user_id,
                    title="Document expiry due soon",
                    message=f"Document '{document.title}' expires on {document.expiry_date}.",
                    notification_type=NotificationType.document_due_soon,
                    severity=NotificationSeverity.warning,
                    related_entity_type=RelatedEntityType.document_control,
                    related_entity_id=document.id,
                ),
            )


def _sync_acknowledgements(
    db: Session,
    document: DocumentControlRecord,
    *,
    actor_id: int | None,
) -> None:
    if not document.acknowledgement_required or not document.acknowledgement_user_ids:
        return
    existing_user_ids = {
        acknowledgement.assigned_to_user_id
        for acknowledgement in db.scalars(
            select(ComplianceAcknowledgement).where(
                ComplianceAcknowledgement.document_control_id == document.id
            )
        ).all()
    }
    for user_id in document.acknowledgement_user_ids:
        if user_id in existing_user_ids:
            continue
        _ensure_user_exists(db, user_id)
        db.add(
            ComplianceAcknowledgement(
                document_title=document.title,
                document_type=document.document_type.value,
                version=document.version,
                site_id=document.site_id,
                document_control_id=document.id,
                assigned_to_user_id=user_id,
                assigned_by_user_id=actor_id or document.created_by_user_id or user_id,
                notes="Assigned from document control workflow.",
            )
        )
    db.commit()


def sync_document_acknowledgements(
    db: Session,
    document: DocumentControlRecord,
    *,
    actor_id: int | None,
) -> None:
    _sync_acknowledgements(db, document, actor_id=actor_id)


def list_documents(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: DocumentStatus | None = None,
    document_type=None,
    site_id: int | None = None,
) -> dict:
    statement: Select[tuple[DocumentControlRecord]] = select(DocumentControlRecord)
    if status is not None:
        statement = statement.where(DocumentControlRecord.status == status)
    if document_type is not None:
        statement = statement.where(DocumentControlRecord.document_type == document_type)
    if site_id is not None:
        statement = statement.where(
            (DocumentControlRecord.site_id == site_id) | (DocumentControlRecord.site_id.is_(None))
        )
    statement = statement.order_by(DocumentControlRecord.updated_at.desc(), DocumentControlRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_document(db: Session, document_id: int) -> DocumentControlRecord:
    document = db.get(DocumentControlRecord, document_id)
    if document is None:
        raise DocumentControlNotFoundError("Document not found")
    return document


def create_document(
    db: Session,
    document_in: DocumentControlCreate,
    *,
    actor_id: int | None,
) -> DocumentControlRecord:
    data = document_in.model_dump()
    data["created_by_user_id"] = actor_id
    _ensure_site_exists(db, data.get("site_id"))
    _ensure_user_exists(db, data.get("approved_by_user_id"))
    _ensure_superseded_document_exists(db, data.get("supersedes_document_id"))
    derive_status(data)
    document = DocumentControlRecord(**data)
    db.add(document)
    db.commit()
    db.refresh(document)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="document_control.create",
        resource_type="document_control",
        resource_id=document.id,
        details={"status": document.status.value, "version": document.version},
    )
    _notify_document_state(db, document)
    if document.status == DocumentStatus.approved:
        _sync_acknowledgements(db, document, actor_id=actor_id)
    return document


def update_document(
    db: Session,
    document: DocumentControlRecord,
    document_in: DocumentControlUpdate,
    *,
    actor_id: int | None,
) -> DocumentControlRecord:
    update_data = document_in.model_dump(exclude_unset=True)
    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    if "approved_by_user_id" in update_data:
        _ensure_user_exists(db, update_data["approved_by_user_id"])
    if "supersedes_document_id" in update_data:
        _ensure_superseded_document_exists(db, update_data["supersedes_document_id"])
    effective_data = {
        "status": update_data.get("status", document.status),
        "expiry_date": update_data.get("expiry_date", document.expiry_date),
        "approved_at": update_data.get("approved_at", document.approved_at),
    }
    derive_status(effective_data)
    update_data["status"] = effective_data["status"]
    if effective_data["status"] == DocumentStatus.approved and update_data.get("approved_at") is None:
        update_data["approved_at"] = effective_data["approved_at"]
    for field, value in update_data.items():
        setattr(document, field, value)
    db.add(document)
    db.commit()
    db.refresh(document)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="document_control.update",
        resource_type="document_control",
        resource_id=document.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_document_state(db, document)
    if document.status == DocumentStatus.approved:
        _sync_acknowledgements(db, document, actor_id=actor_id)
    return document


def refresh_document_statuses(db: Session) -> int:
    documents = list(db.scalars(select(DocumentControlRecord)).all())
    updated = 0
    for document in documents:
        data = {
            "status": document.status,
            "expiry_date": document.expiry_date,
            "approved_at": document.approved_at,
        }
        derive_status(data)
        if document.status != data["status"]:
            document.status = data["status"]
            db.add(document)
            updated += 1
    if updated:
        db.commit()
    return updated


def generate_document_notifications(db: Session) -> int:
    count = 0
    for document in db.scalars(select(DocumentControlRecord)).all():
        before = count
        recipients = _approval_recipients(db, site_id=document.site_id)
        for recipient_user_id in recipients:
            notification = None
            if document.status == DocumentStatus.pending_approval:
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Document pending approval",
                        message=f"Document '{document.title}' is pending approval.",
                        notification_type=NotificationType.document_pending_approval,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.document_control,
                        related_entity_id=document.id,
                    ),
                )
            elif document.status == DocumentStatus.expired:
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Document expired",
                        message=f"Document '{document.title}' has expired.",
                        notification_type=NotificationType.document_expired,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.document_control,
                        related_entity_id=document.id,
                    ),
                )
            elif document.expiry_date is not None and document.expiry_date <= _today() + timedelta(days=14):
                notification = create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Document expiry due soon",
                        message=f"Document '{document.title}' expires on {document.expiry_date}.",
                        notification_type=NotificationType.document_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.document_control,
                        related_entity_id=document.id,
                    ),
                )
            if notification is not None:
                count += 1
        if count < before:
            count = before
    return count
