from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.ppe import (
    PPEAssetStatus,
    PPEComplianceStatus,
    PPECondition,
    PPEIssueStatus,
    PPELossDamageType,
    PPEMovementType,
    PPERecipientType,
    PPEReplacementReason,
    PPERequestStatus,
    PPERequirementLevel,
    PPEReturnOutcome,
    PPEUrgency,
)
from app.schemas.common import PaginatedResponse


class PPECategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    is_active: bool = True


class PPECategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PPECategoryRead(PPECategoryCreate):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEItemBase(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=1, max_length=80)
    description: Optional[str] = None
    manufacturer: Optional[str] = Field(default=None, max_length=180)
    model: Optional[str] = Field(default=None, max_length=180)
    size_applicable: bool = False
    certification_standard: Optional[str] = Field(default=None, max_length=255)
    is_reusable: bool = False
    is_active: bool = True
    default_useful_life_days: Optional[int] = Field(default=None, ge=1)
    inspection_required: bool = False
    default_inspection_interval_days: Optional[int] = Field(default=None, ge=1)
    expiry_tracking: bool = False
    default_replacement_interval_days: Optional[int] = Field(default=None, ge=1)
    minimum_stock_level: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    requires_individual_tracking: bool = False
    is_critical: bool = False


class PPEItemCreate(PPEItemBase):
    pass


class PPEItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    size_applicable: Optional[bool] = None
    certification_standard: Optional[str] = None
    is_reusable: Optional[bool] = None
    is_active: Optional[bool] = None
    default_useful_life_days: Optional[int] = Field(default=None, ge=1)
    inspection_required: Optional[bool] = None
    default_inspection_interval_days: Optional[int] = Field(default=None, ge=1)
    expiry_tracking: Optional[bool] = None
    default_replacement_interval_days: Optional[int] = Field(default=None, ge=1)
    minimum_stock_level: Optional[int] = Field(default=None, ge=0)
    reorder_level: Optional[int] = Field(default=None, ge=0)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    requires_individual_tracking: Optional[bool] = None
    is_critical: Optional[bool] = None


class PPEVariantCreate(BaseModel):
    item_id: int
    name: str = Field(min_length=1, max_length=120)
    sku_suffix: Optional[str] = Field(default=None, max_length=60)
    size: Optional[str] = Field(default=None, max_length=60)
    colour: Optional[str] = Field(default=None, max_length=60)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    is_active: bool = True


class PPEVariantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    sku_suffix: Optional[str] = None
    size: Optional[str] = None
    colour: Optional[str] = None
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class PPEVariantRead(PPEVariantCreate):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEItemRead(PPEItemBase):
    id: int
    organisation_id: int
    category_name: str
    variants: list[PPEVariantRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEItemListRead(PaginatedResponse[PPEItemRead]):
    pass


class PPEStockLocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, max_length=60)
    site_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True


class PPEStockLocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    code: Optional[str] = None
    site_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PPEStockLocationRead(PPEStockLocationCreate):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEInventoryRead(BaseModel):
    id: int
    organisation_id: int
    item_id: int
    variant_id: Optional[int]
    location_id: int
    item_name: str
    variant_name: Optional[str]
    location_name: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    reorder_level: int
    minimum_stock_level: int
    unit_cost: Optional[Decimal]
    last_stock_movement_at: Optional[datetime]
    low_stock: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEInventoryListRead(PaginatedResponse[PPEInventoryRead]):
    pass


class PPEStockReceipt(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    location_id: int
    quantity: int = Field(gt=0)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    reason: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=180)
    opening_balance: bool = False


class PPEStockTransfer(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    source_location_id: int
    destination_location_id: int
    quantity: int = Field(gt=0)
    reason: Optional[str] = None
    reference: Optional[str] = Field(default=None, max_length=180)


class PPEStockAdjustment(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    location_id: int
    quantity_delta: int
    reason: str = Field(min_length=2)
    reference: Optional[str] = None
    movement_type: PPEMovementType = PPEMovementType.adjustment

    @model_validator(mode="after")
    def validate_adjustment(self):
        allowed = {
            PPEMovementType.adjustment,
            PPEMovementType.damaged_write_off,
            PPEMovementType.lost_write_off,
            PPEMovementType.expired_write_off,
        }
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta cannot be zero")
        if self.movement_type not in allowed:
            raise ValueError("Invalid adjustment movement type")
        if self.movement_type != PPEMovementType.adjustment and self.quantity_delta > 0:
            raise ValueError("Write-offs must reduce inventory")
        return self


class PPEStockMovementRead(BaseModel):
    id: int
    organisation_id: int
    inventory_id: int
    item_id: int
    variant_id: Optional[int]
    location_id: int
    quantity: int
    movement_type: PPEMovementType
    actor_user_id: Optional[int]
    reason: Optional[str]
    reference: Optional[str]
    related_issue_id: Optional[int]
    related_return_id: Optional[int]
    transfer_reference: Optional[str]
    balance_after: int
    unit_cost_snapshot: Optional[Decimal]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEAssetCreate(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    location_id: Optional[int] = None
    serial_number: Optional[str] = Field(default=None, max_length=180)
    asset_tag: str = Field(min_length=1, max_length=120)
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    certification_reference: Optional[str] = None
    batch_lot: Optional[str] = None
    status: PPEAssetStatus = PPEAssetStatus.available
    condition: PPECondition = PPECondition.new


class PPEAssetRead(PPEAssetCreate):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEIssueCreate(BaseModel):
    recipient_type: PPERecipientType = PPERecipientType.employee
    recipient_user_id: Optional[int] = None
    contractor_id: Optional[int] = None
    external_recipient_name: Optional[str] = None
    external_recipient_reference: Optional[str] = None
    item_id: int
    variant_id: Optional[int] = None
    asset_id: Optional[int] = None
    stock_location_id: int
    quantity: int = Field(gt=0)
    issue_date: Optional[date] = None
    expected_replacement_date: Optional[date] = None
    expiry_date: Optional[date] = None
    condition_at_issue: PPECondition = PPECondition.new
    acknowledgement_required: Optional[bool] = None
    notes: Optional[str] = None
    request_id: Optional[int] = None
    authorised_negative_override: bool = False

    @model_validator(mode="after")
    def validate_recipient(self):
        if self.recipient_type == PPERecipientType.employee and self.recipient_user_id is None:
            raise ValueError("recipient_user_id is required for an employee issue")
        if self.recipient_type == PPERecipientType.contractor and self.contractor_id is None:
            raise ValueError("contractor_id is required for a contractor issue")
        if self.recipient_type in {PPERecipientType.temporary, PPERecipientType.visitor} and not self.external_recipient_name:
            raise ValueError("external_recipient_name is required")
        return self


class PPEIssueRead(BaseModel):
    id: int
    organisation_id: int
    recipient_type: PPERecipientType
    recipient_user_id: Optional[int]
    contractor_id: Optional[int]
    external_recipient_name: Optional[str]
    external_recipient_reference: Optional[str]
    recipient_name_snapshot: str
    site_id_snapshot: Optional[int]
    department_id_snapshot: Optional[int]
    item_id: int
    variant_id: Optional[int]
    asset_id: Optional[int]
    stock_location_id: int
    quantity: int
    returned_quantity: int
    active_quantity: int
    issue_date: date
    expected_replacement_date: Optional[date]
    expiry_date: Optional[date]
    next_inspection_date: Optional[date]
    condition_at_issue: PPECondition
    status: PPEIssueStatus
    issued_by_user_id: Optional[int]
    acknowledgement_required: bool
    acknowledged_at: Optional[datetime]
    acknowledgement_method: Optional[str]
    acknowledgement_reference: Optional[str]
    notes: Optional[str]
    unit_cost_snapshot: Optional[Decimal]
    item_name_snapshot: str
    item_code_snapshot: str
    variant_name_snapshot: Optional[str]
    stock_location_name_snapshot: str
    replacement_for_issue_id: Optional[int]
    replacement_reason: Optional[PPEReplacementReason]
    request_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEIssueListRead(PaginatedResponse[PPEIssueRead]):
    pass


class PPEAcknowledgementCreate(BaseModel):
    method: str = Field(min_length=2, max_length=80)
    reference: Optional[str] = Field(default=None, max_length=255)


class PPEReturnCreate(BaseModel):
    quantity: int = Field(gt=0)
    condition: PPECondition
    outcome: PPEReturnOutcome
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None


class PPEReturnRead(PPEReturnCreate):
    id: int
    organisation_id: int
    issue_id: int
    received_by_user_id: Optional[int]
    returned_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPELossDamageCreate(BaseModel):
    report_type: PPELossDamageType
    event_date: date
    reason: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None


class PPELossDamageRead(PPELossDamageCreate):
    id: int
    organisation_id: int
    issue_id: int
    reported_by_user_id: Optional[int]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    unified_action_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEReplacementCreate(BaseModel):
    reason: PPEReplacementReason
    stock_location_id: int
    variant_id: Optional[int] = None
    asset_id: Optional[int] = None
    issue_date: Optional[date] = None
    notes: Optional[str] = None


class PPEInspectionCreate(BaseModel):
    issue_id: int
    inspection_date: Optional[date] = None
    condition: PPECondition
    passed: bool
    defects: Optional[str] = None
    next_inspection_date: Optional[date] = None
    notes: Optional[str] = None
    create_unified_action: bool = False


class PPEInspectionRead(BaseModel):
    id: int
    organisation_id: int
    issue_id: int
    inspection_date: date
    inspector_user_id: Optional[int]
    condition: PPECondition
    passed: bool
    defects: Optional[str]
    next_inspection_date: Optional[date]
    notes: Optional[str]
    unified_action_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPERequirementCreate(BaseModel):
    item_id: int
    variant_id: Optional[int] = None
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    task_activity: Optional[str] = None
    hazard_id: Optional[int] = None
    jsa_id: Optional[int] = None
    requirement_level: PPERequirementLevel = PPERequirementLevel.mandatory
    quantity: int = Field(default=1, gt=0)
    replacement_interval_days: Optional[int] = Field(default=None, ge=1)
    inspection_required: bool = False
    certification_requirement: Optional[str] = None
    is_critical: bool = False
    is_active: bool = True


class PPERequirementRead(PPERequirementCreate):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPERequirementUpdate(BaseModel):
    variant_id: Optional[int] = None
    role_name: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    site_id: Optional[int] = None
    task_activity: Optional[str] = None
    hazard_id: Optional[int] = None
    jsa_id: Optional[int] = None
    requirement_level: Optional[PPERequirementLevel] = None
    quantity: Optional[int] = Field(default=None, gt=0)
    replacement_interval_days: Optional[int] = Field(default=None, ge=1)
    inspection_required: Optional[bool] = None
    certification_requirement: Optional[str] = None
    is_critical: Optional[bool] = None
    is_active: Optional[bool] = None


class PPELossDamageReview(BaseModel):
    review_notes: Optional[str] = None


class PPERequestCreate(BaseModel):
    recipient_user_id: Optional[int] = None
    item_id: int
    variant_id: Optional[int] = None
    quantity: int = Field(default=1, gt=0)
    reason: str = Field(min_length=2)
    urgency: PPEUrgency = PPEUrgency.routine


class PPERequestDecision(BaseModel):
    approved: bool
    decision_notes: Optional[str] = None


class PPERequestRead(BaseModel):
    id: int
    organisation_id: int
    requester_user_id: int
    recipient_user_id: int
    item_id: int
    variant_id: Optional[int]
    quantity: int
    reason: str
    urgency: PPEUrgency
    status: PPERequestStatus
    approver_user_id: Optional[int]
    decided_at: Optional[datetime]
    decision_notes: Optional[str]
    issue_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PPEComplianceRequirementRead(BaseModel):
    requirement_id: int
    item_id: int
    item_name: str
    requirement_level: PPERequirementLevel
    quantity_required: int
    quantity_valid: int
    satisfied: bool
    reason: Optional[str] = None


class PPEEmployeeProfileRead(BaseModel):
    employee_user_id: int
    compliance_status: PPEComplianceStatus
    compliance_rate: Optional[float]
    requirements: list[PPEComplianceRequirementRead]
    issued: list[PPEIssueRead]
    missing: list[PPEComplianceRequirementRead]
    replacement_due: list[PPEIssueRead]
    overdue_replacement: list[PPEIssueRead]
    inspection_due: list[PPEIssueRead]
    overdue_inspection: list[PPEIssueRead]
    expired: list[PPEIssueRead]
    damaged_lost_history: list[PPEIssueRead]
    history: list[PPEIssueRead]


class PPEDashboardRead(BaseModel):
    total_catalogue_items: int
    low_stock_items: int
    pending_requests: int
    issues_this_month: int
    replacements_due: int
    overdue_replacements: int
    inspections_due: int
    overdue_inspections: int
    expired_ppe: int
    damaged_ppe: int
    lost_ppe: int
    employees_requiring_ppe: int
    fully_compliant_employees: int
    partially_compliant_employees: int
    non_compliant_employees: int
    compliance_rate: Optional[float]
    issue_cost: Optional[Decimal]
    replacement_cost: Optional[Decimal]
    unavailable_cost_records: int
    by_site: dict[str, dict]
    by_department: dict[str, dict]
    by_category: dict[str, int]


class PPEActionLinkCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    owner_user_id: Optional[int] = None
    due_date: Optional[date] = None
