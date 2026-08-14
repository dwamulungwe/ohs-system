from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class PPEMovementType(str, enum.Enum):
    opening_balance = "opening_balance"
    purchase_receipt = "purchase_receipt"
    issue = "issue"
    return_reusable = "return"
    transfer_out = "transfer_out"
    transfer_in = "transfer_in"
    adjustment = "adjustment"
    damaged_write_off = "damaged_write_off"
    lost_write_off = "lost_write_off"
    expired_write_off = "expired_write_off"


class PPERecipientType(str, enum.Enum):
    employee = "employee"
    contractor = "contractor"
    temporary = "temporary"
    visitor = "visitor"


class PPECondition(str, enum.Enum):
    new = "new"
    good = "good"
    serviceable = "serviceable"
    worn = "worn"
    damaged = "damaged"
    expired = "expired"
    contaminated = "contaminated"
    unserviceable = "unserviceable"


class PPEIssueStatus(str, enum.Enum):
    issued = "issued"
    partially_returned = "partially_returned"
    returned = "returned"
    damaged = "damaged"
    lost = "lost"
    replaced = "replaced"
    expired = "expired"
    unserviceable = "unserviceable"


class PPERequestStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    issued = "issued"


class PPEUrgency(str, enum.Enum):
    routine = "routine"
    urgent = "urgent"
    critical = "critical"


class PPERequirementLevel(str, enum.Enum):
    mandatory = "mandatory"
    recommended = "recommended"


class PPEComplianceStatus(str, enum.Enum):
    compliant = "compliant"
    partially_compliant = "partially_compliant"
    non_compliant = "non_compliant"
    not_applicable = "not_applicable"


class PPEAssetStatus(str, enum.Enum):
    available = "available"
    issued = "issued"
    unserviceable = "unserviceable"
    retired = "retired"
    lost = "lost"


class PPEReturnOutcome(str, enum.Enum):
    reusable = "reusable"
    damaged = "damaged"
    expired = "expired"
    contaminated = "contaminated"
    write_off = "write_off"


class PPELossDamageType(str, enum.Enum):
    lost = "lost"
    damaged = "damaged"
    unusable = "unusable"


class PPEReplacementReason(str, enum.Enum):
    scheduled_replacement = "scheduled_replacement"
    expired = "expired"
    damaged = "damaged"
    lost = "lost"
    worn_out = "worn_out"
    incorrect_size = "incorrect_size"
    role_change = "role_change"
    contamination = "contamination"
    other = "other"


class PPECategory(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_categories"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_ppe_categories_org_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PPEItem(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_items"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_ppe_items_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("ppe_categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    size_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certification_standard: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_reusable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_useful_life_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspection_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_inspection_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expiry_tracking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_replacement_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minimum_stock_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    requires_individual_tracking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped[PPECategory] = relationship(lazy="selectin")
    variants: Mapped[list["PPEVariant"]] = relationship(back_populates="item", cascade="all, delete-orphan", lazy="selectin")

    @property
    def category_name(self) -> str:
        return self.category.name


class PPEVariant(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_variants"
    __table_args__ = (
        UniqueConstraint("organisation_id", "item_id", "name", name="uq_ppe_variants_org_item_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sku_suffix: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(60), index=True, nullable=True)
    colour: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    item: Mapped[PPEItem] = relationship(back_populates="variants", lazy="selectin")


class PPEStockLocation(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_stock_locations"
    __table_args__ = (UniqueConstraint("organisation_id", "name", "site_id", name="uq_ppe_locations_org_name_site"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), index=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PPEInventory(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_inventory"
    __table_args__ = (
        UniqueConstraint("organisation_id", "item_id", "variant_id", "location_id", name="uq_ppe_inventory_scope"),
        CheckConstraint("quantity_reserved >= 0", name="ck_ppe_inventory_reserved_nonnegative"),
        CheckConstraint("quantity_available = quantity_on_hand - quantity_reserved", name="ck_ppe_inventory_quantity_balance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="RESTRICT"), index=True, nullable=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("ppe_stock_locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_stock_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    last_stock_movement_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    item: Mapped[PPEItem] = relationship(lazy="selectin")
    variant: Mapped[Optional[PPEVariant]] = relationship(lazy="selectin")
    location: Mapped[PPEStockLocation] = relationship(lazy="selectin")

    @property
    def low_stock(self) -> bool:
        return self.quantity_available <= self.reorder_level

    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def variant_name(self) -> Optional[str]:
        return self.variant.name if self.variant else None

    @property
    def location_name(self) -> str:
        return self.location.name


class PPEStockMovement(OrganisationOwnedMixin, Base):
    __tablename__ = "ppe_stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("ppe_inventory.id", ondelete="RESTRICT"), index=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="RESTRICT"), index=True, nullable=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("ppe_stock_locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[PPEMovementType] = mapped_column(Enum(PPEMovementType), index=True, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    related_issue_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    related_return_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    transfer_reference: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)


class PPEAsset(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_assets"
    __table_args__ = (
        UniqueConstraint("organisation_id", "asset_tag", name="uq_ppe_assets_org_tag"),
        UniqueConstraint("organisation_id", "serial_number", name="uq_ppe_assets_org_serial"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="RESTRICT"), index=True, nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_stock_locations.id", ondelete="SET NULL"), index=True, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    asset_tag: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    manufacture_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    certification_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    batch_lot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[PPEAssetStatus] = mapped_column(Enum(PPEAssetStatus), default=PPEAssetStatus.available, index=True, nullable=False)
    condition: Mapped[PPECondition] = mapped_column(Enum(PPECondition), default=PPECondition.new, nullable=False)


class PPEIssue(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_issues"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_ppe_issues_quantity_positive"),
        CheckConstraint("returned_quantity >= 0 AND returned_quantity <= quantity", name="ck_ppe_issues_returned_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recipient_type: Mapped[PPERecipientType] = mapped_column(Enum(PPERecipientType), index=True, nullable=False)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id", ondelete="SET NULL"), index=True, nullable=True)
    external_recipient_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    external_recipient_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    recipient_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    site_id_snapshot: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    department_id_snapshot: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="RESTRICT"), index=True, nullable=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_assets.id", ondelete="RESTRICT"), index=True, nullable=True)
    stock_location_id: Mapped[int] = mapped_column(ForeignKey("ppe_stock_locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    returned_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    expected_replacement_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    next_inspection_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    condition_at_issue: Mapped[PPECondition] = mapped_column(Enum(PPECondition), default=PPECondition.new, nullable=False)
    status: Mapped[PPEIssueStatus] = mapped_column(Enum(PPEIssueStatus), default=PPEIssueStatus.issued, index=True, nullable=False)
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    acknowledgement_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledgement_method: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    acknowledgement_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_cost_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    item_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    item_code_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    variant_name_snapshot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    stock_location_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    replacement_for_issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_issues.id", ondelete="SET NULL"), index=True, nullable=True)
    replacement_reason: Mapped[Optional[PPEReplacementReason]] = mapped_column(Enum(PPEReplacementReason), nullable=True)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)

    item: Mapped[PPEItem] = relationship(lazy="selectin")
    variant: Mapped[Optional[PPEVariant]] = relationship(lazy="selectin")
    asset: Mapped[Optional[PPEAsset]] = relationship(lazy="selectin")

    @property
    def active_quantity(self) -> int:
        if self.status in {PPEIssueStatus.returned, PPEIssueStatus.damaged, PPEIssueStatus.lost, PPEIssueStatus.replaced, PPEIssueStatus.expired, PPEIssueStatus.unserviceable}:
            return 0
        return self.quantity - self.returned_quantity


class PPEReturn(OrganisationOwnedMixin, Base):
    __tablename__ = "ppe_returns"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_ppe_returns_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("ppe_issues.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    condition: Mapped[PPECondition] = mapped_column(Enum(PPECondition), nullable=False)
    outcome: Mapped[PPEReturnOutcome] = mapped_column(Enum(PPEReturnOutcome), nullable=False)
    received_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PPELossDamageReport(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_loss_damage_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("ppe_issues.id", ondelete="RESTRICT"), index=True, nullable=False)
    report_type: Mapped[PPELossDamageType] = mapped_column(Enum(PPELossDamageType), index=True, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    unified_action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("corrective_actions.id", ondelete="SET NULL"), index=True, nullable=True)


class PPEInspection(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_inspections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("ppe_issues.id", ondelete="RESTRICT"), index=True, nullable=False)
    inspection_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    inspector_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    condition: Mapped[PPECondition] = mapped_column(Enum(PPECondition), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    defects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_inspection_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unified_action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("corrective_actions.id", ondelete="SET NULL"), index=True, nullable=True)


class PPERequirement(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="SET NULL"), index=True, nullable=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=True)
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=True)
    task_activity: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    hazard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hazards.id", ondelete="SET NULL"), index=True, nullable=True)
    jsa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_safety_analyses.id", ondelete="SET NULL"), index=True, nullable=True)
    requirement_level: Mapped[PPERequirementLevel] = mapped_column(Enum(PPERequirementLevel), default=PPERequirementLevel.mandatory, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    replacement_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inspection_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certification_requirement: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    item: Mapped[PPEItem] = relationship(lazy="selectin")


class PPERequest(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "ppe_requests"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_ppe_requests_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.id", ondelete="RESTRICT"), index=True, nullable=False)
    variant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_variants.id", ondelete="SET NULL"), index=True, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[PPEUrgency] = mapped_column(Enum(PPEUrgency), default=PPEUrgency.routine, index=True, nullable=False)
    status: Mapped[PPERequestStatus] = mapped_column(Enum(PPERequestStatus), default=PPERequestStatus.requested, index=True, nullable=False)
    approver_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ppe_issues.id", ondelete="SET NULL"), index=True, nullable=True)


class PPEReminderDelivery(OrganisationOwnedMixin, Base):
    __tablename__ = "ppe_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint("organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_ppe_reminder_delivery"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    milestone_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    due_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
