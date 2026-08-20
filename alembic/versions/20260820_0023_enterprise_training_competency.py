"""implement enterprise training, competency and work authorization

Revision ID: 20260820_0023
Revises: 20260820_0022
Create Date: 2026-08-20
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260820_0023"
down_revision = "20260820_0022"
branch_labels = None
depends_on = None


DEFAULT_TRAINING_CONFIGURATION = {
    "default_reminder_windows": [90, 60, 30, 7],
    "refresher_automation": False,
    "certificate_verification_required": False,
    "assessment_required_by_training_type": {},
    "medical_prerequisite_enforcement": True,
    "ppe_prerequisite_enforcement": True,
    "permit_jsa_eligibility_enforcement": False,
    "authorization_approval_required": True,
    "competency_validity_default_days": 365,
}

DEFAULT_COURSES = (
    ("SITE_INDUCTION", "Site Induction", "induction", "induction", False, False, None),
    ("FIRST_AID", "First Aid", "emergency response", "emergency_response", True, True, 730),
    ("FIRE_WARDEN", "Fire Warden", "emergency response", "emergency_response", True, True, 365),
    ("WORK_AT_HEIGHT", "Working at Height", "safety training", "safety_training", True, True, 365),
    ("CONFINED_SPACE", "Confined Space Entry", "safety training", "safety_training", True, True, 365),
    ("FORKLIFT", "Forklift Operator", "equipment training", "equipment_training", True, True, 365),
    ("DEFENSIVE_DRIVING", "Defensive Driving", "equipment training", "equipment_training", True, True, 730),
    ("HOT_WORK", "Hot Work", "safety training", "safety_training", True, True, 365),
    ("PERMIT_ISSUER", "Permit Issuer", "compliance training", "compliance_training", True, False, 365),
    ("LOTO", "Lockout/Tagout", "technical", "safety_training", True, True, 365),
    ("RESPIRATOR_USE", "Respirator Use", "occupational health", "safety_training", True, True, 365),
    ("MANUAL_HANDLING", "Manual Handling", "occupational health", "safety_training", False, False, 365),
    ("CHEMICAL_HANDLING", "Chemical Handling", "technical", "safety_training", True, True, 365),
    ("SUPERVISOR_SAFETY", "Supervisor Safety Leadership", "supervisory", "safety_training", False, False, 730),
    ("INCIDENT_INVESTIGATION", "Incident Investigation", "supervisory", "safety_training", True, False, 730),
    ("RISK_ASSESSMENT", "Risk Assessment", "compliance training", "compliance_training", True, False, 730),
    ("JSA_TRAINING", "JSA Training", "compliance training", "compliance_training", True, False, 730),
)

DEFAULT_COMPETENCIES = (
    ("OPERATE_FORKLIFT", "Operate Forklift", "equipment", 365, True, ("FORKLIFT",)),
    ("WORK_AT_HEIGHT", "Work at Height", "high risk work", 365, True, ("WORK_AT_HEIGHT",)),
    ("ENTER_CONFINED_SPACE", "Enter Confined Space", "high risk work", 365, True, ("CONFINED_SPACE",)),
    ("ISSUE_PERMIT", "Issue Permit", "compliance", 365, False, ("PERMIT_ISSUER",)),
    ("CONDUCT_RISK_ASSESSMENT", "Conduct Risk Assessment", "compliance", 730, False, ("RISK_ASSESSMENT",)),
    ("PERFORM_INCIDENT_INVESTIGATION", "Perform Incident Investigation", "supervisory", 730, False, ("INCIDENT_INVESTIGATION",)),
    ("PERFORM_FIRST_AID", "Perform First Aid", "emergency response", 730, False, ("FIRST_AID",)),
    ("HANDLE_CHEMICALS", "Handle Chemicals", "technical", 365, True, ("CHEMICAL_HANDLING",)),
    ("USE_RESPIRATORY_PROTECTION", "Use Respiratory Protection", "occupational health", 365, True, ("RESPIRATOR_USE",)),
    ("APPLY_LOTO", "Apply Lockout/Tagout", "technical", 365, False, ("LOTO",)),
)

TRAINING_KPIS = (
    ("workers_requiring_training", "Workers Requiring Training", "count", "informational"),
    ("training_assignments_open", "Training Assignments Open", "count", "lower_is_better"),
    ("competencies_required", "Competencies Required", "count", "informational"),
    ("competency_compliance_rate", "Competency Compliance Rate", "percent", "higher_is_better"),
    ("competencies_expiring_30", "Competencies Expiring 30", "count", "lower_is_better"),
    ("competencies_expiring_60", "Competencies Expiring 60", "count", "lower_is_better"),
    ("competencies_expiring_90", "Competencies Expiring 90", "count", "lower_is_better"),
    ("expired_competencies", "Expired Competencies", "count", "lower_is_better"),
    ("certificates_expiring", "Certificates Expiring", "count", "lower_is_better"),
    ("authorizations_active", "Authorizations Active", "count", "informational"),
    ("authorizations_expired", "Authorizations Expired", "count", "lower_is_better"),
    ("workers_not_eligible", "Workers Not Eligible for Work", "count", "lower_is_better"),
    ("refresher_training_overdue", "Refresher Training Overdue", "count", "lower_is_better"),
    ("failed_assessments", "Failed Assessments", "count", "lower_is_better"),
    ("reassessment_backlog", "Reassessment Backlog", "count", "lower_is_better"),
)

NEW_TABLES = (
    "training_courses",
    "competencies",
    "contractor_workers",
    "course_competency_mappings",
    "training_requirements",
    "training_assignments",
    "training_sessions",
    "training_attendance",
    "training_assessments",
    "training_certificates",
    "competency_awards",
    "competency_status_events",
    "work_authorizations",
    "training_requests",
    "training_reminder_deliveries",
    "training_deficiency_links",
)

PHASE2D_INDEXES = {
    "training_courses": (
        "active", "category", "code", "id", "name", "organisation_id", "training_type",
    ),
    "competencies": (
        "active", "category", "code", "id", "name", "organisation_id",
    ),
    "contractor_workers": (
        "active", "category", "contractor_id", "external_reference", "full_name", "id",
        "job_title", "organisation_id", "site_id",
    ),
    "course_competency_mappings": (
        "competency_id", "course_id", "id", "organisation_id",
    ),
    "training_requirements": (
        "active", "authorization_type", "competency_id", "contractor_category", "course_id",
        "department_id", "equipment_category", "hazard_id", "id", "job_title", "jsa_id",
        "level", "organisation_id", "permit_type", "ppe_item_id", "role_name", "site_id",
        "task_activity",
    ),
    "training_assignments": (
        "assigned_user_id", "contractor_group", "contractor_worker_id", "course_id",
        "department_id", "due_date", "id", "job_title", "organisation_id",
        "refresher_for_assignment_id", "requirement_id", "role_name", "site_id", "source",
        "status", "team", "training_record_id",
    ),
    "training_sessions": (
        "course_id", "department_id", "id", "organisation_id", "site_id", "starts_at",
        "status", "trainer_user_id",
    ),
    "training_attendance": (
        "assignment_id", "contractor_worker_id", "id", "organisation_id", "session_id",
        "status", "worker_user_id",
    ),
    "training_assessments": (
        "assessment_date", "assessment_type", "assessor_user_id", "assignment_id",
        "competency_id", "contractor_worker_id", "course_id", "id", "organisation_id",
        "passed", "reassessment_due_date", "session_id", "training_record_id", "worker_user_id",
    ),
    "training_certificates": (
        "certificate_number", "competency_id", "contractor_worker_id", "course_id", "expiry_date",
        "id", "organisation_id", "training_record_id", "verification_status", "worker_user_id",
    ),
    "competency_awards": (
        "competency_id", "contractor_worker_id", "id", "organisation_id", "source_award_id",
        "status", "valid_until", "worker_user_id",
    ),
    "competency_status_events": (
        "competency_award_id", "new_status", "organisation_id",
    ),
    "work_authorizations": (
        "authorization_type", "competency_id", "contractor_worker_id", "department_id",
        "equipment_category", "id", "organisation_id", "site_id", "status",
        "supersedes_authorization_id", "task_activity", "valid_until", "worker_user_id",
    ),
    "training_requests": (
        "contractor_worker_id", "course_id", "id", "organisation_id", "requested_for_user_id",
        "requester_user_id", "resulting_assignment_id", "status",
    ),
    "training_reminder_deliveries": (
        "entity_id", "entity_type", "organisation_id", "recipient_user_id",
    ),
    "training_deficiency_links": (
        "competency_id", "corrective_action_id", "deficiency_type", "id", "incident_id",
        "organisation_id", "source_entity_id", "source_entity_type", "training_record_id",
        "worker_user_id",
    ),
}


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    return result[:60] or "HISTORICAL_TRAINING"


def _extend_postgres_enums(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in ("training_session", "training_assessment", "training_certificate", "work_authorization"):
        op.execute(f"ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS '{value}'")


def _phase2d_enum(*values: str, name: str, length: int) -> sa.Enum:
    """Return the frozen non-native enum representation used by Phase 2D."""
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=False,
        length=length,
    )


def _organisation_column() -> sa.Column:
    return sa.Column(
        "organisation_id",
        sa.Integer(),
        sa.ForeignKey("organisations.id", ondelete="RESTRICT"),
        nullable=False,
    )


def _timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_phase2d_catalogue_tables() -> None:
    """Create the frozen catalogue tables needed by the historical backfill."""
    op.create_table(
        "training_courses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column(
            "training_type",
            _phase2d_enum(
                "induction", "toolbox_talk", "safety_training", "equipment_training",
                "emergency_response", "compliance_training", "other",
                name="trainingtype", length=40,
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("provider_required", sa.Boolean(), nullable=False),
        sa.Column("assessment_required", sa.Boolean(), nullable=False),
        sa.Column("passing_score", sa.Float(), nullable=True),
        sa.Column("certificate_required", sa.Boolean(), nullable=False),
        sa.Column("default_validity_period_days", sa.Integer(), nullable=True),
        sa.Column("refresher_required", sa.Boolean(), nullable=False),
        sa.Column("default_refresher_interval_days", sa.Integer(), nullable=True),
        sa.Column("practical_component_required", sa.Boolean(), nullable=False),
        sa.Column("medical_clearance_required", sa.Boolean(), nullable=False),
        sa.Column("medical_programme_codes", sa.JSON(), nullable=False),
        sa.Column("ppe_prerequisite_required", sa.Boolean(), nullable=False),
        sa.Column("ppe_item_ids", sa.JSON(), nullable=False),
        sa.Column("reminder_windows", sa.JSON(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint("organisation_id", "code", name="uq_training_courses_org_code"),
    )

    op.create_table(
        "competencies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("evidence_requirements", sa.JSON(), nullable=False),
        sa.Column("assessment_rules", sa.JSON(), nullable=False),
        sa.Column("validity_period_days", sa.Integer(), nullable=True),
        sa.Column("renewal_rules", sa.JSON(), nullable=False),
        sa.Column("medical_prerequisite", sa.Boolean(), nullable=False),
        sa.Column("medical_programme_codes", sa.JSON(), nullable=False),
        sa.Column("ppe_prerequisite", sa.Boolean(), nullable=False),
        sa.Column("ppe_item_ids", sa.JSON(), nullable=False),
        sa.Column("supervisor_approval_required", sa.Boolean(), nullable=False),
        sa.Column("minimum_experience_days", sa.Integer(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint("organisation_id", "code", name="uq_competencies_org_code"),
    )

    op.create_table(
        "contractor_workers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_reference", sa.String(length=120), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=180), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("medical_clearance_status", sa.String(length=40), nullable=True),
        sa.Column("medical_clearance_expiry", sa.Date(), nullable=True),
        sa.Column("ppe_compliant", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint(
            "organisation_id", "contractor_id", "external_reference",
            name="uq_contractor_worker_reference",
        ),
    )


def _create_phase2d_remaining_tables() -> None:
    """Create the frozen dependent Phase 2D tables in foreign-key order."""
    op.create_table(
        "course_competency_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("contribution_weight", sa.Float(), nullable=True),
        sa.Column("completion_sufficient", sa.Boolean(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint(
            "organisation_id", "course_id", "competency_id",
            name="uq_course_competency_mapping",
        ),
    )

    op.create_table(
        "training_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("authorization_type", sa.String(length=160), nullable=True),
        sa.Column(
            "level",
            _phase2d_enum("mandatory", "recommended", name="requirementlevel", length=20),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("role_name", sa.String(length=80), nullable=True),
        sa.Column("job_title", sa.String(length=180), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        sa.Column("task_activity", sa.String(length=255), nullable=True),
        sa.Column("hazard_id", sa.Integer(), sa.ForeignKey("hazards.id", ondelete="SET NULL"), nullable=True),
        sa.Column("jsa_id", sa.Integer(), sa.ForeignKey("job_safety_analyses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("permit_type", sa.String(length=80), nullable=True),
        sa.Column("equipment_category", sa.String(length=120), nullable=True),
        sa.Column("contractor_category", sa.String(length=120), nullable=True),
        sa.Column("ppe_item_id", sa.Integer(), sa.ForeignKey("ppe_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("medical_programme_codes", sa.JSON(), nullable=False),
        sa.Column("mandatory_certificate", sa.Boolean(), nullable=False),
        sa.Column("assessment_required", sa.Boolean(), nullable=False),
        sa.Column("refresher_interval_days", sa.Integer(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role_name", sa.String(length=80), nullable=True),
        sa.Column("job_title", sa.String(length=180), nullable=True),
        sa.Column("team", sa.String(length=160), nullable=True),
        sa.Column("contractor_group", sa.String(length=160), nullable=True),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "priority",
            _phase2d_enum("low", "normal", "high", "critical", name="assignmentpriority", length=20),
            nullable=False,
        ),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("training_requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("training_record_id", sa.Integer(), sa.ForeignKey("training_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            _phase2d_enum(
                "assigned", "in_progress", "completed", "overdue", "cancelled",
                name="assignmentstatus", length=30,
            ),
            nullable=False,
        ),
        sa.Column(
            "refresher_for_assignment_id", sa.Integer(),
            sa.ForeignKey("training_assignments.id", ondelete="SET NULL"), nullable=True,
        ),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("trainer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "delivery_mode",
            _phase2d_enum("classroom", "practical", "online", "toolbox", "blended", name="deliverymode", length=30),
            nullable=False,
        ),
        sa.Column(
            "status",
            _phase2d_enum("planned", "scheduled", "completed", "cancelled", name="trainingsessionstatus", length=30),
            nullable=False,
        ),
        sa.Column("attachments_metadata", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_attendance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("training_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            _phase2d_enum(
                "invited", "attended", "absent", "partially_attended", "excused",
                name="attendancestatus", length=30,
            ),
            nullable=False,
        ),
        sa.Column("attendance_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance_recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("minutes_attended", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint(
            "organisation_id", "session_id", "worker_user_id",
            name="uq_attendance_session_worker",
        ),
        sa.UniqueConstraint(
            "organisation_id", "session_id", "contractor_worker_id",
            name="uq_attendance_session_contractor",
        ),
    )

    op.create_table(
        "training_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("training_record_id", sa.Integer(), sa.ForeignKey("training_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("training_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("training_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "assessment_type",
            _phase2d_enum(
                "theory", "practical", "observation", "oral", "competency_check",
                name="assessmenttype", length=30,
            ),
            nullable=False,
        ),
        sa.Column("assessor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("competency_demonstrated", sa.Boolean(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("reassessment_required", sa.Boolean(), nullable=False),
        sa.Column("reassessment_due_date", sa.Date(), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_certificates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("training_record_id", sa.Integer(), sa.ForeignKey("training_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("certificate_number", sa.String(length=160), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("provider", sa.String(length=200), nullable=True),
        sa.Column("certificate_file_reference", sa.String(length=512), nullable=True),
        sa.Column(
            "verification_status",
            _phase2d_enum("pending", "verified", "rejected", name="verificationstatus", length=30),
            nullable=False,
        ),
        sa.Column("verification_date", sa.Date(), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_snapshot", sa.JSON(), nullable=False),
        _organisation_column(),
        *_timestamp_columns(),
        sa.UniqueConstraint(
            "organisation_id", "certificate_number",
            name="uq_training_certificates_org_number",
        ),
    )

    op.create_table(
        "competency_awards",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("awarded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            _phase2d_enum(
                "competent", "conditionally_competent", "expired", "suspended", "revoked",
                "pending_assessment", name="competencyawardstatus", length=40,
            ),
            nullable=False,
        ),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("requirements_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_award_id", sa.Integer(), sa.ForeignKey("competency_awards.id", ondelete="SET NULL"), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "competency_status_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("competency_award_id", sa.Integer(), sa.ForeignKey("competency_awards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=True),
        _organisation_column(),
    )

    op.create_table(
        "work_authorizations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("authorization_type", sa.String(length=160), nullable=False),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_activity", sa.String(length=255), nullable=True),
        sa.Column("equipment_category", sa.String(length=120), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "status",
            _phase2d_enum("pending", "active", "expired", "suspended", "revoked", name="authorizationstatus", length=30),
            nullable=False,
        ),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prerequisites_snapshot", sa.JSON(), nullable=False),
        sa.Column("restrictions", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column(
            "supersedes_authorization_id", sa.Integer(),
            sa.ForeignKey("work_authorizations.id", ondelete="SET NULL"), nullable=True,
        ),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_for_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("contractor_worker_id", sa.Integer(), sa.ForeignKey("contractor_workers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "urgency",
            _phase2d_enum("low", "normal", "high", "critical", name="assignmentpriority", length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            _phase2d_enum(
                "requested", "reviewed", "approved", "assigned", "rejected",
                name="trainingrequeststatus", length=30,
            ),
            nullable=False,
        ),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("resulting_assignment_id", sa.Integer(), sa.ForeignKey("training_assignments.id", ondelete="SET NULL"), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
    )

    op.create_table(
        "training_reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_key", sa.String(length=80), nullable=False),
        sa.Column("due_date_snapshot", sa.Date(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        _organisation_column(),
        sa.UniqueConstraint(
            "organisation_id", "entity_type", "entity_id", "recipient_user_id",
            "milestone_key", "due_date_snapshot", name="uq_training_reminder_delivery",
        ),
    )

    op.create_table(
        "training_deficiency_links",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("deficiency_type", sa.String(length=80), nullable=False),
        sa.Column("source_entity_type", sa.String(length=80), nullable=True),
        sa.Column("source_entity_id", sa.Integer(), nullable=True),
        sa.Column("worker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competencies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("training_record_id", sa.Integer(), sa.ForeignKey("training_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("corrective_action_id", sa.Integer(), sa.ForeignKey("corrective_actions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        _organisation_column(),
        *_timestamp_columns(),
    )


def _create_phase2d_indexes() -> None:
    """Create the frozen set of indexes present when revision 0023 was authored."""
    for table_name, column_names in PHASE2D_INDEXES.items():
        for column_name in column_names:
            op.create_index(
                f"ix_{table_name}_{column_name}",
                table_name,
                [column_name],
                unique=False,
            )


def _seed_catalogue(bind, now: datetime) -> None:
    organisations = sa.table("organisations", sa.column("id", sa.Integer))
    courses = sa.table(
        "training_courses",
        sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("name", sa.String), sa.column("code", sa.String),
        sa.column("description", sa.Text), sa.column("category", sa.String),
        sa.column("training_type", sa.String), sa.column("active", sa.Boolean),
        sa.column("provider_required", sa.Boolean), sa.column("assessment_required", sa.Boolean),
        sa.column("passing_score", sa.Float), sa.column("certificate_required", sa.Boolean),
        sa.column("default_validity_period_days", sa.Integer), sa.column("refresher_required", sa.Boolean),
        sa.column("default_refresher_interval_days", sa.Integer), sa.column("practical_component_required", sa.Boolean),
        sa.column("medical_clearance_required", sa.Boolean), sa.column("medical_programme_codes", sa.JSON),
        sa.column("ppe_prerequisite_required", sa.Boolean), sa.column("ppe_item_ids", sa.JSON),
        sa.column("reminder_windows", sa.JSON), sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    competencies = sa.table(
        "competencies",
        sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("name", sa.String), sa.column("code", sa.String), sa.column("description", sa.Text),
        sa.column("category", sa.String), sa.column("active", sa.Boolean),
        sa.column("evidence_requirements", sa.JSON), sa.column("assessment_rules", sa.JSON),
        sa.column("validity_period_days", sa.Integer), sa.column("renewal_rules", sa.JSON),
        sa.column("medical_prerequisite", sa.Boolean), sa.column("medical_programme_codes", sa.JSON),
        sa.column("ppe_prerequisite", sa.Boolean), sa.column("ppe_item_ids", sa.JSON),
        sa.column("supervisor_approval_required", sa.Boolean), sa.column("minimum_experience_days", sa.Integer),
        sa.column("is_system", sa.Boolean), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    mappings = sa.table(
        "course_competency_mappings",
        sa.column("organisation_id", sa.Integer), sa.column("course_id", sa.Integer),
        sa.column("competency_id", sa.Integer), sa.column("required", sa.Boolean),
        sa.column("contribution_weight", sa.Float), sa.column("completion_sufficient", sa.Boolean),
        sa.column("sequence", sa.Integer), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for organisation_id in bind.execute(sa.select(organisations.c.id)).scalars():
        for code, name, category, training_type, assessment, certificate, validity in DEFAULT_COURSES:
            bind.execute(courses.insert().values(
                organisation_id=organisation_id, name=name, code=code, description=None,
                category=category, training_type=training_type, active=True,
                provider_required=False, assessment_required=assessment,
                passing_score=80.0 if assessment else None, certificate_required=certificate,
                default_validity_period_days=validity, refresher_required=bool(validity),
                default_refresher_interval_days=validity, practical_component_required=assessment,
                medical_clearance_required=code in {"WORK_AT_HEIGHT", "CONFINED_SPACE", "FORKLIFT", "RESPIRATOR_USE"},
                medical_programme_codes={
                    "WORK_AT_HEIGHT": ["WORK_AT_HEIGHT"], "CONFINED_SPACE": ["CONFINED_SPACE"],
                    "FORKLIFT": ["FITNESS_TO_WORK"], "RESPIRATOR_USE": ["RESPIRATORY"],
                }.get(code, []),
                ppe_prerequisite_required=code in {"WORK_AT_HEIGHT", "CONFINED_SPACE", "RESPIRATOR_USE"},
                ppe_item_ids=[], reminder_windows=[90, 60, 30, 7], is_system=True,
                created_at=now, updated_at=now,
            ))
        course_ids = dict(bind.execute(sa.select(courses.c.code, courses.c.id).where(courses.c.organisation_id == organisation_id)).all())
        for code, name, category, validity, medical, course_codes in DEFAULT_COMPETENCIES:
            competency_id = bind.execute(competencies.insert().values(
                organisation_id=organisation_id, name=name, code=code, description=None,
                category=category, active=True, evidence_requirements=[],
                assessment_rules={"required": True}, validity_period_days=validity,
                renewal_rules={"refresher_required": True}, medical_prerequisite=medical,
                medical_programme_codes={
                    "WORK_AT_HEIGHT": ["WORK_AT_HEIGHT"], "ENTER_CONFINED_SPACE": ["CONFINED_SPACE"],
                    "OPERATE_FORKLIFT": ["FITNESS_TO_WORK"], "USE_RESPIRATORY_PROTECTION": ["RESPIRATORY"],
                    "HANDLE_CHEMICALS": ["CHEMICAL"],
                }.get(code, []),
                ppe_prerequisite=code in {"WORK_AT_HEIGHT", "ENTER_CONFINED_SPACE", "USE_RESPIRATORY_PROTECTION"},
                ppe_item_ids=[], supervisor_approval_required=True, minimum_experience_days=None,
                is_system=True, created_at=now, updated_at=now,
            ).returning(competencies.c.id)).scalar_one()
            for sequence, course_code in enumerate(course_codes):
                bind.execute(mappings.insert().values(
                    organisation_id=organisation_id, course_id=course_ids[course_code],
                    competency_id=competency_id, required=True, contribution_weight=None,
                    completion_sufficient=False, sequence=sequence, created_at=now, updated_at=now,
                ))


def _backfill_history(bind, now: datetime) -> None:
    records = sa.table(
        "training_records",
        sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("course_id", sa.Integer), sa.column("title", sa.String),
        sa.column("training_type", sa.String), sa.column("site_id", sa.Integer),
        sa.column("assigned_to_user_id", sa.Integer), sa.column("assigned_by_user_id", sa.Integer),
        sa.column("due_date", sa.Date), sa.column("status", sa.String), sa.column("created_at", sa.DateTime(timezone=True)),
    )
    courses = sa.table(
        "training_courses", sa.column("id", sa.Integer), sa.column("organisation_id", sa.Integer),
        sa.column("name", sa.String), sa.column("code", sa.String), sa.column("description", sa.Text),
        sa.column("category", sa.String), sa.column("training_type", sa.String), sa.column("active", sa.Boolean),
        sa.column("provider_required", sa.Boolean), sa.column("assessment_required", sa.Boolean),
        sa.column("passing_score", sa.Float), sa.column("certificate_required", sa.Boolean),
        sa.column("default_validity_period_days", sa.Integer), sa.column("refresher_required", sa.Boolean),
        sa.column("default_refresher_interval_days", sa.Integer), sa.column("practical_component_required", sa.Boolean),
        sa.column("medical_clearance_required", sa.Boolean), sa.column("medical_programme_codes", sa.JSON),
        sa.column("ppe_prerequisite_required", sa.Boolean), sa.column("ppe_item_ids", sa.JSON),
        sa.column("reminder_windows", sa.JSON), sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    assignments = sa.table(
        "training_assignments", sa.column("organisation_id", sa.Integer), sa.column("course_id", sa.Integer),
        sa.column("assigned_user_id", sa.Integer), sa.column("contractor_worker_id", sa.Integer),
        sa.column("department_id", sa.Integer), sa.column("site_id", sa.Integer), sa.column("role_name", sa.String),
        sa.column("job_title", sa.String), sa.column("team", sa.String), sa.column("contractor_group", sa.String),
        sa.column("assigned_by_user_id", sa.Integer), sa.column("assigned_at", sa.DateTime(timezone=True)),
        sa.column("due_date", sa.Date), sa.column("priority", sa.String), sa.column("mandatory", sa.Boolean),
        sa.column("reason", sa.Text), sa.column("source", sa.String), sa.column("requirement_id", sa.Integer),
        sa.column("training_record_id", sa.Integer), sa.column("status", sa.String),
        sa.column("refresher_for_assignment_id", sa.Integer), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    existing = defaultdict(set)
    for org_id, code in bind.execute(sa.select(courses.c.organisation_id, courses.c.code)):
        existing[org_id].add(code)
    course_by_name = {(org, name.casefold()): course_id for org, name, course_id in bind.execute(sa.select(courses.c.organisation_id, courses.c.name, courses.c.id))}
    for row in bind.execute(sa.select(records)).mappings():
        key = (row["organisation_id"], row["title"].casefold())
        course_id = course_by_name.get(key)
        if course_id is None:
            base = f"HIST_{_slug(row['title'])}"
            code = base
            suffix = 2
            while code in existing[row["organisation_id"]]:
                code = f"{base[:55]}_{suffix}"
                suffix += 1
            course_id = bind.execute(courses.insert().values(
                organisation_id=row["organisation_id"], name=row["title"], code=code,
                description="Backfilled from historical TrainingRecord data.", category="historical",
                training_type=row["training_type"], active=True, provider_required=False,
                assessment_required=False, passing_score=None, certificate_required=False,
                default_validity_period_days=None, refresher_required=False,
                default_refresher_interval_days=None, practical_component_required=False,
                medical_clearance_required=False, medical_programme_codes=[],
                ppe_prerequisite_required=False, ppe_item_ids=[], reminder_windows=[90, 60, 30, 7],
                is_system=False, created_at=now, updated_at=now,
            ).returning(courses.c.id)).scalar_one()
            course_by_name[key] = course_id
            existing[row["organisation_id"]].add(code)
        bind.execute(records.update().where(records.c.id == row["id"]).values(course_id=course_id))
        status_value = getattr(row["status"], "value", row["status"])
        assignment_status = status_value if status_value in {"assigned", "in_progress", "completed", "overdue", "cancelled"} else "completed" if status_value == "expired" else "assigned"
        bind.execute(assignments.insert().values(
            organisation_id=row["organisation_id"], course_id=course_id,
            assigned_user_id=row["assigned_to_user_id"], contractor_worker_id=None,
            department_id=None, site_id=row["site_id"], role_name=None, job_title=None,
            team=None, contractor_group=None, assigned_by_user_id=row["assigned_by_user_id"],
            assigned_at=row["created_at"] or now, due_date=row["due_date"], priority="normal",
            mandatory=True, reason="Backfilled from historical TrainingRecord", source="historical_backfill",
            requirement_id=None, training_record_id=row["id"], status=assignment_status,
            refresher_for_assignment_id=None, created_at=row["created_at"] or now, updated_at=now,
        ))


def _seed_kpis(bind, now: datetime) -> None:
    definitions = sa.table(
        "kpi_definitions",
        sa.column("organisation_id", sa.Integer), sa.column("key", sa.String),
        sa.column("name", sa.String), sa.column("description", sa.Text),
        sa.column("category", sa.String), sa.column("unit", sa.String),
        sa.column("calculation_method", sa.String), sa.column("numerator_definition", sa.Text),
        sa.column("denominator_definition", sa.Text), sa.column("multiplier", sa.Float),
        sa.column("direction", sa.String), sa.column("is_active", sa.Boolean),
        sa.column("version", sa.Integer), sa.column("effective_from", sa.Date),
        sa.column("effective_to", sa.Date), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    existing = set(bind.execute(sa.select(definitions.c.key).where(definitions.c.organisation_id.is_(None))).scalars())
    for key, name, unit, direction in TRAINING_KPIS:
        if key in existing:
            continue
        bind.execute(definitions.insert().values(
            organisation_id=None, key=key, name=name,
            description=f"Enterprise training and competency KPI for {name.lower()}.",
            category="Training", unit=unit, calculation_method=key,
            numerator_definition=None, denominator_definition=None, multiplier=None,
            direction=direction, is_active=True, version=1,
            effective_from=date(2026, 1, 1), effective_to=None,
            created_at=now, updated_at=now,
        ))


def upgrade() -> None:
    bind = op.get_bind()
    _extend_postgres_enums(bind)
    now = datetime.now(timezone.utc)

    with op.batch_alter_table("organisation_settings") as batch:
        batch.add_column(sa.Column("training_configuration", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    settings = sa.table("organisation_settings", sa.column("training_configuration", sa.JSON))
    op.execute(settings.update().values(training_configuration=DEFAULT_TRAINING_CONFIGURATION))

    # Catalogue tables must exist before the historical record FK is added.
    # The remaining tables and every index are also declared locally above so
    # this historical revision cannot drift with future application models.
    _create_phase2d_catalogue_tables()

    with op.batch_alter_table("training_records") as batch:
        batch.add_column(sa.Column("course_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_training_records_course_id_training_courses", "training_courses", ["course_id"], ["id"], ondelete="SET NULL")
        batch.create_index(op.f("ix_training_records_course_id"), ["course_id"], unique=False)

    _create_phase2d_remaining_tables()
    _create_phase2d_indexes()

    with op.batch_alter_table("job_safety_analyses") as batch:
        for name in ("required_course_ids", "required_competency_ids", "required_authorization_types", "required_ppe_item_ids", "required_medical_programme_codes"):
            batch.add_column(sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("eligibility_enforcement_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("permits_to_work") as batch:
        batch.add_column(sa.Column("required_worker_user_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("required_contractor_worker_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("eligibility_enforcement_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("eligibility_validation", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    _seed_catalogue(bind, now)
    _backfill_history(bind, now)
    _seed_kpis(bind, now)


def downgrade() -> None:
    bind = op.get_bind()
    kpis = sa.table("kpi_definitions", sa.column("organisation_id", sa.Integer), sa.column("key", sa.String))
    bind.execute(kpis.delete().where(kpis.c.organisation_id.is_(None), kpis.c.key.in_([item[0] for item in TRAINING_KPIS])))

    for table_name in reversed(NEW_TABLES[3:]):
        op.drop_table(table_name)

    with op.batch_alter_table("training_records") as batch:
        batch.drop_index(op.f("ix_training_records_course_id"))
        batch.drop_constraint("fk_training_records_course_id_training_courses", type_="foreignkey")
        batch.drop_column("course_id")

    op.drop_table("contractor_workers")
    op.drop_table("competencies")
    op.drop_table("training_courses")

    with op.batch_alter_table("job_safety_analyses") as batch:
        batch.drop_column("eligibility_enforcement_enabled")
        for name in reversed(("required_course_ids", "required_competency_ids", "required_authorization_types", "required_ppe_item_ids", "required_medical_programme_codes")):
            batch.drop_column(name)

    with op.batch_alter_table("permits_to_work") as batch:
        batch.drop_column("eligibility_validation")
        batch.drop_column("eligibility_enforcement_enabled")
        batch.drop_column("required_contractor_worker_ids")
        batch.drop_column("required_worker_user_ids")

    with op.batch_alter_table("organisation_settings") as batch:
        batch.drop_column("training_configuration")
