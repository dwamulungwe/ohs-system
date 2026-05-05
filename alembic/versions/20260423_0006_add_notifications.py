"""add notifications

Revision ID: 20260423_0006
Revises: 20260423_0005
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_0006"
down_revision = "20260423_0005"
branch_labels = None
depends_on = None

notification_type = sa.Enum(
    "corrective_action_due_soon",
    "corrective_action_overdue",
    "critical_hazard_created",
    "critical_incident_created",
    "inspection_assigned",
    "inspection_due_soon",
    "action_pending_verification",
    name="notificationtype",
)
notification_severity = sa.Enum("info", "warning", "critical", name="notificationseverity")
related_entity_type = sa.Enum("incident", "hazard", "inspection", "corrective_action", name="relatedentitytype")


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("severity", notification_severity, nullable=False),
        sa.Column("related_entity_type", related_entity_type, nullable=False),
        sa.Column("related_entity_id", sa.Integer(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_recipient_user_id"), "notifications", ["recipient_user_id"], unique=False)
    op.create_index(op.f("ix_notifications_notification_type"), "notifications", ["notification_type"], unique=False)
    op.create_index(op.f("ix_notifications_severity"), "notifications", ["severity"], unique=False)
    op.create_index(op.f("ix_notifications_related_entity_type"), "notifications", ["related_entity_type"], unique=False)
    op.create_index(op.f("ix_notifications_related_entity_id"), "notifications", ["related_entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_related_entity_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_related_entity_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_severity"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_notification_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_recipient_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")

    bind = op.get_bind()
    related_entity_type.drop(bind, checkfirst=True)
    notification_severity.drop(bind, checkfirst=True)
    notification_type.drop(bind, checkfirst=True)
