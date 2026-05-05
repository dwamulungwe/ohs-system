from fastapi.testclient import TestClient


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Slip hazard",
        "description": "Wet floor near entrance.",
        "likelihood": 3,
        "impact": 3,
        "status": "open",
        "existing_controls": ["Wet floor sign"],
        "additional_controls": ["Improve drainage"],
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
        "title": "Monthly workshop inspection",
        "inspection_type": "workplace",
        "area_location": "Workshop A",
        "inspector_user_id": 1,
        "inspection_date": "2026-04-23T09:00:00Z",
        "status": "draft",
        "notes": "Routine monthly inspection.",
        "findings_summary": "Several issues observed.",
        "checklist_items": [
            {
                "item_name": "Emergency exits clear",
                "result": "compliant",
                "comment": "All exits accessible.",
                "action_required": False,
            },
            {
                "item_name": "Machine guards fitted",
                "result": "non_compliant",
                "comment": "Guard missing on one machine.",
                "linked_hazard_id": None,
                "action_required": True,
            },
            {
                "item_name": "Housekeeping acceptable",
                "result": "observation",
                "comment": "Minor clutter in storage area.",
                "action_required": False,
            },
        ],
        "attachments_metadata": [
            {
                "file_name": "inspection-photo.jpg",
                "content_type": "image/jpeg",
                "url": "https://example.com/inspections/inspection-photo.jpg",
                "size_bytes": 4096,
            }
        ],
        "linked_hazard_ids": [],
    }
    payload.update(overrides)
    return payload


def test_create_inspection_derives_counts_result_and_links_hazards(client: TestClient) -> None:
    hazard_response = client.post("/api/v1/hazards", json=_hazard_payload())
    hazard_id = hazard_response.json()["id"]
    payload = _inspection_payload(
        linked_hazard_ids=[hazard_id],
        checklist_items=[
            {
                "item_name": "Machine guards fitted",
                "result": "non_compliant",
                "comment": "Guard missing.",
                "linked_hazard_id": hazard_id,
                "action_required": True,
            },
            {
                "item_name": "Walkways marked",
                "result": "observation",
                "comment": "Paint fading.",
                "action_required": False,
            },
        ],
    )

    response = client.post("/api/v1/inspections", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "draft"
    assert body["overall_result"] == "major_non_conformance"
    assert body["number_of_non_conformities"] == 1
    assert body["number_of_observations"] == 1
    assert body["linked_hazard_ids"] == [hazard_id]
    assert body["checklist_items"][0]["linked_hazard_id"] == hazard_id
    assert body["attachments_metadata"][0]["file_name"] == "inspection-photo.jpg"


def test_create_inspection_respects_explicit_overall_result(client: TestClient) -> None:
    response = client.post(
        "/api/v1/inspections",
        json=_inspection_payload(overall_result="critical_non_conformance"),
    )

    assert response.status_code == 201
    assert response.json()["overall_result"] == "critical_non_conformance"


def test_list_inspections_supports_requested_filters(client: TestClient) -> None:
    client.post(
        "/api/v1/inspections",
        json=_inspection_payload(title="Filtered inspection", inspection_type="workplace"),
    )
    client.post(
        "/api/v1/inspections",
        json=_inspection_payload(
            title="Archived permit inspection",
            inspection_type="permit",
            status="archived",
            checklist_items=[],
            findings_summary="No issues.",
        ),
    )

    response = client.get(
        "/api/v1/inspections?status=draft&overall_result=major_non_conformance"
        "&site_id=1&inspector_user_id=1&inspection_type=workplace"
    )

    assert response.status_code == 200
    page = response.json()
    body = page["items"]
    assert page["total"] == 1
    assert len(body) == 1
    assert body[0]["title"] == "Filtered inspection"
    assert body[0]["inspection_type"] == "workplace"


def test_list_inspections_paginates_and_sorts_latest_inspection_first(client: TestClient) -> None:
    client.post("/api/v1/inspections", json=_inspection_payload(title="Older inspection", inspection_date="2026-03-01T09:00:00Z"))
    client.post("/api/v1/inspections", json=_inspection_payload(title="Newer inspection", inspection_date="2026-04-01T09:00:00Z"))

    response = client.get("/api/v1/inspections?skip=0&limit=1")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["skip"] == 0
    assert page["limit"] == 1
    assert [item["title"] for item in page["items"]] == ["Newer inspection"]


def test_get_inspection_returns_single_record(client: TestClient) -> None:
    create_response = client.post("/api/v1/inspections", json=_inspection_payload())

    response = client.get(f"/api/v1/inspections/{create_response.json()['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Monthly workshop inspection"


def test_update_inspection_recalculates_counts_and_result(client: TestClient) -> None:
    create_response = client.post("/api/v1/inspections", json=_inspection_payload())
    inspection_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/inspections/{inspection_id}",
        json={
            "status": "completed",
            "checklist_items": [
                {
                    "item_name": "Emergency lighting",
                    "result": "compliant",
                    "comment": "Tested successfully.",
                    "action_required": False,
                },
                {
                    "item_name": "First aid kit stocked",
                    "result": "observation",
                    "comment": "One item expires soon.",
                    "action_required": False,
                },
            ],
            "findings_summary": "Inspection completed with observation only.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["number_of_non_conformities"] == 0
    assert body["number_of_observations"] == 1
    assert body["overall_result"] == "minor_non_conformance"
    assert body["findings_summary"] == "Inspection completed with observation only."


def test_inspection_validation_rejects_missing_references(client: TestClient) -> None:
    missing_site = client.post("/api/v1/inspections", json=_inspection_payload(site_id=999))
    missing_inspector = client.post("/api/v1/inspections", json=_inspection_payload(inspector_user_id=999))
    missing_hazard = client.post("/api/v1/inspections", json=_inspection_payload(linked_hazard_ids=[999]))
    missing_checklist_hazard = client.post(
        "/api/v1/inspections",
        json=_inspection_payload(
            checklist_items=[
                {
                    "item_name": "Guarding",
                    "result": "non_compliant",
                    "linked_hazard_id": 999,
                    "action_required": True,
                }
            ]
        ),
    )

    assert missing_site.status_code == 404
    assert missing_site.json()["detail"] == "Site not found"
    assert missing_inspector.status_code == 404
    assert missing_inspector.json()["detail"] == "Inspector user not found"
    assert missing_hazard.status_code == 404
    assert missing_hazard.json()["detail"] == "Linked hazard not found"
    assert missing_checklist_hazard.status_code == 404
    assert missing_checklist_hazard.json()["detail"] == "Linked hazard not found"
