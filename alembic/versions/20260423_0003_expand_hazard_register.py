"""expand hazard register

Revision ID: 20260423_0003
Revises: 20260423_0002
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0003"
down_revision = "20260423_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE hazardrisklevel ADD VALUE IF NOT EXISTS 'critical'")
    op.add_column("hazards", sa.Column("likelihood", sa.Integer(), server_default="1", nullable=False))
    op.add_column("hazards", sa.Column("impact", sa.Integer(), server_default="1", nullable=False))
    op.add_column("hazards", sa.Column("risk_score", sa.Integer(), server_default="1", nullable=False))
    op.add_column(
        "hazards",
        sa.Column("existing_controls", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "hazards",
        sa.Column("additional_controls", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column("hazards", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.add_column("hazards", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("hazards", sa.Column("review_date", sa.Date(), nullable=True))
    op.add_column(
        "hazards",
        sa.Column("attachments_metadata", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column("hazards", sa.Column("incident_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_hazards_owner_user_id_users",
        "hazards",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_hazards_incident_id_incidents",
        "hazards",
        "incidents",
        ["incident_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_hazards_owner_user_id"), "hazards", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_hazards_incident_id"), "hazards", ["incident_id"], unique=False)
    op.alter_column("hazards", "likelihood", server_default=None)
    op.alter_column("hazards", "impact", server_default=None)
    op.alter_column("hazards", "risk_score", server_default=None)
    op.alter_column("hazards", "existing_controls", server_default=None)
    op.alter_column("hazards", "additional_controls", server_default=None)
    op.alter_column("hazards", "attachments_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_hazards_incident_id"), table_name="hazards")
    op.drop_index(op.f("ix_hazards_owner_user_id"), table_name="hazards")
    op.drop_constraint("fk_hazards_incident_id_incidents", "hazards", type_="foreignkey")
    op.drop_constraint("fk_hazards_owner_user_id_users", "hazards", type_="foreignkey")
    op.drop_column("hazards", "incident_id")
    op.drop_column("hazards", "attachments_metadata")
    op.drop_column("hazards", "review_date")
    op.drop_column("hazards", "due_date")
    op.drop_column("hazards", "owner_user_id")
    op.drop_column("hazards", "additional_controls")
    op.drop_column("hazards", "existing_controls")
    op.drop_column("hazards", "risk_score")
    op.drop_column("hazards", "impact")
    op.drop_column("hazards", "likelihood")
