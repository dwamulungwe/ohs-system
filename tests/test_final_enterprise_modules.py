from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _medical_payload(**overrides):
    payload = {
        "employee_user_id": 1,
        "site_id": 1,
        "surveillance_type": "Audiometry",
        "due_date": (date.today() + timedelta(days=3)).isoformat(),
        "medical_clearance_status": "pending",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _drill_payload(**overrides):
    payload = {
        "emergency_type": "Fire evacuation",
        "site_id": 1,
        "drill_date": (date.today() + timedelta(days=5)).isoformat(),
        "participants": ["Shift A"],
        "attendance_records": [{"name": "Shift A", "attendance": "present", "notes": None}],
        "issues_found": ["Assembly point congestion"],
        "corrective_actions": ["Remark staging area"],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _document_payload(**overrides):
    payload = {
        "title": "Confined Space SOP",
        "document_type": "sop",
        "version": "1.0",
        "site_id": 1,
        "status": "pending_approval",
        "acknowledgement_required": True,
        "acknowledgement_user_ids": [1],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _corrective_action_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Close audit finding",
        "description": "Track the audit finding to closure.",
        "source_type": "manual",
        "priority": "high",
        "status": "open",
        "assigned_to_user_id": 1,
        "due_date": (date.today() + timedelta(days=7)).isoformat(),
        "closure_evidence_metadata": [],
    }
    payload.update(overrides)
    return payload


def _audit_payload(**overrides):
    payload = {
        "audit_type": "internal",
        "site_id": 1,
        "auditor_user_id": 1,
        "audit_date": date.today().isoformat(),
        "findings": ["Gap in permit signage"],
        "non_conformances": ["Outdated board"],
        "recommendations": ["Replace permit board"],
        "status": "open",
        "audit_score": 86.5,
        "corrective_action_ids": [],
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_final_enterprise_modules_crud_and_exports(client: TestClient) -> None:
    medical = client.post("/api/v1/medical-surveillance", json=_medical_payload())
    drill = client.post("/api/v1/emergency-drills", json=_drill_payload())
    document = client.post("/api/v1/documents", json=_document_payload())
    corrective_action = client.post("/api/v1/corrective-actions", json=_corrective_action_payload())
    audit = client.post(
        "/api/v1/audits",
        json=_audit_payload(corrective_action_ids=[corrective_action.json()["id"]]),
    )

    assert medical.status_code == 201
    assert drill.status_code == 201
    assert document.status_code == 201
    assert corrective_action.status_code == 201
    assert audit.status_code == 201

    medical_id = medical.json()["id"]
    drill_id = drill.json()["id"]
    document_id = document.json()["id"]
    audit_id = audit.json()["id"]

    assert client.get("/api/v1/medical-surveillance").json()["total"] == 1
    assert client.get("/api/v1/emergency-drills").json()["total"] == 1
    assert client.get("/api/v1/documents").json()["total"] == 1
    assert client.get("/api/v1/audits").json()["total"] == 1

    medical_update = client.patch(
        f"/api/v1/medical-surveillance/{medical_id}",
        json={
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "medical_clearance_status": "cleared",
        },
    )
    drill_update = client.patch(
        f"/api/v1/emergency-drills/{drill_id}",
        json={"outcome": "Completed successfully"},
    )
    document_update = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"status": "approved", "approved_by_user_id": 1},
    )
    audit_update = client.patch(
        f"/api/v1/audits/{audit_id}",
        json={"status": "closed", "audit_score": 92.0},
    )

    assert medical_update.status_code == 200
    assert medical_update.json()["status"] == "completed"
    assert drill_update.status_code == 200
    assert drill_update.json()["status"] == "completed"
    assert document_update.status_code == 200
    assert document_update.json()["status"] == "approved"
    assert document_update.json()["approved_at"] is not None
    assert audit_update.status_code == 200
    assert audit_update.json()["status"] == "closed"

    html_endpoints = [
        f"/api/v1/exports/medical-surveillance/{medical_id}/report",
        f"/api/v1/exports/emergency-drills/{drill_id}/report",
        f"/api/v1/exports/documents/{document_id}/report",
        f"/api/v1/exports/audits/{audit_id}/report",
    ]
    csv_endpoints = [
        "/api/v1/exports/medical-surveillance.csv",
        "/api/v1/exports/emergency-drills.csv",
        "/api/v1/exports/documents.csv",
        "/api/v1/exports/audits.csv",
    ]

    for endpoint in html_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert "<html>" in response.text.lower()

    for endpoint in csv_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]


def test_final_enterprise_module_rbac_restrictions(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    safety_officer = create_user_for_role("safety_officer", assigned_site_id=1)
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)

    act_as(safety_officer)
    document = client.post("/api/v1/documents", json=_document_payload(status="draft")).json()
    medical = client.post("/api/v1/medical-surveillance", json=_medical_payload(employee_user_id=safety_officer.id))

    assert medical.status_code == 201
    assert client.patch(
        f"/api/v1/documents/{document['id']}",
        json={"status": "approved", "approved_by_user_id": safety_officer.id},
    ).status_code == 403

    act_as(supervisor)
    assert client.post("/api/v1/medical-surveillance", json=_medical_payload()).status_code == 403
    assert client.post("/api/v1/audits", json=_audit_payload()).status_code == 403
