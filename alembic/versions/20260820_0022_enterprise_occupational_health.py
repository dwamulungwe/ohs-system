"""implement enterprise occupational health and medical surveillance

Revision ID: 20260820_0022
Revises: 20260820_0021
Create Date: 2026-08-20
"""

from datetime import date, datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260820_0022"
down_revision = "20260820_0021"
branch_labels = None
depends_on = None


PROGRAMMES = (
    ("PRE_EMPLOYMENT", "Pre-employment Medical", None, 365),
    ("PERIODIC", "Periodic Medical", 365, 365),
    ("EXIT", "Exit Medical", None, None),
    ("RETURN_TO_WORK", "Return-to-Work Assessment", None, 90),
    ("FITNESS_TO_WORK", "Fitness-to-Work", 365, 365),
    ("AUDIOMETRY", "Audiometry", 365, 365),
    ("SPIROMETRY", "Spirometry", 365, 365),
    ("VISION", "Vision Screening", 730, 730),
    ("RESPIRATORY", "Respiratory Surveillance", 365, 365),
    ("CHEMICAL", "Chemical Exposure Surveillance", 365, 365),
    ("BIOLOGICAL", "Biological Monitoring", 365, 365),
    ("MUSCULOSKELETAL", "Ergonomic / Musculoskeletal Surveillance", 365, 365),
    ("DRIVER", "Driver Medical", 365, 365),
    ("FOOD_HANDLER", "Food Handler Medical", 365, 365),
    ("WORK_AT_HEIGHT", "Working-at-Height Fitness", 365, 365),
    ("CONFINED_SPACE", "Confined-Space Fitness", 365, 365),
)

EXPOSURES = (
    ("NOISE", "Noise"), ("DUST", "Dust"), ("SILICA", "Silica"),
    ("CHEMICALS", "Chemicals"), ("BIOLOGICAL", "Biological hazards"),
    ("VIBRATION", "Vibration"), ("RADIATION", "Radiation"),
    ("HEAT", "Heat"), ("COLD", "Cold"), ("ERGONOMIC_LOAD", "Ergonomic load"),
    ("MANUAL_HANDLING", "Manual handling"),
    ("RESPIRATORY_SENSITIZERS", "Respiratory sensitizers"),
)

OH_KPIS = (
    ("medical_workers_requiring", "Workers Requiring Surveillance", "count", "informational"),
    ("medical_surveillance_compliant", "Surveillance Compliant", "count", "higher_is_better"),
    ("medical_surveillance_compliance_rate", "Surveillance Compliance Rate", "percent", "higher_is_better"),
    ("medical_assessments_due_30", "Assessments Due 30", "count", "lower_is_better"),
    ("medical_assessments_due_60", "Assessments Due 60", "count", "lower_is_better"),
    ("medical_assessments_due_90", "Assessments Due 90", "count", "lower_is_better"),
    ("medical_assessments_overdue", "Assessments Overdue", "count", "lower_is_better"),
    ("medical_certificates_expired", "Certificates Expired", "count", "lower_is_better"),
    ("medical_active_restrictions", "Active Restrictions", "count", "informational"),
    ("medical_rtw_reviews_due", "Return-to-Work Reviews Due", "count", "lower_is_better"),
    ("occupational_illness_suspected", "Occupational Illness Suspected", "count", "lower_is_better"),
    ("occupational_illness_confirmed", "Occupational Illness Confirmed", "count", "lower_is_better"),
    ("medical_missed_appointments", "Missed Medical Appointments", "count", "lower_is_better"),
    ("medical_average_completion_delay", "Average Surveillance Completion Delay", "days", "lower_is_better"),
)

DEFAULT_OH_CONFIGURATION = {
    "default_reminder_windows": [90, 60, 30, 7],
    "appointment_reminder_days": [7, 1],
    "certificate_expiry_reminders": [90, 60, 30, 7],
    "missed_appointment_escalation_count": 2,
    "provider_required": False,
    "restriction_review_reminder_days": 30,
    "return_to_work_review_required": True,
    "retention_days": None,
}


def _owned(*columns):
    return (
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        *columns,
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
    )


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _indexes(table: str, *columns: str) -> None:
    for column in ("organisation_id", *columns):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def _extend_postgres_enums(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in ("medical_assessment", "fitness_certificate", "occupational_illness", "clinic_encounter"):
        op.execute(f"ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("ALTER TYPE correctiveactionsourcetype ADD VALUE IF NOT EXISTS 'occupational_health'")


def upgrade() -> None:
    bind = op.get_bind()
    _extend_postgres_enums(bind)
    now = datetime.now(timezone.utc)

    with op.batch_alter_table("organisation_settings") as batch:
        batch.add_column(sa.Column("occupational_health_configuration", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    settings_table = sa.table(
        "organisation_settings",
        sa.column("occupational_health_configuration", sa.JSON()),
    )
    op.execute(settings_table.update().values(occupational_health_configuration=DEFAULT_OH_CONFIGURATION))

    op.create_table(
        "medical_surveillance_programmes",
        *_owned(
            sa.Column("name", sa.String(180), nullable=False), sa.Column("code", sa.String(80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("default_frequency_days", sa.Integer(), nullable=True), sa.Column("validity_period_days", sa.Integer(), nullable=True),
            sa.Column("reminder_windows", sa.JSON(), nullable=False), sa.Column("provider_requirements", sa.JSON(), nullable=False),
            sa.Column("evidence_required", sa.Boolean(), nullable=False), sa.Column("certificate_required", sa.Boolean(), nullable=False),
            sa.Column("risk_exposure_trigger", sa.Text(), nullable=True), sa.Column("confidentiality_classification", sa.String(40), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False), *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "code", name="uq_medical_programmes_org_code"),
    )
    _indexes("medical_surveillance_programmes", "id", "name", "code", "active")

    op.create_table(
        "occupational_exposure_types",
        *_owned(
            sa.Column("name", sa.String(160), nullable=False), sa.Column("code", sa.String(80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("default_risk_level", sa.String(40), nullable=True), sa.Column("is_system", sa.Boolean(), nullable=False), *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "code", name="uq_exposure_types_org_code"),
    )
    _indexes("occupational_exposure_types", "id", "code")

    op.create_table(
        "medical_providers",
        *_owned(
            sa.Column("name", sa.String(200), nullable=False), sa.Column("facility_name", sa.String(200), nullable=True),
            sa.Column("contact_name", sa.String(180), nullable=True), sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(80), nullable=True), sa.Column("address", sa.Text(), nullable=True),
            sa.Column("services", sa.JSON(), nullable=False), sa.Column("preferred_programme_ids", sa.JSON(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False), *_timestamps(),
        ),
        sa.UniqueConstraint("organisation_id", "name", name="uq_medical_providers_org_name"),
    )
    _indexes("medical_providers", "id", "name")

    op.create_table(
        "medical_surveillance_requirements",
        *_owned(
            sa.Column("programme_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(200), nullable=False),
            sa.Column("mandatory", sa.Boolean(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("job_title", sa.String(180), nullable=True), sa.Column("role_name", sa.String(80), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True), sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("hazard_id", sa.Integer(), nullable=True), sa.Column("exposure_type_id", sa.Integer(), nullable=True),
            sa.Column("jsa_id", sa.Integer(), nullable=True), sa.Column("ppe_item_id", sa.Integer(), nullable=True),
            sa.Column("task_activity", sa.String(255), nullable=True), sa.Column("contractor_category", sa.String(120), nullable=True),
            sa.Column("frequency_days", sa.Integer(), nullable=True), sa.Column("validity_period_days", sa.Integer(), nullable=True),
            sa.Column("rationale", sa.Text(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["programme_id"], ["medical_surveillance_programmes.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["exposure_type_id"], ["occupational_exposure_types.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["jsa_id"], ["job_safety_analyses.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["ppe_item_id"], ["ppe_items.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("medical_surveillance_requirements", "id", "programme_id", "job_title", "role_name", "department_id", "site_id", "hazard_id", "exposure_type_id", "jsa_id", "ppe_item_id")

    record_fks = (
        ("department_id", "departments"), ("programme_id", "medical_surveillance_programmes"),
        ("requirement_id", "medical_surveillance_requirements"), ("created_by_user_id", "users"),
    )
    with op.batch_alter_table("medical_surveillance_records") as batch:
        batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("programme_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("requirement_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("compliance_status", sa.String(40), nullable=False, server_default="pending_assessment"))
        batch.add_column(sa.Column("fitness_outcome", sa.String(40), nullable=True))
        batch.add_column(sa.Column("expiry_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("recurrence_days", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("follow_up_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("follow_up_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        for column, table in record_fks:
            batch.create_foreign_key(f"fk_medical_surveillance_records_{column}_{table}", table, [column], ["id"], ondelete="SET NULL")
        for column in ("department_id", "programme_id", "requirement_id", "compliance_status", "fitness_outcome", "expiry_date", "follow_up_date"):
            batch.create_index(op.f(f"ix_medical_surveillance_records_{column}"), [column], unique=False)

    op.create_table(
        "medical_appointments",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("surveillance_record_id", sa.Integer(), nullable=True),
            sa.Column("programme_id", sa.Integer(), nullable=False), sa.Column("provider_id", sa.Integer(), nullable=True),
            sa.Column("site_id", sa.Integer(), nullable=True), sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("location", sa.String(255), nullable=True), sa.Column("status", sa.String(40), nullable=False),
            sa.Column("rescheduled_from_id", sa.Integer(), nullable=True), sa.Column("cancellation_reason", sa.Text(), nullable=True),
            sa.Column("attendance_recorded_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["surveillance_record_id"], ["medical_surveillance_records.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["programme_id"], ["medical_surveillance_programmes.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["provider_id"], ["medical_providers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["rescheduled_from_id"], ["medical_appointments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("medical_appointments", "id", "worker_user_id", "surveillance_record_id", "programme_id", "provider_id", "site_id", "appointment_at", "status")

    op.create_table(
        "medical_assessments",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("surveillance_record_id", sa.Integer(), nullable=True),
            sa.Column("programme_id", sa.Integer(), nullable=False), sa.Column("appointment_id", sa.Integer(), nullable=True),
            sa.Column("incident_id", sa.Integer(), nullable=True), sa.Column("return_to_work_record_id", sa.Integer(), nullable=True),
            sa.Column("assessment_type", sa.String(120), nullable=False), sa.Column("assessment_date", sa.Date(), nullable=False),
            sa.Column("provider_id", sa.Integer(), nullable=True), sa.Column("provider_name", sa.String(200), nullable=True),
            sa.Column("clinician_name", sa.String(180), nullable=True), sa.Column("facility_name", sa.String(200), nullable=True),
            sa.Column("certificate_reference", sa.String(255), nullable=True), sa.Column("next_due_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=True), sa.Column("fitness_outcome", sa.String(40), nullable=False),
            sa.Column("operational_restrictions", sa.Text(), nullable=True), sa.Column("follow_up_required", sa.Boolean(), nullable=False),
            sa.Column("follow_up_date", sa.Date(), nullable=True), sa.Column("confidential_notes", sa.Text(), nullable=True),
            sa.Column("clinical_results", sa.JSON(), nullable=False), sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["surveillance_record_id"], ["medical_surveillance_records.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["programme_id"], ["medical_surveillance_programmes.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["appointment_id"], ["medical_appointments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["return_to_work_record_id"], ["incident_return_to_work.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["provider_id"], ["medical_providers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("medical_assessments", "id", "worker_user_id", "surveillance_record_id", "programme_id", "appointment_id", "incident_id", "return_to_work_record_id", "assessment_date", "provider_id", "next_due_date", "expiry_date", "fitness_outcome", "follow_up_date")

    op.create_table(
        "fitness_certificates",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("assessment_id", sa.Integer(), nullable=True),
            sa.Column("programme_id", sa.Integer(), nullable=False), sa.Column("provider_id", sa.Integer(), nullable=True),
            sa.Column("certificate_number", sa.String(160), nullable=False), sa.Column("issued_date", sa.Date(), nullable=False),
            sa.Column("expiry_date", sa.Date(), nullable=False), sa.Column("fitness_outcome", sa.String(40), nullable=False),
            sa.Column("operational_restrictions", sa.Text(), nullable=True), sa.Column("certificate_file_reference", sa.String(512), nullable=True),
            sa.Column("renewal_status", sa.String(40), nullable=False), sa.Column("replaced_by_certificate_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["assessment_id"], ["medical_assessments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["programme_id"], ["medical_surveillance_programmes.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["provider_id"], ["medical_providers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["replaced_by_certificate_id"], ["fitness_certificates.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("organisation_id", "certificate_number", name="uq_fitness_certificates_org_number"),
    )
    _indexes("fitness_certificates", "id", "worker_user_id", "assessment_id", "programme_id", "certificate_number", "expiry_date", "renewal_status")

    op.create_table(
        "work_restrictions",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("source_assessment_id", sa.Integer(), nullable=True),
            sa.Column("incident_id", sa.Integer(), nullable=True), sa.Column("return_to_work_record_id", sa.Integer(), nullable=True),
            sa.Column("restriction_type", sa.String(120), nullable=False), sa.Column("description", sa.Text(), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False), sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("permanent", sa.Boolean(), nullable=False), sa.Column("prohibited_activities", sa.JSON(), nullable=False),
            sa.Column("hours_shift_restriction", sa.String(255), nullable=True), sa.Column("lifting_limit_kg", sa.Integer(), nullable=True),
            sa.Column("ppe_requirement", sa.String(255), nullable=True), sa.Column("review_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(40), nullable=False), sa.Column("authorised_by_user_id", sa.Integer(), nullable=True),
            sa.Column("supersedes_restriction_id", sa.Integer(), nullable=True), sa.Column("removed_reason", sa.Text(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["source_assessment_id"], ["medical_assessments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["return_to_work_record_id"], ["incident_return_to_work.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["authorised_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["supersedes_restriction_id"], ["work_restrictions.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("work_restrictions", "id", "worker_user_id", "source_assessment_id", "incident_id", "return_to_work_record_id", "restriction_type", "effective_from", "effective_to", "review_date", "status", "supersedes_restriction_id")

    op.create_table(
        "worker_exposure_assignments",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("exposure_type_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.Integer(), nullable=True), sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("hazard_id", sa.Integer(), nullable=True), sa.Column("jsa_id", sa.Integer(), nullable=True),
            sa.Column("source_type", sa.String(60), nullable=False), sa.Column("source_reference", sa.String(255), nullable=True),
            sa.Column("risk_level", sa.String(40), nullable=True), sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True), sa.Column("triggered_programme_ids", sa.JSON(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["exposure_type_id"], ["occupational_exposure_types.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["hazard_id"], ["hazards.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["jsa_id"], ["job_safety_analyses.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("worker_exposure_assignments", "id", "worker_user_id", "exposure_type_id", "site_id", "department_id", "hazard_id", "jsa_id", "start_date", "end_date")

    op.create_table(
        "occupational_illness_cases",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True), sa.Column("illness_category", sa.String(160), nullable=False),
            sa.Column("status", sa.String(40), nullable=False), sa.Column("date_identified", sa.Date(), nullable=False),
            sa.Column("symptoms_summary", sa.Text(), nullable=True), sa.Column("diagnosis_detail", sa.Text(), nullable=True),
            sa.Column("exposure_assignment_ids", sa.JSON(), nullable=False), sa.Column("related_incident_id", sa.Integer(), nullable=True),
            sa.Column("provider_id", sa.Integer(), nullable=True), sa.Column("clinician_name", sa.String(180), nullable=True),
            sa.Column("regulator_notification_required", sa.Boolean(), nullable=False), sa.Column("regulator_notification_status", sa.String(60), nullable=True),
            sa.Column("work_restriction_ids", sa.JSON(), nullable=False), sa.Column("unified_action_ids", sa.JSON(), nullable=False),
            sa.Column("outcome", sa.Text(), nullable=True), sa.Column("confidential_notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["related_incident_id"], ["incidents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["provider_id"], ["medical_providers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("occupational_illness_cases", "id", "worker_user_id", "site_id", "department_id", "illness_category", "status", "date_identified", "related_incident_id")

    op.create_table(
        "occupational_clinic_encounters",
        *_owned(
            sa.Column("worker_user_id", sa.Integer(), nullable=False), sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("encounter_type", sa.String(80), nullable=False), sa.Column("encountered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("provider_id", sa.Integer(), nullable=True), sa.Column("operational_summary", sa.Text(), nullable=True),
            sa.Column("confidential_notes", sa.Text(), nullable=True), sa.Column("follow_up_required", sa.Boolean(), nullable=False),
            sa.Column("follow_up_date", sa.Date(), nullable=True), sa.Column("related_incident_id", sa.Integer(), nullable=True),
            sa.Column("assessment_id", sa.Integer(), nullable=True), sa.Column("created_by_user_id", sa.Integer(), nullable=True), *_timestamps(),
            sa.ForeignKeyConstraint(["worker_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["provider_id"], ["medical_providers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["related_incident_id"], ["incidents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assessment_id"], ["medical_assessments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        ),
    )
    _indexes("occupational_clinic_encounters", "id", "worker_user_id", "site_id", "encounter_type", "encountered_at", "follow_up_date")

    op.create_table(
        "medical_reminder_deliveries",
        *_owned(
            sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False), sa.Column("milestone_key", sa.String(80), nullable=False),
            sa.Column("due_date_snapshot", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        ),
        sa.UniqueConstraint("organisation_id", "entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_medical_reminder_delivery"),
    )
    _indexes("medical_reminder_deliveries", "entity_type", "entity_id", "recipient_user_id", "milestone_key")

    organisations = sa.table("organisations", sa.column("id", sa.Integer))
    programme_table = sa.table(
        "medical_surveillance_programmes",
        sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("name", sa.String), sa.column("code", sa.String), sa.column("description", sa.Text),
        sa.column("active", sa.Boolean), sa.column("default_frequency_days", sa.Integer),
        sa.column("validity_period_days", sa.Integer), sa.column("reminder_windows", sa.JSON),
        sa.column("provider_requirements", sa.JSON), sa.column("evidence_required", sa.Boolean),
        sa.column("certificate_required", sa.Boolean), sa.column("risk_exposure_trigger", sa.Text),
        sa.column("confidentiality_classification", sa.String), sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    exposure_table = sa.table("occupational_exposure_types", *[sa.column(name) for name in (
        "organisation_id", "name", "code", "description", "active", "default_risk_level", "is_system", "created_at", "updated_at",
    )])
    organisation_ids = list(bind.execute(sa.select(organisations.c.id)).scalars().all())
    for organisation_id in organisation_ids:
        bind.execute(programme_table.insert(), [{
            "organisation_id": organisation_id, "name": name, "code": code,
            "description": f"Standard occupational-health programme: {name}.", "active": True,
            "default_frequency_days": frequency, "validity_period_days": validity,
            "reminder_windows": [90, 60, 30, 7], "provider_requirements": {},
            "evidence_required": True, "certificate_required": True, "risk_exposure_trigger": None,
            "confidentiality_classification": "restricted_medical", "is_system": True,
            "created_at": now, "updated_at": now,
        } for code, name, frequency, validity in PROGRAMMES])
        bind.execute(exposure_table.insert(), [{
            "organisation_id": organisation_id, "name": name, "code": code, "description": None,
            "active": True, "default_risk_level": None, "is_system": True, "created_at": now, "updated_at": now,
        } for code, name in EXPOSURES])

    records = sa.table(
        "medical_surveillance_records",
        sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("employee_user_id", sa.Integer), sa.column("due_date", sa.Date),
        sa.column("completed_at", sa.DateTime(timezone=True)), sa.column("next_due_date", sa.Date),
        sa.column("programme_id", sa.Integer), sa.column("department_id", sa.Integer),
        sa.column("compliance_status", sa.String), sa.column("expiry_date", sa.Date),
        sa.column("recurrence_days", sa.Integer),
    )
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("department_id", sa.Integer))
    for organisation_id in organisation_ids:
        periodic_id = bind.execute(sa.select(programme_table.c.id).where(programme_table.c.organisation_id == organisation_id, programme_table.c.code == "PERIODIC")).scalar_one()
        bind.execute(records.update().where(records.c.organisation_id == organisation_id).values(programme_id=periodic_id, recurrence_days=365))
    rows = bind.execute(sa.select(
        records.c.id, records.c.employee_user_id, records.c.due_date,
        records.c.completed_at, records.c.next_due_date,
    )).mappings().all()
    for row in rows:
        department_id = bind.execute(sa.select(users.c.department_id).where(users.c.id == row["employee_user_id"])).scalar()
        next_due = row["next_due_date"]
        if row["completed_at"] and next_due:
            compliance = "overdue" if next_due < date.today() else "due_soon" if next_due <= date.today() + timedelta(days=90) else "compliant"
        else:
            compliance = "overdue" if row["completed_at"] is None and row["due_date"] and row["due_date"] < date.today() else "compliant" if row["completed_at"] else "pending_assessment"
        bind.execute(records.update().where(records.c.id == row["id"]).values(
            department_id=department_id, compliance_status=compliance, expiry_date=next_due,
        ))

    kpis = sa.table("kpi_definitions", *[sa.column(name) for name in (
        "organisation_id", "key", "name", "description", "category", "unit", "calculation_method",
        "numerator_definition", "denominator_definition", "multiplier", "direction", "is_active",
        "version", "effective_from", "effective_to", "created_at", "updated_at",
    )])
    existing = set(bind.execute(sa.select(kpis.c.key).where(kpis.c.key.in_([row[0] for row in OH_KPIS]))).scalars().all())
    values = [{
        "organisation_id": None, "key": key, "name": name,
        "description": f"Occupational-health KPI for {name.lower()}.", "category": "Occupational Health", "unit": unit,
        "calculation_method": key, "numerator_definition": None, "denominator_definition": None,
        "multiplier": None, "direction": direction, "is_active": True, "version": 1,
        "effective_from": date(2026, 1, 1), "effective_to": None, "created_at": now, "updated_at": now,
    } for key, name, unit, direction in OH_KPIS if key not in existing]
    if values: bind.execute(kpis.insert(), values)


def downgrade() -> None:
    bind = op.get_bind()
    kpis = sa.table(
        "kpi_definitions", sa.column("key", sa.String), sa.column("organisation_id", sa.Integer),
        sa.column("description", sa.Text),
    )
    bind.execute(kpis.delete().where(
        kpis.c.key.in_([row[0] for row in OH_KPIS]),
        kpis.c.organisation_id.is_(None),
        kpis.c.description.like("Occupational-health KPI for %"),
    ))
    for table in (
        "medical_reminder_deliveries", "occupational_clinic_encounters", "occupational_illness_cases",
        "worker_exposure_assignments", "work_restrictions", "fitness_certificates", "medical_assessments",
        "medical_appointments",
    ):
        op.drop_table(table)
    with op.batch_alter_table("medical_surveillance_records") as batch:
        for column in ("department_id", "programme_id", "requirement_id", "compliance_status", "fitness_outcome", "expiry_date", "follow_up_date"):
            batch.drop_index(op.f(f"ix_medical_surveillance_records_{column}"))
        for column, table in (
            ("department_id", "departments"), ("programme_id", "medical_surveillance_programmes"),
            ("requirement_id", "medical_surveillance_requirements"), ("created_by_user_id", "users"),
        ):
            batch.drop_constraint(f"fk_medical_surveillance_records_{column}_{table}", type_="foreignkey")
        for column in (
            "created_by_user_id", "follow_up_date", "follow_up_required", "recurrence_days", "expiry_date",
            "fitness_outcome", "compliance_status", "requirement_id", "programme_id", "department_id",
        ):
            batch.drop_column(column)
    for table in ("medical_surveillance_requirements", "medical_providers", "occupational_exposure_types", "medical_surveillance_programmes"):
        op.drop_table(table)
    with op.batch_alter_table("organisation_settings") as batch:
        batch.drop_column("occupational_health_configuration")
