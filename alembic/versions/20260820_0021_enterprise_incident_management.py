"""implement enterprise incident and investigation management

Revision ID: 20260820_0021
Revises: 20260814_0020
Create Date: 2026-08-20
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260820_0021"
down_revision = "20260814_0020"
branch_labels = None
depends_on = None


CLASSIFICATIONS = (
    ("near_miss", "Near Miss", False, False),
    ("first_aid_injury", "First Aid Injury", False, False),
    ("medical_treatment_injury", "Medical Treatment Injury", True, True),
    ("restricted_work_case", "Restricted Work Case", True, True),
    ("lost_time_injury", "Lost-Time Injury", True, True),
    ("occupational_illness", "Occupational Illness", True, True),
    ("fatality", "Fatality", True, True),
    ("property_damage", "Property Damage", False, False),
    ("environmental_incident", "Environmental Incident", False, False),
    ("vehicle_incident", "Vehicle Incident", False, False),
    ("fire_explosion", "Fire / Explosion", False, True),
    ("security_incident", "Security-Related Incident", False, False),
    ("dangerous_occurrence", "Dangerous Occurrence", False, True),
    ("other", "Other", False, False),
)

CAUSE_CATEGORIES = (
    ("unsafe_act", "Unsafe Act", "immediate"),
    ("unsafe_condition", "Unsafe Condition", "immediate"),
    ("equipment_failure", "Equipment Failure", "immediate"),
    ("procedural_failure", "Procedural Failure", "immediate"),
    ("environmental_condition", "Environmental Condition", "immediate"),
    ("inadequate_training", "Inadequate Training", "underlying"),
    ("inadequate_supervision", "Inadequate Supervision", "underlying"),
    ("poor_maintenance", "Poor Maintenance", "underlying"),
    ("risk_assessment_failure", "Risk Assessment Failure", "underlying"),
    ("procedure_inadequate", "Procedure Inadequate", "underlying"),
    ("communication_failure", "Communication Failure", "underlying"),
    ("resource_constraint", "Resource Constraint", "organisational"),
    ("procurement_design_issue", "Procurement / Design Issue", "organisational"),
    ("management_system_weakness", "Management System Weakness", "root"),
)

INCIDENT_KPIS = (
    ("total_incidents", "Total Incidents", "count"),
    ("near_misses", "Near Misses", "count"),
    ("first_aid_incidents", "First Aid Injuries", "count"),
    ("medical_treatment_incidents", "Medical Treatment Injuries", "count"),
    ("restricted_work_incidents", "Restricted Work Cases", "count"),
    ("lost_time_incidents", "Lost-Time Injuries", "count"),
    ("occupational_illness_incidents", "Occupational Illnesses", "count"),
    ("fatalities", "Fatalities", "count"),
    ("property_damage_incidents", "Property Damage Incidents", "count"),
    ("environmental_incidents", "Environmental Incidents", "count"),
    ("high_critical_incidents", "High / Critical Incidents", "count"),
    ("open_investigations", "Open Investigations", "count"),
    ("overdue_investigations", "Overdue Investigations", "count"),
    ("average_investigation_closure_days", "Average Investigation Closure Days", "days"),
    ("average_incident_closure_days", "Average Incident Closure Days", "days"),
    ("days_since_last_lti", "Days Since Last LTI", "days"),
    ("repeat_cause_categories", "Repeat Cause Categories", "count"),
)


def _json_default(empty: str) -> sa.TextClause:
    return sa.text(f"'{empty}'")


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _owned(*columns):
    return (
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        *columns,
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
    )


def _indexes(table: str, *columns: str) -> None:
    for column in ("organisation_id", *columns):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def _extend_postgres_enums(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in (
        "draft", "reported", "triaged", "under_investigation", "actions_open",
        "pending_closure", "cancelled", "reopened",
    ):
        op.execute(f"ALTER TYPE incidentstatus ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("not_required", "assigned", "pending_review", "completed"):
        op.execute(f"ALTER TYPE incidentinvestigationstatus ADD VALUE IF NOT EXISTS '{value}'")
    for value in (
        "investigator_assigned", "investigation_due", "investigation_overdue",
        "regulator_notification_due", "regulator_notification_overdue",
        "incident_closure_requested", "incident_closure_verification",
        "incident_closure_rejected", "incident_closed", "incident_reopened",
        "return_to_work_review_due",
    ):
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")


def _year(value) -> int:
    if value is not None and hasattr(value, "year"):
        return int(value.year)
    text = str(value or "")
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else datetime.now(timezone.utc).year


def upgrade() -> None:
    bind = op.get_bind()
    _extend_postgres_enums(bind)
    now = bind.execute(sa.select(sa.func.current_timestamp())).scalar_one()

    with op.batch_alter_table("organisation_settings") as batch:
        batch.add_column(sa.Column("incident_configuration", sa.JSON(), nullable=False, server_default=_json_default("{}")))

    with op.batch_alter_table("incidents") as batch:
        batch.add_column(sa.Column("incident_reference", sa.String(80), nullable=True))
        batch.add_column(sa.Column("source_external_id", sa.String(160), nullable=True))
        batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("area_location", sa.String(255), nullable=True))
        batch.add_column(sa.Column("incident_type", sa.String(80), nullable=False, server_default="other"))
        batch.add_column(sa.Column("potential_severity", sa.String(80), nullable=True))
        batch.add_column(sa.Column("actual_consequence", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("supervisor_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("responsible_hs_officer_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("immediate_actions_taken", sa.Text(), nullable=True))
        batch.add_column(sa.Column("immediate_response", sa.JSON(), nullable=False, server_default=_json_default("{}")))
        batch.add_column(sa.Column("immediate_response_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("scene_secured", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("work_stopped", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("emergency_services_called", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("regulator_notification_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("regulator_notification_status", sa.String(40), nullable=False, server_default="not_required"))
        batch.add_column(sa.Column("closure_requested_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("closure_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("closure_summary", sa.Text(), nullable=True))
        batch.add_column(sa.Column("closure_verifier_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("verification_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("lessons_learned", sa.JSON(), nullable=False, server_default=_json_default("{}")))
        batch.add_column(sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("reopened_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reopen_reason", sa.Text(), nullable=True))
        for column, table in (
            ("department_id", "departments"), ("supervisor_user_id", "users"),
            ("responsible_hs_officer_user_id", "users"), ("closure_requested_by_user_id", "users"),
            ("closure_verifier_user_id", "users"), ("reopened_by_user_id", "users"),
        ):
            batch.create_foreign_key(f"fk_incidents_{column}_{table}", table, [column], ["id"], ondelete="SET NULL")
        for column in (
            "incident_reference", "source_external_id", "department_id", "incident_type",
            "potential_severity", "occurred_at", "reported_by_id", "supervisor_user_id",
            "responsible_hs_officer_user_id", "regulator_notification_status",
        ):
            batch.create_index(op.f(f"ix_incidents_{column}"), [column], unique=False)

    incidents = sa.table(
        "incidents", sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("incident_reference", sa.String), sa.column("occurred_at", sa.DateTime(timezone=True)),
        sa.column("reported_at", sa.DateTime(timezone=True)), sa.column("created_at", sa.DateTime(timezone=True)),
    )
    settings = sa.table(
        "organisation_settings", sa.column("organisation_id", sa.Integer),
        sa.column("numbering_prefixes", sa.JSON), sa.column("incident_configuration", sa.JSON),
    )
    prefixes = {}
    for row in bind.execute(sa.select(settings)).all():
        config = row.incident_configuration or {}
        numbers = row.numbering_prefixes or {}
        raw = config.get("reference_prefix") or numbers.get("incident") or "INC"
        prefix = "".join(ch for ch in str(raw).upper() if ch.isalnum() or ch == "-").strip("-")[:20]
        prefixes[row.organisation_id] = prefix or "INC"
    counters = defaultdict(int)
    for row in bind.execute(sa.select(incidents).order_by(incidents.c.organisation_id, incidents.c.occurred_at, incidents.c.id)).all():
        year = _year(row.occurred_at or row.created_at)
        key = (row.organisation_id, year); counters[key] += 1
        reference = f"{prefixes.get(row.organisation_id, 'INC')}-{year}-{counters[key]:06d}"
        bind.execute(incidents.update().where(incidents.c.id == row.id).values(
            incident_reference=reference, reported_at=row.created_at,
        ))
    with op.batch_alter_table("incidents") as batch:
        batch.alter_column("incident_reference", existing_type=sa.String(80), nullable=False)
        batch.alter_column("reported_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_unique_constraint("uq_incidents_org_reference", ["organisation_id", "incident_reference"])

    op.create_table(
        "incident_reference_sequences",
        *_owned(sa.Column("year", sa.Integer(), nullable=False), sa.Column("last_value", sa.Integer(), nullable=False)),
        sa.UniqueConstraint("organisation_id", "year", name="uq_incident_reference_sequence_org_year"),
    )
    _indexes("incident_reference_sequences", "year")
    sequences = sa.table(
        "incident_reference_sequences", sa.column("organisation_id", sa.Integer),
        sa.column("year", sa.Integer), sa.column("last_value", sa.Integer),
    )
    if counters:
        bind.execute(sequences.insert(), [{"organisation_id": key[0], "year": key[1], "last_value": value} for key, value in counters.items()])

    with op.batch_alter_table("incident_investigations") as batch:
        batch.add_column(sa.Column("assigned_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("organisational_factors", sa.JSON(), nullable=False, server_default=_json_default("[]")))
        batch.add_column(sa.Column("scope", sa.Text(), nullable=True))
        batch.add_column(sa.Column("objectives", sa.Text(), nullable=True))
        batch.add_column(sa.Column("evidence_reviewed", sa.JSON(), nullable=False, server_default=_json_default("[]")))
        batch.add_column(sa.Column("persons_interviewed", sa.JSON(), nullable=False, server_default=_json_default("[]")))
        batch.add_column(sa.Column("scene_inspection", sa.JSON(), nullable=False, server_default=_json_default("{}")))
        batch.add_column(sa.Column("documents_reviewed", sa.JSON(), nullable=False, server_default=_json_default("[]")))
        batch.add_column(sa.Column("equipment_involved", sa.JSON(), nullable=False, server_default=_json_default("[]")))
        batch.add_column(sa.Column("investigation_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_incident_investigations_assigned_by_user_id_users", "users", ["assigned_by_user_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "incident_classifications",
        *_owned(
            sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("is_recordable", sa.Boolean(), nullable=False),
            sa.Column("investigation_required", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False), *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "code", name="uq_incident_classifications_org_code"),
    )
    _indexes("incident_classifications", "id", "code")
    op.create_table(
        "incident_cause_categories",
        *_owned(
            sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False),
            sa.Column("level", sa.String(40), nullable=False), sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("is_system", sa.Boolean(), nullable=False), *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "code", name="uq_incident_cause_categories_org_code"),
    )
    _indexes("incident_cause_categories", "id", "code", "level")

    organisations = sa.table("organisations", sa.column("id", sa.Integer))
    org_ids = list(bind.execute(sa.select(organisations.c.id)).scalars().all())
    classification_table = sa.table("incident_classifications", *[sa.column(x) for x in ("organisation_id", "code", "name", "description", "is_recordable", "investigation_required", "is_active", "is_system", "created_at", "updated_at")])
    cause_table = sa.table("incident_cause_categories", *[sa.column(x) for x in ("organisation_id", "code", "name", "level", "description", "is_active", "is_system", "created_at", "updated_at")])
    for org_id in org_ids:
        bind.execute(classification_table.insert(), [{"organisation_id": org_id, "code": code, "name": name, "description": None, "is_recordable": recordable, "investigation_required": required, "is_active": True, "is_system": True, "created_at": now, "updated_at": now} for code, name, recordable, required in CLASSIFICATIONS])
        bind.execute(cause_table.insert(), [{"organisation_id": org_id, "code": code, "name": name, "level": level, "description": None, "is_active": True, "is_system": True, "created_at": now, "updated_at": now} for code, name, level in CAUSE_CATEGORIES])

    op.create_table(
        "incident_people",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("contractor_id", sa.Integer(), nullable=True), sa.Column("external_person_reference", sa.String(160), nullable=True),
            sa.Column("external_name", sa.String(180), nullable=True), sa.Column("employee_number", sa.String(100), nullable=True),
            sa.Column("department_name", sa.String(180), nullable=True), sa.Column("job_title", sa.String(180), nullable=True),
            sa.Column("contact_details", sa.String(255), nullable=True), sa.Column("involvement_role", sa.String(60), nullable=False),
            sa.Column("statement_provided", sa.Boolean(), nullable=False), sa.Column("statement_reference", sa.String(255), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_people", "id", "incident_id", "user_id", "involvement_role")
    op.create_table(
        "incident_injuries",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("incident_person_id", sa.Integer(), nullable=False),
            sa.Column("injury_present", sa.Boolean(), nullable=False), sa.Column("illness_present", sa.Boolean(), nullable=False),
            sa.Column("body_part", sa.String(160), nullable=True), sa.Column("injury_type", sa.String(160), nullable=True),
            sa.Column("diagnosis_description", sa.Text(), nullable=True), sa.Column("treatment_required", sa.Boolean(), nullable=False),
            sa.Column("treatment_location", sa.String(255), nullable=True), sa.Column("treated_by", sa.String(180), nullable=True),
            sa.Column("hospital_referral", sa.Boolean(), nullable=False), sa.Column("admission_required", sa.Boolean(), nullable=False),
            sa.Column("days_lost", sa.Integer(), nullable=False), sa.Column("restricted_work_days", sa.Integer(), nullable=False),
            sa.Column("first_day_absent", sa.Date(), nullable=True), sa.Column("return_to_work_date", sa.Date(), nullable=True),
            sa.Column("permanent_disability", sa.Boolean(), nullable=False), sa.Column("fatality", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["incident_person_id"], ["incident_people.id"], ondelete="CASCADE"),
            sa.CheckConstraint("days_lost >= 0", name="ck_incident_injuries_days_lost"),
            sa.CheckConstraint("restricted_work_days >= 0", name="ck_incident_injuries_restricted_days"),
        ),
    )
    _indexes("incident_injuries", "id", "incident_id", "incident_person_id")
    op.create_table(
        "incident_treatments",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("incident_person_id", sa.Integer(), nullable=False),
            sa.Column("treatment_at", sa.DateTime(timezone=True), nullable=False), sa.Column("treatment_type", sa.String(80), nullable=False),
            sa.Column("provider_name", sa.String(180), nullable=True), sa.Column("treatment_summary", sa.Text(), nullable=True),
            sa.Column("referral", sa.Text(), nullable=True), sa.Column("medical_certificate_reference", sa.String(255), nullable=True),
            sa.Column("restrictions", sa.Text(), nullable=True), sa.Column("follow_up_required", sa.Boolean(), nullable=False),
            sa.Column("medical_surveillance_record_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["incident_person_id"], ["incident_people.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["medical_surveillance_record_id"], ["medical_surveillance_records.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_treatments", "id", "incident_id", "incident_person_id", "treatment_type")
    op.create_table(
        "incident_witness_statements",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("incident_person_id", sa.Integer(), nullable=True),
            sa.Column("witness_user_id", sa.Integer(), nullable=True), sa.Column("witness_name", sa.String(180), nullable=False),
            sa.Column("statement_at", sa.DateTime(timezone=True), nullable=False), sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("taken_by_user_id", sa.Integer(), nullable=True), sa.Column("acknowledged", sa.Boolean(), nullable=False),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True), sa.Column("acknowledgement_reference", sa.String(255), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["incident_person_id"], ["incident_people.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["witness_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["taken_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_witness_statements", "id", "incident_id")
    op.create_table(
        "incident_events",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("event_type", sa.String(80), nullable=False), sa.Column("description", sa.Text(), nullable=False),
            sa.Column("source_reference", sa.String(255), nullable=True), sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_events", "id", "incident_id", "event_at", "event_type")
    op.create_table(
        "incident_cause_analyses",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("investigation_id", sa.Integer(), nullable=True),
            sa.Column("cause_level", sa.String(40), nullable=False), sa.Column("category_code", sa.String(80), nullable=True),
            sa.Column("description", sa.Text(), nullable=False), sa.Column("methodology", sa.String(40), nullable=False),
            sa.Column("problem_statement", sa.Text(), nullable=True), sa.Column("why_steps", sa.JSON(), nullable=False),
            sa.Column("is_root_cause", sa.Boolean(), nullable=False), sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["investigation_id"], ["incident_investigations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_cause_analyses", "id", "incident_id", "investigation_id", "cause_level", "category_code")
    op.create_table(
        "incident_findings",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("investigation_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
            sa.Column("finding_type", sa.String(80), nullable=False), sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("evidence", sa.Text(), nullable=True), sa.Column("root_cause_id", sa.Integer(), nullable=True),
            sa.Column("action_required", sa.Boolean(), nullable=False), sa.Column("unified_action_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["investigation_id"], ["incident_investigations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["root_cause_id"], ["incident_cause_analyses.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["unified_action_id"], ["corrective_actions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_findings", "id", "incident_id", "finding_type", "unified_action_id")
    op.create_table(
        "incident_regulatory_notifications",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("notification_required", sa.Boolean(), nullable=False),
            sa.Column("regulator_name", sa.String(180), nullable=False), sa.Column("legal_basis_reference", sa.String(255), nullable=True),
            sa.Column("notification_deadline", sa.DateTime(timezone=True), nullable=True), sa.Column("status", sa.String(40), nullable=False),
            sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True), sa.Column("notified_by_user_id", sa.Integer(), nullable=True),
            sa.Column("regulator_reference", sa.String(255), nullable=True), sa.Column("evidence_reference", sa.String(255), nullable=True),
            sa.Column("follow_up_required", sa.Boolean(), nullable=False), sa.Column("notes", sa.Text(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["notified_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_regulatory_notifications", "id", "incident_id", "notification_deadline", "status")
    op.create_table(
        "incident_return_to_work",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("incident_person_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(40), nullable=False), sa.Column("medical_clearance_required", sa.Boolean(), nullable=False),
            sa.Column("clearance_received", sa.Boolean(), nullable=False), sa.Column("restrictions", sa.Text(), nullable=True),
            sa.Column("restriction_start", sa.Date(), nullable=True), sa.Column("restriction_end", sa.Date(), nullable=True),
            sa.Column("planned_return_date", sa.Date(), nullable=True), sa.Column("actual_return_date", sa.Date(), nullable=True),
            sa.Column("review_due_date", sa.Date(), nullable=True), sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("medical_surveillance_record_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["incident_person_id"], ["incident_people.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["medical_surveillance_record_id"], ["medical_surveillance_records.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("incident_id", "incident_person_id", name="uq_incident_rtw_person"),
    )
    _indexes("incident_return_to_work", "id", "incident_id", "incident_person_id", "status", "planned_return_date", "review_due_date")
    op.create_table(
        "incident_links",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("linked_entity_type", sa.String(60), nullable=False),
            sa.Column("linked_entity_id", sa.Integer(), nullable=False), sa.Column("involvement", sa.JSON(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("incident_id", "linked_entity_type", "linked_entity_id", name="uq_incident_links_entity"),
    )
    _indexes("incident_links", "id", "incident_id", "linked_entity_type", "linked_entity_id")
    op.create_table(
        "incident_property_damage",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("asset_id", sa.Integer(), nullable=True),
            sa.Column("property_name", sa.String(180), nullable=True), sa.Column("description", sa.Text(), nullable=False),
            sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=True), sa.Column("actual_cost", sa.Numeric(14, 2), nullable=True),
            sa.Column("insurance_claim", sa.Boolean(), nullable=False), sa.Column("claim_reference", sa.String(180), nullable=True),
            sa.Column("repair_status", sa.String(80), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["asset_register_items.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_property_damage", "id", "incident_id")
    op.create_table(
        "incident_environmental_details",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("spill_release", sa.Boolean(), nullable=False),
            sa.Column("material", sa.String(180), nullable=True), sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
            sa.Column("unit", sa.String(40), nullable=True), sa.Column("affected_area", sa.String(255), nullable=True),
            sa.Column("impact_media", sa.JSON(), nullable=False), sa.Column("containment", sa.Text(), nullable=True),
            sa.Column("cleanup", sa.Text(), nullable=True), sa.Column("estimated_environmental_severity", sa.String(80), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        ),
        sa.UniqueConstraint("incident_id", name="uq_incident_environmental_incident_id"),
    )
    _indexes("incident_environmental_details", "id", "incident_id")
    op.create_table(
        "incident_vehicle_details",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("vehicle_asset_id", sa.Integer(), nullable=True),
            sa.Column("driver_person_id", sa.Integer(), nullable=True), sa.Column("passenger_details", sa.JSON(), nullable=False),
            sa.Column("road_location", sa.String(255), nullable=True), sa.Column("third_party_details", sa.Text(), nullable=True),
            sa.Column("police_report_reference", sa.String(180), nullable=True), sa.Column("damage_details", sa.Text(), nullable=True),
            sa.Column("testing_status", sa.String(80), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["vehicle_asset_id"], ["asset_register_items.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["driver_person_id"], ["incident_people.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("incident_id", name="uq_incident_vehicle_incident_id"),
    )
    _indexes("incident_vehicle_details", "id", "incident_id")
    op.create_table(
        "incident_closure_history",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("decision", sa.String(40), nullable=False),
            sa.Column("requested_by_user_id", sa.Integer(), nullable=True), sa.Column("verifier_user_id", sa.Integer(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["verifier_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_closure_history", "id", "incident_id", "decision")
    op.create_table(
        "incident_activities",
        *_owned(
            sa.Column("incident_id", sa.Integer(), nullable=False), sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(80), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("incident_activities", "id", "incident_id", "event_type", "created_at")
    op.create_table(
        "incident_reminder_deliveries",
        *_owned(
            sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False), sa.Column("milestone_key", sa.String(80), nullable=False),
            sa.Column("due_date_snapshot", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        ),
        sa.UniqueConstraint("organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_incident_reminder_delivery"),
    )
    _indexes("incident_reminder_deliveries", "entity_type", "entity_id", "recipient_user_id", "milestone_key")

    kpis = sa.table("kpi_definitions", *[sa.column(name) for name in (
        "organisation_id", "key", "name", "description", "category", "unit", "calculation_method",
        "numerator_definition", "denominator_definition", "multiplier", "direction", "is_active",
        "version", "effective_from", "effective_to", "created_at", "updated_at",
    )])
    existing_keys = set(bind.execute(sa.select(kpis.c.key).where(kpis.c.key.in_([row[0] for row in INCIDENT_KPIS]))).scalars().all())
    rows = [{"organisation_id": None, "key": key, "name": name, "description": f"Incident management KPI for {name.lower()}.", "category": "Incidents", "unit": unit, "calculation_method": key, "numerator_definition": None, "denominator_definition": None, "multiplier": None, "direction": "lower_is_better" if unit != "days" or key != "days_since_last_lti" else "higher_is_better", "is_active": True, "version": 1, "effective_from": date(2026, 1, 1), "effective_to": None, "created_at": now, "updated_at": now} for key, name, unit in INCIDENT_KPIS if key not in existing_keys]
    if rows: bind.execute(kpis.insert(), rows)


def downgrade() -> None:
    bind = op.get_bind()
    kpis = sa.table("kpi_definitions", sa.column("key", sa.String))
    bind.execute(kpis.delete().where(kpis.c.key.in_([row[0] for row in INCIDENT_KPIS])))
    for table in (
        "incident_reminder_deliveries", "incident_activities", "incident_closure_history",
        "incident_vehicle_details", "incident_environmental_details", "incident_property_damage",
        "incident_links", "incident_return_to_work", "incident_regulatory_notifications",
        "incident_findings", "incident_cause_analyses", "incident_events",
        "incident_witness_statements", "incident_treatments", "incident_injuries",
        "incident_people", "incident_cause_categories", "incident_classifications",
        "incident_reference_sequences",
    ):
        op.drop_table(table)
    with op.batch_alter_table("incident_investigations") as batch:
        batch.drop_constraint("fk_incident_investigations_assigned_by_user_id_users", type_="foreignkey")
        for column in (
            "investigation_started_at", "equipment_involved", "documents_reviewed", "scene_inspection",
            "persons_interviewed", "evidence_reviewed", "objectives", "scope",
            "organisational_factors", "assigned_at", "assigned_by_user_id",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("incidents") as batch:
        batch.drop_constraint("uq_incidents_org_reference", type_="unique")
        for column in (
            "regulator_notification_status", "responsible_hs_officer_user_id", "supervisor_user_id",
            "reported_by_id", "occurred_at", "potential_severity", "incident_type", "department_id",
            "source_external_id", "incident_reference",
        ):
            try: batch.drop_index(op.f(f"ix_incidents_{column}"))
            except Exception: pass
        for column, table in (
            ("reopened_by_user_id", "users"), ("closure_verifier_user_id", "users"),
            ("closure_requested_by_user_id", "users"), ("responsible_hs_officer_user_id", "users"),
            ("supervisor_user_id", "users"), ("department_id", "departments"),
        ):
            batch.drop_constraint(f"fk_incidents_{column}_{table}", type_="foreignkey")
        for column in (
            "reopen_reason", "reopened_by_user_id", "reopened_at", "lessons_learned", "verified_at",
            "verification_notes", "closure_verifier_user_id", "closure_summary", "closure_requested_at",
            "closure_requested_by_user_id", "regulator_notification_status", "regulator_notification_required",
            "emergency_services_called", "work_stopped", "scene_secured", "immediate_response_notes",
            "immediate_response", "immediate_actions_taken", "responsible_hs_officer_user_id",
            "supervisor_user_id", "reported_at", "actual_consequence", "potential_severity",
            "incident_type", "area_location", "department_id", "source_external_id", "incident_reference",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("organisation_settings") as batch:
        batch.drop_column("incident_configuration")
