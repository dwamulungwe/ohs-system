"""add permit to work

Revision ID: 20260423_0008
Revises: 20260423_0007
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0008"
down_revision = "20260423_0007"
branch_labels = None
depends_on = None

permit_type = sa.Enum(
    "hot_work",
    "confined_space",
    "electrical",
    "work_at_height",
    "excavation",
    "lifting",
    "maintenance",
    "contractor",
    name="permittype",
)
permit_status = sa.Enum(
    "draft",
    "pending_approval",
    "approved",
    "active",
    "suspended",
    "expired",
    "closed",
    "cancelled",
    "rejected",
    name="permitstatus",
)


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'permit_pending_approval'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'permit_nearing_expiry'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'permit_expired'")
    op.execute("ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS 'permit'")

    op.create_table(
        "permits_to_work",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("permit_number", sa.String(length=80), nullable=False),
        sa.Column("permit_type", permit_type, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("area_location", sa.String(length=255), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_team_or_contractor", sa.String(length=255), nullable=True),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", permit_status, nullable=False),
        sa.Column("risk_summary", sa.Text(), nullable=True),
        sa.Column("precautions_required", sa.JSON(), nullable=False),
        sa.Column("ppe_required", sa.JSON(), nullable=False),
        sa.Column("isolation_required", sa.Boolean(), nullable=False),
        sa.Column("gas_test_required", sa.Boolean(), nullable=False),
        sa.Column("gas_test_results", sa.JSON(), nullable=False),
        sa.Column("emergency_controls", sa.JSON(), nullable=False),
        sa.Column("closure_notes", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permits_to_work_id"), "permits_to_work", ["id"], unique=False)
    op.create_index(op.f("ix_permits_to_work_permit_number"), "permits_to_work", ["permit_number"], unique=True)
    op.create_index(op.f("ix_permits_to_work_permit_type"), "permits_to_work", ["permit_type"], unique=False)
    op.create_index(op.f("ix_permits_to_work_status"), "permits_to_work", ["status"], unique=False)
    op.create_index(op.f("ix_permits_to_work_site_id"), "permits_to_work", ["site_id"], unique=False)
    op.create_index(op.f("ix_permits_to_work_requested_by_user_id"), "permits_to_work", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_permits_to_work_issued_by_user_id"), "permits_to_work", ["issued_by_user_id"], unique=False)
    op.create_index(op.f("ix_permits_to_work_approved_by_user_id"), "permits_to_work", ["approved_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_permits_to_work_approved_by_user_id"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_issued_by_user_id"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_requested_by_user_id"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_site_id"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_status"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_permit_type"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_permit_number"), table_name="permits_to_work")
    op.drop_index(op.f("ix_permits_to_work_id"), table_name="permits_to_work")
    op.drop_table("permits_to_work")

    bind = op.get_bind()
    permit_status.drop(bind, checkfirst=True)
    permit_type.drop(bind, checkfirst=True)
