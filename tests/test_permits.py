from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.permit_service import (
    generate_permit_expired_notifications,
    generate_permit_nearing_expiry_notifications,
)


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _future_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _permit_payload(**overrides):
    payload = {
        "permit_number": "PTW-001",
        "permit_type": "hot_work",
        "title": "Welding repair",
        "description": "Welding repair on production line.",
        "site_id": 1,
        "area_location": "Workshop bay 2",
        "requested_by_user_id": 1,
        "issued_by_user_id": 1,
        "approved_by_user_id": 1,
        "assigned_team_or_contractor": "Maintenance team",
        "start_datetime": _future(1),
        "end_datetime": _future(8),
        "status": "pending_approval",
        "risk_summary": "Fire and fume hazards.",
        "precautions_required": ["Fire watch", "Remove combustibles"],
        "ppe_required": ["Gloves", "Face shield"],
        "isolation_required": False,
        "gas_test_required": False,
        "gas_test_results": [],
        "emergency_controls": ["Extinguisher nearby"],
        "closure_notes": None,
        "closed_at": None,
        "attachments_metadata": [
            {
                "file_name": "permit.pdf",
                "content_type": "application/pdf",
                "url": "https://example.com/permits/permit.pdf",
                "size_bytes": 1234,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_create_list_get_update_permit(client: TestClient) -> None:
    create_response = client.post("/api/v1/permits", json=_permit_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["permit_number"] == "PTW-001"
    assert created["status"] == "pending_approval"
    assert created["attachments_metadata"][0]["file_name"] == "permit.pdf"

    list_response = client.get("/api/v1/permits?status=pending_approval&permit_type=hot_work&site_id=1&requested_by_user_id=1&issued_by_user_id=1&approved_by_user_id=1")
    page = list_response.json()
    assert list_response.status_code == 200
    assert page["total"] == 1
    assert page["items"][0]["permit_number"] == "PTW-001"

    get_response = client.get(f"/api/v1/permits/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    patch_response = client.patch(f"/api/v1/permits/{created['id']}", json={"status": "approved"})
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "approved"


def test_permit_transition_rules(client: TestClient) -> None:
    draft = client.post("/api/v1/permits", json=_permit_payload(permit_number="PTW-002", status="draft"))
    draft_id = draft.json()["id"]

    invalid_active = client.patch(f"/api/v1/permits/{draft_id}", json={"status": "active"})
    invalid_closed = client.patch(f"/api/v1/permits/{draft_id}", json={"status": "closed"})

    assert invalid_active.status_code == 422
    assert "approved" in invalid_active.json()["detail"]
    assert invalid_closed.status_code == 422
    assert "approved, active, or suspended" in invalid_closed.json()["detail"]

    approved = client.patch(f"/api/v1/permits/{draft_id}", json={"status": "approved"})
    active = client.patch(f"/api/v1/permits/{draft_id}", json={"status": "active"})
    closed = client.patch(f"/api/v1/permits/{draft_id}", json={"status": "closed", "closure_notes": "Work completed"})

    assert approved.status_code == 200
    assert active.status_code == 200
    assert closed.status_code == 200
    assert closed.json()["closed_at"] is not None


def test_permit_expiry_derivation_and_filters(client: TestClient) -> None:
    expired = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-003",
            start_datetime=_past(10),
            end_datetime=_past(1),
            status="approved",
        ),
    )
    client.post(
        "/api/v1/permits",
        json=_permit_payload(permit_number="PTW-004", permit_type="maintenance", precautions_required=[]),
    )

    assert expired.status_code == 201
    assert expired.json()["status"] == "expired"

    filtered = client.get("/api/v1/permits?status=expired&date_from=2000-01-01&date_to=2999-01-01")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["permit_number"] == "PTW-003"


def test_permit_validation_references_datetime_and_type_rules(client: TestClient) -> None:
    bad_site = client.post("/api/v1/permits", json=_permit_payload(site_id=999))
    bad_user = client.post("/api/v1/permits", json=_permit_payload(requested_by_user_id=999))
    bad_range = client.post("/api/v1/permits", json=_permit_payload(start_datetime=_future(8), end_datetime=_future(1)))
    bad_hot_work = client.post("/api/v1/permits", json=_permit_payload(precautions_required=[]))
    bad_confined_space = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_type="confined_space",
            permit_number="PTW-CS-001",
            precautions_required=[],
            gas_test_required=True,
            gas_test_results=[],
        ),
    )
    electrical = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_type="electrical",
            permit_number="PTW-EL-001",
            precautions_required=[],
            isolation_required=True,
        ),
    )

    assert bad_site.status_code == 404
    assert bad_site.json()["detail"] == "Site not found"
    assert bad_user.status_code == 404
    assert bad_user.json()["detail"] == "Referenced user not found"
    assert bad_range.status_code == 422
    assert "start_datetime" in bad_range.json()["detail"]
    assert bad_hot_work.status_code == 422
    assert "precautions_required" in bad_hot_work.json()["detail"]
    assert bad_confined_space.status_code == 422
    assert "gas_test_results" in bad_confined_space.json()["detail"]
    assert electrical.status_code == 201
    assert electrical.json()["isolation_required"] is True


def test_permit_notification_helpers(client: TestClient, db_session: Session) -> None:
    pending = client.post("/api/v1/permits", json=_permit_payload(permit_number="PTW-005", status="pending_approval"))
    nearing = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-006",
            status="approved",
            start_datetime=_past(1),
            end_datetime=_future_days(60),
        ),
    )
    later = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-008",
            status="approved",
            start_datetime=_past(1),
            end_datetime=_future_days(120),
        ),
    )
    expired = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-007",
            status="approved",
            start_datetime=_past(10),
            end_datetime=_past(1),
        ),
    )

    assert pending.status_code == 201
    assert nearing.status_code == 201
    assert later.status_code == 201
    assert expired.status_code == 201

    pending_notifications = client.get("/api/v1/notifications?notification_type=permit_pending_approval").json()["items"]
    nearing_notifications = generate_permit_nearing_expiry_notifications(db_session)
    expired_notifications = generate_permit_expired_notifications(db_session)

    assert len(pending_notifications) == 1
    assert pending_notifications[0]["related_entity_id"] == pending.json()["id"]
    assert len(nearing_notifications) == 1
    assert nearing_notifications[0].notification_type.value == "permit_nearing_expiry"
    assert "expires within 90 days" in nearing_notifications[0].message
    assert len(expired_notifications) == 1
    assert expired_notifications[0].notification_type.value == "permit_expired"
