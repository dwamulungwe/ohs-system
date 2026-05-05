from fastapi.testclient import TestClient


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Forklift collision",
        "description": "Forklift clipped a storage rack during loading.",
        "severity": "high",
        "status": "open",
        "occurred_at": "2026-04-23T08:30:00Z",
        "attachments_metadata": [
            {
                "file_name": "photo-1.jpg",
                "content_type": "image/jpeg",
                "url": "https://example.com/evidence/photo-1.jpg",
                "size_bytes": 58214,
                "checksum": "sha256:abc123",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_create_incident_with_status_severity_and_attachments(client: TestClient) -> None:
    response = client.post("/api/v1/incidents", json=_incident_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["reported_by_id"] == 1
    assert body["status"] == "open"
    assert body["severity"] == "high"
    assert body["attachments_metadata"][0]["file_name"] == "photo-1.jpg"


def test_list_incidents_supports_status_severity_and_site_filters(client: TestClient) -> None:
    client.post("/api/v1/incidents", json=_incident_payload(title="Filtered incident", severity="critical"))
    client.post("/api/v1/incidents", json=_incident_payload(title="Other incident", severity="low", status="resolved"))

    response = client.get("/api/v1/incidents?status=open&severity=critical&site_id=1")

    assert response.status_code == 200
    page = response.json()
    body = page["items"]
    assert page["total"] == 1
    assert len(body) == 1
    assert body[0]["title"] == "Filtered incident"
    assert body[0]["severity"] == "critical"
    assert body[0]["status"] == "open"


def test_list_incidents_paginates_and_sorts_newest_first(client: TestClient) -> None:
    client.post("/api/v1/incidents", json=_incident_payload(title="Older incident", occurred_at="2026-03-01T08:00:00Z"))
    client.post("/api/v1/incidents", json=_incident_payload(title="Newer incident", occurred_at="2026-04-01T08:00:00Z"))

    response = client.get("/api/v1/incidents?skip=0&limit=1")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["skip"] == 0
    assert page["limit"] == 1
    assert [item["title"] for item in page["items"]] == ["Newer incident"]


def test_get_incident_returns_single_record(client: TestClient) -> None:
    create_response = client.post("/api/v1/incidents", json=_incident_payload())

    response = client.get(f"/api/v1/incidents/{create_response.json()['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Forklift collision"


def test_update_incident_status_severity_and_attachments(client: TestClient) -> None:
    create_response = client.post("/api/v1/incidents", json=_incident_payload())
    incident_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "status": "investigating",
            "severity": "critical",
            "attachments_metadata": [
                {
                    "file_name": "investigation.pdf",
                    "content_type": "application/pdf",
                    "url": "https://example.com/evidence/investigation.pdf",
                    "size_bytes": 2048,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "investigating"
    assert body["severity"] == "critical"
    assert body["attachments_metadata"][0]["file_name"] == "investigation.pdf"


def test_create_incident_rejects_unknown_site(client: TestClient) -> None:
    response = client.post("/api/v1/incidents", json=_incident_payload(site_id=999))

    assert response.status_code == 404
    assert response.json()["detail"] == "Site not found"
