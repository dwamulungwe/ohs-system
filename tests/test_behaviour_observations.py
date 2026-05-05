from fastapi.testclient import TestClient


def _observation_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Unsafe ladder use",
        "observation_type": "unsafe_act",
        "status": "open",
        "severity": "medium",
        "description": "Worker climbed without securing the ladder.",
        "immediate_action_taken": "Stopped the task and briefed the worker.",
        "follow_up_notes": None,
        "person_involved_name": "Contractor team",
        "action_required": True,
        "observed_at": "2026-04-26T10:15:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_create_behaviour_observation_sets_reporter(client: TestClient) -> None:
    response = client.post("/api/v1/behaviour-observations", json=_observation_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["observed_by_user_id"] == 1
    assert body["observation_type"] == "unsafe_act"


def test_list_behaviour_observations_supports_status_and_type_filters(client: TestClient) -> None:
    client.post("/api/v1/behaviour-observations", json=_observation_payload(title="Unsafe act"))
    client.post(
        "/api/v1/behaviour-observations",
        json=_observation_payload(
            title="Positive observation",
            observation_type="positive_observation",
            status="reviewed",
            action_required=False,
        ),
    )

    response = client.get("/api/v1/behaviour-observations?observation_type=positive_observation&status=reviewed")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Positive observation"


def test_close_behaviour_observation_sets_closure_metadata(client: TestClient) -> None:
    created = client.post("/api/v1/behaviour-observations", json=_observation_payload()).json()

    response = client.patch(
        f"/api/v1/behaviour-observations/{created['id']}",
        json={"status": "closed", "follow_up_notes": "Coach completed."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "closed"
    assert body["closed_by_user_id"] == 1
    assert body["closed_at"] is not None
