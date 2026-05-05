"""add final enterprise modules

Revision ID: 20260429_0014
Revises: 20260429_0013
Create Date: 2026-04-29

"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_0014"
down_revision = "20260429_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in (
            "medical_surveillance",
            "emergency_drill",
            "document_control",
            "audit_management",
        ):
            op.execute(f"ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS '{value}'")
        for value in (
            "medical_surveillance_due_soon",
            "medical_surveillance_overdue",
            "emergency_drill_due_soon",
            "emergency_drill_overdue",
            "document_pending_approval",
            "document_due_soon",
            "document_expired",
            "audit_open",
        ):
            op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")
        for value in (
            "medical_surveillance",
            "emergency_drill",
            "document_control",
            "audit_management",
        ):
            op.execute(f"ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS '{value}'")
        op.execute("ALTER TYPE approvalentitytype ADD VALUE IF NOT EXISTS 'document_control'")
        op.execute("ALTER TYPE approvalactiontype ADD VALUE IF NOT EXISTS 'document_approval'")

    op.add_column("users", sa.Column("phone_number", sa.String(length=40), nullable=True))

    op.create_table(
        "medical_surveillance_records",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("surveillance_type", sa.String(length=120), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("due", "completed", "overdue", name="medicalsurveillancestatus"),
            nullable=False,
        ),
        sa.Column("results_summary", sa.Text(), nullable=True),
        sa.Column(
            "medical_clearance_status",
            sa.Enum(
                "pending",
                "cleared",
                "restricted",
                "not_cleared",
                name="medicalclearancestatus",
            ),
            nullable=False,
        ),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_medical_surveillance_records_id"), "medical_surveillance_records", ["id"], unique=False)
    op.create_index(op.f("ix_medical_surveillance_records_employee_user_id"), "medical_surveillance_records", ["employee_user_id"], unique=False)
    op.create_index(op.f("ix_medical_surveillance_records_site_id"), "medical_surveillance_records", ["site_id"], unique=False)
    op.create_index(op.f("ix_medical_surveillance_records_status"), "medical_surveillance_records", ["status"], unique=False)

    op.create_table(
        "emergency_drills",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("emergency_type", sa.String(length=120), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("drill_date", sa.Date(), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("attendance_records", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("issues_found", sa.JSON(), nullable=False),
        sa.Column("corrective_actions", sa.JSON(), nullable=False),
        sa.Column("next_drill_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("scheduled", "completed", "overdue", "archived", name="emergencydrillstatus"),
            nullable=False,
        ),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_emergency_drills_id"), "emergency_drills", ["id"], unique=False)
    op.create_index(op.f("ix_emergency_drills_site_id"), "emergency_drills", ["site_id"], unique=False)
    op.create_index(op.f("ix_emergency_drills_status"), "emergency_drills", ["status"], unique=False)

    op.create_table(
        "document_control_records",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum("policy", "sop", "procedure", "form", name="documenttype"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_approval",
                "approved",
                "expired",
                "archived",
                name="documentstatus",
            ),
            nullable=False,
        ),
        sa.Column("acknowledgement_required", sa.Boolean(), nullable=False),
        sa.Column("acknowledgement_user_ids", sa.JSON(), nullable=False),
        sa.Column("supersedes_document_id", sa.Integer(), nullable=True),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_document_id"], ["document_control_records.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_document_control_records_id"), "document_control_records", ["id"], unique=False)
    op.create_index(op.f("ix_document_control_records_site_id"), "document_control_records", ["site_id"], unique=False)
    op.create_index(op.f("ix_document_control_records_document_type"), "document_control_records", ["document_type"], unique=False)
    op.create_index(op.f("ix_document_control_records_status"), "document_control_records", ["status"], unique=False)

    op.add_column(
        "compliance_acknowledgements",
        sa.Column("document_control_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_compliance_acknowledgements_document_control_id"),
        "compliance_acknowledgements",
        ["document_control_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_compliance_acknowledgements_document_control_id",
        "compliance_acknowledgements",
        "document_control_records",
        ["document_control_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "audit_management_records",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "audit_type",
            sa.Enum("internal", "external", "compliance", name="audittype"),
            nullable=False,
        ),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("auditor_user_id", sa.Integer(), nullable=False),
        sa.Column("audit_date", sa.Date(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("non_conformances", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="auditstatus"),
            nullable=False,
        ),
        sa.Column("audit_score", sa.Float(), nullable=True),
        sa.Column("corrective_action_ids", sa.JSON(), nullable=False),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["auditor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_audit_management_records_id"), "audit_management_records", ["id"], unique=False)
    op.create_index(op.f("ix_audit_management_records_site_id"), "audit_management_records", ["site_id"], unique=False)
    op.create_index(op.f("ix_audit_management_records_auditor_user_id"), "audit_management_records", ["auditor_user_id"], unique=False)
    op.create_index(op.f("ix_audit_management_records_audit_type"), "audit_management_records", ["audit_type"], unique=False)
    op.create_index(op.f("ix_audit_management_records_status"), "audit_management_records", ["status"], unique=False)

    op.create_table(
        "notification_delivery_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("notification_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", name="notificationdeliverychannel"),
            nullable=False,
        ),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "failed", "skipped", name="notificationdeliverystatus"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_notification_delivery_logs_id"), "notification_delivery_logs", ["id"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_notification_id"), "notification_delivery_logs", ["notification_id"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_recipient_user_id"), "notification_delivery_logs", ["recipient_user_id"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_channel"), "notification_delivery_logs", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_status"), "notification_delivery_logs", ["status"], unique=False)

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("job_name", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failed", name="jobrunstatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_job_runs_id"), "job_runs", ["id"], unique=False)
    op.create_index(op.f("ix_job_runs_job_name"), "job_runs", ["job_name"], unique=False)
    op.create_index(op.f("ix_job_runs_status"), "job_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_runs_status"), table_name="job_runs")
    op.drop_index(op.f("ix_job_runs_job_name"), table_name="job_runs")
    op.drop_index(op.f("ix_job_runs_id"), table_name="job_runs")
    op.drop_table("job_runs")

    op.drop_index(op.f("ix_notification_delivery_logs_status"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_channel"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_recipient_user_id"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_notification_id"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_id"), table_name="notification_delivery_logs")
    op.drop_table("notification_delivery_logs")

    op.drop_index(op.f("ix_audit_management_records_status"), table_name="audit_management_records")
    op.drop_index(op.f("ix_audit_management_records_audit_type"), table_name="audit_management_records")
    op.drop_index(op.f("ix_audit_management_records_auditor_user_id"), table_name="audit_management_records")
    op.drop_index(op.f("ix_audit_management_records_site_id"), table_name="audit_management_records")
    op.drop_index(op.f("ix_audit_management_records_id"), table_name="audit_management_records")
    op.drop_table("audit_management_records")

    op.drop_constraint("fk_compliance_acknowledgements_document_control_id", "compliance_acknowledgements", type_="foreignkey")
    op.drop_index(op.f("ix_compliance_acknowledgements_document_control_id"), table_name="compliance_acknowledgements")
    op.drop_column("compliance_acknowledgements", "document_control_id")

    op.drop_index(op.f("ix_document_control_records_status"), table_name="document_control_records")
    op.drop_index(op.f("ix_document_control_records_document_type"), table_name="document_control_records")
    op.drop_index(op.f("ix_document_control_records_site_id"), table_name="document_control_records")
    op.drop_index(op.f("ix_document_control_records_id"), table_name="document_control_records")
    op.drop_table("document_control_records")

    op.drop_index(op.f("ix_emergency_drills_status"), table_name="emergency_drills")
    op.drop_index(op.f("ix_emergency_drills_site_id"), table_name="emergency_drills")
    op.drop_index(op.f("ix_emergency_drills_id"), table_name="emergency_drills")
    op.drop_table("emergency_drills")

    op.drop_index(op.f("ix_medical_surveillance_records_status"), table_name="medical_surveillance_records")
    op.drop_index(op.f("ix_medical_surveillance_records_site_id"), table_name="medical_surveillance_records")
    op.drop_index(op.f("ix_medical_surveillance_records_employee_user_id"), table_name="medical_surveillance_records")
    op.drop_index(op.f("ix_medical_surveillance_records_id"), table_name="medical_surveillance_records")
    op.drop_table("medical_surveillance_records")

    op.drop_column("users", "phone_number")

    sa.Enum(name="jobrunstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationdeliverystatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationdeliverychannel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="auditstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audittype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="documentstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="documenttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="emergencydrillstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="medicalclearancestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="medicalsurveillancestatus").drop(op.get_bind(), checkfirst=True)
