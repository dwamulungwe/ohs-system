"""add enterprise ohs feature pack

Revision ID: 20260429_0013
Revises: 20260429_0012
Create Date: 2026-04-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_0013"
down_revision = "20260429_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in (
            "incident_investigation",
            "legal_compliance",
            "jsa",
            "contractor",
            "asset_register",
        ):
            op.execute(f"ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS '{value}'")

        for value in (
            "investigation_pending_approval",
            "investigation_approved",
            "legal_compliance_due_soon",
            "legal_compliance_overdue",
            "jsa_pending_approval",
            "jsa_review_due_soon",
            "jsa_review_overdue",
            "contractor_insurance_due_soon",
            "contractor_insurance_overdue",
            "contractor_documents_due_soon",
            "contractor_documents_overdue",
            "asset_inspection_due_soon",
            "asset_inspection_overdue",
            "asset_defective",
        ):
            op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")

        for value in (
            "incident_investigation",
            "legal_compliance",
            "jsa",
            "contractor",
            "asset_register",
        ):
            op.execute(f"ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        "incident_investigations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("investigation_lead_user_id", sa.Integer(), nullable=True),
        sa.Column("investigation_team", sa.JSON(), nullable=False),
        sa.Column("witness_statements", sa.JSON(), nullable=False),
        sa.Column("immediate_causes", sa.JSON(), nullable=False),
        sa.Column("underlying_causes", sa.JSON(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("five_whys", sa.JSON(), nullable=False),
        sa.Column("contributing_factors", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "in_progress",
                "pending_approval",
                "approved",
                "closed",
                name="incidentinvestigationstatus",
            ),
            nullable=False,
        ),
        sa.Column("target_completion_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investigation_lead_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("incident_id", name="uq_incident_investigations_incident_id"),
    )
    op.create_index(op.f("ix_incident_investigations_id"), "incident_investigations", ["id"], unique=False)
    op.create_index(op.f("ix_incident_investigations_incident_id"), "incident_investigations", ["incident_id"], unique=False)
    op.create_index(op.f("ix_incident_investigations_site_id"), "incident_investigations", ["site_id"], unique=False)
    op.create_index(op.f("ix_incident_investigations_status"), "incident_investigations", ["status"], unique=False)

    op.create_table(
        "legal_compliance_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("regulatory_body", sa.String(length=200), nullable=False),
        sa.Column("legal_reference", sa.String(length=200), nullable=False),
        sa.Column("requirement_summary", sa.Text(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "compliance_status",
            sa.Enum(
                "compliant",
                "partial",
                "non_compliant",
                "not_applicable",
                "pending_review",
                name="legalcompliancestatus",
            ),
            nullable=False,
        ),
        sa.Column("review_frequency", sa.String(length=120), nullable=False),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_required", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_legal_compliance_items_id"), "legal_compliance_items", ["id"], unique=False)
    op.create_index(op.f("ix_legal_compliance_items_site_id"), "legal_compliance_items", ["site_id"], unique=False)
    op.create_index(op.f("ix_legal_compliance_items_owner_user_id"), "legal_compliance_items", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_legal_compliance_items_compliance_status"), "legal_compliance_items", ["compliance_status"], unique=False)

    op.create_table(
        "job_safety_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("department_or_area", sa.String(length=200), nullable=False),
        sa.Column("job_steps", sa.JSON(), nullable=False),
        sa.Column("hazards", sa.JSON(), nullable=False),
        sa.Column("controls", sa.JSON(), nullable=False),
        sa.Column("ppe_required", sa.JSON(), nullable=False),
        sa.Column(
            "residual_risk_level",
            sa.Enum("low", "medium", "high", "critical", name="residualrisklevel"),
            nullable=False,
        ),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "pending_approval", "approved", "expired", "archived", name="jsastatus"),
            nullable=False,
        ),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_job_safety_analyses_id"), "job_safety_analyses", ["id"], unique=False)
    op.create_index(op.f("ix_job_safety_analyses_site_id"), "job_safety_analyses", ["site_id"], unique=False)
    op.create_index(op.f("ix_job_safety_analyses_status"), "job_safety_analyses", ["status"], unique=False)

    op.create_table(
        "contractors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("contractor_name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=200), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("contact_phone", sa.String(length=80), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("work_scope", sa.Text(), nullable=False),
        sa.Column(
            "onboarding_status",
            sa.Enum("pending", "in_progress", "completed", name="contractoronboardingstatus"),
            nullable=False,
        ),
        sa.Column(
            "induction_status",
            sa.Enum("pending", "completed", "expired", name="contractorinductionstatus"),
            nullable=False,
        ),
        sa.Column("insurance_expiry_date", sa.Date(), nullable=True),
        sa.Column(
            "compliance_documents_status",
            sa.Enum("incomplete", "complete", "expired", name="contractorcompliancedocumentsstatus"),
            nullable=False,
        ),
        sa.Column("approved_for_work", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("documents_expiry_date", sa.Date(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_contractors_id"), "contractors", ["id"], unique=False)
    op.create_index(op.f("ix_contractors_site_id"), "contractors", ["site_id"], unique=False)

    op.create_table(
        "asset_register_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(
                "equipment",
                "ppe",
                "emergency_equipment",
                "fire_extinguisher",
                "first_aid_kit",
                name="assettype",
            ),
            nullable=False,
        ),
        sa.Column("asset_name", sa.String(length=200), nullable=False),
        sa.Column("asset_tag", sa.String(length=120), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("inspection_frequency", sa.String(length=120), nullable=False),
        sa.Column("next_inspection_date", sa.Date(), nullable=True),
        sa.Column(
            "condition_status",
            sa.Enum("good", "needs_attention", "defective", "retired", name="assetconditionstatus"),
            nullable=False,
        ),
        sa.Column("last_inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("asset_tag"),
    )
    op.create_index(op.f("ix_asset_register_items_id"), "asset_register_items", ["id"], unique=False)
    op.create_index(op.f("ix_asset_register_items_asset_type"), "asset_register_items", ["asset_type"], unique=False)
    op.create_index(op.f("ix_asset_register_items_asset_tag"), "asset_register_items", ["asset_tag"], unique=True)
    op.create_index(op.f("ix_asset_register_items_site_id"), "asset_register_items", ["site_id"], unique=False)
    op.create_index(op.f("ix_asset_register_items_condition_status"), "asset_register_items", ["condition_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_asset_register_items_condition_status"), table_name="asset_register_items")
    op.drop_index(op.f("ix_asset_register_items_site_id"), table_name="asset_register_items")
    op.drop_index(op.f("ix_asset_register_items_asset_tag"), table_name="asset_register_items")
    op.drop_index(op.f("ix_asset_register_items_asset_type"), table_name="asset_register_items")
    op.drop_index(op.f("ix_asset_register_items_id"), table_name="asset_register_items")
    op.drop_table("asset_register_items")

    op.drop_index(op.f("ix_contractors_site_id"), table_name="contractors")
    op.drop_index(op.f("ix_contractors_id"), table_name="contractors")
    op.drop_table("contractors")

    op.drop_index(op.f("ix_job_safety_analyses_status"), table_name="job_safety_analyses")
    op.drop_index(op.f("ix_job_safety_analyses_site_id"), table_name="job_safety_analyses")
    op.drop_index(op.f("ix_job_safety_analyses_id"), table_name="job_safety_analyses")
    op.drop_table("job_safety_analyses")

    op.drop_index(op.f("ix_legal_compliance_items_compliance_status"), table_name="legal_compliance_items")
    op.drop_index(op.f("ix_legal_compliance_items_owner_user_id"), table_name="legal_compliance_items")
    op.drop_index(op.f("ix_legal_compliance_items_site_id"), table_name="legal_compliance_items")
    op.drop_index(op.f("ix_legal_compliance_items_id"), table_name="legal_compliance_items")
    op.drop_table("legal_compliance_items")

    op.drop_index(op.f("ix_incident_investigations_status"), table_name="incident_investigations")
    op.drop_index(op.f("ix_incident_investigations_site_id"), table_name="incident_investigations")
    op.drop_index(op.f("ix_incident_investigations_incident_id"), table_name="incident_investigations")
    op.drop_index(op.f("ix_incident_investigations_id"), table_name="incident_investigations")
    op.drop_table("incident_investigations")

    sa.Enum(name="assetconditionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="assettype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="contractorcompliancedocumentsstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="contractorinductionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="contractoronboardingstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="jsastatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="residualrisklevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="legalcompliancestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incidentinvestigationstatus").drop(op.get_bind(), checkfirst=True)
