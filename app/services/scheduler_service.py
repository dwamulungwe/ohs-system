from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from time import sleep

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job_run import JobRun, JobRunStatus
from app.models.legal_compliance import LegalComplianceItem
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.training import (
    ComplianceAcknowledgement,
    ComplianceAcknowledgementStatus,
    TrainingRecord,
    TrainingStatus,
)
from app.schemas.notification import NotificationCreate
from app.services.document_control_service import (
    generate_document_notifications,
    refresh_document_statuses,
)
from app.services.emergency_drill_service import (
    generate_emergency_drill_notifications,
    refresh_emergency_drill_statuses,
)
from app.services.medical_surveillance_service import (
    generate_medical_surveillance_notifications,
    refresh_medical_surveillance_statuses,
)
from app.services.notification_service import (
    create_notification_once,
    generate_corrective_action_due_soon_notifications,
    generate_corrective_action_overdue_notifications,
)
from app.services.permit_service import (
    generate_permit_expired_notifications,
    generate_permit_nearing_expiry_notifications,
)
from app.services.query_utils import paginate
from app.services.training_service import (
    generate_expired_training_notifications,
    generate_overdue_compliance_acknowledgement_notifications,
    generate_overdue_training_notifications,
)

_scheduler_stop_event = Event()
_scheduler_thread: Optional[Thread] = None


class JobRunNotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_job_run(db: Session, job_name: str) -> JobRun:
    job_run = JobRun(job_name=job_name, status=JobRunStatus.running, started_at=_now())
    db.add(job_run)
    db.commit()
    db.refresh(job_run)
    return job_run


def _complete_job_run(
    db: Session,
    job_run: JobRun,
    *,
    status: JobRunStatus,
    records_processed: int,
    details: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> JobRun:
    job_run.status = status
    job_run.records_processed = records_processed
    job_run.details = details
    job_run.error_message = error_message
    job_run.completed_at = _now()
    db.add(job_run)
    db.commit()
    db.refresh(job_run)
    return job_run


def _run_job(db: Session, job_name: str, runner) -> JobRun:
    job_run = _create_job_run(db, job_name)
    try:
        records_processed, details = runner(db)
        return _complete_job_run(
            db,
            job_run,
            status=JobRunStatus.success,
            records_processed=records_processed,
            details=details,
        )
    except Exception as exc:
        return _complete_job_run(
            db,
            job_run,
            status=JobRunStatus.failed,
            records_processed=0,
            details=None,
            error_message=str(exc),
        )


def _run_medical_surveillance_job(db: Session) -> tuple[int, dict]:
    updated = refresh_medical_surveillance_statuses(db)
    notifications = generate_medical_surveillance_notifications(db)
    return updated + notifications, {"updated_records": updated, "notifications_created": notifications}


def _run_emergency_drill_job(db: Session) -> tuple[int, dict]:
    updated = refresh_emergency_drill_statuses(db)
    notifications = generate_emergency_drill_notifications(db)
    return updated + notifications, {"updated_records": updated, "notifications_created": notifications}


def _run_document_control_job(db: Session) -> tuple[int, dict]:
    updated = refresh_document_statuses(db)
    notifications = generate_document_notifications(db)
    return updated + notifications, {"updated_records": updated, "notifications_created": notifications}


def _run_general_reminders_job(db: Session) -> tuple[int, dict]:
    total = 0
    parts = {
        "corrective_action_due_soon": len(generate_corrective_action_due_soon_notifications(db)),
        "corrective_action_overdue": len(generate_corrective_action_overdue_notifications(db)),
        "training_overdue": len(generate_overdue_training_notifications(db)),
        "training_expired": len(generate_expired_training_notifications(db)),
        "compliance_acknowledgements_overdue": len(
            generate_overdue_compliance_acknowledgement_notifications(db)
        ),
        "permit_due_soon": len(generate_permit_nearing_expiry_notifications(db)),
        "permit_expired": len(generate_permit_expired_notifications(db)),
    }
    total += sum(parts.values())

    today = _now().date()
    for item in db.scalars(select(LegalComplianceItem)).all():
        notification = None
        if item.next_review_date is None or item.owner_user_id is None:
            continue
        if item.next_review_date < today:
            notification = create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=item.owner_user_id,
                    title="Legal compliance review overdue",
                    message=f"Legal compliance item '{item.title}' is overdue for review.",
                    notification_type=NotificationType.legal_compliance_overdue,
                    severity=NotificationSeverity.critical,
                    related_entity_type=RelatedEntityType.legal_compliance,
                    related_entity_id=item.id,
                ),
            )
        elif item.next_review_date <= today + timedelta(days=7):
            notification = create_notification_once(
                db,
                NotificationCreate(
                    recipient_user_id=item.owner_user_id,
                    title="Legal compliance review due soon",
                    message=f"Legal compliance item '{item.title}' is due for review by {item.next_review_date}.",
                    notification_type=NotificationType.legal_compliance_due_soon,
                    severity=NotificationSeverity.warning,
                    related_entity_type=RelatedEntityType.legal_compliance,
                    related_entity_id=item.id,
                ),
            )
        if notification is not None:
            total += 1
            parts["legal_compliance"] = parts.get("legal_compliance", 0) + 1

    return total, parts


def _run_kpi_refresh_job(db: Session) -> tuple[int, dict]:
    records = list(db.scalars(select(TrainingRecord)).all())
    overdue_training = 0
    for record in records:
        if (
            record.due_date is not None
            and record.due_date < _now().date()
            and record.status not in {TrainingStatus.completed, TrainingStatus.expired, TrainingStatus.cancelled}
        ):
            record.status = TrainingStatus.overdue
            db.add(record)
            overdue_training += 1
    acknowledgements = list(db.scalars(select(ComplianceAcknowledgement)).all())
    overdue_acks = 0
    for acknowledgement in acknowledgements:
        if (
            acknowledgement.status == ComplianceAcknowledgementStatus.assigned
            and acknowledgement.assigned_at.date() < _now().date()
        ):
            continue
        if acknowledgement.status == ComplianceAcknowledgementStatus.overdue:
            overdue_acks += 1
    if overdue_training:
        db.commit()
    return overdue_training + overdue_acks, {
        "training_records_updated": overdue_training,
        "overdue_acknowledgements_seen": overdue_acks,
    }


JOB_RUNNERS = {
    "medical_surveillance_maintenance": _run_medical_surveillance_job,
    "emergency_drill_maintenance": _run_emergency_drill_job,
    "document_control_maintenance": _run_document_control_job,
    "general_reminders": _run_general_reminders_job,
    "kpi_refresh": _run_kpi_refresh_job,
}


def run_all_scheduled_jobs(db: Session) -> list[JobRun]:
    return [_run_job(db, job_name, runner) for job_name, runner in JOB_RUNNERS.items()]


def list_job_runs(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    job_name: Optional[str] = None,
    job_status: Optional[JobRunStatus] = None,
) -> dict:
    statement: Select[tuple[JobRun]] = select(JobRun)
    if job_name is not None:
        statement = statement.where(JobRun.job_name == job_name)
    if job_status is not None:
        statement = statement.where(JobRun.status == job_status)
    statement = statement.order_by(JobRun.started_at.desc(), JobRun.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_job_run(db: Session, job_run_id: int) -> JobRun:
    job_run = db.get(JobRun, job_run_id)
    if job_run is None:
        raise JobRunNotFoundError("Job run not found")
    return job_run


def _scheduler_loop() -> None:
    while not _scheduler_stop_event.is_set():
        db = SessionLocal()
        try:
            run_all_scheduled_jobs(db)
        finally:
            db.close()
        for _ in range(settings.SCHEDULER_POLL_SECONDS):
            if _scheduler_stop_event.is_set():
                break
            sleep(1)


def start_scheduler() -> None:
    global _scheduler_thread
    if not settings.SCHEDULER_ENABLED or _scheduler_thread is not None:
        return
    _scheduler_stop_event.clear()
    _scheduler_thread = Thread(target=_scheduler_loop, name="ohs-scheduler", daemon=True)
    _scheduler_thread.start()


def stop_scheduler() -> None:
    global _scheduler_thread
    _scheduler_stop_event.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
