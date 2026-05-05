"""add training and compliance

Revision ID: 20260423_0007
Revises: 20260423_0006
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0007"
down_revision = "20260423_0006"
branch_labels = None
depends_on = None

training_type = sa.Enum(
    "induction",
    "toolbox_talk",
    "safety_training",
    "equipment_training",
    "emergency_response",
    "compliance_training",
    "other",
    name="trainingtype",
)
training_status = sa.Enum("assigned", "in_progress", "completed", "overdue", "expired", "cancelled", name="trainingstatus")
ack_status = sa.Enum("assigned", "acknowledged", "overdue", "superseded", name="complianceacknowledgementstatus")


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'training_overdue'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'training_expired'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'compliance_acknowledgement_overdue'")
    op.execute("ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS 'training_record'")
    op.execute("ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS 'compliance_acknowledgement'")

    op.create_table(
        "training_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("training_type", training_type, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("status", training_status, nullable=False),
        sa.Column("certificate_metadata", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_records_id"), "training_records", ["id"], unique=False)
    op.create_index(op.f("ix_training_records_training_type"), "training_records", ["training_type"], unique=False)
    op.create_index(op.f("ix_training_records_status"), "training_records", ["status"], unique=False)
    op.create_index(op.f("ix_training_records_site_id"), "training_records", ["site_id"], unique=False)
    op.create_index(op.f("ix_training_records_assigned_to_user_id"), "training_records", ["assigned_to_user_id"], unique=False)

    op.create_table(
        "compliance_acknowledgements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_title", sa.String(length=200), nullable=False),
        sa.Column("document_type", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", ack_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_compliance_acknowledgements_id"), "compliance_acknowledgements", ["id"], unique=False)
    op.create_index(op.f("ix_compliance_acknowledgements_document_type"), "compliance_acknowledgements", ["document_type"], unique=False)
    op.create_index(op.f("ix_compliance_acknowledgements_status"), "compliance_acknowledgements", ["status"], unique=False)
    op.create_index(op.f("ix_compliance_acknowledgements_site_id"), "compliance_acknowledgements", ["site_id"], unique=False)
    op.create_index(
        op.f("ix_compliance_acknowledgements_assigned_to_user_id"),
        "compliance_acknowledgements",
        ["assigned_to_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_compliance_acknowledgements_assigned_to_user_id"), table_name="compliance_acknowledgements")
    op.drop_index(op.f("ix_compliance_acknowledgements_site_id"), table_name="compliance_acknowledgements")
    op.drop_index(op.f("ix_compliance_acknowledgements_status"), table_name="compliance_acknowledgements")
    op.drop_index(op.f("ix_compliance_acknowledgements_document_type"), table_name="compliance_acknowledgements")
    op.drop_index(op.f("ix_compliance_acknowledgements_id"), table_name="compliance_acknowledgements")
    op.drop_table("compliance_acknowledgements")
    op.drop_index(op.f("ix_training_records_assigned_to_user_id"), table_name="training_records")
    op.drop_index(op.f("ix_training_records_site_id"), table_name="training_records")
    op.drop_index(op.f("ix_training_records_status"), table_name="training_records")
    op.drop_index(op.f("ix_training_records_training_type"), table_name="training_records")
    op.drop_index(op.f("ix_training_records_id"), table_name="training_records")
    op.drop_table("training_records")

    bind = op.get_bind()
    ack_status.drop(bind, checkfirst=True)
    training_status.drop(bind, checkfirst=True)
    training_type.drop(bind, checkfirst=True)
