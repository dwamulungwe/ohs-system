"""add attachments table

Revision ID: 20260427_0010
Revises: 20260427_0009
Create Date: 2026-04-27

"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0010"
down_revision = "20260427_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "incident",
                "hazard",
                "inspection",
                "corrective_action",
                "permit",
                "training",
                "compliance_acknowledgement",
                name="attachmententitytype",
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_attachments_id"), "attachments", ["id"], unique=False)
    op.create_index(op.f("ix_attachments_entity_type"), "attachments", ["entity_type"], unique=False)
    op.create_index(op.f("ix_attachments_entity_id"), "attachments", ["entity_id"], unique=False)
    op.create_index(op.f("ix_attachments_uploaded_by_user_id"), "attachments", ["uploaded_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attachments_uploaded_by_user_id"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_entity_id"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_entity_type"), table_name="attachments")
    op.drop_index(op.f("ix_attachments_id"), table_name="attachments")
    op.drop_table("attachments")
    sa.Enum(name="attachmententitytype").drop(op.get_bind(), checkfirst=True)
