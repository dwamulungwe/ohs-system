"""add SIO module and reusable data imports

Revision ID: 20260811_0015
Revises: 20260429_0014
Create Date: 2026-08-11

"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0015"
down_revision = "20260429_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE correctiveactionsourcetype ADD VALUE IF NOT EXISTS 'sio'")

    op.create_table(
        "safety_improvement_observations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("external_reference_id", sa.String(length=160), nullable=True),
        sa.Column("source_system", sa.String(length=120), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("incident_classification", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "unassigned",
                "assigned_to_responsible_person",
                "assigned_to_action_tracker",
                "complete",
                "no_action_required",
                "open",
                name="siostatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "observation_nature",
            sa.Enum("positive", "negative", name="sioobservationnature"),
            nullable=False,
        ),
        sa.Column("responsible_department", sa.String(length=200), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("responsible_hs_officer_user_id", sa.Integer(), nullable=True),
        sa.Column("responsible_hs_officer_name", sa.String(length=255), nullable=True),
        sa.Column(
            "urgency",
            sa.Enum("low", "medium", "high", "urgent", "not_applicable", name="siourgency"),
            nullable=True,
        ),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("responsible_person_user_id", sa.Integer(), nullable=True),
        sa.Column("responsible_person_name", sa.String(length=255), nullable=True),
        sa.Column("property_damage", sa.String(length=255), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_created_by", sa.String(length=255), nullable=True),
        sa.Column("source_modified_by", sa.String(length=255), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("legacy_metadata", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("linked_hazard_id", sa.Integer(), nullable=True),
        sa.Column("linked_incident_id", sa.Integer(), nullable=True),
        sa.Column("linked_corrective_action_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsible_hs_officer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responsible_person_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_hazard_id"], ["hazards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["linked_corrective_action_id"], ["corrective_actions.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "source_system", "external_reference_id", name="uq_sios_source_external_reference"
        ),
        sa.UniqueConstraint("linked_hazard_id"),
        sa.UniqueConstraint("linked_incident_id"),
        sa.UniqueConstraint("linked_corrective_action_id"),
    )
    for column in (
        "id",
        "observation_date",
        "department",
        "source_type",
        "incident_classification",
        "status",
        "observation_nature",
        "site_id",
        "responsible_hs_officer_user_id",
        "urgency",
        "category",
        "responsible_person_user_id",
        "created_by_user_id",
    ):
        op.create_index(
            op.f(f"ix_safety_improvement_observations_{column}"),
            "safety_improvement_observations",
            [column],
            unique=False,
        )

    op.create_table(
        "data_import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("importer_type", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "previewed",
                "processing",
                "completed",
                "completed_with_errors",
                "failed",
                name="importjobstatus",
            ),
            nullable=False,
        ),
        sa.Column("is_dry_run", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("successful_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("failed_rows", sa.Integer(), nullable=False),
        sa.Column("validation_messages", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("id", "importer_type", "source_system", "status", "created_by_user_id"):
        op.create_index(op.f(f"ix_data_import_jobs_{column}"), "data_import_jobs", [column], unique=False)

    op.create_table(
        "data_import_rows",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("external_reference_id", sa.String(length=160), nullable=True),
        sa.Column("source_site_name", sa.String(length=180), nullable=True),
        sa.Column("resolved_site_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "valid",
                "unresolved_site",
                "duplicate",
                "invalid",
                "imported",
                "failed",
                name="importrowstatus",
            ),
            nullable=False,
        ),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("imported_sio_id", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["data_import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["imported_sio_id"], ["safety_improvement_observations.id"], ondelete="SET NULL"
        ),
    )
    for column in (
        "id",
        "job_id",
        "external_reference_id",
        "resolved_site_id",
        "status",
    ):
        op.create_index(op.f(f"ix_data_import_rows_{column}"), "data_import_rows", [column], unique=False)


def downgrade() -> None:
    for column in ("status", "resolved_site_id", "external_reference_id", "job_id", "id"):
        op.drop_index(op.f(f"ix_data_import_rows_{column}"), table_name="data_import_rows")
    op.drop_table("data_import_rows")

    for column in ("created_by_user_id", "status", "source_system", "importer_type", "id"):
        op.drop_index(op.f(f"ix_data_import_jobs_{column}"), table_name="data_import_jobs")
    op.drop_table("data_import_jobs")

    for column in (
        "created_by_user_id",
        "responsible_person_user_id",
        "category",
        "urgency",
        "responsible_hs_officer_user_id",
        "site_id",
        "observation_nature",
        "status",
        "incident_classification",
        "source_type",
        "department",
        "observation_date",
        "id",
    ):
        op.drop_index(
            op.f(f"ix_safety_improvement_observations_{column}"),
            table_name="safety_improvement_observations",
        )
    op.drop_table("safety_improvement_observations")

    bind = op.get_bind()
    sa.Enum(name="importrowstatus").drop(bind, checkfirst=True)
    sa.Enum(name="importjobstatus").drop(bind, checkfirst=True)
    sa.Enum(name="siourgency").drop(bind, checkfirst=True)
    sa.Enum(name="sioobservationnature").drop(bind, checkfirst=True)
    sa.Enum(name="siostatus").drop(bind, checkfirst=True)

    if bind.dialect.name == "postgresql":
        op.execute("UPDATE corrective_actions SET source_type = 'manual', source_id = NULL WHERE source_type = 'sio'")
        op.execute("ALTER TABLE corrective_actions ALTER COLUMN source_type TYPE VARCHAR USING source_type::text")
        op.execute("DROP TYPE correctiveactionsourcetype")
        op.execute("CREATE TYPE correctiveactionsourcetype AS ENUM ('incident', 'hazard', 'inspection', 'manual')")
        op.execute(
            "ALTER TABLE corrective_actions ALTER COLUMN source_type TYPE correctiveactionsourcetype "
            "USING source_type::correctiveactionsourcetype"
        )
