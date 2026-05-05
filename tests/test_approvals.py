from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.corrective_action import CorrectiveAction
from app.models.incident import Incident
from app.models.notification import Notification, NotificationType
from app.models.site import Site


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Forklift incident",
        "description": "Forklift impacted a pallet rack.",
        "severity": "high",
        "status": "open",
        "occurred_at": "2026-04-23T08:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Unprotected edge",
        "description": "Platform edge without effective barrier.",
        "likelihood": 4,
        "impact": 5,
        "status": "open",
        "existing_controls": [],
        "additional_controls": [],
        "owner_user_id": 1,
        "due_date": "2026-05-01",
        "review_date": "2026-05-15",
        "attachments_metadata": [],
        "incident_id": None,
    }
    payload.update(overrides)
    return payload


def _corrective_action_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Install guard rail",
        "description": "Install and verify a fixed guard rail.",
        "source_type": "manual",
        "source_id": None,
        "assigned_to_user_id": 1,
        "created_by_user_id": None,
        "priority": "high",
        "status": "open",
        "due_date": "2026-05-10",
        "started_at": None,
        "completed_at": None,
        "closure_notes": "Guard rail installed.",
        "closure_evidence_metadata": [],
        "verification_notes": None,
        "verified_by_user_id": None,
        "verified_at": None,
    }
    payload.update(overrides)
    return payload


def _permit_payload(**overrides):
    payload = {
        "permit_number": "PTW-900",
        "permit_type": "hot_work",
        "title": "Welding repair",
        "description": "Welding repair on pipe rack.",
        "site_id": 1,
        "area_location": "Pipe rack",
        "requested_by_user_id": 1,
        "issued_by_user_id": 1,
        "approved_by_user_id": None,
        "assigned_team_or_contractor": "Maintenance team",
        "start_datetime": _future(1),
        "end_datetime": _future(6),
        "status": "draft",
        "risk_summary": "Fire risk",
        "precautions_required": ["Fire watch"],
        "ppe_required": ["Gloves"],
        "isolation_required": False,
        "gas_test_required": False,
        "gas_test_results": [],
        "emergency_controls": ["Extinguisher"],
        "closure_notes": None,
        "closed_at": None,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_request_approval_success(client: TestClient, db_session: Session, create_user_for_role, act_as) -> None:
    safety_officer = create_user_for_role("safety_officer")
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()

    act_as(safety_officer)
    response = client.post(
        f"/api/v1/approvals/incident/{incident['id']}/request",
        json={"action_type": "incident_closure", "request_notes": "Investigation complete."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entity_type"] == "incident"
    assert body["action_type"] == "incident_closure"
    assert body["status"] == "pending"

    updated_incident = db_session.get(Incident, incident["id"])
    assert updated_incident.closure_requested is True


def test_duplicate_pending_approval_blocked(client: TestClient, create_user_for_role, act_as) -> None:
    safety_officer = create_user_for_role("safety_officer")
    permit = client.post("/api/v1/permits", json=_permit_payload()).json()

    act_as(safety_officer)
    first = client.post(
        f"/api/v1/approvals/permit/{permit['id']}/request",
        json={"action_type": "permit_approval", "request_notes": "Ready for final review."},
    )
    second = client.post(
        f"/api/v1/approvals/permit/{permit['id']}/request",
        json={"action_type": "permit_approval", "request_notes": "Retrying duplicate request."},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "pending approval already exists" in second.json()["detail"]


def test_unauthorized_request_denied(client: TestClient, create_user_for_role, act_as) -> None:
    employee = create_user_for_role("employee", assigned_site_id=1)
    hazard = client.post("/api/v1/hazards", json=_hazard_payload()).json()

    act_as(employee)
    response = client.post(
        f"/api/v1/approvals/hazard/{hazard['id']}/request",
        json={"action_type": "hazard_review", "request_notes": "Please review this hazard."},
    )

    assert response.status_code == 403


def test_unauthorized_decision_denied(client: TestClient, create_user_for_role, act_as) -> None:
    safety_officer = create_user_for_role("safety_officer")
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()

    act_as(safety_officer)
    approval = client.post(
        f"/api/v1/approvals/incident/{incident['id']}/request",
        json={"action_type": "incident_closure", "request_notes": "Closure ready."},
    ).json()

    response = client.patch(
        f"/api/v1/approvals/{approval['id']}/decision",
        json={"status": "approved", "decision_notes": "Attempting unauthorized approval."},
    )

    assert response.status_code == 403


def test_approve_flow_updates_related_entity(client: TestClient, create_user_for_role, act_as, db_session: Session) -> None:
    safety_officer = create_user_for_role("safety_officer")
    manager = create_user_for_role("ohs_manager")
    action = client.post("/api/v1/corrective-actions", json=_corrective_action_payload()).json()

    act_as(safety_officer)
    approval = client.post(
        f"/api/v1/approvals/corrective_action/{action['id']}/request",
        json={
            "action_type": "corrective_action_verification",
            "request_notes": "Closure evidence is ready for verification.",
        },
    ).json()

    act_as(manager)
    response = client.patch(
        f"/api/v1/approvals/{approval['id']}/decision",
        json={"status": "approved", "decision_notes": "Verified on walkthrough."},
    )

    assert response.status_code == 200
    updated_action = db_session.get(CorrectiveAction, action["id"])
    assert updated_action.status.value == "closed"
    assert updated_action.verified_by_user_id == manager.id
    assert updated_action.verified_at is not None


def test_reject_flow_stores_decision_notes(client: TestClient, create_user_for_role, act_as, db_session: Session) -> None:
    safety_officer = create_user_for_role("safety_officer")
    manager = create_user_for_role("ohs_manager")
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()

    act_as(safety_officer)
    approval = client.post(
        f"/api/v1/approvals/incident/{incident['id']}/request",
        json={"action_type": "incident_closure", "request_notes": "Closure proposed."},
    ).json()

    act_as(manager)
    response = client.patch(
        f"/api/v1/approvals/{approval['id']}/decision",
        json={"status": "rejected", "decision_notes": "Additional evidence is still required."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["decision_notes"] == "Additional evidence is still required."

    updated_incident = db_session.get(Incident, incident["id"])
    assert updated_incident.status.value == "open"
    assert updated_incident.closure_requested is False


def test_approval_listing_respects_site_scope(
    client: TestClient,
    create_user_for_role,
    act_as,
    db_session: Session,
) -> None:
    safety_officer = create_user_for_role("safety_officer")
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    db_session.add(Site(id=2, name="Remote Yard", code="RYD", address="Remote site", created_by_id=1))
    db_session.commit()

    incident_site_one = client.post("/api/v1/incidents", json=_incident_payload(title="Site one incident")).json()
    incident_site_two = client.post(
        "/api/v1/incidents",
        json=_incident_payload(site_id=2, title="Site two incident"),
    ).json()

    act_as(safety_officer)
    client.post(
        f"/api/v1/approvals/incident/{incident_site_one['id']}/request",
        json={"action_type": "incident_closure"},
    )
    client.post(
        f"/api/v1/approvals/incident/{incident_site_two['id']}/request",
        json={"action_type": "incident_closure"},
    )

    act_as(supervisor)
    response = client.get("/api/v1/approvals")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["entity_id"] == incident_site_one["id"]


def test_notifications_and_audit_logs_are_created(
    client: TestClient,
    create_user_for_role,
    act_as,
    db_session: Session,
) -> None:
    safety_officer = create_user_for_role("safety_officer")
    permit = client.post("/api/v1/permits", json=_permit_payload(permit_number="PTW-901")).json()

    act_as(safety_officer)
    approval = client.post(
        f"/api/v1/approvals/permit/{permit['id']}/request",
        json={"action_type": "permit_approval", "request_notes": "Permit package is complete."},
    ).json()

    act_as(1)
    decision = client.patch(
        f"/api/v1/approvals/{approval['id']}/decision",
        json={"status": "approved", "decision_notes": "Approved for execution."},
    )

    assert decision.status_code == 200

    notifications = list(
        db_session.scalars(
            select(Notification).where(
                Notification.notification_type.in_(
                    [NotificationType.approval_requested, NotificationType.approval_approved]
                )
            )
        ).all()
    )
    notification_types = {notification.notification_type for notification in notifications}
    assert NotificationType.approval_requested in notification_types
    assert NotificationType.approval_approved in notification_types

    audit_actions = {
        log.action
        for log in db_session.scalars(
            select(AuditLog).where(AuditLog.action.in_(["approval.requested", "approval.approved"]))
        ).all()
    }
    assert "approval.requested" in audit_actions
    assert "approval.approved" in audit_actions
