"""add organisation tenancy, departments, settings, and feature entitlements

Revision ID: 20260811_0016
Revises: 20260811_0015
Create Date: 2026-08-11
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260811_0016"
down_revision = "20260811_0015"
branch_labels = None
depends_on = None


DEFAULT_ORGANISATION_ID = 1
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
)

TENANT_TABLES = (
    "approval_workflows",
    "asset_register_items",
    "attachments",
    "audit_logs",
    "audit_management_records",
    "behaviour_observations",
    "contractors",
    "corrective_actions",
    "data_import_jobs",
    "data_import_rows",
    "document_control_records",
    "emergency_drills",
    "hazards",
    "incidents",
    "incident_investigations",
    "inspections",
    "job_runs",
    "job_safety_analyses",
    "legal_compliance_items",
    "medical_surveillance_records",
    "notifications",
    "notification_delivery_logs",
    "permits_to_work",
    "roles",
    "safety_communications",
    "safety_kpi_records",
    "safety_improvement_observations",
    "sites",
    "training_records",
    "compliance_acknowledgements",
    "users",
)


def _add_organisation_column(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column("organisation_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            f"fk_{table_name}_organisation_id_organisations",
            "organisations",
            ["organisation_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f(f"ix_{table_name}_organisation_id"), ["organisation_id"], unique=False
        )
    op.execute(
        sa.text(f"UPDATE {table_name} SET organisation_id = :organisation_id").bindparams(
            organisation_id=DEFAULT_ORGANISATION_ID
        )
    )
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column("organisation_id", existing_type=sa.Integer(), nullable=False)


def _drop_organisation_column(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_index(op.f(f"ix_{table_name}_organisation_id"))
        batch_op.drop_constraint(
            f"fk_{table_name}_organisation_id_organisations", type_="foreignkey"
        )
        batch_op.drop_column("organisation_id")


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    bind = op.get_bind()
    op.create_table(
        "organisations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("primary_contact_name", sa.String(length=255), nullable=True),
        sa.Column("primary_contact_email", sa.String(length=255), nullable=True),
        sa.Column("primary_contact_phone", sa.String(length=80), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_organisations_code"),
        sa.UniqueConstraint("slug", name="uq_organisations_slug"),
    )
    op.create_index(op.f("ix_organisations_id"), "organisations", ["id"], unique=False)
    op.create_index(op.f("ix_organisations_code"), "organisations", ["code"], unique=True)
    op.create_index(op.f("ix_organisations_slug"), "organisations", ["slug"], unique=True)
    op.bulk_insert(
        sa.table(
            "organisations",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("code", sa.String),
            sa.column("slug", sa.String),
            sa.column("timezone", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": DEFAULT_ORGANISATION_ID,
                "name": "OHS Default Organisation",
                "code": "DEFAULT",
                "slug": "ohs-default-organisation",
                "timezone": "Africa/Lusaka",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "SELECT setval(pg_get_serial_sequence('organisations', 'id'), "
            "(SELECT MAX(id) FROM organisations), true)"
        )

    for table_name in TENANT_TABLES:
        _add_organisation_column(table_name)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.execute(
        sa.text("UPDATE users SET is_platform_admin = :is_admin WHERE lower(email) = :email").bindparams(
            is_admin=True, email="admin@ohs.local"
        )
    )

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_department_id", sa.Integer(), nullable=True),
        sa.Column("manager_user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_departments_org_name"),
        sa.UniqueConstraint("organisation_id", "code", name="uq_departments_org_code"),
    )
    for column in ("id", "organisation_id", "parent_department_id", "manager_user_id"):
        op.create_index(op.f(f"ix_departments_{column}"), "departments", [column], unique=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_users_department_id"), ["department_id"], unique=False)

    op.create_table(
        "organisation_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("branding", sa.JSON(), nullable=False),
        sa.Column("date_time_preferences", sa.JSON(), nullable=False),
        sa.Column("terminology", sa.JSON(), nullable=False),
        sa.Column("permit_expiry_warning_days", sa.Integer(), nullable=False),
        sa.Column("dashboard_preferences", sa.JSON(), nullable=False),
        sa.Column("notification_preferences", sa.JSON(), nullable=False),
        sa.Column("risk_matrix_configuration", sa.JSON(), nullable=False),
        sa.Column("numbering_prefixes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organisation_id", name="uq_organisation_settings_organisation_id"),
    )
    op.create_index(op.f("ix_organisation_settings_id"), "organisation_settings", ["id"], unique=False)
    op.create_index(
        op.f("ix_organisation_settings_organisation_id"),
        "organisation_settings",
        ["organisation_id"],
        unique=True,
    )
    op.bulk_insert(
        sa.table(
            "organisation_settings",
            sa.column("organisation_id", sa.Integer),
            sa.column("branding", sa.JSON),
            sa.column("date_time_preferences", sa.JSON),
            sa.column("terminology", sa.JSON),
            sa.column("permit_expiry_warning_days", sa.Integer),
            sa.column("dashboard_preferences", sa.JSON),
            sa.column("notification_preferences", sa.JSON),
            sa.column("risk_matrix_configuration", sa.JSON),
            sa.column("numbering_prefixes", sa.JSON),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "organisation_id": DEFAULT_ORGANISATION_ID,
                "branding": {},
                "date_time_preferences": {},
                "terminology": {},
                "permit_expiry_warning_days": 30,
                "dashboard_preferences": {},
                "notification_preferences": {},
                "risk_matrix_configuration": {},
                "numbering_prefixes": {},
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    op.create_table(
        "organisation_features",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organisation_id", "key", name="uq_organisation_features_org_key"),
    )
    for column in ("id", "organisation_id", "key"):
        op.create_index(
            op.f(f"ix_organisation_features_{column}"),
            "organisation_features",
            [column],
            unique=False,
        )
    feature_table = sa.table(
        "organisation_features",
        sa.column("organisation_id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("is_enabled", sa.Boolean),
        sa.column("configuration", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        feature_table,
        [
            {
                "organisation_id": DEFAULT_ORGANISATION_ID,
                "key": key,
                "is_enabled": True,
                "configuration": {},
                "created_at": now,
                "updated_at": now,
            }
            for key in MODULE_KEYS
        ],
    )

    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_sites_code"), table_name="sites")
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=False)
    op.create_index(op.f("ix_sites_code"), "sites", ["code"], unique=False)
    with op.batch_alter_table("roles") as batch_op:
        batch_op.create_unique_constraint("uq_roles_org_name", ["organisation_id", "name"])
    with op.batch_alter_table("sites") as batch_op:
        batch_op.create_unique_constraint("uq_sites_org_code", ["organisation_id", "code"])
    with op.batch_alter_table("safety_improvement_observations") as batch_op:
        batch_op.drop_constraint("uq_sios_source_external_reference", type_="unique")
        batch_op.create_unique_constraint(
            "uq_sios_source_external_reference",
            ["organisation_id", "source_system", "external_reference_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("safety_improvement_observations") as batch_op:
        batch_op.drop_constraint("uq_sios_source_external_reference", type_="unique")
        batch_op.create_unique_constraint(
            "uq_sios_source_external_reference", ["source_system", "external_reference_id"]
        )
    with op.batch_alter_table("roles") as batch_op:
        batch_op.drop_constraint("uq_roles_org_name", type_="unique")
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_constraint("uq_sites_org_code", type_="unique")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_sites_code"), table_name="sites")
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)
    op.create_index(op.f("ix_sites_code"), "sites", ["code"], unique=True)

    op.drop_table("organisation_features")
    op.drop_table("organisation_settings")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_department_id"))
        batch_op.drop_constraint("fk_users_department_id_departments", type_="foreignkey")
        batch_op.drop_column("department_id")
    op.drop_table("departments")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_platform_admin")

    for table_name in reversed(TENANT_TABLES):
        _drop_organisation_column(table_name)

    op.drop_index(op.f("ix_organisations_slug"), table_name="organisations")
    op.drop_index(op.f("ix_organisations_code"), table_name="organisations")
    op.drop_index(op.f("ix_organisations_id"), table_name="organisations")
    op.drop_table("organisations")
