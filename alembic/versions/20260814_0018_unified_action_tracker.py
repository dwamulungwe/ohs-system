"""implement the unified action tracker

Revision ID: 20260814_0018
Revises: 20260811_0017
Create Date: 2026-08-14
"""

from collections import defaultdict
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260814_0018"
down_revision = "20260811_0017"
branch_labels = None
depends_on = None


NEW_ACTION_STATUSES = (
    "draft",
    "assigned",
    "accepted",
    "completion_requested",
    "declined",
    "on_hold",
    "reopened",
)
NEW_ACTION_SOURCES = (
    "sio",
    "audit",
    "permit",
    "jsa",
    "training",
    "compliance",
    "contractor",
    "emergency_drill",
    "document_control",
    "ppe",
    "fleet",
    "environmental",
    "management_of_change",
)
NEW_NOTIFICATION_TYPES = (
    "action_assigned",
    "action_reassigned",
    "action_declined",
    "action_due_soon",
    "action_overdue",
    "action_escalation",
    "action_extension_requested",
    "action_extension_approved",
    "action_extension_rejected",
    "action_completion_requested",
    "action_verification_requested",
    "action_verification_rejected",
    "action_closed",
    "action_reopened",
    "action_recurring_generated",
)


def _postgres_add_enum_values(bind) -> None:
    if bind.dialect.name != "postgresql":
        return
    for value in NEW_ACTION_STATUSES:
        op.execute(f"ALTER TYPE correctiveactionstatus ADD VALUE IF NOT EXISTS '{value}'")
    for value in NEW_ACTION_SOURCES:
        op.execute(f"ALTER TYPE correctiveactionsourcetype ADD VALUE IF NOT EXISTS '{value}'")
    for value in NEW_NOTIFICATION_TYPES:
        op.execute(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'")


def _year(value) -> int:
    if value is not None:
        if hasattr(value, "year"):
            return int(value.year)
        text = str(value)
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return datetime.now(timezone.utc).year


def _backfill_references(bind) -> dict[tuple[int, int], int]:
    actions = sa.table(
        "corrective_actions",
        sa.column("id", sa.Integer),
        sa.column("organisation_id", sa.Integer),
        sa.column("action_reference", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    settings = sa.table(
        "organisation_settings",
        sa.column("organisation_id", sa.Integer),
        sa.column("numbering_prefixes", sa.JSON),
    )
    prefixes: dict[int, str] = {}
    for row in bind.execute(sa.select(settings)).all():
        raw = row.numbering_prefixes or {}
        value = raw.get("action", "ACT") if isinstance(raw, dict) else "ACT"
        value = "".join(
            character
            for character in str(value).upper()
            if character.isalnum() or character == "-"
        ).strip("-")[:20]
        prefixes[row.organisation_id] = value or "ACT"
    counters: dict[tuple[int, int], int] = defaultdict(int)
    rows = bind.execute(
        sa.select(actions).order_by(
            actions.c.organisation_id, actions.c.created_at, actions.c.id
        )
    ).all()
    for row in rows:
        year = _year(row.created_at)
        key = (row.organisation_id, year)
        counters[key] += 1
        reference = f"{prefixes.get(row.organisation_id, 'ACT')}-{year}-{counters[key]:06d}"
        bind.execute(
            actions.update()
            .where(actions.c.id == row.id)
            .values(action_reference=reference)
        )
    return dict(counters)


def _create_index_set(table_name: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(
            op.f(f"ix_{table_name}_{column}"), table_name, [column], unique=False
        )


def upgrade() -> None:
    bind = op.get_bind()
    _postgres_add_enum_values(bind)

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "action_workflow_configuration",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )

    recurrence_frequency = sa.Enum(
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "yearly",
        name="actionrecurrencefrequency",
        native_enum=False,
        length=40,
    )
    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.add_column(sa.Column("action_reference", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("acceptance_criteria", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("source_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(sa.Column("original_due_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("progress_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assigned_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completion_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completion_requested_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("assignment_decline_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reopen_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reopened_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cancellation_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("number_of_extensions", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("automation_suppressed", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("recurrence_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("recurrence_frequency", recurrence_frequency, nullable=True))
        batch_op.add_column(sa.Column("recurrence_interval", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("next_due_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("recurrence_end_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("recurrence_parent_action_id", sa.Integer(), nullable=True))
        batch_op.alter_column("site_id", existing_type=sa.Integer(), nullable=True)
        for column in (
            "assigned_by_user_id",
            "completion_requested_by_user_id",
            "reopened_by_user_id",
        ):
            batch_op.create_foreign_key(
                f"fk_corrective_actions_{column}_users",
                "users",
                [column],
                ["id"],
                ondelete="SET NULL",
            )
        batch_op.create_foreign_key(
            "fk_corrective_actions_recurrence_parent_action_id",
            "corrective_actions",
            ["recurrence_parent_action_id"],
            ["id"],
            ondelete="SET NULL",
        )
        for column in (
            "action_reference",
            "source_type",
            "source_id",
            "priority",
            "status",
            "due_date",
            "original_due_date",
            "assigned_by_user_id",
            "completion_requested_by_user_id",
            "reopened_by_user_id",
            "next_due_date",
            "recurrence_parent_action_id",
        ):
            batch_op.create_index(op.f(f"ix_corrective_actions_{column}"), [column], unique=False)

    op.execute(sa.text("UPDATE corrective_actions SET original_due_date = due_date WHERE original_due_date IS NULL"))
    op.execute(sa.text("UPDATE corrective_actions SET status = 'in_progress' WHERE status = 'overdue'"))
    op.execute(sa.text("UPDATE corrective_actions SET closed_at = verified_at WHERE status = 'closed' AND closed_at IS NULL"))
    counters = _backfill_references(bind)
    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.alter_column("action_reference", existing_type=sa.String(length=80), nullable=False)
        batch_op.create_unique_constraint(
            "uq_actions_org_action_reference", ["organisation_id", "action_reference"]
        )
        batch_op.create_unique_constraint(
            "uq_actions_org_recurrence_parent",
            ["organisation_id", "recurrence_parent_action_id"],
        )

    op.create_table(
        "action_reference_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organisation_id", "year", name="uq_action_sequences_org_year"),
    )
    _create_index_set("action_reference_sequences", ("id", "organisation_id", "year"))
    if counters:
        op.bulk_insert(
            sa.table(
                "action_reference_sequences",
                sa.column("organisation_id", sa.Integer),
                sa.column("year", sa.Integer),
                sa.column("last_value", sa.Integer),
            ),
            [
                {"organisation_id": key[0], "year": key[1], "last_value": value}
                for key, value in sorted(counters.items())
            ],
        )

    op.create_table(
        "action_contributors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("action_id", "user_id", name="uq_action_contributors_action_user"),
    )
    _create_index_set("action_contributors", ("id", "organisation_id", "action_id", "user_id"))

    op.create_table(
        "action_assignment_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("assignment_type", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _create_index_set("action_assignment_history", ("id", "organisation_id", "action_id", "owner_user_id", "assigned_by_user_id", "created_at"))

    task_status = sa.Enum("open", "in_progress", "completed", "cancelled", name="actiontaskstatus", native_enum=False, length=40)
    op.create_table(
        "action_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _create_index_set("action_tasks", ("id", "organisation_id", "action_id", "owner_user_id", "due_date", "status"))

    extension_status = sa.Enum("pending", "approved", "rejected", name="actionextensiondecisionstatus", native_enum=False, length=40)
    op.create_table(
        "action_extension_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("previous_due_date", sa.Date(), nullable=True),
        sa.Column("requested_due_date", sa.Date(), nullable=False),
        sa.Column("extension_reason", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_status", extension_status, nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _create_index_set("action_extension_requests", ("id", "organisation_id", "action_id", "requested_by_user_id", "requested_at", "decision_status", "decided_by_user_id"))

    op.create_table(
        "action_activities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _create_index_set("action_activities", ("id", "organisation_id", "action_id", "actor_user_id", "event_type", "created_at"))

    op.create_table(
        "action_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    _create_index_set("action_comments", ("id", "organisation_id", "action_id", "author_user_id", "created_at"))

    op.create_table(
        "action_reminder_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("organisation_id", sa.Integer(), nullable=False),
        sa.Column("action_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("milestone_key", sa.String(length=80), nullable=False),
        sa.Column("due_date_snapshot", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("action_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_action_reminder_delivery"),
    )
    _create_index_set("action_reminder_deliveries", ("id", "organisation_id", "action_id", "recipient_user_id", "milestone_key"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE notifications SET notification_type = 'corrective_action_due_soon' WHERE notification_type IN ('action_assigned', 'action_reassigned', 'action_due_soon', 'action_extension_approved', 'action_closed', 'action_recurring_generated')"))
    op.execute(sa.text("UPDATE notifications SET notification_type = 'corrective_action_overdue' WHERE notification_type IN ('action_declined', 'action_overdue', 'action_escalation', 'action_extension_requested', 'action_extension_rejected', 'action_completion_requested', 'action_verification_requested', 'action_verification_rejected', 'action_reopened')"))

    for table_name in (
        "action_reminder_deliveries",
        "action_comments",
        "action_activities",
        "action_extension_requests",
        "action_tasks",
        "action_assignment_history",
        "action_contributors",
        "action_reference_sequences",
    ):
        op.drop_table(table_name)

    op.execute(sa.text("UPDATE corrective_actions SET status = 'open' WHERE status IN ('draft', 'assigned', 'accepted', 'declined', 'on_hold', 'reopened')"))
    op.execute(sa.text("UPDATE corrective_actions SET status = 'pending_verification' WHERE status = 'completion_requested'"))
    # Revision 0015 already introduced SIO as a supported corrective-action
    # source, so retain both sides of that established link when rolling back
    # to 0017. Only source types introduced by this revision are normalised.
    op.execute(sa.text("UPDATE corrective_actions SET source_type = 'manual', source_id = NULL WHERE source_type IN ('audit', 'permit', 'jsa', 'training', 'compliance', 'contractor', 'emergency_drill', 'document_control', 'ppe', 'fleet', 'environmental', 'management_of_change')"))
    op.execute(sa.text("UPDATE corrective_actions SET site_id = (SELECT MIN(sites.id) FROM sites WHERE sites.organisation_id = corrective_actions.organisation_id) WHERE site_id IS NULL"))

    with op.batch_alter_table("corrective_actions") as batch_op:
        batch_op.drop_constraint("uq_actions_org_recurrence_parent", type_="unique")
        batch_op.drop_constraint("uq_actions_org_action_reference", type_="unique")
        for column in reversed((
            "action_reference", "source_type", "source_id", "priority", "status", "due_date",
            "original_due_date", "assigned_by_user_id", "completion_requested_by_user_id",
            "reopened_by_user_id", "next_due_date", "recurrence_parent_action_id",
        )):
            batch_op.drop_index(op.f(f"ix_corrective_actions_{column}"))
        batch_op.drop_constraint("fk_corrective_actions_recurrence_parent_action_id", type_="foreignkey")
        for column in ("reopened_by_user_id", "completion_requested_by_user_id", "assigned_by_user_id"):
            batch_op.drop_constraint(f"fk_corrective_actions_{column}_users", type_="foreignkey")
        for column in reversed((
            "action_reference", "acceptance_criteria", "source_metadata", "original_due_date",
            "progress_percent", "progress_notes", "assigned_by_user_id", "assigned_at", "accepted_at",
            "completion_requested_at", "completion_requested_by_user_id", "closed_at", "reopened_at",
            "cancelled_at", "assignment_decline_reason", "reopen_reason", "reopened_by_user_id",
            "cancellation_reason", "number_of_extensions", "automation_suppressed", "recurrence_enabled",
            "recurrence_frequency", "recurrence_interval", "next_due_date", "recurrence_end_date",
            "recurrence_parent_action_id",
        )):
            batch_op.drop_column(column)
        batch_op.alter_column("site_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("organisation_settings") as batch_op:
        batch_op.drop_column("action_workflow_configuration")
