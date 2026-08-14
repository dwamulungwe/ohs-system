"""implement enterprise PPE management

Revision ID: 20260814_0020
Revises: 20260814_0019
Create Date: 2026-08-14
"""

from datetime import date

from alembic import op
import sqlalchemy as sa


revision = "20260814_0020"
down_revision = "20260814_0019"
branch_labels = None
depends_on = None


CATEGORY_NAMES = (
    "Head Protection",
    "Eye Protection",
    "Hearing Protection",
    "Respiratory Protection",
    "Hand Protection",
    "Foot Protection",
    "Protective Clothing",
    "Fall Protection",
    "High Visibility",
    "Face Protection",
)

PPE_KPIS = (
    ("ppe_employees_requiring", "Employees Requiring PPE", "count", "informational"),
    ("ppe_employees_compliant", "Fully PPE Compliant Employees", "count", "higher_is_better"),
    ("ppe_employees_partially_compliant", "Partially PPE Compliant Employees", "count", "lower_is_better"),
    ("ppe_employees_non_compliant", "Non-Compliant Employees", "count", "lower_is_better"),
    ("ppe_compliance_rate", "PPE Compliance Rate", "percent", "higher_is_better"),
    ("ppe_replacement_due", "PPE Due Replacement", "count", "lower_is_better"),
    ("ppe_replacement_overdue", "PPE Overdue Replacement", "count", "lower_is_better"),
    ("ppe_expiring_30", "PPE Expiring in 30 Days", "count", "lower_is_better"),
    ("ppe_expiring_60", "PPE Expiring in 60 Days", "count", "lower_is_better"),
    ("ppe_expiring_90", "PPE Expiring in 90 Days", "count", "lower_is_better"),
    ("ppe_inspections_overdue", "PPE Inspections Overdue", "count", "lower_is_better"),
    ("ppe_requests_outstanding", "PPE Requests Outstanding", "count", "lower_is_better"),
    ("ppe_low_stock_items", "Low-Stock PPE Items", "count", "lower_is_better"),
    ("ppe_damaged", "Damaged PPE", "count", "lower_is_better"),
    ("ppe_lost", "Lost PPE", "count", "lower_is_better"),
    ("ppe_issued", "PPE Issued During Period", "count", "informational"),
    ("ppe_issue_cost", "PPE Issue Cost", "currency", "informational"),
    ("ppe_replacement_cost", "PPE Replacement Cost", "currency", "informational"),
)


def _enum(name: str, *values: str):
    return sa.Enum(*values, name=name)


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column], unique=False)


def _owned_columns(*columns):
    return [
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        *columns,
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
    ]


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _extend_shared_enums(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in ("ppe_item", "ppe_issue", "ppe_inspection", "ppe_loss_damage"):
        op.execute(f"ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS '{value}'")
    for value in (
        "ppe_request_submitted", "ppe_request_approved", "ppe_request_rejected", "ppe_issued",
        "ppe_replacement_due", "ppe_replacement_overdue", "ppe_inspection_due",
        "ppe_inspection_overdue", "ppe_expiring", "ppe_low_stock", "ppe_critical_failure",
        "ppe_loss_damage_review",
    ):
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("ppe_item", "ppe_issue", "ppe_request", "ppe_inspection", "ppe_loss_damage"):
        op.execute(f"ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("ALTER TYPE correctiveactionsourcetype ADD VALUE IF NOT EXISTS 'ppe'")


def upgrade() -> None:
    bind = op.get_bind()
    _extend_shared_enums(bind)

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.add_column(sa.Column("ppe_configuration", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("job_title", sa.String(180), nullable=True))
        batch_op.create_index(op.f("ix_users_job_title"), ["job_title"], unique=False)

    now = bind.execute(sa.select(sa.func.current_timestamp())).scalar_one()
    organisations = sa.table("organisations", sa.column("id", sa.Integer))
    features = sa.table(
        "organisation_features",
        sa.column("organisation_id", sa.Integer), sa.column("key", sa.String),
        sa.column("is_enabled", sa.Boolean), sa.column("configuration", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    existing = set(bind.execute(sa.select(features.c.organisation_id).where(features.c.key == "ppe")).scalars().all())
    for organisation_id in bind.execute(sa.select(organisations.c.id)).scalars().all():
        if organisation_id not in existing:
            bind.execute(features.insert().values(organisation_id=organisation_id, key="ppe", is_enabled=True, configuration={}, created_at=now, updated_at=now))

    op.create_table(
        "ppe_categories",
        *_owned_columns(
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("code", sa.String(50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "name", name="uq_ppe_categories_org_name"),
    )
    _indexes("ppe_categories", "id", "organisation_id", "name")

    categories = sa.table(
        "ppe_categories",
        sa.column("organisation_id", sa.Integer), sa.column("name", sa.String), sa.column("code", sa.String),
        sa.column("description", sa.Text), sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for organisation_id in bind.execute(sa.select(organisations.c.id)).scalars().all():
        bind.execute(categories.insert(), [{"organisation_id": organisation_id, "name": name, "code": None, "description": None, "is_active": True, "created_at": now, "updated_at": now} for name in CATEGORY_NAMES])

    op.create_table(
        "ppe_items",
        *_owned_columns(
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(180), nullable=False), sa.Column("code", sa.String(80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("manufacturer", sa.String(180), nullable=True),
            sa.Column("model", sa.String(180), nullable=True), sa.Column("size_applicable", sa.Boolean(), nullable=False),
            sa.Column("certification_standard", sa.String(255), nullable=True), sa.Column("is_reusable", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("default_useful_life_days", sa.Integer(), nullable=True),
            sa.Column("inspection_required", sa.Boolean(), nullable=False), sa.Column("default_inspection_interval_days", sa.Integer(), nullable=True),
            sa.Column("expiry_tracking", sa.Boolean(), nullable=False), sa.Column("default_replacement_interval_days", sa.Integer(), nullable=True),
            sa.Column("minimum_stock_level", sa.Integer(), nullable=False), sa.Column("reorder_level", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True), sa.Column("requires_individual_tracking", sa.Boolean(), nullable=False),
            sa.Column("is_critical", sa.Boolean(), nullable=False), *_timestamps(),
            sa.ForeignKeyConstraint(["category_id"], ["ppe_categories.id"], ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint("organisation_id", "code", name="uq_ppe_items_org_code"),
    )
    _indexes("ppe_items", "id", "organisation_id", "category_id", "name", "code")

    op.create_table(
        "ppe_variants",
        *_owned_columns(
            sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
            sa.Column("sku_suffix", sa.String(60), nullable=True), sa.Column("size", sa.String(60), nullable=True),
            sa.Column("colour", sa.String(60), nullable=True), sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False), *_timestamps(),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="CASCADE"),
        ),
        sa.UniqueConstraint("organisation_id", "item_id", "name", name="uq_ppe_variants_org_item_name"),
    )
    _indexes("ppe_variants", "id", "organisation_id", "item_id", "size")

    op.create_table(
        "ppe_stock_locations",
        *_owned_columns(
            sa.Column("name", sa.String(180), nullable=False), sa.Column("code", sa.String(60), nullable=True),
            sa.Column("site_id", sa.Integer(), nullable=True), sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False), *_timestamps(),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("organisation_id", "name", "site_id", name="uq_ppe_locations_org_name_site"),
    )
    _indexes("ppe_stock_locations", "id", "organisation_id", "name", "site_id")

    op.create_table(
        "ppe_inventory",
        *_owned_columns(
            sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("variant_id", sa.Integer(), nullable=True),
            sa.Column("location_id", sa.Integer(), nullable=False), sa.Column("quantity_on_hand", sa.Integer(), nullable=False),
            sa.Column("quantity_reserved", sa.Integer(), nullable=False), sa.Column("quantity_available", sa.Integer(), nullable=False),
            sa.Column("reorder_level", sa.Integer(), nullable=False), sa.Column("minimum_stock_level", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True), sa.Column("last_stock_movement_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["location_id"], ["ppe_stock_locations.id"], ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint("organisation_id", "item_id", "variant_id", "location_id", name="uq_ppe_inventory_scope"),
        sa.CheckConstraint("quantity_reserved >= 0", name="ck_ppe_inventory_reserved_nonnegative"),
        sa.CheckConstraint("quantity_available = quantity_on_hand - quantity_reserved", name="ck_ppe_inventory_quantity_balance"),
    )
    _indexes("ppe_inventory", "id", "organisation_id", "item_id", "variant_id", "location_id")

    movement_type = _enum("ppemovementtype", "opening_balance", "purchase_receipt", "issue", "return", "transfer_out", "transfer_in", "adjustment", "damaged_write_off", "lost_write_off", "expired_write_off")
    op.create_table(
        "ppe_stock_movements",
        *_owned_columns(
            sa.Column("inventory_id", sa.Integer(), nullable=False), sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("variant_id", sa.Integer(), nullable=True), sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("movement_type", movement_type, nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True), sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("reference", sa.String(180), nullable=True), sa.Column("related_issue_id", sa.Integer(), nullable=True),
            sa.Column("related_return_id", sa.Integer(), nullable=True), sa.Column("transfer_reference", sa.String(80), nullable=True),
            sa.Column("balance_after", sa.Integer(), nullable=False), sa.Column("unit_cost_snapshot", sa.Numeric(14, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["inventory_id"], ["ppe_inventory.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["location_id"], ["ppe_stock_locations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("ppe_stock_movements", "id", "organisation_id", "inventory_id", "item_id", "variant_id", "location_id", "movement_type", "actor_user_id", "reference", "related_issue_id", "related_return_id", "transfer_reference", "created_at")

    asset_status = _enum("ppeassetstatus", "available", "issued", "unserviceable", "retired", "lost")
    condition = _enum("ppecondition", "new", "good", "serviceable", "worn", "damaged", "expired", "contaminated", "unserviceable")
    op.create_table(
        "ppe_assets",
        *_owned_columns(
            sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("variant_id", sa.Integer(), nullable=True),
            sa.Column("location_id", sa.Integer(), nullable=True), sa.Column("serial_number", sa.String(180), nullable=True),
            sa.Column("asset_tag", sa.String(120), nullable=False), sa.Column("manufacture_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True), sa.Column("certification_reference", sa.String(255), nullable=True),
            sa.Column("batch_lot", sa.String(120), nullable=True), sa.Column("status", asset_status, nullable=False),
            sa.Column("condition", condition, nullable=False), *_timestamps(),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["location_id"], ["ppe_stock_locations.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("organisation_id", "asset_tag", name="uq_ppe_assets_org_tag"),
        sa.UniqueConstraint("organisation_id", "serial_number", name="uq_ppe_assets_org_serial"),
    )
    _indexes("ppe_assets", "id", "organisation_id", "item_id", "variant_id", "location_id", "serial_number", "asset_tag", "expiry_date", "status")

    recipient_type = _enum("pperecipienttype", "employee", "contractor", "temporary", "visitor")
    issue_status = _enum("ppeissuestatus", "issued", "partially_returned", "returned", "damaged", "lost", "replaced", "expired", "unserviceable")
    replacement_reason = _enum("ppereplacementreason", "scheduled_replacement", "expired", "damaged", "lost", "worn_out", "incorrect_size", "role_change", "contamination", "other")
    op.create_table(
        "ppe_issues",
        *_owned_columns(
            sa.Column("recipient_type", recipient_type, nullable=False), sa.Column("recipient_user_id", sa.Integer(), nullable=True),
            sa.Column("contractor_id", sa.Integer(), nullable=True), sa.Column("external_recipient_name", sa.String(180), nullable=True),
            sa.Column("external_recipient_reference", sa.String(120), nullable=True), sa.Column("recipient_name_snapshot", sa.String(180), nullable=False),
            sa.Column("site_id_snapshot", sa.Integer(), nullable=True), sa.Column("department_id_snapshot", sa.Integer(), nullable=True),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("variant_id", sa.Integer(), nullable=True), sa.Column("asset_id", sa.Integer(), nullable=True),
            sa.Column("stock_location_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("returned_quantity", sa.Integer(), nullable=False), sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("expected_replacement_date", sa.Date(), nullable=True), sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column("next_inspection_date", sa.Date(), nullable=True), sa.Column("condition_at_issue", condition, nullable=False),
            sa.Column("status", issue_status, nullable=False), sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
            sa.Column("acknowledgement_required", sa.Boolean(), nullable=False), sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledgement_method", sa.String(80), nullable=True), sa.Column("acknowledgement_reference", sa.String(255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True), sa.Column("unit_cost_snapshot", sa.Numeric(14, 2), nullable=True),
            sa.Column("item_name_snapshot", sa.String(180), nullable=False), sa.Column("item_code_snapshot", sa.String(80), nullable=False),
            sa.Column("variant_name_snapshot", sa.String(120), nullable=True), sa.Column("stock_location_name_snapshot", sa.String(180), nullable=False),
            sa.Column("replacement_for_issue_id", sa.Integer(), nullable=True),
            sa.Column("replacement_reason", replacement_reason, nullable=True), sa.Column("request_id", sa.Integer(), nullable=True),
            *_timestamps(),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["asset_id"], ["ppe_assets.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["stock_location_id"], ["ppe_stock_locations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["replacement_for_issue_id"], ["ppe_issues.id"], ondelete="SET NULL"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_ppe_issues_quantity_positive"),
        sa.CheckConstraint("returned_quantity >= 0 AND returned_quantity <= quantity", name="ck_ppe_issues_returned_quantity"),
    )
    _indexes("ppe_issues", "id", "organisation_id", "recipient_type", "recipient_user_id", "contractor_id", "site_id_snapshot", "department_id_snapshot", "item_id", "variant_id", "asset_id", "stock_location_id", "issue_date", "expected_replacement_date", "expiry_date", "next_inspection_date", "status", "issued_by_user_id", "replacement_for_issue_id", "request_id")

    return_outcome = _enum("ppereturnoutcome", "reusable", "damaged", "expired", "contaminated", "write_off")
    op.create_table(
        "ppe_returns",
        *_owned_columns(
            sa.Column("issue_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("returned_at", sa.DateTime(timezone=True), nullable=False), sa.Column("condition", condition, nullable=False),
            sa.Column("outcome", return_outcome, nullable=False), sa.Column("received_by_user_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["issue_id"], ["ppe_issues.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_ppe_returns_quantity_positive"),
    )
    _indexes("ppe_returns", "id", "organisation_id", "issue_id", "returned_at")

    loss_type = _enum("ppelossdamagetype", "lost", "damaged", "unusable")
    op.create_table(
        "ppe_loss_damage_reports",
        *_owned_columns(
            sa.Column("issue_id", sa.Integer(), nullable=False), sa.Column("report_type", loss_type, nullable=False),
            sa.Column("event_date", sa.Date(), nullable=False), sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("reported_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("unified_action_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["issue_id"], ["ppe_issues.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["reported_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["unified_action_id"], ["corrective_actions.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("ppe_loss_damage_reports", "id", "organisation_id", "issue_id", "report_type", "event_date", "reported_by_user_id", "reviewed_by_user_id", "unified_action_id")

    op.create_table(
        "ppe_inspections",
        *_owned_columns(
            sa.Column("issue_id", sa.Integer(), nullable=False), sa.Column("inspection_date", sa.Date(), nullable=False),
            sa.Column("inspector_user_id", sa.Integer(), nullable=True), sa.Column("condition", condition, nullable=False),
            sa.Column("passed", sa.Boolean(), nullable=False), sa.Column("defects", sa.Text(), nullable=True),
            sa.Column("next_inspection_date", sa.Date(), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("unified_action_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["issue_id"], ["ppe_issues.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["inspector_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["unified_action_id"], ["corrective_actions.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("ppe_inspections", "id", "organisation_id", "issue_id", "inspection_date", "inspector_user_id", "passed", "next_inspection_date", "unified_action_id")

    requirement_level = _enum("pperequirementlevel", "mandatory", "recommended")
    op.create_table(
        "ppe_requirements",
        *_owned_columns(
            sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("variant_id", sa.Integer(), nullable=True),
            sa.Column("role_name", sa.String(80), nullable=True), sa.Column("job_title", sa.String(180), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True), sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("task_activity", sa.String(255), nullable=True), sa.Column("hazard_id", sa.Integer(), nullable=True),
            sa.Column("jsa_id", sa.Integer(), nullable=True), sa.Column("requirement_level", requirement_level, nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("replacement_interval_days", sa.Integer(), nullable=True),
            sa.Column("inspection_required", sa.Boolean(), nullable=False), sa.Column("certification_requirement", sa.String(255), nullable=True),
            sa.Column("is_critical", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), *_timestamps(),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["jsa_id"], ["job_safety_analyses.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("ppe_requirements", "id", "organisation_id", "item_id", "variant_id", "role_name", "job_title", "department_id", "site_id", "task_activity", "hazard_id", "jsa_id", "requirement_level")

    urgency = _enum("ppeurgency", "routine", "urgent", "critical")
    request_status = _enum("pperequeststatus", "requested", "approved", "rejected", "issued")
    op.create_table(
        "ppe_requests",
        *_owned_columns(
            sa.Column("requester_user_id", sa.Integer(), nullable=False), sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False), sa.Column("variant_id", sa.Integer(), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("urgency", urgency, nullable=False), sa.Column("status", request_status, nullable=False),
            sa.Column("approver_user_id", sa.Integer(), nullable=True), sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("decision_notes", sa.Text(), nullable=True), sa.Column("issue_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["item_id"], ["ppe_items.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["variant_id"], ["ppe_variants.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["issue_id"], ["ppe_issues.id"], ondelete="SET NULL"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_ppe_requests_quantity_positive"),
    )
    _indexes("ppe_requests", "id", "organisation_id", "requester_user_id", "recipient_user_id", "item_id", "variant_id", "urgency", "status", "approver_user_id", "issue_id")

    op.create_table(
        "ppe_reminder_deliveries",
        *_owned_columns(
            sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False), sa.Column("milestone_key", sa.String(80), nullable=False),
            sa.Column("due_date_snapshot", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        ),
        sa.UniqueConstraint("organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_ppe_reminder_delivery"),
    )
    _indexes("ppe_reminder_deliveries", "id", "organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key")

    kpis = sa.table(
        "kpi_definitions",
        *[sa.column(name) for name in (
            "organisation_id", "key", "name", "description", "category", "unit", "calculation_method",
            "numerator_definition", "denominator_definition", "multiplier", "direction", "is_active",
            "version", "effective_from", "effective_to", "created_at", "updated_at",
        )],
    )
    existing_kpis = set(bind.execute(sa.select(kpis.c.key).where(kpis.c.key.in_([row[0] for row in PPE_KPIS]))).scalars().all())
    rows = []
    for key, name, unit, direction in PPE_KPIS:
        if key in existing_kpis:
            continue
        rows.append({"organisation_id": None, "key": key, "name": name, "description": f"PPE management KPI for {name.lower()}.", "category": "PPE", "unit": unit, "calculation_method": key, "numerator_definition": None, "denominator_definition": None, "multiplier": None, "direction": direction, "is_active": True, "version": 1, "effective_from": date(2026, 1, 1), "effective_to": None, "created_at": now, "updated_at": now})
    if rows:
        bind.execute(kpis.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    kpis = sa.table("kpi_definitions", sa.column("key", sa.String))
    bind.execute(kpis.delete().where(kpis.c.key.in_([row[0] for row in PPE_KPIS])))
    features = sa.table("organisation_features", sa.column("key", sa.String))
    bind.execute(features.delete().where(features.c.key == "ppe"))

    for table_name in (
        "ppe_reminder_deliveries", "ppe_inspections", "ppe_loss_damage_reports", "ppe_returns",
        "ppe_requests", "ppe_stock_movements", "ppe_issues", "ppe_requirements", "ppe_assets",
        "ppe_inventory", "ppe_stock_locations", "ppe_variants", "ppe_items", "ppe_categories",
    ):
        op.drop_table(table_name)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_job_title"))
        batch_op.drop_column("job_title")
    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.drop_column("ppe_configuration")
    if bind.dialect.name == "postgresql":
        for enum_name in (
            "pperequeststatus", "ppeurgency", "pperequirementlevel", "ppelossdamagetype",
            "ppereturnoutcome", "ppereplacementreason", "ppeissuestatus", "pperecipienttype",
            "ppecondition", "ppeassetstatus", "ppemovementtype",
        ):
            sa.Enum(name=enum_name).drop(bind, checkfirst=True)
