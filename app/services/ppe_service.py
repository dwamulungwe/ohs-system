from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contractor import ContractorRecord
from app.models.corrective_action import CorrectiveActionPriority, CorrectiveActionSourceType
from app.models.department import Department
from app.models.hazard import Hazard
from app.models.jsa import JobSafetyAnalysis
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.organisation import OrganisationSettings
from app.models.ppe import (
    PPEAsset,
    PPEAssetStatus,
    PPECategory,
    PPEComplianceStatus,
    PPECondition,
    PPEInspection,
    PPEInventory,
    PPEIssue,
    PPEIssueStatus,
    PPEItem,
    PPELossDamageReport,
    PPELossDamageType,
    PPEMovementType,
    PPERecipientType,
    PPEReminderDelivery,
    PPERequest,
    PPERequestStatus,
    PPERequirement,
    PPERequirementLevel,
    PPEReturn,
    PPEReturnOutcome,
    PPEStockLocation,
    PPEStockMovement,
    PPEVariant,
)
from app.models.site import Site
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.notification import NotificationCreate
from app.schemas.ppe import (
    PPEActionLinkCreate,
    PPEAcknowledgementCreate,
    PPEAssetCreate,
    PPECategoryCreate,
    PPECategoryUpdate,
    PPEInspectionCreate,
    PPEIssueCreate,
    PPEItemCreate,
    PPEItemUpdate,
    PPELossDamageCreate,
    PPEReplacementCreate,
    PPERequestCreate,
    PPERequestDecision,
    PPERequirementCreate,
    PPERequirementUpdate,
    PPEReturnCreate,
    PPEStockAdjustment,
    PPEStockLocationCreate,
    PPEStockLocationUpdate,
    PPEStockReceipt,
    PPEStockTransfer,
    PPEVariantCreate,
    PPEVariantUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.notification_service import create_notification, create_notification_once, get_active_user_ids_for_roles
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER, get_normalized_role_names
from app.services.tenancy import current_organisation_id


class PPEServiceError(Exception):
    pass


class PPENotFoundError(PPEServiceError):
    pass


class PPEValidationError(PPEServiceError):
    pass


class PPEInsufficientStockError(PPEValidationError):
    pass


ACTIVE_ISSUE_STATUSES = {PPEIssueStatus.issued, PPEIssueStatus.partially_returned}
DEFAULT_CONFIGURATION = {
    "request_approval_required": True,
    "replacement_reminder_windows": [90, 60, 30, 7],
    "inspection_reminder_windows": [90, 60, 30, 7],
    "expiry_reminder_windows": [90, 60, 30, 7],
    "low_stock_notifications": True,
    "allow_negative_inventory": False,
    "recipient_acknowledgement_required": True,
    "critical_ppe_requires_current_inspection": True,
    "create_actions_for_critical_failures": False,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _settings(db: Session) -> dict:
    record = db.scalar(select(OrganisationSettings))
    configured = record.ppe_configuration if record else {}
    return {**DEFAULT_CONFIGURATION, **(configured or {})}


def _get(db: Session, model, record_id: Optional[int], label: str, *, optional: bool = False):
    if record_id is None and optional:
        return None
    record = db.get(model, record_id)
    if record is None:
        raise PPENotFoundError(f"{label} not found")
    return record


def _audit(db: Session, *, actor_id: Optional[int], action: str, resource_type: str, resource_id: int, details: Optional[dict] = None) -> None:
    write_audit_log(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )


def _validate_variant(item: PPEItem, variant: Optional[PPEVariant]) -> None:
    if variant is not None and variant.item_id != item.id:
        raise PPEValidationError("Variant does not belong to the selected PPE item")


def list_categories(db: Session, *, active_only: bool = False) -> list[PPECategory]:
    statement = select(PPECategory)
    if active_only:
        statement = statement.where(PPECategory.is_active.is_(True))
    return list(db.scalars(statement.order_by(PPECategory.name.asc())).all())


def create_category(db: Session, payload: PPECategoryCreate, *, actor_id: int) -> PPECategory:
    category = PPECategory(**payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PPEValidationError("A PPE category with this name already exists") from exc
    db.refresh(category)
    _audit(db, actor_id=actor_id, action="ppe.category.create", resource_type="ppe_category", resource_id=category.id)
    return category


def update_category(db: Session, category_id: int, payload: PPECategoryUpdate, *, actor_id: int) -> PPECategory:
    category = _get(db, PPECategory, category_id, "PPE category")
    fields = payload.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    _audit(db, actor_id=actor_id, action="ppe.category.update", resource_type="ppe_category", resource_id=category.id, details={"fields": sorted(fields)})
    return category


def list_items(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    active: Optional[bool] = None,
    search: Optional[str] = None,
) -> dict:
    statement: Select[tuple[PPEItem]] = select(PPEItem)
    if category_id is not None:
        statement = statement.where(PPEItem.category_id == category_id)
    if active is not None:
        statement = statement.where(PPEItem.is_active == active)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(PPEItem.name.ilike(pattern), PPEItem.code.ilike(pattern)))
    statement = statement.order_by(PPEItem.name.asc(), PPEItem.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_item(db: Session, item_id: int) -> PPEItem:
    return _get(db, PPEItem, item_id, "PPE item")


def create_item(db: Session, payload: PPEItemCreate, *, actor_id: int) -> PPEItem:
    _get(db, PPECategory, payload.category_id, "PPE category")
    item = PPEItem(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PPEValidationError("A PPE item with this code already exists") from exc
    db.refresh(item)
    _audit(db, actor_id=actor_id, action="ppe.item.create", resource_type="ppe_item", resource_id=item.id)
    return item


def update_item(db: Session, item_id: int, payload: PPEItemUpdate, *, actor_id: int) -> PPEItem:
    item = get_item(db, item_id)
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("category_id") is not None:
        _get(db, PPECategory, fields["category_id"], "PPE category")
    for key, value in fields.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    _audit(db, actor_id=actor_id, action="ppe.item.update", resource_type="ppe_item", resource_id=item.id, details={"fields": sorted(fields)})
    return item


def create_variant(db: Session, payload: PPEVariantCreate, *, actor_id: int) -> PPEVariant:
    item = get_item(db, payload.item_id)
    if not item.size_applicable and payload.size:
        raise PPEValidationError("Size variants are not enabled for this PPE item")
    variant = PPEVariant(**payload.model_dump())
    db.add(variant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PPEValidationError("This PPE variant already exists") from exc
    db.refresh(variant)
    _audit(db, actor_id=actor_id, action="ppe.variant.create", resource_type="ppe_variant", resource_id=variant.id)
    return variant


def update_variant(db: Session, variant_id: int, payload: PPEVariantUpdate, *, actor_id: int) -> PPEVariant:
    variant = _get(db, PPEVariant, variant_id, "PPE variant")
    fields = payload.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(variant, key, value)
    db.commit()
    db.refresh(variant)
    _audit(db, actor_id=actor_id, action="ppe.variant.update", resource_type="ppe_variant", resource_id=variant.id, details={"fields": sorted(fields)})
    return variant


def list_locations(db: Session, *, site_id: Optional[int] = None, active_only: bool = False) -> list[PPEStockLocation]:
    statement = select(PPEStockLocation)
    if site_id is not None:
        statement = statement.where(PPEStockLocation.site_id == site_id)
    if active_only:
        statement = statement.where(PPEStockLocation.is_active.is_(True))
    return list(db.scalars(statement.order_by(PPEStockLocation.name.asc())).all())


def create_location(db: Session, payload: PPEStockLocationCreate, *, actor_id: int) -> PPEStockLocation:
    if payload.site_id is not None:
        _get(db, Site, payload.site_id, "Site")
    location = PPEStockLocation(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    _audit(db, actor_id=actor_id, action="ppe.location.create", resource_type="ppe_stock_location", resource_id=location.id)
    return location


def update_location(db: Session, location_id: int, payload: PPEStockLocationUpdate, *, actor_id: int) -> PPEStockLocation:
    location = _get(db, PPEStockLocation, location_id, "PPE stock location")
    fields = payload.model_dump(exclude_unset=True)
    if "site_id" in fields and fields["site_id"] is not None:
        _get(db, Site, fields["site_id"], "Site")
    for key, value in fields.items():
        setattr(location, key, value)
    db.commit()
    db.refresh(location)
    _audit(db, actor_id=actor_id, action="ppe.location.update", resource_type="ppe_stock_location", resource_id=location.id, details={"fields": sorted(fields)})
    return location


def _inventory_statement(item_id: int, variant_id: Optional[int], location_id: int):
    statement = select(PPEInventory).where(PPEInventory.item_id == item_id, PPEInventory.location_id == location_id)
    statement = statement.where(PPEInventory.variant_id == variant_id) if variant_id is not None else statement.where(PPEInventory.variant_id.is_(None))
    return statement


def _get_or_create_inventory(
    db: Session,
    *,
    item: PPEItem,
    variant: Optional[PPEVariant],
    location: PPEStockLocation,
    unit_cost: Optional[Decimal] = None,
) -> PPEInventory:
    inventory = db.scalar(_inventory_statement(item.id, variant.id if variant else None, location.id).with_for_update())
    if inventory is None:
        inventory = PPEInventory(
            item_id=item.id,
            variant_id=variant.id if variant else None,
            location_id=location.id,
            quantity_on_hand=0,
            quantity_reserved=0,
            quantity_available=0,
            reorder_level=item.reorder_level,
            minimum_stock_level=item.minimum_stock_level,
            unit_cost=unit_cost if unit_cost is not None else (variant.unit_cost if variant and variant.unit_cost is not None else item.unit_cost),
        )
        db.add(inventory)
        db.flush()
    return inventory


def _apply_movement(
    db: Session,
    inventory: PPEInventory,
    *,
    quantity: int,
    movement_type: PPEMovementType,
    actor_id: Optional[int],
    reason: Optional[str] = None,
    reference: Optional[str] = None,
    related_issue_id: Optional[int] = None,
    related_return_id: Optional[int] = None,
    transfer_reference: Optional[str] = None,
    allow_negative: bool = False,
) -> PPEStockMovement:
    new_on_hand = inventory.quantity_on_hand + quantity
    new_available = new_on_hand - inventory.quantity_reserved
    if (new_on_hand < 0 or new_available < 0) and not allow_negative:
        db.rollback()
        raise PPEInsufficientStockError(
            f"Insufficient stock: {inventory.quantity_available} available, {abs(quantity)} requested"
        )
    inventory.quantity_on_hand = new_on_hand
    inventory.quantity_available = new_available
    inventory.last_stock_movement_at = _now()
    movement = PPEStockMovement(
        inventory_id=inventory.id,
        item_id=inventory.item_id,
        variant_id=inventory.variant_id,
        location_id=inventory.location_id,
        quantity=quantity,
        movement_type=movement_type,
        actor_user_id=actor_id,
        reason=reason,
        reference=reference,
        related_issue_id=related_issue_id,
        related_return_id=related_return_id,
        transfer_reference=transfer_reference,
        balance_after=new_on_hand,
        unit_cost_snapshot=inventory.unit_cost,
    )
    db.add_all([inventory, movement])
    return movement


def list_inventory(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    location_id: Optional[int] = None,
    item_id: Optional[int] = None,
    category_id: Optional[int] = None,
    variant_id: Optional[int] = None,
    low_stock: Optional[bool] = None,
) -> dict:
    statement: Select[tuple[PPEInventory]] = select(PPEInventory).join(PPEInventory.location).join(PPEInventory.item)
    if site_id is not None:
        statement = statement.where(PPEStockLocation.site_id == site_id)
    if location_id is not None:
        statement = statement.where(PPEInventory.location_id == location_id)
    if item_id is not None:
        statement = statement.where(PPEInventory.item_id == item_id)
    if category_id is not None:
        statement = statement.where(PPEItem.category_id == category_id)
    if variant_id is not None:
        statement = statement.where(PPEInventory.variant_id == variant_id)
    if low_stock is True:
        statement = statement.where(PPEInventory.quantity_available <= PPEInventory.reorder_level)
    elif low_stock is False:
        statement = statement.where(PPEInventory.quantity_available > PPEInventory.reorder_level)
    statement = statement.order_by(PPEItem.name.asc(), PPEStockLocation.name.asc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def receive_stock(db: Session, payload: PPEStockReceipt, *, actor_id: int) -> PPEInventory:
    item = get_item(db, payload.item_id)
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    location = _get(db, PPEStockLocation, payload.location_id, "PPE stock location")
    inventory = _get_or_create_inventory(db, item=item, variant=variant, location=location, unit_cost=payload.unit_cost)
    if payload.unit_cost is not None:
        inventory.unit_cost = payload.unit_cost
    movement_type = PPEMovementType.opening_balance if payload.opening_balance else PPEMovementType.purchase_receipt
    _apply_movement(db, inventory, quantity=payload.quantity, movement_type=movement_type, actor_id=actor_id, reason=payload.reason, reference=payload.reference)
    db.commit()
    db.refresh(inventory)
    _audit(db, actor_id=actor_id, action="ppe.stock.receive", resource_type="ppe_inventory", resource_id=inventory.id, details={"quantity": payload.quantity, "location_id": location.id})
    return inventory


def receive_stock_bulk(db: Session, payloads: list[PPEStockReceipt], *, actor_id: int) -> list[PPEInventory]:
    inventories: list[PPEInventory] = []
    try:
        for payload in payloads:
            item = get_item(db, payload.item_id)
            variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
            _validate_variant(item, variant)
            location = _get(db, PPEStockLocation, payload.location_id, "PPE stock location")
            inventory = _get_or_create_inventory(db, item=item, variant=variant, location=location, unit_cost=payload.unit_cost)
            if payload.unit_cost is not None:
                inventory.unit_cost = payload.unit_cost
            _apply_movement(
                db,
                inventory,
                quantity=payload.quantity,
                movement_type=PPEMovementType.opening_balance if payload.opening_balance else PPEMovementType.purchase_receipt,
                actor_id=actor_id,
                reason=payload.reason,
                reference=payload.reference,
            )
            inventories.append(inventory)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for inventory in inventories:
        db.refresh(inventory)
        _audit(db, actor_id=actor_id, action="ppe.stock.receive", resource_type="ppe_inventory", resource_id=inventory.id, details={"bulk": True})
    return inventories


def transfer_stock(db: Session, payload: PPEStockTransfer, *, actor_id: int) -> list[PPEStockMovement]:
    if payload.source_location_id == payload.destination_location_id:
        raise PPEValidationError("Source and destination locations must differ")
    item = get_item(db, payload.item_id)
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    source_location = _get(db, PPEStockLocation, payload.source_location_id, "Source location")
    destination_location = _get(db, PPEStockLocation, payload.destination_location_id, "Destination location")
    source = db.scalar(_inventory_statement(item.id, variant.id if variant else None, source_location.id).with_for_update())
    if source is None:
        raise PPEInsufficientStockError("No stock exists at the source location")
    destination = _get_or_create_inventory(db, item=item, variant=variant, location=destination_location, unit_cost=source.unit_cost)
    transfer_reference = f"PPE-TFR-{uuid4().hex[:12].upper()}"
    out = _apply_movement(db, source, quantity=-payload.quantity, movement_type=PPEMovementType.transfer_out, actor_id=actor_id, reason=payload.reason, reference=payload.reference, transfer_reference=transfer_reference)
    incoming = _apply_movement(db, destination, quantity=payload.quantity, movement_type=PPEMovementType.transfer_in, actor_id=actor_id, reason=payload.reason, reference=payload.reference, transfer_reference=transfer_reference)
    db.commit()
    db.refresh(out)
    db.refresh(incoming)
    _audit(db, actor_id=actor_id, action="ppe.stock.transfer", resource_type="ppe_stock_movement", resource_id=out.id, details={"quantity": payload.quantity, "destination_movement_id": incoming.id, "transfer_reference": transfer_reference})
    return [out, incoming]


def adjust_stock(db: Session, payload: PPEStockAdjustment, *, actor_id: int) -> PPEInventory:
    item = get_item(db, payload.item_id)
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    location = _get(db, PPEStockLocation, payload.location_id, "PPE stock location")
    inventory = _get_or_create_inventory(db, item=item, variant=variant, location=location)
    _apply_movement(db, inventory, quantity=payload.quantity_delta, movement_type=payload.movement_type, actor_id=actor_id, reason=payload.reason, reference=payload.reference)
    db.commit()
    db.refresh(inventory)
    _audit(db, actor_id=actor_id, action="ppe.stock.adjust", resource_type="ppe_inventory", resource_id=inventory.id, details={"quantity_delta": payload.quantity_delta, "movement_type": payload.movement_type.value})
    return inventory


def list_movements(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    location_id: Optional[int] = None,
    item_id: Optional[int] = None,
    movement_type: Optional[PPEMovementType] = None,
) -> dict:
    statement: Select[tuple[PPEStockMovement]] = select(PPEStockMovement)
    if site_id is not None:
        statement = statement.join(PPEStockLocation, PPEStockMovement.location_id == PPEStockLocation.id).where(PPEStockLocation.site_id == site_id)
    if location_id is not None:
        statement = statement.where(PPEStockMovement.location_id == location_id)
    if item_id is not None:
        statement = statement.where(PPEStockMovement.item_id == item_id)
    if movement_type is not None:
        statement = statement.where(PPEStockMovement.movement_type == movement_type)
    statement = statement.order_by(PPEStockMovement.created_at.desc(), PPEStockMovement.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def create_asset(db: Session, payload: PPEAssetCreate, *, actor_id: int) -> PPEAsset:
    item = get_item(db, payload.item_id)
    if not item.requires_individual_tracking:
        raise PPEValidationError("Individual asset tracking is not enabled for this PPE item")
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    if payload.location_id is not None:
        _get(db, PPEStockLocation, payload.location_id, "PPE stock location")
    asset = PPEAsset(**payload.model_dump())
    db.add(asset)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PPEValidationError("Asset tag or serial number already exists") from exc
    db.refresh(asset)
    _audit(db, actor_id=actor_id, action="ppe.asset.create", resource_type="ppe_asset", resource_id=asset.id)
    return asset


def _issue_due_dates(item: PPEItem, payload: PPEIssueCreate) -> tuple[Optional[date], Optional[date]]:
    issue_date = payload.issue_date or _today()
    replacement = payload.expected_replacement_date
    if replacement is None and item.default_replacement_interval_days:
        replacement = issue_date + timedelta(days=item.default_replacement_interval_days)
    inspection = None
    if item.inspection_required and item.default_inspection_interval_days:
        inspection = issue_date + timedelta(days=item.default_inspection_interval_days)
    return replacement, inspection


def issue_ppe(db: Session, payload: PPEIssueCreate, *, actor_id: int, allow_override: bool = False) -> PPEIssue:
    item = get_item(db, payload.item_id)
    if not item.is_active:
        raise PPEValidationError("Inactive PPE items cannot be issued")
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    location = _get(db, PPEStockLocation, payload.stock_location_id, "PPE stock location")
    recipient = _get(db, User, payload.recipient_user_id, "Recipient user", optional=True)
    contractor = _get(db, ContractorRecord, payload.contractor_id, "Contractor", optional=True)
    if payload.recipient_type == PPERecipientType.employee and recipient is None:
        raise PPEValidationError("A valid employee recipient is required")
    if payload.recipient_type == PPERecipientType.contractor and contractor is None:
        raise PPEValidationError("A valid contractor recipient is required")
    if recipient is not None:
        recipient_name_snapshot = recipient.full_name
        site_id_snapshot = recipient.assigned_site_id
        department_id_snapshot = recipient.department_id
    elif contractor is not None:
        recipient_name_snapshot = contractor.contractor_name
        site_id_snapshot = contractor.site_id
        department_id_snapshot = None
    else:
        recipient_name_snapshot = payload.external_recipient_name or payload.external_recipient_reference or "External recipient"
        site_id_snapshot = location.site_id
        department_id_snapshot = None
    inventory = db.scalar(_inventory_statement(item.id, variant.id if variant else None, location.id).with_for_update())
    if inventory is None:
        raise PPEInsufficientStockError("No stock is available for this item and location")
    asset = _get(db, PPEAsset, payload.asset_id, "PPE asset", optional=True)
    if item.requires_individual_tracking:
        if asset is None:
            raise PPEValidationError("A tracked PPE asset is required")
        if payload.quantity != 1:
            raise PPEValidationError("Serialized PPE must be issued one asset at a time")
        if asset.item_id != item.id or asset.variant_id != (variant.id if variant else None):
            raise PPEValidationError("Tracked asset does not match the selected item and variant")
        if asset.status != PPEAssetStatus.available:
            raise PPEValidationError("Tracked PPE asset is not available")
    elif asset is not None:
        raise PPEValidationError("An asset cannot be selected for commodity PPE")

    request = _get(db, PPERequest, payload.request_id, "PPE request", optional=True)
    if request is not None and request.status != PPERequestStatus.approved:
        raise PPEValidationError("Only approved requests can be issued")
    replacement_date, inspection_date = _issue_due_dates(item, payload)
    issue = PPEIssue(
        recipient_type=payload.recipient_type,
        recipient_user_id=payload.recipient_user_id,
        contractor_id=payload.contractor_id,
        external_recipient_name=payload.external_recipient_name,
        external_recipient_reference=payload.external_recipient_reference,
        recipient_name_snapshot=recipient_name_snapshot,
        site_id_snapshot=site_id_snapshot,
        department_id_snapshot=department_id_snapshot,
        item_id=item.id,
        variant_id=variant.id if variant else None,
        asset_id=asset.id if asset else None,
        stock_location_id=location.id,
        quantity=payload.quantity,
        issue_date=payload.issue_date or _today(),
        expected_replacement_date=replacement_date,
        expiry_date=payload.expiry_date or (asset.expiry_date if asset else None),
        next_inspection_date=inspection_date,
        condition_at_issue=payload.condition_at_issue,
        issued_by_user_id=actor_id,
        acknowledgement_required=payload.acknowledgement_required if payload.acknowledgement_required is not None else bool(_settings(db)["recipient_acknowledgement_required"]),
        notes=payload.notes,
        unit_cost_snapshot=inventory.unit_cost,
        item_name_snapshot=item.name,
        item_code_snapshot=item.code,
        variant_name_snapshot=variant.name if variant else None,
        stock_location_name_snapshot=location.name,
        request_id=payload.request_id,
    )
    db.add(issue)
    db.flush()
    _apply_movement(
        db,
        inventory,
        quantity=-payload.quantity,
        movement_type=PPEMovementType.issue,
        actor_id=actor_id,
        reason=f"Issued to {payload.recipient_type.value}",
        related_issue_id=issue.id,
        allow_negative=(
            allow_override
            and payload.authorised_negative_override
            and bool(_settings(db).get("allow_negative_inventory", False))
        ),
    )
    if asset is not None:
        asset.status = PPEAssetStatus.issued
        asset.location_id = None
        asset.condition = payload.condition_at_issue
    if request is not None:
        request.status = PPERequestStatus.issued
        request.issue_id = issue.id
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(issue)
    _audit(db, actor_id=actor_id, action="ppe.issue", resource_type="ppe_issue", resource_id=issue.id, details={"quantity": issue.quantity, "location_id": location.id, "override_requested": payload.authorised_negative_override})
    if issue.recipient_user_id is not None:
        create_notification_once(db, NotificationCreate(recipient_user_id=issue.recipient_user_id, title="PPE issued", message=f"{issue.quantity} × {issue.item_name_snapshot} has been issued to you.", notification_type=NotificationType.ppe_issued, severity=NotificationSeverity.info, related_entity_type=RelatedEntityType.ppe_issue, related_entity_id=issue.id))
    return issue


def list_issues(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
    recipient_user_id: Optional[int] = None,
    item_id: Optional[int] = None,
    status: Optional[PPEIssueStatus] = None,
    replacement_due_before: Optional[date] = None,
    inspection_due_before: Optional[date] = None,
    expiry_before: Optional[date] = None,
) -> dict:
    statement: Select[tuple[PPEIssue]] = select(PPEIssue)
    if site_id is not None:
        statement = statement.where(PPEIssue.site_id_snapshot == site_id)
    if department_id is not None:
        statement = statement.where(PPEIssue.department_id_snapshot == department_id)
    if recipient_user_id is not None:
        statement = statement.where(PPEIssue.recipient_user_id == recipient_user_id)
    if item_id is not None:
        statement = statement.where(PPEIssue.item_id == item_id)
    if status is not None:
        statement = statement.where(PPEIssue.status == status)
    if replacement_due_before is not None:
        statement = statement.where(PPEIssue.expected_replacement_date <= replacement_due_before)
    if inspection_due_before is not None:
        statement = statement.where(PPEIssue.next_inspection_date <= inspection_due_before)
    if expiry_before is not None:
        statement = statement.where(PPEIssue.expiry_date <= expiry_before)
    statement = statement.order_by(PPEIssue.issue_date.desc(), PPEIssue.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_issue(db: Session, issue_id: int) -> PPEIssue:
    return _get(db, PPEIssue, issue_id, "PPE issue")


def acknowledge_issue(db: Session, issue_id: int, payload: PPEAcknowledgementCreate, *, actor_id: int) -> PPEIssue:
    issue = get_issue(db, issue_id)
    if issue.recipient_type == PPERecipientType.employee and issue.recipient_user_id != actor_id:
        raise PPEValidationError("Only the PPE recipient may acknowledge receipt")
    if issue.acknowledged_at is not None:
        return issue
    issue.acknowledged_at = _now()
    issue.acknowledgement_method = payload.method
    issue.acknowledgement_reference = payload.reference
    db.commit()
    db.refresh(issue)
    _audit(db, actor_id=actor_id, action="ppe.issue.acknowledge", resource_type="ppe_issue", resource_id=issue.id, details={"method": payload.method})
    return issue


def return_ppe(db: Session, issue_id: int, payload: PPEReturnCreate, *, actor_id: int) -> PPEReturn:
    issue = get_issue(db, issue_id)
    if issue.status not in ACTIVE_ISSUE_STATUSES:
        raise PPEValidationError("This PPE issue is no longer returnable")
    if payload.quantity > issue.active_quantity:
        raise PPEValidationError("Returned quantity exceeds the active issued quantity")
    returned = PPEReturn(
        issue_id=issue.id,
        quantity=payload.quantity,
        returned_at=payload.returned_at or _now(),
        condition=payload.condition,
        outcome=payload.outcome,
        received_by_user_id=actor_id,
        notes=payload.notes,
    )
    db.add(returned)
    db.flush()
    issue.returned_quantity += payload.quantity
    if issue.returned_quantity == issue.quantity:
        issue.status = {
            PPEReturnOutcome.reusable: PPEIssueStatus.returned,
            PPEReturnOutcome.expired: PPEIssueStatus.expired,
            PPEReturnOutcome.damaged: PPEIssueStatus.damaged,
            PPEReturnOutcome.contaminated: PPEIssueStatus.unserviceable,
            PPEReturnOutcome.write_off: PPEIssueStatus.unserviceable,
        }[payload.outcome]
    else:
        issue.status = PPEIssueStatus.partially_returned
    if payload.outcome == PPEReturnOutcome.reusable:
        inventory = db.scalar(_inventory_statement(issue.item_id, issue.variant_id, issue.stock_location_id).with_for_update())
        if inventory is None:
            raise PPEValidationError("Original inventory record not found")
        _apply_movement(db, inventory, quantity=payload.quantity, movement_type=PPEMovementType.return_reusable, actor_id=actor_id, reason=payload.notes, related_issue_id=issue.id, related_return_id=returned.id)
        if issue.asset_id:
            asset = _get(db, PPEAsset, issue.asset_id, "PPE asset")
            asset.status = PPEAssetStatus.available
            asset.location_id = issue.stock_location_id
            asset.condition = payload.condition
    elif issue.asset_id:
        asset = _get(db, PPEAsset, issue.asset_id, "PPE asset")
        asset.status = PPEAssetStatus.unserviceable
        asset.condition = payload.condition
    db.commit()
    db.refresh(returned)
    _audit(db, actor_id=actor_id, action="ppe.return", resource_type="ppe_return", resource_id=returned.id, details={"issue_id": issue.id, "quantity": returned.quantity, "outcome": returned.outcome.value})
    return returned


def report_loss_damage(db: Session, issue_id: int, payload: PPELossDamageCreate, *, actor_id: int) -> PPELossDamageReport:
    issue = get_issue(db, issue_id)
    if issue.status not in ACTIVE_ISSUE_STATUSES:
        raise PPEValidationError("This issue is no longer active")
    if issue.recipient_user_id is not None and issue.recipient_user_id != actor_id:
        # Manager endpoints enforce broader permissions; the service keeps the
        # self-reporting path tenant-safe and explicit.
        pass
    report = PPELossDamageReport(issue_id=issue.id, reported_by_user_id=actor_id, **payload.model_dump())
    db.add(report)
    issue.status = PPEIssueStatus.lost if payload.report_type == PPELossDamageType.lost else PPEIssueStatus.damaged
    if issue.asset_id:
        asset = _get(db, PPEAsset, issue.asset_id, "PPE asset")
        asset.status = PPEAssetStatus.lost if payload.report_type == PPELossDamageType.lost else PPEAssetStatus.unserviceable
        asset.condition = PPECondition.unserviceable if payload.report_type != PPELossDamageType.lost else asset.condition
    db.commit()
    db.refresh(report)
    _audit(db, actor_id=actor_id, action="ppe.loss_damage.report", resource_type="ppe_loss_damage", resource_id=report.id, details={"issue_id": issue.id, "type": payload.report_type.value})
    for recipient_id in get_active_user_ids_for_roles(db, role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER]):
        create_notification_once(db, NotificationCreate(recipient_user_id=recipient_id, title="PPE loss/damage reported", message=f"{issue.item_name_snapshot} was reported {payload.report_type.value}.", notification_type=NotificationType.ppe_loss_damage_review, severity=NotificationSeverity.warning, related_entity_type=RelatedEntityType.ppe_loss_damage, related_entity_id=report.id))
    return report


def replace_ppe(db: Session, old_issue_id: int, payload: PPEReplacementCreate, *, actor_id: int) -> PPEIssue:
    old = get_issue(db, old_issue_id)
    if old.status not in ACTIVE_ISSUE_STATUSES | {PPEIssueStatus.damaged, PPEIssueStatus.lost, PPEIssueStatus.expired, PPEIssueStatus.unserviceable}:
        raise PPEValidationError("This PPE issue cannot be replaced")
    issue_payload = PPEIssueCreate(
        recipient_type=old.recipient_type,
        recipient_user_id=old.recipient_user_id,
        contractor_id=old.contractor_id,
        external_recipient_name=old.external_recipient_name,
        external_recipient_reference=old.external_recipient_reference,
        item_id=old.item_id,
        variant_id=payload.variant_id if payload.variant_id is not None else old.variant_id,
        asset_id=payload.asset_id,
        stock_location_id=payload.stock_location_id,
        quantity=old.active_quantity or old.quantity,
        issue_date=payload.issue_date,
        notes=payload.notes,
    )
    replacement = issue_ppe(db, issue_payload, actor_id=actor_id)
    replacement.replacement_for_issue_id = old.id
    replacement.replacement_reason = payload.reason
    old.status = PPEIssueStatus.replaced
    db.commit()
    db.refresh(replacement)
    _audit(db, actor_id=actor_id, action="ppe.replace", resource_type="ppe_issue", resource_id=replacement.id, details={"replaced_issue_id": old.id, "reason": payload.reason.value})
    return replacement


def create_inspection(db: Session, payload: PPEInspectionCreate, *, actor_id: int) -> PPEInspection:
    issue = get_issue(db, payload.issue_id)
    item = get_item(db, issue.item_id)
    if not item.inspection_required and not item.is_reusable:
        raise PPEValidationError("This PPE item is not configured for inspection")
    inspection_date = payload.inspection_date or _today()
    next_date = payload.next_inspection_date
    if next_date is None and item.default_inspection_interval_days:
        next_date = inspection_date + timedelta(days=item.default_inspection_interval_days)
    inspection = PPEInspection(
        issue_id=issue.id,
        inspection_date=inspection_date,
        inspector_user_id=actor_id,
        condition=payload.condition,
        passed=payload.passed,
        defects=payload.defects,
        next_inspection_date=next_date,
        notes=payload.notes,
    )
    db.add(inspection)
    issue.next_inspection_date = next_date
    if not payload.passed:
        issue.status = PPEIssueStatus.unserviceable
        if issue.asset_id:
            asset = _get(db, PPEAsset, issue.asset_id, "PPE asset")
            asset.status = PPEAssetStatus.unserviceable
            asset.condition = payload.condition
    db.commit()
    db.refresh(inspection)
    _audit(db, actor_id=actor_id, action="ppe.inspection", resource_type="ppe_inspection", resource_id=inspection.id, details={"passed": inspection.passed, "issue_id": issue.id})
    if not payload.passed and item.is_critical:
        for recipient_id in get_active_user_ids_for_roles(db, role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER]):
            create_notification_once(db, NotificationCreate(recipient_user_id=recipient_id, title="Critical PPE inspection failed", message=f"{issue.item_name_snapshot} failed inspection and is unserviceable.", notification_type=NotificationType.ppe_critical_failure, severity=NotificationSeverity.critical, related_entity_type=RelatedEntityType.ppe_inspection, related_entity_id=inspection.id))
    if payload.create_unified_action or (not payload.passed and item.is_critical and _settings(db)["create_actions_for_critical_failures"]):
        action_payload = PPEActionLinkCreate(title=f"Failed PPE inspection: {issue.item_name_snapshot}", description=payload.defects or "Critical PPE failed inspection and requires corrective action.")
        link_unified_action(db, inspection, action_payload, actor_id=actor_id, site_id=_recipient_site_id(db, issue))
    return inspection


def list_inspections(db: Session, *, skip: int = 0, limit: int = 100, site_id: Optional[int] = None, passed: Optional[bool] = None, due_before: Optional[date] = None) -> dict:
    statement: Select[tuple[PPEInspection]] = select(PPEInspection).join(PPEIssue, PPEInspection.issue_id == PPEIssue.id)
    if site_id is not None:
        statement = statement.where(PPEIssue.site_id_snapshot == site_id)
    if passed is not None:
        statement = statement.where(PPEInspection.passed == passed)
    if due_before is not None:
        statement = statement.where(PPEInspection.next_inspection_date <= due_before)
    statement = statement.order_by(PPEInspection.inspection_date.desc(), PPEInspection.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def create_requirement(db: Session, payload: PPERequirementCreate, *, actor_id: int) -> PPERequirement:
    item = get_item(db, payload.item_id)
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    if payload.site_id is not None:
        _get(db, Site, payload.site_id, "Site")
    if payload.department_id is not None:
        _get(db, Department, payload.department_id, "Department")
    if payload.hazard_id is not None:
        _get(db, Hazard, payload.hazard_id, "Hazard")
    if payload.jsa_id is not None:
        _get(db, JobSafetyAnalysis, payload.jsa_id, "JSA")
    requirement = PPERequirement(**payload.model_dump())
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    _audit(db, actor_id=actor_id, action="ppe.requirement.create", resource_type="ppe_requirement", resource_id=requirement.id)
    return requirement


def create_requirements_bulk(db: Session, payloads: list[PPERequirementCreate], *, actor_id: int) -> list[PPERequirement]:
    created: list[PPERequirement] = []
    try:
        for payload in payloads:
            item = get_item(db, payload.item_id)
            variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
            _validate_variant(item, variant)
            for value, model, label in (
                (payload.site_id, Site, "Site"),
                (payload.department_id, Department, "Department"),
                (payload.hazard_id, Hazard, "Hazard"),
                (payload.jsa_id, JobSafetyAnalysis, "JSA"),
            ):
                if value is not None:
                    _get(db, model, value, label)
            requirement = PPERequirement(**payload.model_dump())
            db.add(requirement)
            created.append(requirement)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for requirement in created:
        db.refresh(requirement)
        _audit(db, actor_id=actor_id, action="ppe.requirement.create", resource_type="ppe_requirement", resource_id=requirement.id, details={"bulk": True})
    return created


def update_requirement(db: Session, requirement_id: int, payload: PPERequirementUpdate, *, actor_id: int) -> PPERequirement:
    requirement = _get(db, PPERequirement, requirement_id, "PPE requirement")
    fields = payload.model_dump(exclude_unset=True)
    variant = _get(db, PPEVariant, fields.get("variant_id"), "PPE variant", optional=True) if "variant_id" in fields else None
    if variant is not None:
        _validate_variant(requirement.item, variant)
    for field, model, label in (
        ("site_id", Site, "Site"), ("department_id", Department, "Department"),
        ("hazard_id", Hazard, "Hazard"), ("jsa_id", JobSafetyAnalysis, "JSA"),
    ):
        if field in fields and fields[field] is not None:
            _get(db, model, fields[field], label)
    for key, value in fields.items():
        setattr(requirement, key, value)
    db.commit()
    db.refresh(requirement)
    _audit(db, actor_id=actor_id, action="ppe.requirement.update", resource_type="ppe_requirement", resource_id=requirement.id, details={"fields": sorted(fields)})
    return requirement


def review_loss_damage(db: Session, report_id: int, *, actor_id: int, notes: Optional[str] = None) -> PPELossDamageReport:
    report = _get(db, PPELossDamageReport, report_id, "PPE loss/damage report")
    report.reviewed_by_user_id = actor_id
    report.reviewed_at = _now()
    if notes:
        report.description = f"{report.description or ''}\nReview: {notes}".strip()
    db.commit()
    db.refresh(report)
    _audit(db, actor_id=actor_id, action="ppe.loss_damage.review", resource_type="ppe_loss_damage", resource_id=report.id, details={"notes_provided": bool(notes)})
    return report


def list_requirements(db: Session, *, site_id: Optional[int] = None, department_id: Optional[int] = None, role_name: Optional[str] = None, item_id: Optional[int] = None, active_only: bool = True) -> list[PPERequirement]:
    statement = select(PPERequirement)
    if site_id is not None:
        statement = statement.where(or_(PPERequirement.site_id == site_id, PPERequirement.site_id.is_(None)))
    if department_id is not None:
        statement = statement.where(or_(PPERequirement.department_id == department_id, PPERequirement.department_id.is_(None)))
    if role_name is not None:
        statement = statement.where(or_(PPERequirement.role_name == role_name, PPERequirement.role_name.is_(None)))
    if item_id is not None:
        statement = statement.where(PPERequirement.item_id == item_id)
    if active_only:
        statement = statement.where(PPERequirement.is_active.is_(True))
    return list(db.scalars(statement.order_by(PPERequirement.id.desc())).all())


def _applicable_requirements(db: Session, user: User) -> list[PPERequirement]:
    role_names = get_normalized_role_names(user)
    statement = select(PPERequirement).where(PPERequirement.is_active.is_(True))
    requirements = list(db.scalars(statement).all())
    applicable = []
    for requirement in requirements:
        if requirement.site_id is not None and requirement.site_id != user.assigned_site_id:
            continue
        if requirement.department_id is not None and requirement.department_id != user.department_id:
            continue
        if requirement.role_name is not None and requirement.role_name not in role_names:
            continue
        if requirement.job_title is not None and requirement.job_title.casefold() != (user.job_title or "").casefold():
            continue
        # Task, hazard and JSA requirements are linked for use by those
        # workflows but are not silently assigned to every employee.
        if requirement.task_activity or requirement.hazard_id or requirement.jsa_id:
            continue
        applicable.append(requirement)
    return applicable


def _issue_valid_for_requirement(db: Session, issue: PPEIssue, requirement: PPERequirement, *, today: date) -> tuple[bool, Optional[str]]:
    if issue.status not in ACTIVE_ISSUE_STATUSES or issue.active_quantity <= 0:
        return False, "not active"
    if issue.item_id != requirement.item_id:
        return False, "wrong item"
    if requirement.variant_id is not None and issue.variant_id != requirement.variant_id:
        return False, "wrong variant"
    if issue.expiry_date is not None and issue.expiry_date < today:
        return False, "expired"
    if issue.expected_replacement_date is not None and issue.expected_replacement_date < today:
        return False, "replacement overdue"
    if requirement.inspection_required and issue.next_inspection_date is not None and issue.next_inspection_date < today:
        return False, "inspection overdue"
    if requirement.certification_requirement:
        item = get_item(db, issue.item_id)
        if requirement.certification_requirement.casefold() not in (item.certification_standard or "").casefold():
            return False, "certification requirement not met"
    if issue.asset_id:
        asset = _get(db, PPEAsset, issue.asset_id, "PPE asset")
        if asset.status != PPEAssetStatus.issued:
            return False, "asset unserviceable"
        if asset.expiry_date is not None and asset.expiry_date < today:
            return False, "asset expired"
    return True, None


def employee_profile(db: Session, employee_user_id: int, *, as_of: Optional[date] = None) -> dict:
    user = _get(db, User, employee_user_id, "Employee")
    requirements = _applicable_requirements(db, user)
    history = list(db.scalars(select(PPEIssue).where(PPEIssue.recipient_user_id == user.id).order_by(PPEIssue.issue_date.desc(), PPEIssue.id.desc())).all())
    today = as_of or _today()
    rows = []
    for requirement in requirements:
        valid_quantity = 0
        failure_reason = None
        for issue in history:
            valid, reason = _issue_valid_for_requirement(db, issue, requirement, today=today)
            if valid:
                valid_quantity += issue.active_quantity
            elif issue.item_id == requirement.item_id and failure_reason is None:
                failure_reason = reason
        rows.append({
            "requirement_id": requirement.id,
            "item_id": requirement.item_id,
            "item_name": requirement.item.name,
            "requirement_level": requirement.requirement_level,
            "quantity_required": requirement.quantity,
            "quantity_valid": valid_quantity,
            "satisfied": valid_quantity >= requirement.quantity,
            "reason": None if valid_quantity >= requirement.quantity else failure_reason or "not issued",
        })
    mandatory = [row for row in rows if row["requirement_level"] == PPERequirementLevel.mandatory]
    satisfied = [row for row in mandatory if row["satisfied"]]
    if not mandatory:
        compliance = PPEComplianceStatus.not_applicable
        rate = None
    elif len(satisfied) == len(mandatory):
        compliance = PPEComplianceStatus.compliant
        rate = 100.0
    elif satisfied:
        compliance = PPEComplianceStatus.partially_compliant
        rate = round(len(satisfied) / len(mandatory) * 100, 2)
    else:
        compliance = PPEComplianceStatus.non_compliant
        rate = 0.0
    active = [issue for issue in history if issue.status in ACTIVE_ISSUE_STATUSES]
    due_horizon = today + timedelta(days=30)
    return {
        "employee_user_id": user.id,
        "compliance_status": compliance,
        "compliance_rate": rate,
        "requirements": rows,
        "issued": active,
        "missing": [row for row in mandatory if not row["satisfied"]],
        "replacement_due": [issue for issue in active if issue.expected_replacement_date is not None and today <= issue.expected_replacement_date <= due_horizon],
        "overdue_replacement": [issue for issue in active if issue.expected_replacement_date is not None and issue.expected_replacement_date < today],
        "inspection_due": [issue for issue in active if issue.next_inspection_date is not None and today <= issue.next_inspection_date <= due_horizon],
        "overdue_inspection": [issue for issue in active if issue.next_inspection_date is not None and issue.next_inspection_date < today],
        "expired": [issue for issue in history if issue.expiry_date is not None and issue.expiry_date < today],
        "damaged_lost_history": [issue for issue in history if issue.status in {PPEIssueStatus.damaged, PPEIssueStatus.lost, PPEIssueStatus.unserviceable}],
        "history": history,
    }


def create_request(db: Session, payload: PPERequestCreate, *, requester_id: int) -> PPERequest:
    requester = _get(db, User, requester_id, "Requester")
    recipient_id = payload.recipient_user_id or requester_id
    _get(db, User, recipient_id, "Recipient")
    item = get_item(db, payload.item_id)
    variant = _get(db, PPEVariant, payload.variant_id, "PPE variant", optional=True)
    _validate_variant(item, variant)
    approval_required = bool(_settings(db)["request_approval_required"])
    request = PPERequest(
        requester_user_id=requester_id,
        recipient_user_id=recipient_id,
        item_id=item.id,
        variant_id=variant.id if variant else None,
        quantity=payload.quantity,
        reason=payload.reason,
        urgency=payload.urgency,
        status=PPERequestStatus.requested if approval_required else PPERequestStatus.approved,
        approver_user_id=requester_id if not approval_required else None,
        decided_at=_now() if not approval_required else None,
        decision_notes="Auto-approved by organisation PPE configuration" if not approval_required else None,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _audit(db, actor_id=requester_id, action="ppe.request.create", resource_type="ppe_request", resource_id=request.id)
    if approval_required:
        for recipient_user_id in get_active_user_ids_for_roles(db, role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER]):
            create_notification_once(db, NotificationCreate(recipient_user_id=recipient_user_id, title="PPE request submitted", message=f"A request for {item.name} requires review.", notification_type=NotificationType.ppe_request_submitted, severity=NotificationSeverity.warning, related_entity_type=RelatedEntityType.ppe_request, related_entity_id=request.id))
    return request


def list_requests(db: Session, *, skip: int = 0, limit: int = 100, status: Optional[PPERequestStatus] = None, requester_user_id: Optional[int] = None, recipient_user_id: Optional[int] = None, site_id: Optional[int] = None) -> dict:
    statement: Select[tuple[PPERequest]] = select(PPERequest)
    if status is not None:
        statement = statement.where(PPERequest.status == status)
    if requester_user_id is not None:
        statement = statement.where(PPERequest.requester_user_id == requester_user_id)
    if recipient_user_id is not None:
        statement = statement.where(PPERequest.recipient_user_id == recipient_user_id)
    if site_id is not None:
        statement = statement.join(User, PPERequest.recipient_user_id == User.id).where(User.assigned_site_id == site_id)
    statement = statement.order_by(PPERequest.created_at.desc(), PPERequest.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def decide_request(db: Session, request_id: int, payload: PPERequestDecision, *, actor_id: int) -> PPERequest:
    request = _get(db, PPERequest, request_id, "PPE request")
    if request.status != PPERequestStatus.requested:
        raise PPEValidationError("Only pending PPE requests can be decided")
    request.status = PPERequestStatus.approved if payload.approved else PPERequestStatus.rejected
    request.approver_user_id = actor_id
    request.decided_at = _now()
    request.decision_notes = payload.decision_notes
    db.commit()
    db.refresh(request)
    _audit(db, actor_id=actor_id, action=f"ppe.request.{request.status.value}", resource_type="ppe_request", resource_id=request.id)
    create_notification_once(db, NotificationCreate(recipient_user_id=request.requester_user_id, title=f"PPE request {request.status.value}", message=f"Your PPE request was {request.status.value}.", notification_type=NotificationType.ppe_request_approved if payload.approved else NotificationType.ppe_request_rejected, severity=NotificationSeverity.info if payload.approved else NotificationSeverity.warning, related_entity_type=RelatedEntityType.ppe_request, related_entity_id=request.id))
    return request


def _recipient_site_id(db: Session, issue: PPEIssue) -> Optional[int]:
    if issue.site_id_snapshot is not None:
        return issue.site_id_snapshot
    if issue.recipient_user_id:
        user = db.get(User, issue.recipient_user_id)
        return user.assigned_site_id if user else None
    location = db.get(PPEStockLocation, issue.stock_location_id)
    return location.site_id if location else None


def link_unified_action(db: Session, entity, payload: PPEActionLinkCreate, *, actor_id: int, site_id: Optional[int] = None):
    action = create_corrective_action(
        db,
        CorrectiveActionCreate(
            title=payload.title,
            description=payload.description,
            source_type=CorrectiveActionSourceType.ppe,
            source_id=entity.id,
            source_metadata={"ppe_entity_type": entity.__class__.__name__, "ppe_entity_id": entity.id},
            priority=CorrectiveActionPriority.high,
            site_id=site_id,
            owner_user_id=payload.owner_user_id,
            current_due_date=payload.due_date,
        ),
        current_user_id=actor_id,
    )
    entity.unified_action_id = action.id
    db.commit()
    _audit(db, actor_id=actor_id, action="ppe.unified_action.link", resource_type="ppe", resource_id=entity.id, details={"action_id": action.id})
    return action


def _reminder_windows(configuration: dict, key: str) -> list[int]:
    values = configuration.get(key, [])
    return sorted({int(value) for value in values if isinstance(value, int) and value >= 0})


def _create_scheduled_notification(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    recipient_user_id: int,
    milestone_key: str,
    due_date: date,
    notification: NotificationCreate,
) -> bool:
    exists = db.scalar(select(PPEReminderDelivery.id).where(
        PPEReminderDelivery.entity_type == entity_type,
        PPEReminderDelivery.entity_id == entity_id,
        PPEReminderDelivery.recipient_user_id == recipient_user_id,
        PPEReminderDelivery.milestone_key == milestone_key,
        PPEReminderDelivery.due_date_snapshot == due_date,
    ))
    if exists is not None:
        return False
    db.add(PPEReminderDelivery(entity_type=entity_type, entity_id=entity_id, recipient_user_id=recipient_user_id, milestone_key=milestone_key, due_date_snapshot=due_date))
    create_notification(db, notification)
    return True


def generate_ppe_reminders(db: Session) -> dict:
    configuration = _settings(db)
    today = _today()
    counts = {"replacement": 0, "inspection": 0, "expiry": 0, "low_stock": 0}
    issues = list(db.scalars(select(PPEIssue).where(PPEIssue.status.in_(list(ACTIVE_ISSUE_STATUSES)), PPEIssue.recipient_user_id.is_not(None))).all())
    reminder_specs = [
        ("replacement", "replacement_reminder_windows", "expected_replacement_date", NotificationType.ppe_replacement_due, NotificationType.ppe_replacement_overdue),
        ("inspection", "inspection_reminder_windows", "next_inspection_date", NotificationType.ppe_inspection_due, NotificationType.ppe_inspection_overdue),
        ("expiry", "expiry_reminder_windows", "expiry_date", NotificationType.ppe_expiring, NotificationType.ppe_expiring),
    ]
    for issue in issues:
        for label, settings_key, field, due_type, overdue_type in reminder_specs:
            due_date = getattr(issue, field)
            if due_date is None:
                continue
            days = (due_date - today).days
            if days < 0:
                milestone = "overdue"
                notification_type = overdue_type
                severity = NotificationSeverity.critical
            else:
                window = next((window for window in _reminder_windows(configuration, settings_key) if days <= window), None)
                if window is None:
                    continue
                milestone = f"{window}_days"
                notification_type = due_type
                severity = NotificationSeverity.warning
            created = _create_scheduled_notification(
                db,
                entity_type="issue",
                entity_id=issue.id,
                recipient_user_id=issue.recipient_user_id,
                milestone_key=f"{label}:{milestone}",
                due_date=due_date,
                notification=NotificationCreate(recipient_user_id=issue.recipient_user_id, title=f"PPE {label} reminder", message=f"{issue.item_name_snapshot} {label} date is {due_date}.", notification_type=notification_type, severity=severity, related_entity_type=RelatedEntityType.ppe_issue, related_entity_id=issue.id),
            )
            counts[label] += int(created)
    if configuration.get("low_stock_notifications", True):
        inventory_records = list(db.scalars(select(PPEInventory).where(PPEInventory.quantity_available <= PPEInventory.reorder_level)).all())
        managers = get_active_user_ids_for_roles(db, role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER])
        stable_date = date(1970, 1, 1)
        for inventory in inventory_records:
            movements = list(db.scalars(select(PPEStockMovement).where(
                PPEStockMovement.inventory_id == inventory.id
            ).order_by(PPEStockMovement.id.asc())).all())
            crossing_id = movements[-1].id if movements else inventory.id
            for movement in movements:
                available_after = movement.balance_after - inventory.quantity_reserved
                available_before = available_after - movement.quantity
                if available_before > inventory.reorder_level and available_after <= inventory.reorder_level:
                    crossing_id = movement.id
            for recipient_id in managers:
                created = _create_scheduled_notification(
                    db,
                    entity_type="inventory",
                    entity_id=inventory.id,
                    recipient_user_id=recipient_id,
                    milestone_key=f"low_stock:{crossing_id}",
                    due_date=stable_date,
                    notification=NotificationCreate(recipient_user_id=recipient_id, title="PPE stock is low", message=f"{inventory.item_name} at {inventory.location_name} has {inventory.quantity_available} available.", notification_type=NotificationType.ppe_low_stock, severity=NotificationSeverity.critical if inventory.quantity_available == 0 else NotificationSeverity.warning, related_entity_type=RelatedEntityType.ppe_item, related_entity_id=inventory.item_id),
                )
                counts["low_stock"] += int(created)
    return counts


def dashboard(db: Session, *, site_id: Optional[int] = None, department_id: Optional[int] = None, as_of: Optional[date] = None) -> dict:
    today = as_of or _today()
    due_horizon = today + timedelta(days=30)
    item_statement = select(PPEItem).where(PPEItem.is_active.is_(True))
    items = list(db.scalars(item_statement).all())
    inventory_statement = select(PPEInventory).join(PPEStockLocation)
    if site_id is not None:
        inventory_statement = inventory_statement.where(PPEStockLocation.site_id == site_id)
    inventories = list(db.scalars(inventory_statement).all())
    issue_statement = select(PPEIssue)
    if site_id is not None:
        issue_statement = issue_statement.where(PPEIssue.site_id_snapshot == site_id)
    if department_id is not None:
        issue_statement = issue_statement.where(PPEIssue.department_id_snapshot == department_id)
    issues = list(db.scalars(issue_statement).all())
    active = [issue for issue in issues if issue.status in ACTIVE_ISSUE_STATUSES]
    request_statement = select(PPERequest)
    if site_id is not None or department_id is not None:
        request_statement = request_statement.join(User, PPERequest.recipient_user_id == User.id)
    if site_id is not None:
        request_statement = request_statement.where(User.assigned_site_id == site_id)
    if department_id is not None:
        request_statement = request_statement.where(User.department_id == department_id)
    requests = list(db.scalars(request_statement).all())
    user_statement = select(User).where(User.is_active.is_(True))
    if site_id is not None:
        user_statement = user_statement.where(User.assigned_site_id == site_id)
    if department_id is not None:
        user_statement = user_statement.where(User.department_id == department_id)
    profiles = [employee_profile(db, user.id, as_of=today) for user in db.scalars(user_statement).all()]
    applicable_profiles = [profile for profile in profiles if profile["compliance_status"] != PPEComplianceStatus.not_applicable]
    compliant = sum(profile["compliance_status"] == PPEComplianceStatus.compliant for profile in applicable_profiles)
    partially = sum(profile["compliance_status"] == PPEComplianceStatus.partially_compliant for profile in applicable_profiles)
    non_compliant = sum(profile["compliance_status"] == PPEComplianceStatus.non_compliant for profile in applicable_profiles)
    current_month = today.replace(day=1)
    issued_period = [issue for issue in issues if current_month <= issue.issue_date <= today]
    known_issue_costs = [issue.unit_cost_snapshot * issue.quantity for issue in issued_period if issue.unit_cost_snapshot is not None]
    missing_issue_costs = sum(issue.unit_cost_snapshot is None for issue in issued_period)
    replacements = [issue for issue in issued_period if issue.replacement_for_issue_id is not None]
    known_replacement_costs = [issue.unit_cost_snapshot * issue.quantity for issue in replacements if issue.unit_cost_snapshot is not None]
    missing_replacement_costs = sum(issue.unit_cost_snapshot is None for issue in replacements)
    by_category = {}
    for inventory in inventories:
        by_category[inventory.item.category_name] = by_category.get(inventory.item.category_name, 0) + inventory.quantity_available
    by_site: dict[str, dict] = {}
    by_department: dict[str, dict] = {}
    for profile in applicable_profiles:
        user = db.get(User, profile["employee_user_id"])
        site_key = str(user.assigned_site_id or "unassigned")
        department_key = str(user.department_id or "unassigned")
        for mapping, key in ((by_site, site_key), (by_department, department_key)):
            bucket = mapping.setdefault(key, {"employees": 0, "compliant": 0, "partially_compliant": 0, "non_compliant": 0})
            bucket["employees"] += 1
            bucket[profile["compliance_status"].value] += 1
    return {
        "total_catalogue_items": len(items),
        "low_stock_items": sum(inventory.low_stock for inventory in inventories),
        "pending_requests": sum(request.status == PPERequestStatus.requested for request in requests),
        "issues_this_month": len(issued_period),
        "replacements_due": sum(issue.expected_replacement_date is not None and today <= issue.expected_replacement_date <= due_horizon for issue in active),
        "overdue_replacements": sum(issue.expected_replacement_date is not None and issue.expected_replacement_date < today for issue in active),
        "inspections_due": sum(issue.next_inspection_date is not None and today <= issue.next_inspection_date <= due_horizon for issue in active),
        "overdue_inspections": sum(issue.next_inspection_date is not None and issue.next_inspection_date < today for issue in active),
        "expired_ppe": sum(issue.expiry_date is not None and issue.expiry_date < today for issue in active),
        "damaged_ppe": sum(issue.status == PPEIssueStatus.damaged for issue in issues),
        "lost_ppe": sum(issue.status == PPEIssueStatus.lost for issue in issues),
        "employees_requiring_ppe": len(applicable_profiles),
        "fully_compliant_employees": compliant,
        "partially_compliant_employees": partially,
        "non_compliant_employees": non_compliant,
        "compliance_rate": round(compliant / len(applicable_profiles) * 100, 2) if applicable_profiles else None,
        "issue_cost": None if missing_issue_costs else sum(known_issue_costs, Decimal("0")),
        "replacement_cost": None if missing_replacement_costs else sum(known_replacement_costs, Decimal("0")),
        "unavailable_cost_records": missing_issue_costs,
        "by_site": by_site,
        "by_department": by_department,
        "by_category": by_category,
    }


def _csv(headers: list[str], rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_ppe_csv(db: Session, report: str, *, site_id: Optional[int] = None, department_id: Optional[int] = None) -> str:
    if report == "inventory":
        records = list_inventory(db, site_id=site_id, limit=5000)["items"]
        headers = ["Item", "Variant", "Location", "On Hand", "Reserved", "Available", "Reorder Level", "Unit Cost", "Low Stock"]
        rows = [{"Item": row.item_name, "Variant": row.variant_name or "", "Location": row.location_name, "On Hand": row.quantity_on_hand, "Reserved": row.quantity_reserved, "Available": row.quantity_available, "Reorder Level": row.reorder_level, "Unit Cost": row.unit_cost if row.unit_cost is not None else "unavailable", "Low Stock": row.low_stock} for row in records]
    elif report in {"issues", "employee-register", "replacement-schedule", "inspection-schedule"}:
        records = list_issues(db, site_id=site_id, department_id=department_id, limit=5000)["items"]
        headers = ["Issue ID", "Employee User ID", "Item", "Variant", "Quantity", "Status", "Issue Date", "Replacement Date", "Inspection Date", "Expiry Date", "Unit Cost"]
        rows = [{"Issue ID": row.id, "Employee User ID": row.recipient_user_id or "", "Item": row.item_name_snapshot, "Variant": row.variant_name_snapshot or "", "Quantity": row.quantity, "Status": row.status.value, "Issue Date": row.issue_date, "Replacement Date": row.expected_replacement_date or "", "Inspection Date": row.next_inspection_date or "", "Expiry Date": row.expiry_date or "", "Unit Cost": row.unit_cost_snapshot if row.unit_cost_snapshot is not None else "unavailable"} for row in records]
    elif report == "movements":
        records = list_movements(db, site_id=site_id, limit=5000)["items"]
        headers = ["Movement ID", "Item ID", "Variant ID", "Location ID", "Type", "Quantity", "Balance After", "Reference", "Actor User ID", "Timestamp"]
        rows = [{"Movement ID": row.id, "Item ID": row.item_id, "Variant ID": row.variant_id or "", "Location ID": row.location_id, "Type": row.movement_type.value, "Quantity": row.quantity, "Balance After": row.balance_after, "Reference": row.reference or "", "Actor User ID": row.actor_user_id or "", "Timestamp": row.created_at.isoformat()} for row in records]
    elif report in {"compliance", "low-stock"}:
        if report == "low-stock":
            records = list_inventory(db, site_id=site_id, low_stock=True, limit=5000)["items"]
            headers = ["Item", "Variant", "Location", "Available", "Reorder Level", "Minimum Stock"]
            rows = [{"Item": row.item_name, "Variant": row.variant_name or "", "Location": row.location_name, "Available": row.quantity_available, "Reorder Level": row.reorder_level, "Minimum Stock": row.minimum_stock_level} for row in records]
        else:
            statement = select(User).where(User.is_active.is_(True))
            if site_id is not None:
                statement = statement.where(User.assigned_site_id == site_id)
            if department_id is not None:
                statement = statement.where(User.department_id == department_id)
            profiles = [employee_profile(db, user.id) for user in db.scalars(statement).all()]
            headers = ["Employee User ID", "Compliance Status", "Compliance Rate", "Missing Mandatory"]
            rows = [{"Employee User ID": profile["employee_user_id"], "Compliance Status": profile["compliance_status"].value, "Compliance Rate": profile["compliance_rate"] if profile["compliance_rate"] is not None else "not_applicable", "Missing Mandatory": "; ".join(row["item_name"] for row in profile["missing"])} for profile in profiles]
    else:
        raise PPEValidationError("Unsupported PPE export report")
    return _csv(headers, rows)
