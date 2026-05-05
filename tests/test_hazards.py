from fastapi.testclient import TestClient


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Linked incident",
        "description": "Incident used to verify optional hazard linkage.",
        "severity": "medium",
        "status": "open",
        "occurred_at": "2026-04-23T08:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Unguarded machine edge",
        "description": "Exposed cutting edge near the production walkway.",
        "likelihood": 4,
        "impact": 5,
        "status": "open",
        "existing_controls": ["Warning sign"],
        "additional_controls": ["Install fixed guard", "Update operator briefing"],
        "owner_user_id": 1,
        "due_date": "2026-05-01",
        "review_date": "2026-05-15",
        "attachments_metadata": [
            {
                "file_name": "hazard-photo.jpg",
                "content_type": "image/jpeg",
                "url": "https://example.com/hazards/hazard-photo.jpg",
                "size_bytes": 9912,
                "checksum": "sha256:def456",
            }
        ],
        "incident_id": None,
    }
    payload.update(overrides)
    return payload


def test_create_hazard_calculates_risk_and_stores_register_fields(client: TestClient) -> None:
    incident_response = client.post("/api/v1/incidents", json=_incident_payload())
    incident_id = incident_response.json()["id"]

    response = client.post("/api/v1/hazards", json=_hazard_payload(incident_id=incident_id))

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["likelihood"] == 4
    assert body["impact"] == 5
    assert body["risk_score"] == 20
    assert body["risk_level"] == "critical"
    assert body["owner_user_id"] == 1
    assert body["incident_id"] == incident_id
    assert body["existing_controls"] == ["Warning sign"]
    assert body["additional_controls"] == ["Install fixed guard", "Update operator briefing"]
    assert body["attachments_metadata"][0]["file_name"] == "hazard-photo.jpg"


def test_list_hazards_supports_status_risk_site_and_owner_filters(client: TestClient) -> None:
    client.post("/api/v1/hazards", json=_hazard_payload(title="Critical open hazard"))
    client.post(
        "/api/v1/hazards",
        json=_hazard_payload(title="Medium controlled hazard", likelihood=2, impact=3, status="controlled"),
    )

    response = client.get("/api/v1/hazards?status=open&risk_level=critical&site_id=1&owner_user_id=1")

    assert response.status_code == 200
    page = response.json()
    body = page["items"]
    assert page["total"] == 1
    assert len(body) == 1
    assert body[0]["title"] == "Critical open hazard"
    assert body[0]["risk_level"] == "critical"
    assert body[0]["status"] == "open"


def test_list_hazards_paginates_and_sorts_highest_risk_first(client: TestClient) -> None:
    client.post("/api/v1/hazards", json=_hazard_payload(title="Medium hazard", likelihood=2, impact=3))
    client.post("/api/v1/hazards", json=_hazard_payload(title="Critical hazard", likelihood=5, impact=5))

    response = client.get("/api/v1/hazards?skip=0&limit=1")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["skip"] == 0
    assert page["limit"] == 1
    assert [item["title"] for item in page["items"]] == ["Critical hazard"]


def test_get_hazard_returns_single_record(client: TestClient) -> None:
    create_response = client.post("/api/v1/hazards", json=_hazard_payload())

    response = client.get(f"/api/v1/hazards/{create_response.json()['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Unguarded machine edge"


def test_update_hazard_recalculates_risk_and_updates_controls(client: TestClient) -> None:
    create_response = client.post("/api/v1/hazards", json=_hazard_payload())
    hazard_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/hazards/{hazard_id}",
        json={
            "likelihood": 2,
            "impact": 3,
            "status": "controlled",
            "existing_controls": ["Fixed guard installed"],
            "additional_controls": ["Monthly inspection"],
            "review_date": "2026-06-01",
            "attachments_metadata": [
                {
                    "file_name": "guard-install.pdf",
                    "content_type": "application/pdf",
                    "url": "https://example.com/hazards/guard-install.pdf",
                    "size_bytes": 1200,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "controlled"
    assert body["likelihood"] == 2
    assert body["impact"] == 3
    assert body["risk_score"] == 6
    assert body["risk_level"] == "medium"
    assert body["existing_controls"] == ["Fixed guard installed"]
    assert body["additional_controls"] == ["Monthly inspection"]
    assert body["attachments_metadata"][0]["file_name"] == "guard-install.pdf"


def test_hazard_likelihood_and_impact_are_limited_to_one_through_five(client: TestClient) -> None:
    response = client.post("/api/v1/hazards", json=_hazard_payload(likelihood=6))

    assert response.status_code == 422


def test_create_hazard_rejects_missing_references(client: TestClient) -> None:
    missing_site = client.post("/api/v1/hazards", json=_hazard_payload(site_id=999))
    missing_owner = client.post("/api/v1/hazards", json=_hazard_payload(owner_user_id=999))
    missing_incident = client.post("/api/v1/hazards", json=_hazard_payload(incident_id=999))

    assert missing_site.status_code == 404
    assert missing_site.json()["detail"] == "Site not found"
    assert missing_owner.status_code == 404
    assert missing_owner.json()["detail"] == "Owner user not found"
    assert missing_incident.status_code == 404
    assert missing_incident.json()["detail"] == "Linked incident not found"
