from fastapi.testclient import TestClient


def _communication_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Morning toolbox talk",
        "communication_type": "toolbox_talk",
        "status": "published",
        "summary": "Discuss forklift movement controls.",
        "details": "Focus on walkways, reversing, and spotters.",
        "audience": "Warehouse team",
        "requires_acknowledgement": False,
        "issued_at": "2026-04-25T07:30:00Z",
        "expires_at": None,
        "owner_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_create_and_get_safety_communication(client: TestClient) -> None:
    create_response = client.post("/api/v1/safety-communications", json=_communication_payload())

    assert create_response.status_code == 201
    communication_id = create_response.json()["id"]

    response = client.get(f"/api/v1/safety-communications/{communication_id}")

    assert response.status_code == 200
    assert response.json()["communication_type"] == "toolbox_talk"


def test_list_safety_communications_supports_filters(client: TestClient) -> None:
    client.post("/api/v1/safety-communications", json=_communication_payload(title="Toolbox talk"))
    client.post(
        "/api/v1/safety-communications",
        json=_communication_payload(
            title="Safety alert",
            communication_type="safety_alert",
            status="draft",
        ),
    )

    response = client.get("/api/v1/safety-communications?communication_type=safety_alert&status=draft")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Safety alert"


def test_update_safety_communication_status(client: TestClient) -> None:
    created = client.post("/api/v1/safety-communications", json=_communication_payload(status="draft")).json()

    response = client.patch(
        f"/api/v1/safety-communications/{created['id']}",
        json={"status": "published", "audience": "All staff"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["audience"] == "All staff"
