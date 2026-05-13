from __future__ import annotations

from typing import Optional
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.asset_register import AssetConditionStatus, AssetRegisterItem, AssetType
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.site import Site
from app.models.user import User
from app.schemas.asset_register import AssetRegisterCreate, AssetRegisterUpdate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once, get_active_user_ids_for_roles
from app.services.query_utils import paginate
from app.services.rbac import ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER


class AssetRegisterServiceError(Exception):
    pass


class AssetRegisterNotFoundError(AssetRegisterServiceError):
    pass


class AssetRegisterValidationError(AssetRegisterServiceError):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise AssetRegisterValidationError("Site not found")


def _ensure_user_exists(db: Session, user_id: Optional[int]) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise AssetRegisterValidationError("Referenced user not found")


def _ensure_unique_asset_tag(
    db: Session,
    *,
    asset_tag: str,
    exclude_id: Optional[int] = None,
) -> None:
    statement = select(AssetRegisterItem).where(AssetRegisterItem.asset_tag == asset_tag)
    if exclude_id is not None:
        statement = statement.where(AssetRegisterItem.id != exclude_id)
    if db.scalar(statement) is not None:
        raise AssetRegisterValidationError("Asset tag already exists")


def _reminder_recipients(db: Session, *, site_id: int, assigned_to_user_id: Optional[int]) -> list[int]:
    recipient_ids = []
    if assigned_to_user_id is not None:
        recipient_ids.append(assigned_to_user_id)
    recipient_ids.extend(
        get_active_user_ids_for_roles(
            db,
            role_names=[ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER],
            site_id=site_id,
        )
    )
    seen = set()
    unique = []
    for item in recipient_ids:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _notify_asset_conditions(db: Session, asset: AssetRegisterItem) -> None:
    recipients = _reminder_recipients(
        db,
        site_id=asset.site_id,
        assigned_to_user_id=asset.assigned_to_user_id,
    )
    today = _today()
    due_soon_by = today + timedelta(days=7)

    for recipient_user_id in recipients:
        if asset.next_inspection_date is not None:
            if asset.next_inspection_date < today:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Asset inspection overdue",
                        message=f"Inspection for asset '{asset.asset_name}' is overdue.",
                        notification_type=NotificationType.asset_inspection_overdue,
                        severity=NotificationSeverity.critical,
                        related_entity_type=RelatedEntityType.asset_register,
                        related_entity_id=asset.id,
                    ),
                )
            elif asset.next_inspection_date <= due_soon_by:
                create_notification_once(
                    db,
                    NotificationCreate(
                        recipient_user_id=recipient_user_id,
                        title="Asset inspection due soon",
                        message=f"Inspection for asset '{asset.asset_name}' is due by {asset.next_inspection_date}.",
                        notification_type=NotificationType.asset_inspection_due_soon,
                        severity=NotificationSeverity.warning,
                        related_entity_type=RelatedEntityType.asset_register,
                        related_entity_id=asset.id,
                    ),
                )

        if asset.condition_status == AssetConditionStatus.defective:
            create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=recipient_user_id,
                    title="Defective asset requires action",
                    message=f"Asset '{asset.asset_name}' is marked defective.",
                    notification_type=NotificationType.asset_defective,
                    severity=NotificationSeverity.critical,
                    related_entity_type=RelatedEntityType.asset_register,
                    related_entity_id=asset.id,
                ),
            )


def list_assets(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    asset_type: Optional[AssetType] = None,
    condition_status: Optional[AssetConditionStatus] = None,
    assigned_to_user_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[AssetRegisterItem]] = select(AssetRegisterItem)
    if site_id is not None:
        statement = statement.where(AssetRegisterItem.site_id == site_id)
    if asset_type is not None:
        statement = statement.where(AssetRegisterItem.asset_type == asset_type)
    if condition_status is not None:
        statement = statement.where(AssetRegisterItem.condition_status == condition_status)
    if assigned_to_user_id is not None:
        statement = statement.where(AssetRegisterItem.assigned_to_user_id == assigned_to_user_id)
    statement = statement.order_by(AssetRegisterItem.asset_name.asc(), AssetRegisterItem.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_asset(db: Session, asset_id: int) -> AssetRegisterItem:
    asset = db.get(AssetRegisterItem, asset_id)
    if asset is None:
        raise AssetRegisterNotFoundError("Asset register item not found")
    return asset


def create_asset(db: Session, asset_in: AssetRegisterCreate, *, actor_id: Optional[int]) -> AssetRegisterItem:
    data = asset_in.model_dump()
    _ensure_site_exists(db, data["site_id"])
    _ensure_user_exists(db, data.get("assigned_to_user_id"))
    _ensure_unique_asset_tag(db, asset_tag=data["asset_tag"])
    asset = AssetRegisterItem(**data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="asset_register.create",
        resource_type="asset_register",
        resource_id=asset.id,
        details={"condition_status": asset.condition_status.value},
    )
    _notify_asset_conditions(db, asset)
    return asset


def update_asset(
    db: Session,
    asset: AssetRegisterItem,
    asset_in: AssetRegisterUpdate,
    *,
    actor_id: Optional[int],
) -> AssetRegisterItem:
    update_data = asset_in.model_dump(exclude_unset=True)
    if "site_id" in update_data and update_data["site_id"] is not None:
        _ensure_site_exists(db, update_data["site_id"])
    _ensure_user_exists(db, update_data.get("assigned_to_user_id"))
    if "asset_tag" in update_data and update_data["asset_tag"] is not None:
        _ensure_unique_asset_tag(db, asset_tag=update_data["asset_tag"], exclude_id=asset.id)
    for field, value in update_data.items():
        setattr(asset, field, value)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="asset_register.update",
        resource_type="asset_register",
        resource_id=asset.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    _notify_asset_conditions(db, asset)
    return asset
