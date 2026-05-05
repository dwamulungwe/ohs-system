"""add approval workflows

Revision ID: 20260427_0011
Revises: 20260427_0010
Create Date: 2026-04-27

"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0011"
down_revision = "20260427_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_workflows",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum("incident", "hazard", "corrective_action", "permit", name="approvalentitytype"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_approver_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "action_type",
            sa.Enum(
                "incident_closure",
                "hazard_review",
                "corrective_action_verification",
                "permit_approval",
                name="approvalactiontype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "cancelled", name="approvalstatus"),
            nullable=False,
        ),
        sa.Column("request_notes", sa.Text(), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_approval_workflows_id"), "approval_workflows", ["id"], unique=False)
    op.create_index(
        op.f("ix_approval_workflows_entity_type"),
        "approval_workflows",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_entity_id"),
        "approval_workflows",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_requested_by_user_id"),
        "approval_workflows",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_assigned_approver_user_id"),
        "approval_workflows",
        ["assigned_approver_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_action_type"),
        "approval_workflows",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_status"),
        "approval_workflows",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_workflows_decided_by_user_id"),
        "approval_workflows",
        ["decided_by_user_id"],
        unique=False,
    )

    op.add_column(
        "incidents",
        sa.Column("closure_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("incidents", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("closed_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_incidents_closed_by_user_id_users",
        "incidents",
        "users",
        ["closed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("hazards", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hazards", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_hazards_reviewed_by_user_id_users",
        "hazards",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("permits_to_work", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("incidents", "closure_requested", server_default=None)


def downgrade() -> None:
    op.drop_column("permits_to_work", "approved_at")

    op.drop_constraint("fk_hazards_reviewed_by_user_id_users", "hazards", type_="foreignkey")
    op.drop_column("hazards", "reviewed_by_user_id")
    op.drop_column("hazards", "reviewed_at")

    op.drop_constraint("fk_incidents_closed_by_user_id_users", "incidents", type_="foreignkey")
    op.drop_column("incidents", "closed_by_user_id")
    op.drop_column("incidents", "closed_at")
    op.drop_column("incidents", "closure_requested")

    op.drop_index(op.f("ix_approval_workflows_decided_by_user_id"), table_name="approval_workflows")
    op.drop_index(op.f("ix_approval_workflows_status"), table_name="approval_workflows")
    op.drop_index(op.f("ix_approval_workflows_action_type"), table_name="approval_workflows")
    op.drop_index(
        op.f("ix_approval_workflows_assigned_approver_user_id"),
        table_name="approval_workflows",
    )
    op.drop_index(op.f("ix_approval_workflows_requested_by_user_id"), table_name="approval_workflows")
    op.drop_index(op.f("ix_approval_workflows_entity_id"), table_name="approval_workflows")
    op.drop_index(op.f("ix_approval_workflows_entity_type"), table_name="approval_workflows")
    op.drop_index(op.f("ix_approval_workflows_id"), table_name="approval_workflows")
    op.drop_table("approval_workflows")
    sa.Enum(name="approvalstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approvalactiontype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="approvalentitytype").drop(op.get_bind(), checkfirst=True)
