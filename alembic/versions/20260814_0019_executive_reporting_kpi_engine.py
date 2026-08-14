"""implement executive reporting and KPI engine

Revision ID: 20260814_0019
Revises: 20260814_0018
Create Date: 2026-08-14
"""

from datetime import date

from alembic import op
import sqlalchemy as sa


revision = "20260814_0019"
down_revision = "20260814_0018"
branch_labels = None
depends_on = None


KPI_GROUPS = {
    "SIO": (
        "sio_raised", "sio_positive", "sio_negative", "sio_open", "sio_overdue",
        "sio_high_urgent", "sio_closure_rate", "sio_on_time_closure_rate",
        "sio_average_closure_days",
    ),
    "Actions": (
        "action_open", "action_overdue", "action_overdue_rate", "action_due_7_days",
        "action_due_30_days", "action_high_critical_overdue", "action_awaiting_verification",
        "action_reopened", "action_extension_requests", "action_original_due_on_time_closure_rate",
        "action_current_due_on_time_closure_rate", "action_average_closure_days",
        "action_median_closure_days", "action_verification_rejection_rate",
    ),
    "Incidents": (
        "total_incidents", "near_miss_count", "first_aid_count", "medical_treatment_count",
        "restricted_work_count", "lost_time_injury_count", "occupational_illness_count",
        "fatality_count", "property_damage_count", "environmental_incident_count",
        "high_critical_incidents", "open_investigations", "overdue_investigations",
        "average_investigation_closure_days", "days_since_last_lti", "trir", "ltifr",
    ),
    "Risk & Hazards": (
        "open_hazards", "critical_hazards", "high_risk_hazards", "uncontrolled_hazards",
        "overdue_controls", "hazards_due_review", "new_hazards", "hazards_closed",
        "residual_high_risk_hazards",
    ),
    "Inspections": (
        "inspections_planned", "inspections_completed", "inspections_missed",
        "inspection_completion_rate", "inspection_findings", "critical_inspection_findings",
        "repeat_inspection_findings",
    ),
    "Audits": (
        "audits_planned", "audits_completed", "audit_completion_rate", "major_findings",
        "minor_findings", "open_audit_findings", "overdue_audit_findings",
        "repeat_audit_findings",
    ),
    "Training": (
        "training_required", "training_completed", "training_overdue", "training_expiring_30",
        "training_expiring_60", "training_expiring_90", "training_compliance_rate",
        "competency_gaps",
    ),
    "Permits & Compliance": (
        "active_permits", "permits_renewal_30", "permits_renewal_60", "permits_renewal_90",
        "expired_permits", "permit_renewal_started", "compliance_total", "compliance_compliant",
        "compliance_due_soon", "compliance_overdue", "compliance_rate",
    ),
}


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column], unique=False)


def _kpi_rows(now) -> list[dict]:
    percent_keys = {key for values in KPI_GROUPS.values() for key in values if key.endswith("_rate")}
    day_keys = {key for values in KPI_GROUPS.values() for key in values if "days" in key}
    lower_keys = {
        key
        for values in KPI_GROUPS.values()
        for key in values
        if any(token in key for token in ("overdue", "critical", "high_risk", "uncontrolled", "missed", "gap", "expired", "rejection", "incident", "injury", "illness", "fatality", "damage"))
    }
    higher_keys = {
        key for values in KPI_GROUPS.values() for key in values
        if key.endswith("closure_rate") or key.endswith("completion_rate") or key.endswith("compliance_rate") or key == "days_since_last_lti"
    }
    rows = []
    for category, keys in KPI_GROUPS.items():
        for key in keys:
            unit = "percent" if key in percent_keys else "days" if key in day_keys else "rate" if key in {"trir", "ltifr"} else "count"
            direction = "higher_is_better" if key in higher_keys else "lower_is_better" if key in lower_keys or key in {"trir", "ltifr"} else "informational"
            rows.append(
                {
                    "organisation_id": None,
                    "key": key,
                    "name": key.replace("_", " ").title().replace("Sio", "SIO").replace("Lti", "LTI").replace("Trir", "TRIR").replace("Ltifr", "LTIFR"),
                    "description": f"Period KPI for {key.replace('_', ' ')}.",
                    "category": category,
                    "unit": unit,
                    "calculation_method": key,
                    "numerator_definition": "Recordable incidents" if key == "trir" else "Lost-time injuries" if key == "ltifr" else None,
                    "denominator_definition": "Actual employee plus contractor hours worked" if key in {"trir", "ltifr"} else None,
                    "multiplier": 200000.0 if key == "trir" else 1000000.0 if key == "ltifr" else None,
                    "direction": direction,
                    "is_active": True,
                    "version": 1,
                    "effective_from": date(2026, 1, 1),
                    "effective_to": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return rows


def upgrade() -> None:
    bind = op.get_bind()
    now = sa.func.now()

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "reporting_configuration",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )

    organisations = sa.table("organisations", sa.column("id", sa.Integer))
    organisation_features = sa.table(
        "organisation_features",
        sa.column("organisation_id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("is_enabled", sa.Boolean),
        sa.column("configuration", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    existing_reporting_orgs = set(
        bind.execute(
            sa.select(organisation_features.c.organisation_id).where(organisation_features.c.key == "reporting")
        ).scalars().all()
    )
    for organisation_id in bind.execute(sa.select(organisations.c.id)).scalars().all():
        if organisation_id not in existing_reporting_orgs:
            bind.execute(
                organisation_features.insert().values(
                    organisation_id=organisation_id,
                    key="reporting",
                    is_enabled=True,
                    configuration={},
                    created_at=now,
                    updated_at=now,
                )
            )

    period_type = sa.Enum("monthly", "quarterly", "annual", "custom", name="reportingperiodtype", native_enum=False, length=30)
    period_status = sa.Enum("draft", "under_review", "approved", "locked", "reopened", name="reportingperiodstatus", native_enum=False, length=30)
    direction = sa.Enum("higher_is_better", "lower_is_better", "target_range", "informational", name="kpidirection", native_enum=False, length=40)
    snapshot_status = sa.Enum("good", "warning", "critical", "informational", "insufficient_data", name="kpisnapshotstatus", native_enum=False, length=30)

    op.create_table(
        "reporting_periods",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("period_type", period_type, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", period_status, nullable=False),
        sa.Column("prepared_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.Column("report_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("report_reference", sa.String(120), nullable=True),
        sa.Column("supersedes_period_id", sa.Integer(), nullable=True),
        sa.Column("restatement_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reopened_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_period_id"], ["reporting_periods.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organisation_id", "name", "period_type", "report_version", name="uq_reporting_period_org_name_type_version"),
    )
    _indexes("reporting_periods", "id", "organisation_id", "period_type", "start_date", "end_date", "status", "prepared_by_user_id", "reviewed_by_user_id", "approved_by_user_id", "reopened_by_user_id", "report_reference", "supersedes_period_id")

    op.create_table(
        "reporting_period_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("reporting_period_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporting_period_id"], ["reporting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _indexes("reporting_period_history", "id", "organisation_id", "reporting_period_id", "actor_user_id", "event_type", "created_at")

    op.create_table(
        "kpi_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("calculation_method", sa.String(120), nullable=False),
        sa.Column("numerator_definition", sa.Text(), nullable=True),
        sa.Column("denominator_definition", sa.Text(), nullable=True),
        sa.Column("multiplier", sa.Float(), nullable=True),
        sa.Column("direction", direction, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organisation_id", "key", "version", name="uq_kpi_definition_scope_key_version"),
    )
    _indexes("kpi_definitions", "id", "organisation_id", "key", "category", "is_active", "effective_from", "effective_to")
    kpi_table = sa.table(
        "kpi_definitions",
        *[sa.column(name) for name in (
            "organisation_id", "key", "name", "description", "category", "unit",
            "calculation_method", "numerator_definition", "denominator_definition", "multiplier",
            "direction", "is_active", "version", "effective_from", "effective_to", "created_at", "updated_at",
        )],
    )
    op.bulk_insert(kpi_table, _kpi_rows(bind.execute(sa.select(sa.func.current_timestamp())).scalar_one()))

    op.create_table(
        "organisation_kpi_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("kpi_key", sa.String(120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organisation_id", "kpi_key", name="uq_org_kpi_setting_key"),
    )
    _indexes("organisation_kpi_settings", "id", "organisation_id", "kpi_key")

    op.create_table(
        "kpi_targets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("kpi_definition_id", sa.Integer(), nullable=False),
        sa.Column("kpi_key", sa.String(120), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("warning_threshold", sa.Float(), nullable=True),
        sa.Column("critical_threshold", sa.Float(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["kpi_definition_id"], ["kpi_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _indexes("kpi_targets", "id", "organisation_id", "kpi_definition_id", "kpi_key", "site_id", "department_id", "effective_from", "effective_to")

    op.create_table(
        "workforce_exposures",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("employee_headcount", sa.Integer(), nullable=True),
        sa.Column("contractor_headcount", sa.Integer(), nullable=True),
        sa.Column("employee_hours_worked", sa.Float(), nullable=True),
        sa.Column("contractor_hours_worked", sa.Float(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _indexes("workforce_exposures", "id", "organisation_id", "site_id", "department_id", "period_start", "period_end")

    op.create_table(
        "kpi_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("reporting_period_id", sa.Integer(), nullable=False),
        sa.Column("kpi_definition_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("kpi_key", sa.String(120), nullable=False),
        sa.Column("kpi_name", sa.String(180), nullable=False),
        sa.Column("kpi_version", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("numerator", sa.Float(), nullable=True),
        sa.Column("denominator", sa.Float(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("status", snapshot_status, nullable=False),
        sa.Column("calculation_metadata", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporting_period_id"], ["reporting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kpi_definition_id"], ["kpi_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
    )
    _indexes("kpi_snapshots", "id", "organisation_id", "reporting_period_id", "kpi_definition_id", "site_id", "department_id", "kpi_key", "status", "generated_at")

    op.create_table(
        "report_sections",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("reporting_period_id", sa.Integer(), nullable=False),
        sa.Column("section_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporting_period_id"], ["reporting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reporting_period_id", "section_key", name="uq_report_section_period_key"),
    )
    _indexes("report_sections", "id", "organisation_id", "reporting_period_id", "section_key")

    op.create_table(
        "management_action_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("reporting_period_id", sa.Integer(), nullable=False),
        sa.Column("linked_action_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(30), nullable=False),
        sa.Column("issue_summary", sa.Text(), nullable=False),
        sa.Column("management_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporting_period_id"], ["reporting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_action_id"], ["corrective_actions.id"], ondelete="RESTRICT"),
    )
    _indexes("management_action_plan_items", "id", "organisation_id", "reporting_period_id", "linked_action_id")

    op.create_table(
        "report_exports",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("reporting_period_id", sa.Integer(), nullable=False),
        sa.Column("export_format", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("generated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporting_period_id"], ["reporting_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _indexes("report_exports", "id", "organisation_id", "reporting_period_id", "export_format", "generated_at")


def downgrade() -> None:
    bind = op.get_bind()
    organisation_features = sa.table(
        "organisation_features",
        sa.column("key", sa.String),
    )
    bind.execute(organisation_features.delete().where(organisation_features.c.key == "reporting"))

    for table_name in (
        "report_exports",
        "management_action_plan_items",
        "report_sections",
        "kpi_snapshots",
        "workforce_exposures",
        "kpi_targets",
        "organisation_kpi_settings",
        "kpi_definitions",
        "reporting_period_history",
        "reporting_periods",
    ):
        op.drop_table(table_name)

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.drop_column("reporting_configuration")
