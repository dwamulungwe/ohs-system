from __future__ import annotations

from typing import Optional
from datetime import date, datetime, time, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.safety_kpi import SafetyKPIRecord
from app.models.site import Site
from app.schemas.safety_kpi import SafetyKPICreate, SafetyKPIUpdate
from app.services.audit_service import write_audit_log
from app.services.query_utils import paginate

TRIFR_LTIFR_MULTIPLIER = 1_000_000


class SafetyKPIServiceError(Exception):
    pass


class SafetyKPINotFoundError(SafetyKPIServiceError):
    pass


class SafetyKPISiteNotFoundError(SafetyKPIServiceError):
    pass


class SafetyKPIDuplicatePeriodError(SafetyKPIServiceError):
    pass


def _period_boundary(value: date, *, end_of_day: bool) -> datetime:
    return datetime.combine(
        value,
        time.max if end_of_day else time.min,
        tzinfo=timezone.utc,
    )


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise SafetyKPISiteNotFoundError(f"Site {site_id} was not found")


def _ensure_unique_period(
    db: Session,
    *,
    site_id: int,
    period_start: date,
    period_end: date,
    exclude_id: Optional[int] = None,
) -> None:
    statement = select(SafetyKPIRecord).where(
        SafetyKPIRecord.site_id == site_id,
        SafetyKPIRecord.period_start == period_start,
        SafetyKPIRecord.period_end == period_end,
    )
    if exclude_id is not None:
        statement = statement.where(SafetyKPIRecord.id != exclude_id)
    if db.scalar(statement) is not None:
        raise SafetyKPIDuplicatePeriodError("A KPI record already exists for this site and period")


def _incident_metrics(
    db: Session,
    *,
    site_id: int,
    period_start: date,
    period_end: date,
) -> dict[str, int | float]:
    incidents = db.scalars(
        select(Incident).where(
            Incident.site_id == site_id,
            Incident.occurred_at >= _period_boundary(period_start, end_of_day=False),
            Incident.occurred_at <= _period_boundary(period_end, end_of_day=True),
        )
    ).all()
    recordable_incidents = sum(1 for incident in incidents if incident.is_recordable or incident.is_lost_time)
    lost_time_incidents = sum(1 for incident in incidents if incident.is_lost_time)
    return {
        "recordable_incidents": recordable_incidents,
        "lost_time_incidents": lost_time_incidents,
    }


def _frequency_rate(incidents_count: int, hours_worked: float) -> float:
    if hours_worked <= 0:
        return 0.0
    return round((incidents_count * TRIFR_LTIFR_MULTIPLIER) / hours_worked, 2)


def _serialize_record(db: Session, record: SafetyKPIRecord) -> dict:
    metrics = _incident_metrics(
        db,
        site_id=record.site_id,
        period_start=record.period_start,
        period_end=record.period_end,
    )
    return {
        "id": record.id,
        "site_id": record.site_id,
        "period_start": record.period_start,
        "period_end": record.period_end,
        "hours_worked": record.hours_worked,
        "reporting_label": record.reporting_label,
        "employees_count": record.employees_count,
        "contractors_count": record.contractors_count,
        "notes": record.notes,
        "created_by_user_id": record.created_by_user_id,
        "recordable_incidents": metrics["recordable_incidents"],
        "lost_time_incidents": metrics["lost_time_incidents"],
        "trifr": _frequency_rate(metrics["recordable_incidents"], record.hours_worked),
        "ltifr": _frequency_rate(metrics["lost_time_incidents"], record.hours_worked),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def list_safety_kpis(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
) -> dict:
    statement: Select[tuple[SafetyKPIRecord]] = select(SafetyKPIRecord)
    if site_id is not None:
        statement = statement.where(SafetyKPIRecord.site_id == site_id)
    statement = statement.order_by(SafetyKPIRecord.period_end.desc(), SafetyKPIRecord.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {
        "items": [_serialize_record(db, item) for item in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


def get_safety_kpi(db: Session, record_id: int) -> SafetyKPIRecord:
    record = db.get(SafetyKPIRecord, record_id)
    if record is None:
        raise SafetyKPINotFoundError(f"Safety KPI {record_id} was not found")
    return record


def get_safety_kpi_read(db: Session, record_id: int) -> dict:
    return _serialize_record(db, get_safety_kpi(db, record_id))


def create_safety_kpi(
    db: Session,
    record_in: SafetyKPICreate,
    *,
    actor_id: Optional[int],
) -> dict:
    _ensure_site_exists(db, record_in.site_id)
    _ensure_unique_period(
        db,
        site_id=record_in.site_id,
        period_start=record_in.period_start,
        period_end=record_in.period_end,
    )
    record = SafetyKPIRecord(**record_in.model_dump(), created_by_user_id=actor_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="safety_kpi.create",
        resource_type="safety_kpi",
        resource_id=record.id,
        details={"site_id": record.site_id},
    )
    return _serialize_record(db, record)


def update_safety_kpi(
    db: Session,
    record: SafetyKPIRecord,
    record_in: SafetyKPIUpdate,
    *,
    actor_id: Optional[int],
) -> dict:
    update_data = record_in.model_dump(exclude_unset=True)
    next_site_id = update_data.get("site_id", record.site_id)
    next_period_start = update_data.get("period_start", record.period_start)
    next_period_end = update_data.get("period_end", record.period_end)

    _ensure_site_exists(db, next_site_id)
    _ensure_unique_period(
        db,
        site_id=next_site_id,
        period_start=next_period_start,
        period_end=next_period_end,
        exclude_id=record.id,
    )

    for field, value in update_data.items():
        setattr(record, field, value)

    db.add(record)
    db.commit()
    db.refresh(record)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="safety_kpi.update",
        resource_type="safety_kpi",
        resource_id=record.id,
        details={"updated_fields": sorted(update_data.keys())},
    )
    return _serialize_record(db, record)
