from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def test_core_create_update_and_status_transition_actions_are_audited(client: TestClient, db_session: Session) -> None:
    incident_create = client.post(
        "/api/v1/incidents",
        json={
            "site_id": 1,
            "title": "Audit incident",
            "description": "Incident audit trail.",
            "severity": "medium",
            "status": "open",
            "occurred_at": "2026-04-23T08:30:00Z",
            "attachments_metadata": [],
        },
    )
    incident_id = incident_create.json()["id"]
    client.patch(f"/api/v1/incidents/{incident_id}", json={"status": "investigating"})

    hazard_create = client.post(
        "/api/v1/hazards",
        json={
            "site_id": 1,
            "title": "Audit hazard",
            "description": "Hazard audit trail.",
            "likelihood": 4,
            "impact": 5,
            "status": "open",
            "existing_controls": [],
            "additional_controls": [],
            "owner_user_id": 1,
            "attachments_metadata": [],
        },
    )
    hazard_id = hazard_create.json()["id"]
    client.patch(f"/api/v1/hazards/{hazard_id}", json={"status": "controlled"})

    inspection_create = client.post(
        "/api/v1/inspections",
        json={
            "site_id": 1,
            "title": "Audit inspection",
            "inspection_type": "workplace",
            "area_location": "Audit area",
            "inspector_user_id": 1,
            "inspection_date": "2026-04-23T09:00:00Z",
            "status": "draft",
            "checklist_items": [],
            "attachments_metadata": [],
            "linked_hazard_ids": [],
        },
    )
    inspection_id = inspection_create.json()["id"]
    client.patch(f"/api/v1/inspections/{inspection_id}", json={"status": "completed"})

    action_create = client.post(
        "/api/v1/corrective-actions",
        json={
            "site_id": 1,
            "title": "Audit action",
            "description": "Corrective action audit trail.",
            "source_type": "manual",
            "priority": "medium",
            "status": "open",
            "assigned_to_user_id": 1,
            "due_date": "2026-05-10",
            "closure_evidence_metadata": [],
        },
    )
    action_id = action_create.json()["id"]
    client.patch(f"/api/v1/corrective-actions/{action_id}", json={"status": "pending_verification"})

    actions = {entry.action for entry in db_session.query(AuditLog).all()}

    assert {
        "incident.create",
        "incident.update",
        "incident.status_transition",
        "hazard.create",
        "hazard.update",
        "hazard.status_transition",
        "inspection.create",
        "inspection.update",
        "inspection.status_transition",
        "corrective_action.create",
        "corrective_action.update",
        "corrective_action.status_transition",
    }.issubset(actions)
