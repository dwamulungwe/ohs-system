from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationSeverity, NotificationType, RelatedEntityType
from app.models.notification_delivery import NotificationDeliveryStatus
from app.models.training import TrainingRecord, TrainingStatus, TrainingType
from app.models.common import utcnow
from app.services.notification_delivery_service import dispatch_notification_delivery
from app.services.scheduler_service import run_all_scheduled_jobs


def _medical_payload(user_id: int, **overrides):
    payload = {
        "employee_user_id": user_id,
        "site_id": 1,
        "surveillance_type": "Spirometry",
        "due_date": (date.today() - timedelta(days=2)).isoformat(),
        "medical_clearance_status": "pending",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _drill_payload(**overrides):
    payload = {
        "emergency_type": "Spill response",
        "site_id": 1,
        "drill_date": (date.today() + timedelta(days=2)).isoformat(),
        "participants": ["Response team"],
        "attendance_records": [],
        "issues_found": [],
        "corrective_actions": [],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _document_payload(**overrides):
    payload = {
        "title": "Emergency Preparedness SOP",
        "document_type": "sop",
        "version": "2.0",
        "site_id": 1,
        "status": "pending_approval",
        "expiry_date": (date.today() + timedelta(days=5)).isoformat(),
        "acknowledgement_required": False,
        "acknowledgement_user_ids": [],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _audit_payload(**overrides):
    payload = {
        "audit_type": "compliance",
        "site_id": 1,
        "auditor_user_id": 1,
        "audit_date": date.today().isoformat(),
        "findings": ["Open housekeeping item"],
        "non_conformances": [],
        "recommendations": ["Close out the housekeeping item"],
        "status": "open",
        "audit_score": None,
        "corrective_action_ids": [],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_scheduler_runs_final_module_jobs_and_creates_reminders(
    client,
    db_session: Session,
    create_user_for_role,
) -> None:
    ohs_manager = create_user_for_role("ohs_manager", assigned_site_id=1)
    safety_officer = create_user_for_role("safety_officer", assigned_site_id=1)

    db_session.add(
        TrainingRecord(
            title="Expired induction",
            training_type=TrainingType.induction,
            site_id=1,
            assigned_to_user_id=ohs_manager.id,
            assigned_by_user_id=1,
            due_date=date.today() - timedelta(days=1),
            status=TrainingStatus.assigned,
            certificate_metadata=[],
        )
    )
    db_session.commit()

    medical = client.post("/api/v1/medical-surveillance", json=_medical_payload(ohs_manager.id))
    drill = client.post("/api/v1/emergency-drills", json=_drill_payload())
    document = client.post("/api/v1/documents", json=_document_payload())
    expiring_document = client.post(
        "/api/v1/documents",
        json=_document_payload(
            title="Approved expiring document",
            status="approved",
            approved_by_user_id=1,
        ),
    )
    audit = client.post("/api/v1/audits", json=_audit_payload(auditor_user_id=safety_officer.id))

    assert medical.status_code == 201
    assert drill.status_code == 201
    assert document.status_code == 201
    assert expiring_document.status_code == 201
    assert audit.status_code == 201

    job_runs = run_all_scheduled_jobs(db_session)

    assert {job_run.job_name for job_run in job_runs} == {
        "medical_surveillance_maintenance",
        "emergency_drill_maintenance",
        "document_control_maintenance",
        "general_reminders",
        "kpi_refresh",
    }
    assert all(job_run.status.value == "success" for job_run in job_runs)

    # The first pass rolls assigned training into overdue during kpi_refresh;
    # the second pass emits the overdue training reminder from general_reminders.
    run_all_scheduled_jobs(db_session)

    notification_types = {
        notification.notification_type
        for notification in db_session.scalars(select(Notification)).all()
    }
    assert NotificationType.medical_surveillance_overdue in notification_types
    assert NotificationType.emergency_drill_due_soon in notification_types
    assert NotificationType.document_pending_approval in notification_types
    assert NotificationType.document_due_soon in notification_types
    assert NotificationType.audit_open in notification_types
    assert NotificationType.training_overdue in notification_types


def test_notification_delivery_dispatch_and_endpoints(client, db_session: Session) -> None:
    notification = Notification(
        recipient_user_id=1,
        title="Delivery test",
        message="Check notification delivery logging.",
        notification_type=NotificationType.audit_open,
        severity=NotificationSeverity.warning,
        related_entity_type=RelatedEntityType.audit_management,
        related_entity_id=99,
        is_read=False,
        created_at=utcnow(),
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    logs = dispatch_notification_delivery(db_session, notification)

    assert len(logs) == 2
    assert {log.status for log in logs} == {NotificationDeliveryStatus.skipped}

    listing = client.get("/api/v1/notification-deliveries")
    assert listing.status_code == 200
    assert listing.json()["total"] == 2

    detail = client.get(f"/api/v1/notification-deliveries/{logs[0].id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == NotificationDeliveryStatus.skipped.value

    job_run_listing = client.get("/api/v1/job-runs")
    assert job_run_listing.status_code == 200
