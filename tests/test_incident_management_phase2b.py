from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.corrective_action import CorrectiveAction, CorrectiveActionSourceType
from app.models.incident import Incident, IncidentStatus
from app.models.notification import Notification, NotificationType
from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.site import Site
from app.services.incident_management_service import generate_incident_reminders
from app.services.tenancy import unscoped_session


def incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Conveyor entanglement near miss",
        "description": "An operator stopped the conveyor before contact occurred.",
        "incident_type": "near_miss",
        "severity": "medium",
        "status": "reported",
        "occurred_at": "2026-04-23T08:30:00Z",
        "area_location": "Packing line 2",
        "immediate_response": {"area_isolated": True, "supervisor_notified": True},
    }
    payload.update(overrides)
    return payload


def create_incident(client: TestClient, **overrides) -> dict:
    response = client.post("/api/v1/incidents", json=incident_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_incident_numbering_is_year_local_and_workspace_is_structured(client: TestClient) -> None:
    first = create_incident(client)
    second = create_incident(client, title="Second incident")
    prior_year = create_incident(client, title="Prior-year incident", occurred_at="2025-12-31T23:00:00Z")

    assert first["incident_reference"] == "INC-2026-000001"
    assert second["incident_reference"] == "INC-2026-000002"
    assert prior_year["incident_reference"] == "INC-2025-000001"
    workspace = client.get(f"/api/v1/incidents/{first['id']}/workspace").json()
    assert workspace["incident_type"] == "near_miss"
    assert workspace["immediate_response"]["area_isolated"] is True
    assert workspace["activities"][0]["event_type"] == "incident_created"


def test_custom_classification_and_cause_taxonomy(client: TestClient) -> None:
    classification = client.post("/api/v1/incidents/classifications", json={
        "code": "process_safety_event", "name": "Process Safety Event",
        "is_recordable": True, "investigation_required": True,
    })
    assert classification.status_code == 201
    incident = create_incident(client, incident_type="process_safety_event")
    assert incident["is_recordable"] is True

    category = client.post("/api/v1/incidents/cause-categories", json={
        "code": "isolation_design", "name": "Isolation Design", "level": "root",
    })
    assert category.status_code == 201
    cause = client.post(f"/api/v1/incidents/{incident['id']}/causes", json={
        "cause_level": "root", "category_code": "isolation_design",
        "description": "Isolation points were not accessible.", "methodology": "five_whys",
        "problem_statement": "Unexpected energisation was possible.",
        "why_steps": [
            {"sequence": 1, "question": "Why?", "answer": "The isolator was inaccessible."},
            {"sequence": 2, "question": "Why?", "answer": "The original design omitted access."},
        ],
        "is_root_cause": True,
    })
    assert cause.status_code == 201, cause.text
    assert len(cause.json()["why_steps"]) == 2


def test_people_medical_treatment_and_return_to_work_are_permission_restricted(
    client: TestClient, create_user_for_role, act_as,
) -> None:
    incident = create_incident(client, incident_type="lost_time_injury", severity="high")
    person = client.post(f"/api/v1/incidents/{incident['id']}/people", json={
        "external_name": "External Technician", "involvement_role": "injured_person",
        "job_title": "Technician",
    })
    assert person.status_code == 201
    person_id = person.json()["id"]
    injury = client.post(f"/api/v1/incidents/{incident['id']}/injuries", json={
        "incident_person_id": person_id, "injury_present": True,
        "body_part": "Hand", "injury_type": "Laceration",
        "diagnosis_description": "Confidential diagnosis", "treatment_required": True,
        "days_lost": 2, "first_day_absent": "2026-04-23",
    })
    assert injury.status_code == 201
    assert client.post(f"/api/v1/incidents/{incident['id']}/treatments", json={
        "incident_person_id": person_id, "treatment_type": "clinic_treatment",
        "treatment_summary": "Wound care", "follow_up_required": True,
    }).status_code == 201
    rtw = client.post(f"/api/v1/incidents/{incident['id']}/return-to-work", json={
        "incident_person_id": person_id, "status": "restricted_duties",
        "medical_clearance_required": True, "clearance_received": True,
        "restrictions": "No lifting", "planned_return_date": "2026-04-25",
    })
    assert rtw.status_code == 201

    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    act_as(supervisor)
    assert client.get(f"/api/v1/incidents/{incident['id']}/medical").status_code == 403
    assert client.get(f"/api/v1/incidents/{incident['id']}/workspace").status_code == 200


def test_investigation_timeline_findings_and_unified_action(client: TestClient) -> None:
    incident = create_incident(client, severity="high")
    investigation = client.post("/api/v1/incident-investigations", json={
        "incident_id": incident["id"], "investigation_lead_user_id": 1,
        "status": "assigned", "target_completion_date": "2026-04-30",
        "scope": "Examine guarding and isolation.", "objectives": "Prevent recurrence.",
    })
    assert investigation.status_code == 201, investigation.text
    investigation_id = investigation.json()["id"]
    for next_status in ("in_progress", "pending_review", "completed"):
        response = client.patch(f"/api/v1/incident-investigations/{investigation_id}", json={"status": next_status})
        assert response.status_code == 200, response.text
    event = client.post(f"/api/v1/incidents/{incident['id']}/events", json={
        "event_at": "2026-04-23T08:29:00Z", "event_type": "pre_event",
        "description": "Operator noticed abnormal noise.",
    })
    assert event.status_code == 201
    finding = client.post(f"/api/v1/incidents/{incident['id']}/findings", json={
        "investigation_id": investigation_id, "title": "Guard interlock bypassed",
        "description": "The interlock could be bypassed.", "finding_type": "non_conformance",
        "severity": "critical", "action_required": True,
    })
    assert finding.status_code == 201
    action = client.post(f"/api/v1/incidents/{incident['id']}/actions", json={
        "finding_id": finding.json()["id"], "title": "Redesign interlock",
        "description": "Install a tamper-resistant monitored interlock.",
        "acceptance_criteria": "Functional safety test passed.", "priority": "critical",
        "owner_user_id": 1, "due_date": "2026-05-15",
    })
    assert action.status_code == 201, action.text
    assert action.json()["source_type"] == "incident"
    assert action.json()["source_id"] == incident["id"]


def test_regulatory_closure_verification_and_reopening(
    client: TestClient, create_user_for_role, act_as,
) -> None:
    incident = create_incident(
        client, severity="high", incident_type="dangerous_occurrence",
        regulator_notification_required=True, regulator_notification_status="required",
    )
    investigation = client.post("/api/v1/incident-investigations", json={
        "incident_id": incident["id"], "status": "completed",
        "scope": "Determine causal factors.",
    })
    assert investigation.status_code == 201
    regulatory = client.post(f"/api/v1/incidents/{incident['id']}/regulatory", json={
        "notification_required": True, "regulator_name": "Configured Regulator",
        "notification_deadline": "2026-04-24T12:00:00Z", "status": "submitted",
        "notified_at": "2026-04-23T10:00:00Z", "regulator_reference": "REG-42",
    })
    assert regulatory.status_code == 201
    verifier = create_user_for_role("ohs_manager")
    requested = client.post(f"/api/v1/incidents/{incident['id']}/closure/request", json={
        "closure_summary": "Investigation and notification complete.",
        "lessons_learned": {"what_changed": "Isolation standard revised."},
        "verifier_user_id": verifier.id,
    })
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "pending_closure"
    assert client.post(f"/api/v1/incidents/{incident['id']}/closure/verify", json={
        "approved": True, "notes": "Independent verification complete.",
    }).status_code == 422
    act_as(verifier)
    closed = client.post(f"/api/v1/incidents/{incident['id']}/closure/verify", json={
        "approved": True, "notes": "Independent verification complete.",
    })
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    reopened = client.post(f"/api/v1/incidents/{incident['id']}/reopen", json={"reason": "New evidence received."})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "reopened"


def test_linkage_dashboard_exports_and_reminder_deduplication(client: TestClient, db_session) -> None:
    incident = create_incident(client, severity="critical")
    hazard = client.post("/api/v1/hazards", json={
        "site_id": 1, "title": "Inadequate guarding", "description": "Accessible nip point.",
        "likelihood": 5, "impact": 5, "status": "open", "owner_user_id": 1,
        "existing_controls": [], "additional_controls": ["Install fixed guard"],
    })
    assert hazard.status_code == 201
    link = client.post(f"/api/v1/incidents/{incident['id']}/links", json={
        "linked_entity_type": "hazard", "linked_entity_id": hazard.json()["id"],
        "involvement": {"systemic_hazard": True},
    })
    assert link.status_code == 201
    assert client.get(f"/api/v1/incidents/linked/hazard/{hazard.json()['id']}").json()[0]["id"] == incident["id"]
    investigation = client.post("/api/v1/incident-investigations", json={
        "incident_id": incident["id"], "investigation_lead_user_id": 1,
        "status": "assigned", "target_completion_date": "2026-04-20",
    })
    assert investigation.status_code == 201
    first = generate_incident_reminders(db_session)
    second = generate_incident_reminders(db_session)
    assert first["investigation_overdue"] == 1
    assert second.get("investigation_overdue", 0) == 0
    notification_types = set(db_session.scalars(select(Notification.notification_type)).all())
    assert NotificationType.investigation_overdue in notification_types
    assert client.get("/api/v1/incidents/dashboard").json()["open_incidents"] == 1
    assert client.get("/api/v1/exports/incident-register.csv").status_code == 200
    assert client.get("/api/v1/exports/incident-root-causes.csv").status_code == 200


def test_cross_tenant_incident_ids_fail_closed(client: TestClient, db_session) -> None:
    with unscoped_session(db_session, allow_writes=True):
        organisation = Organisation(id=2, name="Other Tenant", code="OTHER", slug="other", timezone="UTC")
        db_session.add(organisation); db_session.flush()
        db_session.add(OrganisationSettings(organisation_id=2))
        db_session.add(OrganisationFeature(organisation_id=2, key="incidents", is_enabled=True))
        site = Site(id=99, organisation_id=2, name="Other Site", code="OTHER", address="Elsewhere")
        db_session.add(site); db_session.flush()
        other = Incident(
            organisation_id=2, site_id=99, incident_reference="INC-2026-000001",
            title="Other tenant incident", description="Must remain hidden.",
            incident_type="other", severity="low", status=IncidentStatus.reported,
            occurred_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )
        db_session.add(other); db_session.commit(); other_id = other.id
    assert client.get(f"/api/v1/incidents/{other_id}").status_code == 404
