"""add safety kpis communications and behaviour observations

Revision ID: 20260429_0012
Revises: 20260427_0011
Create Date: 2026-04-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_0012"
down_revision = "20260427_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'safety_communication'")
        op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'behaviour_observation'")

    op.add_column(
        "incidents",
        sa.Column("is_recordable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "incidents",
        sa.Column("is_lost_time", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "safety_kpi_records",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("hours_worked", sa.Float(), nullable=False),
        sa.Column("reporting_label", sa.String(length=120), nullable=True),
        sa.Column("employees_count", sa.Integer(), nullable=True),
        sa.Column("contractors_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("site_id", "period_start", "period_end", name="uq_safety_kpi_records_site_period"),
    )
    op.create_index(op.f("ix_safety_kpi_records_id"), "safety_kpi_records", ["id"], unique=False)
    op.create_index(op.f("ix_safety_kpi_records_site_id"), "safety_kpi_records", ["site_id"], unique=False)

    op.create_table(
        "safety_communications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "communication_type",
            sa.Enum(
                "toolbox_talk",
                "safety_alert",
                "poster",
                "signage",
                "campaign",
                name="safetycommunicationtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived", name="safetycommunicationstatus"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(length=200), nullable=True),
        sa.Column("requires_acknowledgement", sa.Boolean(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_safety_communications_id"), "safety_communications", ["id"], unique=False)
    op.create_index(op.f("ix_safety_communications_site_id"), "safety_communications", ["site_id"], unique=False)
    op.create_index(
        op.f("ix_safety_communications_communication_type"),
        "safety_communications",
        ["communication_type"],
        unique=False,
    )
    op.create_index(op.f("ix_safety_communications_status"), "safety_communications", ["status"], unique=False)

    op.create_table(
        "behaviour_observations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "observation_type",
            sa.Enum(
                "unsafe_act",
                "positive_observation",
                "conduct_issue",
                "event_safety_observation",
                name="behaviourobservationtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "reviewed", "actioned", "closed", name="behaviourobservationstatus"),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", name="behaviourobservationseverity"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("immediate_action_taken", sa.Text(), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("person_involved_name", sa.String(length=160), nullable=True),
        sa.Column("action_required", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["observed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_behaviour_observations_id"), "behaviour_observations", ["id"], unique=False)
    op.create_index(op.f("ix_behaviour_observations_site_id"), "behaviour_observations", ["site_id"], unique=False)
    op.create_index(
        op.f("ix_behaviour_observations_observation_type"),
        "behaviour_observations",
        ["observation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_behaviour_observations_status"),
        "behaviour_observations",
        ["status"],
        unique=False,
    )

    op.alter_column("incidents", "is_recordable", server_default=None)
    op.alter_column("incidents", "is_lost_time", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_behaviour_observations_status"), table_name="behaviour_observations")
    op.drop_index(op.f("ix_behaviour_observations_observation_type"), table_name="behaviour_observations")
    op.drop_index(op.f("ix_behaviour_observations_site_id"), table_name="behaviour_observations")
    op.drop_index(op.f("ix_behaviour_observations_id"), table_name="behaviour_observations")
    op.drop_table("behaviour_observations")

    op.drop_index(op.f("ix_safety_communications_status"), table_name="safety_communications")
    op.drop_index(
        op.f("ix_safety_communications_communication_type"),
        table_name="safety_communications",
    )
    op.drop_index(op.f("ix_safety_communications_site_id"), table_name="safety_communications")
    op.drop_index(op.f("ix_safety_communications_id"), table_name="safety_communications")
    op.drop_table("safety_communications")

    op.drop_index(op.f("ix_safety_kpi_records_site_id"), table_name="safety_kpi_records")
    op.drop_index(op.f("ix_safety_kpi_records_id"), table_name="safety_kpi_records")
    op.drop_table("safety_kpi_records")

    op.drop_column("incidents", "is_lost_time")
    op.drop_column("incidents", "is_recordable")

    sa.Enum(name="behaviourobservationseverity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="behaviourobservationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="behaviourobservationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="safetycommunicationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="safetycommunicationtype").drop(op.get_bind(), checkfirst=True)
