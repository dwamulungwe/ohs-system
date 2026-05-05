"""expand inspection module

Revision ID: 20260423_0004
Revises: 20260423_0003
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0004"
down_revision = "20260423_0003"
branch_labels = None
depends_on = None

inspection_overall_result = sa.Enum(
    "compliant",
    "minor_non_conformance",
    "major_non_conformance",
    "critical_non_conformance",
    name="inspectionoverallresult",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspection_overall_result.create(bind, checkfirst=True)

    op.execute(
        "CREATE TYPE inspectionstatus_new AS ENUM ('draft', 'in_progress', 'completed', 'archived')"
    )
    op.execute(
        """
        ALTER TABLE inspections
        ALTER COLUMN status TYPE inspectionstatus_new
        USING (
            CASE status::text
                WHEN 'scheduled' THEN 'draft'
                WHEN 'cancelled' THEN 'archived'
                ELSE status::text
            END
        )::inspectionstatus_new
        """
    )
    op.execute("DROP TYPE inspectionstatus")
    op.execute("ALTER TYPE inspectionstatus_new RENAME TO inspectionstatus")

    op.alter_column("inspections", "scheduled_at", new_column_name="inspection_date")
    op.alter_column("inspections", "inspector_id", new_column_name="inspector_user_id")
    op.drop_column("inspections", "completed_at")

    op.add_column(
        "inspections",
        sa.Column("inspection_type", sa.String(length=120), server_default="general", nullable=False),
    )
    op.add_column(
        "inspections",
        sa.Column("area_location", sa.String(length=255), server_default="Unspecified", nullable=False),
    )
    op.add_column("inspections", sa.Column("findings_summary", sa.Text(), nullable=True))
    op.add_column(
        "inspections",
        sa.Column("overall_result", inspection_overall_result, server_default="compliant", nullable=False),
    )
    op.add_column(
        "inspections",
        sa.Column("number_of_non_conformities", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "inspections",
        sa.Column("number_of_observations", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "inspections",
        sa.Column("checklist_items", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "inspections",
        sa.Column("attachments_metadata", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.create_index(op.f("ix_inspections_inspection_type"), "inspections", ["inspection_type"], unique=False)
    op.create_index(op.f("ix_inspections_inspector_user_id"), "inspections", ["inspector_user_id"], unique=False)

    op.create_table(
        "inspection_linked_hazards",
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.Column("hazard_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("inspection_id", "hazard_id"),
    )

    op.alter_column("inspections", "inspection_type", server_default=None)
    op.alter_column("inspections", "area_location", server_default=None)
    op.alter_column("inspections", "overall_result", server_default=None)
    op.alter_column("inspections", "number_of_non_conformities", server_default=None)
    op.alter_column("inspections", "number_of_observations", server_default=None)
    op.alter_column("inspections", "checklist_items", server_default=None)
    op.alter_column("inspections", "attachments_metadata", server_default=None)
    op.alter_column("inspections", "inspector_user_id", nullable=False)


def downgrade() -> None:
    op.drop_table("inspection_linked_hazards")
    op.drop_index(op.f("ix_inspections_inspector_user_id"), table_name="inspections")
    op.drop_index(op.f("ix_inspections_inspection_type"), table_name="inspections")
    op.drop_column("inspections", "attachments_metadata")
    op.drop_column("inspections", "checklist_items")
    op.drop_column("inspections", "number_of_observations")
    op.drop_column("inspections", "number_of_non_conformities")
    op.drop_column("inspections", "overall_result")
    op.drop_column("inspections", "findings_summary")
    op.drop_column("inspections", "area_location")
    op.drop_column("inspections", "inspection_type")
    op.add_column("inspections", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("inspections", "inspector_user_id", new_column_name="inspector_id", nullable=True)
    op.alter_column("inspections", "inspection_date", new_column_name="scheduled_at")

    op.execute(
        "CREATE TYPE inspectionstatus_old AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled')"
    )
    op.execute(
        """
        ALTER TABLE inspections
        ALTER COLUMN status TYPE inspectionstatus_old
        USING (
            CASE status::text
                WHEN 'draft' THEN 'scheduled'
                WHEN 'archived' THEN 'cancelled'
                ELSE status::text
            END
        )::inspectionstatus_old
        """
    )
    op.execute("DROP TYPE inspectionstatus")
    op.execute("ALTER TYPE inspectionstatus_old RENAME TO inspectionstatus")

    bind = op.get_bind()
    inspection_overall_result.drop(bind, checkfirst=True)
