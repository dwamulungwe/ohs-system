from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.site import Site


@pytest.fixture(autouse=True)
def upload_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    yield


def _create_incident(client: TestClient, *, site_id: int = 1) -> int:
    response = client.post(
        "/api/v1/incidents",
        json={
            "site_id": site_id,
            "title": "Forklift near miss",
            "description": "Operator stopped before contact.",
            "severity": "medium",
            "status": "open",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "attachments_metadata": [],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_attachment(
    client: TestClient,
    entity_type: str,
    entity_id: int,
    *,
    filename: str = "evidence.pdf",
    content: bytes = b"pdf-evidence",
    content_type: str = "application/pdf",
    description: str = "Initial evidence",
):
    return client.post(
        f"/api/v1/attachments/{entity_type}/{entity_id}",
        data={"description": description},
        files={"file": (filename, content, content_type)},
    )


def test_upload_list_download_and_delete_attachment(client: TestClient) -> None:
    incident_id = _create_incident(client)

    upload_response = _upload_attachment(client, "incident", incident_id)
    assert upload_response.status_code == 201
    attachment = upload_response.json()
    assert attachment["original_filename"] == "evidence.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["description"] == "Initial evidence"
    assert attachment["download_url"].endswith(f"/attachments/{attachment['id']}/download")

    list_response = client.get(f"/api/v1/attachments/incident/{incident_id}")
    assert list_response.status_code == 200
    attachments = list_response.json()
    assert len(attachments) == 1
    assert attachments[0]["id"] == attachment["id"]

    detail_response = client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["attachments"][0]["id"] == attachment["id"]

    download_response = client.get(f"/api/v1/attachments/{attachment['id']}/download")
    assert download_response.status_code == 200
    assert download_response.content == b"pdf-evidence"
    assert "attachment;" in download_response.headers["content-disposition"].lower()

    delete_response = client.delete(f"/api/v1/attachments/{attachment['id']}")
    assert delete_response.status_code == 204

    final_list = client.get(f"/api/v1/attachments/incident/{incident_id}")
    assert final_list.status_code == 200
    assert final_list.json() == []


def test_invalid_file_type_rejected(client: TestClient) -> None:
    incident_id = _create_incident(client)

    response = _upload_attachment(
        client,
        "incident",
        incident_id,
        filename="malware.exe",
        content=b"not-allowed",
        content_type="application/octet-stream",
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported file type"


def test_oversized_file_rejected(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATTACHMENT_MAX_FILE_SIZE_BYTES", 10)
    incident_id = _create_incident(client)

    response = _upload_attachment(
        client,
        "incident",
        incident_id,
        content=b"01234567890",
    )

    assert response.status_code == 413
    assert "maximum allowed size" in response.json()["detail"]


def test_employee_cannot_upload_incident_attachment(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    incident_id = _create_incident(client)
    employee = create_user_for_role("employee", assigned_site_id=1)
    act_as(employee)

    response = _upload_attachment(client, "incident", incident_id)

    assert response.status_code == 403


def test_supervisor_cannot_access_attachment_outside_assigned_site(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Remote Site", code="REMOTE", address="Remote", created_by_id=1))
    db_session.commit()

    incident_id = _create_incident(client, site_id=1)
    attachment = _upload_attachment(client, "incident", incident_id).json()

    supervisor = create_user_for_role("supervisor", assigned_site_id=2)
    act_as(supervisor)

    list_response = client.get(f"/api/v1/attachments/incident/{incident_id}")
    download_response = client.get(f"/api/v1/attachments/{attachment['id']}/download")

    assert list_response.status_code == 403
    assert download_response.status_code == 403


def test_uploader_can_delete_but_other_employee_cannot(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    employee = create_user_for_role("employee", assigned_site_id=1)
    response = client.post(
        "/api/v1/training",
        json={
            "title": "Self-service training",
            "training_type": "induction",
            "site_id": 1,
            "assigned_to_user_id": employee.id,
            "assigned_by_user_id": None,
            "due_date": None,
            "completed_at": None,
            "expiry_date": None,
            "status": "assigned",
            "certificate_metadata": [],
            "notes": None,
        },
    )
    assert response.status_code == 201
    training_id = response.json()["id"]

    act_as(employee)
    upload_response = _upload_attachment(client, "training", training_id)
    assert upload_response.status_code == 201
    attachment_id = upload_response.json()["id"]

    other_employee = create_user_for_role("employee", assigned_site_id=1)
    act_as(other_employee)
    denied_response = client.delete(f"/api/v1/attachments/{attachment_id}")
    assert denied_response.status_code == 403

    act_as(employee)
    delete_response = client.delete(f"/api/v1/attachments/{attachment_id}")
    assert delete_response.status_code == 204


def test_attachment_entity_not_found(client: TestClient) -> None:
    response = _upload_attachment(client, "incident", 9999)

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"
