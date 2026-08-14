from typing import Optional
from datetime import date, datetime, time, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction, CorrectiveActionStatus


def date_start(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def date_end(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def apply_date_filters(statement: Select, date_field, *, date_from: Optional[date], date_to: Optional[date]) -> Select:
    start_at = date_start(date_from)
    end_at = date_end(date_to)
    if start_at is not None:
        statement = statement.where(date_field >= start_at)
    if end_at is not None:
        statement = statement.where(date_field <= end_at)
    return statement


def paginate(db: Session, statement: Select, *, skip: int, limit: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    items = list(db.scalars(statement.offset(skip).limit(limit)).all())
    return items, total


def is_corrective_action_overdue(action: CorrectiveAction, *, today: Optional[date] = None) -> bool:
    today = today or date.today()
    if action.current_due_date is None:
        return False
    if action.lifecycle_status in {
        CorrectiveActionStatus.closed,
        CorrectiveActionStatus.cancelled,
        CorrectiveActionStatus.draft,
    }:
        return False
    return action.current_due_date < today


def apply_overdue_status(data: dict) -> None:
    """Compatibility no-op: overdue is derived and never a lifecycle state."""
    if data.get("status") == CorrectiveActionStatus.overdue:
        data["status"] = CorrectiveActionStatus.in_progress
