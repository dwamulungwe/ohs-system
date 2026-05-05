"""add incident attachments metadata

Revision ID: 20260423_0002
Revises: 20260423_0001
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0002"
down_revision = "20260423_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("attachments_metadata", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.alter_column("incidents", "attachments_metadata", server_default=None)


def downgrade() -> None:
    op.drop_column("incidents", "attachments_metadata")
