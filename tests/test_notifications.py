from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import (
    generate_corrective_action_due_soon_notifications,
    generate_corrective_action_overdue_notifications,
)


def _notification_payload(**overrides):
    payload = {
        "recipient_user_id": 1,
        "title": "Safety reminder",
        "message": "Please review your assigned action.",
        "notification_type": "corrective_action_due_soon",
        "severity": "warning",
        "related_entity_type": "corrective_action",
        "related_entity_id": 1,
    }
    payload.update(overrides)
    return payload


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Critical incident",
        "description": "Serious incident requiring immediate review.",
        "severity": "critical",
        "status": "open",
        "occurred_at": "2026-04-23T08:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Critical hazard",
        "description": "High energy hazard.",
        "likelihood": 5,
        "impact": 5,
        "status": "open",
        "existing_controls": [],
        "additional_controls": [],
        "owner_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _corrective_action_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Verify corrective action",
        "description": "Verify the action has been completed.",
        "source_type": "manual",
        "priority": "medium",
        "status": "open",
        "assigned_to_user_id": 1,
        "due_date": (date.today() + timedelta(days=3)).isoformat(),
        "closure_evidence_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_create_list_get_and_filter_notifications(client: TestClient) -> None:
    client.post("/api/v1/notifications", json=_notification_payload())
    client.post(
        "/api/v1/notifications",
        json=_notification_payload(
            title="Critical incident notice",
            notification_type="critical_incident_created",
            severity="critical",
            related_entity_type="incident",
            related_entity_id=2,
        ),
    )

    response = client.get("/api/v1/notifications?is_read=false&severity=critical&notification_type=critical_incident_created&recipient_user_id=1")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1
    assert page["items"][0]["title"] == "Critical incident notice"
    assert page["items"][0]["is_read"] is False

    notification_id = page["items"][0]["id"]
    get_response = client.get(f"/api/v1/notifications/{notification_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == notification_id


def test_mark_as_read_and_unread_count(client: TestClient) -> None:
    create_response = client.post("/api/v1/notifications", json=_notification_payload())
    notification_id = create_response.json()["id"]

    unread_response = client.get("/api/v1/notifications/unread-count")
    assert unread_response.status_code == 200
    assert unread_response.json()["unread_count"] == 1

    read_response = client.patch(f"/api/v1/notifications/{notification_id}/read")
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True
    assert read_response.json()["read_at"] is not None

    unread_after = client.get("/api/v1/notifications/unread-count")
    assert unread_after.json()["unread_count"] == 0


def test_mark_all_as_read_only_affects_current_user(client: TestClient, db_session: Session) -> None:
    db_session.add(
        User(
            id=2,
            email="worker@example.com",
            full_name="Worker User",
            hashed_password="not-used",
            is_active=True,
            roles=[],
        )
    )
    db_session.commit()
    client.post("/api/v1/notifications", json=_notification_payload(recipient_user_id=1, related_entity_id=1))
    client.post("/api/v1/notifications", json=_notification_payload(recipient_user_id=2, related_entity_id=2))

    response = client.patch("/api/v1/notifications/mark-all-as-read")

    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    unread_for_user_2 = db_session.query(Notification).filter(
        Notification.recipient_user_id == 2,
        Notification.is_read.is_(False),
    ).count()
    assert unread_for_user_2 == 1


def test_workflows_trigger_critical_incident_and_hazard_notifications(client: TestClient) -> None:
    incident_response = client.post("/api/v1/incidents", json=_incident_payload())
    hazard_response = client.post("/api/v1/hazards", json=_hazard_payload())

    notifications = client.get("/api/v1/notifications?severity=critical").json()["items"]
    notification_types = {notification["notification_type"] for notification in notifications}

    assert incident_response.status_code == 201
    assert hazard_response.status_code == 201
    assert "critical_incident_created" in notification_types
    assert "critical_hazard_created" in notification_types


def test_updates_trigger_critical_notifications_when_escalated(client: TestClient) -> None:
    incident_response = client.post("/api/v1/incidents", json=_incident_payload(severity="medium"))
    hazard_response = client.post("/api/v1/hazards", json=_hazard_payload(likelihood=2, impact=2))

    client.patch(f"/api/v1/incidents/{incident_response.json()['id']}", json={"severity": "critical"})
    client.patch(f"/api/v1/hazards/{hazard_response.json()['id']}", json={"likelihood": 5, "impact": 5})

    notification_types = {
        notification["notification_type"]
        for notification in client.get("/api/v1/notifications?severity=critical").json()["items"]
    }

    assert "critical_incident_created" in notification_types
    assert "critical_hazard_created" in notification_types


def test_corrective_action_pending_verification_triggers_notification(client: TestClient) -> None:
    action_response = client.post("/api/v1/corrective-actions", json=_corrective_action_payload())
    action_id = action_response.json()["id"]

    client.patch(f"/api/v1/corrective-actions/{action_id}", json={"status": "pending_verification"})

    notifications = client.get("/api/v1/notifications?notification_type=action_pending_verification").json()["items"]
    assert len(notifications) == 1
    assert notifications[0]["related_entity_id"] == action_id


def test_manual_due_soon_and_overdue_generators_create_notifications(client: TestClient, db_session: Session) -> None:
    due_soon = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Due soon action", due_date=(date.today() + timedelta(days=2)).isoformat()),
    )
    overdue = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Overdue action", due_date=(date.today() - timedelta(days=2)).isoformat()),
    )

    due_notifications = generate_corrective_action_due_soon_notifications(db_session, days_ahead=7)
    overdue_notifications = generate_corrective_action_overdue_notifications(db_session)

    assert due_soon.status_code == 201
    assert overdue.status_code == 201
    assert len(due_notifications) == 1
    assert due_notifications[0].notification_type.value == "corrective_action_due_soon"
    assert len(overdue_notifications) == 1
    assert overdue_notifications[0].notification_type.value == "corrective_action_overdue"
