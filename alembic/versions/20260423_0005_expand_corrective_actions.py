"""expand corrective actions

Revision ID: 20260423_0005
Revises: 20260423_0004
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0005"
down_revision = "20260423_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE correctiveactionpriority ADD VALUE IF NOT EXISTS 'critical'")
    op.execute("ALTER TYPE correctiveactionstatus ADD VALUE IF NOT EXISTS 'pending_verification'")
    op.execute("ALTER TYPE correctiveactionstatus ADD VALUE IF NOT EXISTS 'closed'")

    op.alter_column("corrective_actions", "assigned_to_id", new_column_name="assigned_to_user_id")
    op.add_column("corrective_actions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("corrective_actions", sa.Column("closure_notes", sa.Text(), nullable=True))
    op.add_column(
        "corrective_actions",
        sa.Column("closure_evidence_metadata", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column("corrective_actions", sa.Column("verification_notes", sa.Text(), nullable=True))
    op.add_column("corrective_actions", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("corrective_actions", sa.Column("verified_by_user_id", sa.Integer(), nullable=True))
    op.add_column("corrective_actions", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_corrective_actions_created_by_user_id_users",
        "corrective_actions",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_corrective_actions_verified_by_user_id_users",
        "corrective_actions",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_corrective_actions_assigned_to_user_id"),
        "corrective_actions",
        ["assigned_to_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_corrective_actions_created_by_user_id"),
        "corrective_actions",
        ["created_by_user_id"],
        unique=False,
    )
    op.alter_column("corrective_actions", "closure_evidence_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_corrective_actions_created_by_user_id"), table_name="corrective_actions")
    op.drop_index(op.f("ix_corrective_actions_assigned_to_user_id"), table_name="corrective_actions")
    op.drop_constraint("fk_corrective_actions_verified_by_user_id_users", "corrective_actions", type_="foreignkey")
    op.drop_constraint("fk_corrective_actions_created_by_user_id_users", "corrective_actions", type_="foreignkey")
    op.drop_column("corrective_actions", "verified_at")
    op.drop_column("corrective_actions", "verified_by_user_id")
    op.drop_column("corrective_actions", "created_by_user_id")
    op.drop_column("corrective_actions", "verification_notes")
    op.drop_column("corrective_actions", "closure_evidence_metadata")
    op.drop_column("corrective_actions", "closure_notes")
    op.drop_column("corrective_actions", "started_at")
    op.alter_column("corrective_actions", "assigned_to_user_id", new_column_name="assigned_to_id")
