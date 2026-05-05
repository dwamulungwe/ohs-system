from fastapi.testclient import TestClient


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Hand injury",
        "description": "Minor hand injury during maintenance.",
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
        "title": "Missing guard",
        "description": "Machine guard is missing.",
        "likelihood": 4,
        "impact": 4,
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


def _inspection_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Corrective source inspection",
        "inspection_type": "workplace",
        "area_location": "Workshop B",
        "inspector_user_id": 1,
        "inspection_date": "2026-04-23T09:00:00Z",
        "status": "draft",
        "notes": "Inspection for corrective source testing.",
        "findings_summary": "Observation found.",
        "checklist_items": [
            {
                "item_name": "Guarding",
                "result": "observation",
                "comment": "Review guard placement.",
                "action_required": True,
            }
        ],
        "attachments_metadata": [],
        "linked_hazard_ids": [],
    }
    payload.update(overrides)
    return payload


def _corrective_action_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Install replacement guard",
        "description": "Install and verify replacement machine guard.",
        "source_type": "manual",
        "source_id": None,
        "assigned_to_user_id": 1,
        "created_by_user_id": None,
        "priority": "high",
        "status": "open",
        "due_date": "2026-05-10",
        "started_at": None,
        "completed_at": None,
        "closure_notes": None,
        "closure_evidence_metadata": [],
        "verification_notes": None,
        "verified_by_user_id": None,
        "verified_at": None,
    }
    payload.update(overrides)
    return payload


def test_create_corrective_action_with_source_and_evidence_fields(client: TestClient) -> None:
    incident_response = client.post("/api/v1/incidents", json=_incident_payload())
    incident_id = incident_response.json()["id"]

    response = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(
            source_type="incident",
            source_id=incident_id,
            priority="critical",
            closure_evidence_metadata=[
                {
                    "file_name": "guard-photo.jpg",
                    "content_type": "image/jpeg",
                    "url": "https://example.com/actions/guard-photo.jpg",
                    "size_bytes": 2048,
                    "checksum": "sha256:xyz",
                }
            ],
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["source_type"] == "incident"
    assert body["source_id"] == incident_id
    assert body["priority"] == "critical"
    assert body["status"] == "open"
    assert body["assigned_to_user_id"] == 1
    assert body["created_by_user_id"] == 1
    assert body["closure_evidence_metadata"][0]["file_name"] == "guard-photo.jpg"


def test_list_corrective_actions_supports_requested_filters(client: TestClient) -> None:
    hazard_response = client.post("/api/v1/hazards", json=_hazard_payload())
    hazard_id = hazard_response.json()["id"]
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(source_type="hazard", source_id=hazard_id, priority="high"),
    )
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Low priority manual action", priority="low", status="cancelled"),
    )

    response = client.get(
        "/api/v1/corrective-actions?status=open&priority=high&site_id=1"
        "&assigned_to_user_id=1&source_type=hazard"
    )

    assert response.status_code == 200
    page = response.json()
    body = page["items"]
    assert page["total"] == 1
    assert len(body) == 1
    assert body[0]["title"] == "Install replacement guard"
    assert body[0]["source_type"] == "hazard"


def test_list_corrective_actions_paginates_and_sorts_by_due_date_then_newest(client: TestClient) -> None:
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Later action", due_date="2026-06-01"),
    )
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Earlier action", due_date="2026-05-01"),
    )

    response = client.get("/api/v1/corrective-actions?skip=0&limit=1")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["skip"] == 0
    assert page["limit"] == 1
    assert [item["title"] for item in page["items"]] == ["Earlier action"]


def test_get_corrective_action_returns_single_record(client: TestClient) -> None:
    create_response = client.post("/api/v1/corrective-actions", json=_corrective_action_payload())

    response = client.get(f"/api/v1/corrective-actions/{create_response.json()['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Install replacement guard"


def test_update_corrective_action_sets_completion_and_verification_timestamps(client: TestClient) -> None:
    create_response = client.post("/api/v1/corrective-actions", json=_corrective_action_payload())
    action_id = create_response.json()["id"]

    pending_response = client.patch(
        f"/api/v1/corrective-actions/{action_id}",
        json={
            "status": "pending_verification",
            "closure_notes": "Guard installed and tested.",
            "closure_evidence_metadata": [
                {
                    "file_name": "completion.pdf",
                    "content_type": "application/pdf",
                    "url": "https://example.com/actions/completion.pdf",
                    "size_bytes": 4096,
                }
            ],
        },
    )

    assert pending_response.status_code == 200
    pending_body = pending_response.json()
    assert pending_body["status"] == "pending_verification"
    assert pending_body["completed_at"] is not None
    assert pending_body["closure_notes"] == "Guard installed and tested."

    closed_response = client.patch(
        f"/api/v1/corrective-actions/{action_id}",
        json={
            "status": "closed",
            "verified_by_user_id": 1,
            "verification_notes": "Verified during follow-up inspection.",
        },
    )

    assert closed_response.status_code == 200
    closed_body = closed_response.json()
    assert closed_body["status"] == "closed"
    assert closed_body["completed_at"] == pending_body["completed_at"]
    assert closed_body["verified_by_user_id"] == 1
    assert closed_body["verified_at"] is not None
    assert closed_body["verification_notes"] == "Verified during follow-up inspection."


def test_corrective_action_overdue_status_is_derived(client: TestClient) -> None:
    response = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(due_date="2000-01-01", status="open"),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "overdue"


def test_corrective_action_validates_site_users_and_source_references(client: TestClient) -> None:
    missing_site = client.post("/api/v1/corrective-actions", json=_corrective_action_payload(site_id=999))
    missing_assignee = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(assigned_to_user_id=999),
    )
    missing_creator = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(created_by_user_id=999),
    )
    missing_verifier = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(verified_by_user_id=999),
    )
    invalid_source = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(source_type="incident", source_id=None),
    )
    missing_source = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(source_type="incident", source_id=999),
    )

    assert missing_site.status_code == 404
    assert missing_site.json()["detail"] == "Site not found"
    assert missing_assignee.status_code == 404
    assert missing_assignee.json()["detail"] == "Referenced user not found"
    assert missing_creator.status_code == 404
    assert missing_creator.json()["detail"] == "Referenced user not found"
    assert missing_verifier.status_code == 404
    assert missing_verifier.json()["detail"] == "Referenced user not found"
    assert invalid_source.status_code == 422
    assert invalid_source.json()["detail"] == "Invalid source reference"
    assert missing_source.status_code == 404
    assert missing_source.json()["detail"] == "Source record not found"


def test_corrective_action_accepts_inspection_source(client: TestClient) -> None:
    inspection_response = client.post("/api/v1/inspections", json=_inspection_payload())
    inspection_id = inspection_response.json()["id"]

    response = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(source_type="inspection", source_id=inspection_id),
    )

    assert response.status_code == 201
    assert response.json()["source_type"] == "inspection"
    assert response.json()["source_id"] == inspection_id
