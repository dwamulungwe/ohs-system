from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.training_service import (
    generate_expired_training_notifications,
    generate_overdue_compliance_acknowledgement_notifications,
    generate_overdue_training_notifications,
)


def _training_payload(**overrides):
    payload = {
        "title": "Forklift induction",
        "training_type": "equipment_training",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "due_date": (date.today() + timedelta(days=10)).isoformat(),
        "completed_at": None,
        "expiry_date": None,
        "status": "assigned",
        "certificate_metadata": [
            {
                "file_name": "certificate.pdf",
                "content_type": "application/pdf",
                "url": "https://example.com/training/certificate.pdf",
                "size_bytes": 1024,
            }
        ],
        "notes": "Complete before operating forklift.",
    }
    payload.update(overrides)
    return payload


def _ack_payload(**overrides):
    payload = {
        "document_title": "PPE Policy",
        "document_type": "policy",
        "version": "1.0",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_at": None,
        "status": "assigned",
        "notes": "Review and acknowledge.",
    }
    payload.update(overrides)
    return payload


def test_create_list_get_update_training_record(client: TestClient) -> None:
    create_response = client.post("/api/v1/training", json=_training_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["assigned_by_user_id"] == 1
    assert created["status"] == "assigned"
    assert created["certificate_metadata"][0]["file_name"] == "certificate.pdf"

    list_response = client.get("/api/v1/training?status=assigned&training_type=equipment_training&site_id=1&assigned_to_user_id=1")
    page = list_response.json()
    assert list_response.status_code == 200
    assert page["total"] == 1
    assert page["items"][0]["title"] == "Forklift induction"

    get_response = client.get(f"/api/v1/training/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    patch_response = client.patch(
        f"/api/v1/training/{created['id']}",
        json={"completed_at": datetime.now(timezone.utc).isoformat()},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "completed"


def test_training_overdue_and_expired_status_derivation(client: TestClient) -> None:
    overdue_response = client.post(
        "/api/v1/training",
        json=_training_payload(title="Overdue training", due_date=(date.today() - timedelta(days=1)).isoformat()),
    )
    expired_response = client.post(
        "/api/v1/training",
        json=_training_payload(
            title="Expired training",
            completed_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
            expiry_date=(date.today() - timedelta(days=1)).isoformat(),
        ),
    )

    assert overdue_response.status_code == 201
    assert overdue_response.json()["status"] == "overdue"
    assert expired_response.status_code == 201
    assert expired_response.json()["status"] == "expired"


def test_training_date_filters_and_validation(client: TestClient) -> None:
    client.post("/api/v1/training", json=_training_payload(title="May training", due_date="2026-05-10"))
    client.post("/api/v1/training", json=_training_payload(title="June training", due_date="2026-06-10"))

    filtered = client.get("/api/v1/training?date_from=2026-05-01&date_to=2026-05-31")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["title"] == "May training"

    missing_site = client.post("/api/v1/training", json=_training_payload(site_id=999))
    missing_user = client.post("/api/v1/training", json=_training_payload(assigned_to_user_id=999))
    assert missing_site.status_code == 404
    assert missing_site.json()["detail"] == "Site not found"
    assert missing_user.status_code == 404
    assert missing_user.json()["detail"] == "Referenced user not found"


def test_create_list_get_update_compliance_acknowledgement(client: TestClient) -> None:
    create_response = client.post("/api/v1/compliance-acknowledgements", json=_ack_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["assigned_by_user_id"] == 1
    assert created["status"] == "assigned"

    list_response = client.get("/api/v1/compliance-acknowledgements?status=assigned&document_type=policy&site_id=1&assigned_to_user_id=1")
    page = list_response.json()
    assert list_response.status_code == 200
    assert page["total"] == 1
    assert page["items"][0]["document_title"] == "PPE Policy"

    get_response = client.get(f"/api/v1/compliance-acknowledgements/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    patch_response = client.patch(
        f"/api/v1/compliance-acknowledgements/{created['id']}",
        json={"acknowledged_at": datetime.now(timezone.utc).isoformat()},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "acknowledged"


def test_compliance_overdue_derivation_and_validation(client: TestClient) -> None:
    old_assigned_at = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    overdue_response = client.post(
        "/api/v1/compliance-acknowledgements",
        json=_ack_payload(document_title="Old SOP", assigned_at=old_assigned_at),
    )
    missing_site = client.post("/api/v1/compliance-acknowledgements", json=_ack_payload(site_id=999))
    missing_user = client.post("/api/v1/compliance-acknowledgements", json=_ack_payload(assigned_to_user_id=999))

    assert overdue_response.status_code == 201
    assert overdue_response.json()["status"] == "overdue"
    assert missing_site.status_code == 404
    assert missing_site.json()["detail"] == "Site not found"
    assert missing_user.status_code == 404
    assert missing_user.json()["detail"] == "Referenced user not found"


def test_training_and_compliance_notification_generators(client: TestClient, db_session: Session) -> None:
    client.post(
        "/api/v1/training",
        json=_training_payload(title="Notify overdue", due_date=(date.today() - timedelta(days=1)).isoformat()),
    )
    client.post(
        "/api/v1/training",
        json=_training_payload(
            title="Notify expired",
            completed_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
            expiry_date=(date.today() - timedelta(days=1)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/compliance-acknowledgements",
        json=_ack_payload(
            document_title="Notify acknowledgement",
            assigned_at=(datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        ),
    )

    overdue_training = generate_overdue_training_notifications(db_session)
    expired_training = generate_expired_training_notifications(db_session)
    overdue_acknowledgements = generate_overdue_compliance_acknowledgement_notifications(db_session)

    assert len(overdue_training) == 1
    assert overdue_training[0].notification_type.value == "training_overdue"
    assert len(expired_training) == 1
    assert expired_training[0].notification_type.value == "training_expired"
    assert len(overdue_acknowledgements) == 1
    assert overdue_acknowledgements[0].notification_type.value == "compliance_acknowledgement_overdue"
