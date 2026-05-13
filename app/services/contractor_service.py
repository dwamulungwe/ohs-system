from __future__ import annotations

from typing import Optional
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.contractor import (
    ContractorComplianceDocumentsStatus,
    ContractorInductionStatus,
    ContractorOnboardingStatus,
    ContractorRecord,
)
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.schemas.contractor import ContractorCreate, ContractorUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once, get_active_user_ids_for_roles
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER


class ContractorServiceError(Exception):
    pass


class ContractorNotFoundError(ContractorServiceError):
    pass


class ContractorValidationError(ContractorServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise ContractorValidationError("Site not found")


def _validate_approval(data: dict, *, existing: Optional[ContractorRecord] = None) -> None:
    approved_for_work = data.get(
        "approved_for_work",
        existing.approved_for_work if existing is not None else False,
    )
    induction_status = data.get(
        "induction_status",
        existing.induction_status if existing is not None else ContractorInductionStatus.pending,
    )
    documents_status = data.get(
        "compliance_documents_status",
        existing.compliance_documents_status if existing is not None else ContractorComplianceDocumentsStatus.incomplete,
    )
    insurance_expiry = data.get(
        "insurance_expiry_date",
        existing.insurance_expiry_date if existing is not None else None,
    )
    documents_expiry = data.get(
        "documents_expiry_date",
        existing.documents_expiry_date if existing is not None else None,
    )

    if not approved_for_work:
        return
    if induction_status != ContractorInductionStatus.completed:
        raise ContractorValidationError("Contractor cannot be approved until induction is completed")
    if documents_status != ContractorComplianceDocumentsStatus.complete:
        raise ContractorValidationError("Contractor cannot be approved until compliance documents are complete")
    if insurance_expiry is not None and insurance_expiry < _today():
        raise ContractorValidationError("Contractor cannot be approved with expired insurance")
    if documents_expiry is not None and documents_expiry < _today():
        raise ContractorValidationError("Contractor cannot be approved with expired compliance documents")


def _reminder_recipients(db: Session, site_id: int) -> list[int]:
    return get_active_user_ids_for_roles(
        db,
        role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER],
        site_id=site_id,
    )


def _notify_expiry_dates(db: Session, contractor: ContractorRecord) -> None:
    today = _today()
    due_soon_by = today + timedelta(days=14)
    recipients = _reminder_recipients(db, contractor.site_id)
    for recipient_user_id in recipients:
        if contractor.insurance_expiry_date is not None:
            if contractor.insurance_expiry_date < today:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Contractor insurance overdue",
                        message=f"Insurance for contractor '{contractor.contractor_name}' is expired.",
                        notification_type=NotificationType.contractor_insurance_overdue,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.contractor,
                        related_entity_id=contractor.id,
                    ),
                )
            elif contractor.insurance_expiry_date <= due_soon_by:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Contractor insurance due soon",
                        message=f"Insurance for contractor '{contractor.contractor_name}' expires on {contractor.insurance_expiry_date}.",
                        notification_type=NotificationType.contractor_insurance_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.contractor,
                        related_entity_id=contractor.id,
                    ),
                )

        if contractor.documents_expiry_date is not None:
            if contractor.documents_expiry_date < today:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Contractor documents overdue",
                        message=f"Compliance documents for contractor '{contractor.contractor_name}' are expired.",
                        notification_type=NotificationType.contractor_documents_overdue,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.contractor,
                        related_entity_id=contractor.id,
                    ),
                )
            elif contractor.documents_expiry_date <= due_soon_by:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Contractor documents due soon",
                        message=f"Compliance documents for contractor '{contractor.contractor_name}' expire on {contractor.documents_expiry_date}.",
                        notification_type=NotificationType.contractor_documents_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.contractor,
                        related_entity_id=contractor.id,
                    ),
                )


def list_contractors(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    approved_for_work: Optional[bool] = None,
    onboarding_status: Optional[ContractorOnboardingStatus] = None,
    induction_status: Optional[ContractorInductionStatus] = None,
) -> dict:
    statement: Select[tuple[ContractorRecord]] = select(ContractorRecord)
    if site_id is not None:
        statement = statement.where(ContractorRecord.site_id == site_id)
    if approved_for_work is not None:
        statement = statement.where(ContractorRecord.approved_for_work == approved_for_work)
    if onboarding_status is not None:
        statement = statement.where(ContractorRecord.onboarding_status == onboarding_status)
    if induction_status is not None:
        statement = statement.where(ContractorRecord.induction_status == induction_status)
    statement = statement.order_by(ContractorRecord.contractor_name.asc(), ContractorRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_contractor(db: Session, contractor_id: int) -> ContractorRecord:
    contractor = db.get(ContractorRecord, contractor_id)
    if contractor is None:
        raise ContractorNotFoundError("Contractor not found")
    return contractor


def create_contractor(db: Session, contractor_in: ContractorCreate, *, actor_id: Optional[int]) -> ContractorRecord:
    data = contractor_in.model_dump()
    _ensure_site_exists(db, data["site_id"])
    _validate_approval(data)
    contractor = ContractorRecord(**data)
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="contractor.create",
        resource_type="contractor",
        resource_id=contractor.id,
        details={"approved_for_work": contractor.approved_for_work},
    )
    _notify_expiry_dates(db, contractor)
    return contractor


def update_contractor(
    db: Session,
    contractor: ContractorRecord,
    contractor_in: ContractorUpdate,
    *,
    actor_id: Optional[int],
) -> ContractorRecord:
    update_data = contractor_in.model_dump(exclude_unset=True)
    if "site_id" in update_data and update_data["site_id"] is not None:
        _ensure_site_exists(db, update_data["site_id"])
    _validate_approval(update_data, existing=contractor)
    for field, value in update_data.items():
        setattr(contractor, field, value)
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="contractor.update",
        resource_type="contractor",
        resource_id=contractor.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_expiry_dates(db, contractor)
    return contractor
