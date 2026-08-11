"""enhance SIO operational workflow

Revision ID: 20260811_0017
Revises: 20260811_0016
Create Date: 2026-08-11
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260811_0017"
down_revision = "20260811_0016"
branch_labels = None
depends_on = None


NEW_SIO_STATUS_VALUES = ("assigned", "in_progress", "pending_verification", "closed", "reopened")
NEW_NOTIFICATION_TYPES = (
    "sio_assigned",
    "sio_reassigned",
    "sio_assignment_declined",
    "sio_due_soon",
    "sio_overdue",
    "sio_closure_requested",
    "sio_verification_required",
    "sio_reopened",
    "sio_urgent_high",
)


def _postgres_add_enum_values(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in NEW_SIO_STATUS_VALUES:
        op.execute(f"ALTER TYPE siostatus ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'sio'")
    op.execute("ALTER TYPE relatedentitytype ADD VALUE IF NOT EXISTS 'sio'")
    for value in NEW_NOTIFICATION_TYPES:
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")


def _year_from_row(row) -> int:
    for value in (row.observation_date, row.source_created_at, row.created_at):
        if value is None:
            continue
        if hasattr(value, "year"):
            return int(value.year)
        text = str(value)
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return datetime.now(timezone.utc).year


def _backfill_reference_numbers(bind) -> dict[tuple[int, int], int]:
    sio_table = sa.table(
        "safety_improvement_observations",
        sa.column("id", sa.Integer),
        sa.column("organisation_id", sa.Integer),
        sa.column("reference_number", sa.String),
        sa.column("observation_date", sa.Date),
        sa.column("source_created_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    settings_table = sa.table(
        "organisation_settings",
        sa.column("organisation_id", sa.Integer),
        sa.column("numbering_prefixes", sa.JSON),
    )
    prefixes: dict[int, str] = {}
    for row in bind.execute(sa.select(settings_table)).all():
        raw = row.numbering_prefixes or {}
        prefix = raw.get("sio", "SIO") if isinstance(raw, dict) else "SIO"
        sanitized = "".join(
            character for character in str(prefix).upper() if character.isalnum() or character == "-"
        ).strip("-")[:20]
        prefixes[row.organisation_id] = sanitized or "SIO"

    counters: dict[tuple[int, int], int] = defaultdict(int)
    rows = bind.execute(
        sa.select(sio_table).order_by(
            sio_table.c.organisation_id,
            sio_table.c.created_at,
            sio_table.c.id,
        )
    ).all()
    for row in rows:
        year = _year_from_row(row)
        key = (row.organisation_id, year)
        counters[key] += 1
        reference = f"{prefixes.get(row.organisation_id, 'SIO')}-{year}-{counters[key]:06d}"
        bind.execute(
            sio_table.update().where(sio_table.c.id == row.id).values(reference_number=reference)
        )
    return dict(counters)


def upgrade() -> None:
    bind = op.get_bind()
    _postgres_add_enum_values(bind)

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sio_workflow_configuration",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )

    with op.batch_alter_table("attachments") as batch_op:
        batch_op.add_column(sa.Column("evidence_type", sa.String(length=80), nullable=True))
        batch_op.create_index(op.f("ix_attachments_evidence_type"), ["evidence_type"], unique=False)

    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("responsible_department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_corrective_actions_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_corrective_actions_responsible_department_id_departments",
            "departments",
            ["responsible_department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_corrective_actions_department_id"), ["department_id"], unique=False)
        batch_op.create_index(
            op.f("ix_corrective_actions_responsible_department_id"),
            ["responsible_department_id"],
            unique=False,
        )

    assignment_status = sa.Enum(
        "unassigned",
        "assigned",
        "accepted",
        "declined",
        "reassigned",
        name="sioassignmentstatus",
        native_enum=False,
        length=40,
    )
    with op.batch_alter_table("safety_improvement_observations") as batch_op:
        batch_op.add_column(sa.Column("reference_number", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("responsible_department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("responsible_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assigned_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "assignment_status",
                assignment_status,
                nullable=False,
                server_default="unassigned",
            )
        )
        batch_op.add_column(sa.Column("assignment_decline_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("due_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("investigation_required", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("investigator_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("investigation_started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("investigation_completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("immediate_cause", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("underlying_cause", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("root_cause", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("contributing_factors", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch_op.add_column(sa.Column("investigation_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("lessons_learned", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("closure_requested_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("closure_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("closure_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("verified_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verification_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("no_action_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reopened_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reopen_reason", sa.Text(), nullable=True))

        for column, target in (
            ("department_id", "departments"),
            ("responsible_department_id", "departments"),
            ("responsible_user_id", "users"),
            ("assigned_by_user_id", "users"),
            ("investigator_user_id", "users"),
            ("closure_requested_by_user_id", "users"),
            ("verified_by_user_id", "users"),
            ("reopened_by_user_id", "users"),
        ):
            batch_op.create_foreign_key(
                f"fk_sios_{column}_{target}",
                target,
                [column],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                op.f(f"ix_safety_improvement_observations_{column}"), [column], unique=False
            )
        for column in ("reference_number", "assignment_status", "due_date"):
            batch_op.create_index(
                op.f(f"ix_safety_improvement_observations_{column}"), [column], unique=False
            )

    op.execute(
        sa.text(
            "UPDATE safety_improvement_observations "
            "SET responsible_user_id = responsible_person_user_id "
            "WHERE responsible_person_user_id IS NOT NULL"
        )
    )
    counters = _backfill_reference_numbers(bind)
    with op.batch_alter_table("safety_improvement_observations") as batch_op:
        batch_op.alter_column("reference_number", existing_type=sa.String(length=80), nullable=False)
        batch_op.create_unique_constraint(
            "uq_sios_org_reference_number", ["organisation_id", "reference_number"]
        )

    op.create_table(
        "sio_reference_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organisation_id", "year", name="uq_sio_sequences_org_year"),
    )
    for column in ("id", "organisation_id", "year"):
        op.create_index(
            op.f(f"ix_sio_reference_sequences_{column}"),
            "sio_reference_sequences",
            [column],
            unique=False,
        )
    sequence_table = sa.table(
        "sio_reference_sequences",
        sa.column("organisation_id", sa.Integer),
        sa.column("year", sa.Integer),
        sa.column("last_value", sa.Integer),
    )
    if counters:
        op.bulk_insert(
            sequence_table,
            [
                {"organisation_id": key[0], "year": key[1], "last_value": value}
                for key, value in sorted(counters.items())
            ],
        )

    op.create_table(
        "sio_activities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("sio_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sio_id"], ["safety_improvement_observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("id", "organisation_id", "sio_id", "actor_user_id", "event_type", "created_at"):
        op.create_index(op.f(f"ix_sio_activities_{column}"), "sio_activities", [column], unique=False)

    op.create_table(
        "sio_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("sio_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sio_id"], ["safety_improvement_observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("id", "organisation_id", "sio_id", "author_user_id", "created_at"):
        op.create_index(op.f(f"ix_sio_comments_{column}"), "sio_comments", [column], unique=False)


def downgrade() -> None:
    # Preserve conceptual state using values understood by the Phase 1A application.
    for new_status, legacy_status in (
        ("assigned", "assigned_to_responsible_person"),
        ("in_progress", "assigned_to_action_tracker"),
        ("pending_verification", "complete"),
        ("closed", "complete"),
        ("reopened", "open"),
    ):
        op.execute(
            sa.text(
                "UPDATE safety_improvement_observations SET status = :legacy "
                "WHERE status = :current"
            ).bindparams(legacy=legacy_status, current=new_status)
        )

    op.drop_table("sio_comments")
    op.drop_table("sio_activities")
    op.drop_table("sio_reference_sequences")

    with op.batch_alter_table("safety_improvement_observations") as batch_op:
        batch_op.drop_constraint("uq_sios_org_reference_number", type_="unique")
        for column in ("reference_number", "assignment_status", "due_date"):
            batch_op.drop_index(op.f(f"ix_safety_improvement_observations_{column}"))
        for column, target in reversed(
            (
                ("department_id", "departments"),
                ("responsible_department_id", "departments"),
                ("responsible_user_id", "users"),
                ("assigned_by_user_id", "users"),
                ("investigator_user_id", "users"),
                ("closure_requested_by_user_id", "users"),
                ("verified_by_user_id", "users"),
                ("reopened_by_user_id", "users"),
            )
        ):
            batch_op.drop_index(op.f(f"ix_safety_improvement_observations_{column}"))
            batch_op.drop_constraint(f"fk_sios_{column}_{target}", type_="foreignkey")
        for column in reversed(
            (
                "reference_number",
                "department_id",
                "responsible_department_id",
                "responsible_user_id",
                "assigned_by_user_id",
                "assigned_at",
                "assignment_status",
                "assignment_decline_reason",
                "due_date",
                "completed_at",
                "closed_at",
                "investigation_required",
                "investigator_user_id",
                "investigation_started_at",
                "investigation_completed_at",
                "immediate_cause",
                "underlying_cause",
                "root_cause",
                "contributing_factors",
                "investigation_summary",
                "lessons_learned",
                "closure_requested_by_user_id",
                "closure_requested_at",
                "closure_notes",
                "verified_by_user_id",
                "verified_at",
                "verification_notes",
                "no_action_reason",
                "reopened_by_user_id",
                "reopened_at",
                "reopen_reason",
            )
        ):
            batch_op.drop_column(column)

    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.drop_index(op.f("ix_corrective_actions_responsible_department_id"))
        batch_op.drop_index(op.f("ix_corrective_actions_department_id"))
        batch_op.drop_constraint(
            "fk_corrective_actions_responsible_department_id_departments", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_corrective_actions_department_id_departments", type_="foreignkey")
        batch_op.drop_column("responsible_department_id")
        batch_op.drop_column("department_id")

    with op.batch_alter_table("attachments") as batch_op:
        batch_op.drop_index(op.f("ix_attachments_evidence_type"))
        batch_op.drop_column("evidence_type")

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.drop_column("sio_workflow_configuration")
