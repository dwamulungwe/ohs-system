"""initial schema

Revision ID: 20260423_0001
Revises:
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "20260423_0001"
down_revision = None
branch_labels = None
depends_on = None

incident_severity = sa.Enum("low", "medium", "high", "critical", name="incidentseverity")
incident_status = sa.Enum("open", "investigating", "resolved", "closed", name="incidentstatus")
hazard_risk_level = sa.Enum("low", "medium", "high", "extreme", name="hazardrisklevel")
hazard_status = sa.Enum("open", "controlled", "closed", name="hazardstatus")
inspection_status = sa.Enum("scheduled", "in_progress", "completed", "cancelled", name="inspectionstatus")
corrective_action_priority = sa.Enum("low", "medium", "high", "urgent", name="correctiveactionpriority")
corrective_action_status = sa.Enum(
    "open",
    "in_progress",
    "completed",
    "overdue",
    "cancelled",
    name="correctiveactionstatus",
)
corrective_action_source_type = sa.Enum(
    "incident",
    "hazard",
    "inspection",
    "manual",
    name="correctiveactionsourcetype",
)


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sites_code"), "sites", ["code"], unique=True)
    op.create_index(op.f("ix_sites_id"), "sites", ["id"], unique=False)

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", incident_severity, nullable=False),
        sa.Column("status", incident_status, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reported_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incidents_id"), "incidents", ["id"], unique=False)
    op.create_index(op.f("ix_incidents_site_id"), "incidents", ["site_id"], unique=False)

    op.create_table(
        "hazards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("risk_level", hazard_risk_level, nullable=False),
        sa.Column("status", hazard_status, nullable=False),
        sa.Column("reported_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reported_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hazards_id"), "hazards", ["id"], unique=False)
    op.create_index(op.f("ix_hazards_site_id"), "hazards", ["site_id"], unique=False)

    op.create_table(
        "inspections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", inspection_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("inspector_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["inspector_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inspections_id"), "inspections", ["id"], unique=False)
    op.create_index(op.f("ix_inspections_site_id"), "inspections", ["site_id"], unique=False)

    op.create_table(
        "corrective_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", corrective_action_source_type, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("priority", corrective_action_priority, nullable=False),
        sa.Column("status", corrective_action_status, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_corrective_actions_id"), "corrective_actions", ["id"], unique=False)
    op.create_index(op.f("ix_corrective_actions_site_id"), "corrective_actions", ["site_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"], unique=False)

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {"name": "admin", "description": "Default admin role", "created_at": now, "updated_at": now},
            {
                "name": "safety_manager",
                "description": "Default safety manager role",
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "supervisor",
                "description": "Default supervisor role",
                "created_at": now,
                "updated_at": now,
            },
            {"name": "worker", "description": "Default worker role", "created_at": now, "updated_at": now},
            {"name": "auditor", "description": "Default auditor role", "created_at": now, "updated_at": now},
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_corrective_actions_site_id"), table_name="corrective_actions")
    op.drop_index(op.f("ix_corrective_actions_id"), table_name="corrective_actions")
    op.drop_table("corrective_actions")
    op.drop_index(op.f("ix_inspections_site_id"), table_name="inspections")
    op.drop_index(op.f("ix_inspections_id"), table_name="inspections")
    op.drop_table("inspections")
    op.drop_index(op.f("ix_hazards_site_id"), table_name="hazards")
    op.drop_index(op.f("ix_hazards_id"), table_name="hazards")
    op.drop_table("hazards")
    op.drop_index(op.f("ix_incidents_site_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_id"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index(op.f("ix_sites_id"), table_name="sites")
    op.drop_index(op.f("ix_sites_code"), table_name="sites")
    op.drop_table("sites")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_id"), table_name="roles")
    op.drop_table("roles")

    bind = op.get_bind()
    for enum_type in [
        corrective_action_source_type,
        corrective_action_status,
        corrective_action_priority,
        inspection_status,
        hazard_status,
        hazard_risk_level,
        incident_status,
        incident_severity,
    ]:
        enum_type.drop(bind, checkfirst=True)
