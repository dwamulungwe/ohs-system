from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.site import Site


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC incident",
        "description": "Incident for role access control tests.",
        "severity": "medium",
        "status": "open",
        "occurred_at": "2026-04-27T08:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC hazard",
        "description": "Hazard for role access control tests.",
        "likelihood": 4,
        "impact": 4,
        "status": "open",
        "existing_controls": [],
        "additional_controls": [],
        "owner_user_id": 1,
        "due_date": "2026-05-05",
        "review_date": "2026-05-12",
        "attachments_metadata": [],
        "incident_id": None,
    }
    payload.update(overrides)
    return payload


def _inspection_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC inspection",
        "inspection_type": "workplace",
        "area_location": "Warehouse",
        "inspector_user_id": 1,
        "inspection_date": "2026-04-27T09:00:00Z",
        "status": "draft",
        "notes": "Inspection for role tests.",
        "findings_summary": "Observation logged.",
        "checklist_items": [],
        "attachments_metadata": [],
        "linked_hazard_ids": [],
    }
    payload.update(overrides)
    return payload


def _corrective_action_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC corrective action",
        "description": "Corrective action for role access control tests.",
        "source_type": "manual",
        "priority": "medium",
        "status": "open",
        "assigned_to_user_id": 1,
        "due_date": (date.today() + timedelta(days=3)).isoformat(),
        "closure_evidence_metadata": [],
    }
    payload.update(overrides)
    return payload


def _permit_payload(**overrides):
    payload = {
        "permit_number": "RBAC-PTW-001",
        "permit_type": "hot_work",
        "title": "RBAC permit",
        "description": "Permit for role access control tests.",
        "site_id": 1,
        "area_location": "Plant room",
        "requested_by_user_id": 1,
        "issued_by_user_id": 1,
        "approved_by_user_id": 1,
        "assigned_team_or_contractor": "Maintenance",
        "start_datetime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "end_datetime": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        "status": "pending_approval",
        "risk_summary": "Fire risk.",
        "precautions_required": ["Fire watch"],
        "ppe_required": ["Gloves"],
        "isolation_required": False,
        "gas_test_required": False,
        "gas_test_results": [],
        "emergency_controls": ["Extinguisher"],
        "closure_notes": None,
        "closed_at": None,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _kpi_payload(**overrides):
    payload = {
        "site_id": 1,
        "period_start": "2026-04-01",
        "period_end": "2026-04-30",
        "hours_worked": 100000,
        "reporting_label": "April 2026",
        "employees_count": 25,
        "contractors_count": 5,
        "notes": "RBAC KPI period.",
    }
    payload.update(overrides)
    return payload


def _communication_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC toolbox talk",
        "communication_type": "toolbox_talk",
        "status": "published",
        "summary": "Short RBAC communication summary.",
        "details": "Detailed message.",
        "audience": "Shift team",
        "requires_acknowledgement": False,
        "issued_at": "2026-04-27T07:30:00Z",
        "expires_at": None,
        "owner_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _observation_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "RBAC behaviour observation",
        "observation_type": "unsafe_act",
        "status": "open",
        "severity": "medium",
        "description": "Behaviour observation for role access control tests.",
        "immediate_action_taken": "Stopped the task.",
        "follow_up_notes": None,
        "person_involved_name": "Team A",
        "action_required": True,
        "observed_at": "2026-04-27T10:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _training_payload(**overrides):
    payload = {
        "title": "RBAC training",
        "training_type": "equipment_training",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "due_date": (date.today() + timedelta(days=7)).isoformat(),
        "completed_at": None,
        "expiry_date": None,
        "status": "assigned",
        "certificate_metadata": [],
        "notes": "Training assignment for RBAC tests.",
    }
    payload.update(overrides)
    return payload


def _ack_payload(**overrides):
    payload = {
        "document_title": "RBAC SOP",
        "document_type": "policy",
        "version": "1.0",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_at": None,
        "status": "assigned",
        "notes": "Compliance acknowledgement for RBAC tests.",
    }
    payload.update(overrides)
    return payload


def test_admin_retains_full_access(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Site(id=2, name="Remote Plant", code="REMOTE", address="Remote Road", created_by_id=1))
    db_session.commit()

    assert client.get("/api/v1/users").status_code == 200
    assert client.post("/api/v1/sites", json={"name": "Camp", "code": "CAMP", "address": "Camp Road"}).status_code == 201
    assert client.post("/api/v1/roles", json={"name": "temporary_role", "description": "Temporary"}).status_code == 201
    assert client.get("/api/v1/audit-logs").status_code == 200
    assert client.get("/api/v1/dashboard/overview").status_code == 200


def test_ohs_manager_has_operational_access_but_cannot_manage_roles(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    manager = create_user_for_role("ohs_manager")
    act_as(manager)

    created = client.post("/api/v1/incidents", json=_incident_payload()).json()
    close_response = client.patch(
        f"/api/v1/incidents/{created['id']}",
        json={"status": "closed"},
    )

    assert client.get("/api/v1/users").status_code == 200
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"
    assert client.post("/api/v1/roles", json={"name": "blocked_role", "description": "Blocked"}).status_code == 403


def test_safety_officer_can_manage_operations_but_not_users_or_permit_approval(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    safety_officer = create_user_for_role("safety_officer")
    employee = create_user_for_role("employee", assigned_site_id=1)
    act_as(safety_officer)

    inspection_response = client.post(
        "/api/v1/inspections",
        json=_inspection_payload(inspector_user_id=safety_officer.id),
    )
    training_response = client.post(
        "/api/v1/training",
        json=_training_payload(assigned_to_user_id=employee.id),
    )
    permit_response = client.post(
        "/api/v1/permits",
        json=_permit_payload(permit_number="RBAC-PTW-002", approved_by_user_id=None),
    )
    kpi_response = client.post("/api/v1/safety-kpis", json=_kpi_payload())
    communication_response = client.post(
        "/api/v1/safety-communications",
        json=_communication_payload(owner_user_id=safety_officer.id),
    )
    observation_response = client.post("/api/v1/behaviour-observations", json=_observation_payload())

    assert inspection_response.status_code == 201
    assert training_response.status_code == 201
    assert permit_response.status_code == 201
    assert kpi_response.status_code == 201
    assert communication_response.status_code == 201
    assert observation_response.status_code == 201
    assert client.get("/api/v1/users").status_code == 200
    assert client.patch(
        f"/api/v1/permits/{permit_response.json()['id']}",
        json={"status": "approved"},
    ).status_code == 403


def test_supervisor_is_site_scoped_and_can_only_update_assigned_corrective_actions(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Warehouse", code="WH", address="Warehouse Road", created_by_id=1))
    db_session.commit()
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    act_as(supervisor)

    own_site_incident = client.post("/api/v1/incidents", json=_incident_payload(site_id=1))
    other_site_incident = client.post("/api/v1/incidents", json=_incident_payload(site_id=2, title="Wrong site"))
    communication_response = client.post("/api/v1/safety-communications", json=_communication_payload(site_id=1))
    observation_response = client.post("/api/v1/behaviour-observations", json=_observation_payload(site_id=1))
    forbidden_kpi = client.post("/api/v1/safety-kpis", json=_kpi_payload(site_id=1))

    act_as(1)
    action_id = client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(assigned_to_user_id=supervisor.id),
    ).json()["id"]
    client.post("/api/v1/incidents", json=_incident_payload(site_id=2, title="Remote incident"))

    act_as(supervisor)
    scoped_list = client.get("/api/v1/incidents")
    own_update = client.patch(
        f"/api/v1/corrective-actions/{action_id}",
        json={"status": "pending_verification", "closure_notes": "Work finished"},
    )
    forbidden_close = client.patch(
        f"/api/v1/corrective-actions/{action_id}",
        json={"status": "closed"},
    )

    assert own_site_incident.status_code == 201
    assert other_site_incident.status_code == 403
    assert communication_response.status_code == 201
    assert observation_response.status_code == 201
    assert forbidden_kpi.status_code == 403
    assert scoped_list.status_code == 200
    assert scoped_list.json()["total"] == 1
    assert own_update.status_code == 200
    assert own_update.json()["status"] == "pending_verification"
    assert forbidden_close.status_code == 403


def test_employee_is_site_scoped_has_self_service_access_and_no_dashboard(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Yard", code="YARD", address="Yard Road", created_by_id=1))
    db_session.commit()
    employee = create_user_for_role("employee", assigned_site_id=1)

    act_as(1)
    training_id = client.post(
        "/api/v1/training",
        json=_training_payload(assigned_to_user_id=employee.id),
    ).json()["id"]
    acknowledgement_id = client.post(
        "/api/v1/compliance-acknowledgements",
        json=_ack_payload(assigned_to_user_id=employee.id),
    ).json()["id"]
    client.post("/api/v1/incidents", json=_incident_payload(site_id=2, title="Remote employee incident"))

    act_as(employee)
    own_incident = client.post("/api/v1/incidents", json=_incident_payload(site_id=1, title="Employee incident"))
    own_hazard = client.post(
        "/api/v1/hazards",
        json=_hazard_payload(site_id=1, owner_user_id=None, title="Employee hazard"),
    )
    own_observation = client.post(
        "/api/v1/behaviour-observations",
        json=_observation_payload(site_id=1, title="Employee observation"),
    )
    communication_list = client.get("/api/v1/safety-communications")
    forbidden_kpi = client.post("/api/v1/safety-kpis", json=_kpi_payload(site_id=1))
    forbidden_incident_update = client.patch(
        f"/api/v1/incidents/{own_incident.json()['id']}",
        json={"status": "closed"},
    )
    training_list = client.get("/api/v1/training")
    training_update = client.patch(
        f"/api/v1/training/{training_id}",
        json={"completed_at": datetime.now(timezone.utc).isoformat()},
    )
    acknowledgement_update = client.patch(
        f"/api/v1/compliance-acknowledgements/{acknowledgement_id}",
        json={"acknowledged_at": datetime.now(timezone.utc).isoformat()},
    )
    permit_request = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="RBAC-PTW-003",
            site_id=1,
            requested_by_user_id=999,
            issued_by_user_id=None,
            approved_by_user_id=None,
        ),
    )
    forbidden_dashboard = client.get("/api/v1/dashboard/overview")
    scoped_incidents = client.get("/api/v1/incidents")

    assert own_incident.status_code == 201
    assert own_hazard.status_code == 201
    assert own_observation.status_code == 201
    assert communication_list.status_code == 200
    assert forbidden_kpi.status_code == 403
    assert forbidden_incident_update.status_code == 403
    assert training_list.status_code == 200
    assert training_list.json()["total"] == 1
    assert training_update.status_code == 200
    assert training_update.json()["status"] == "completed"
    assert acknowledgement_update.status_code == 200
    assert acknowledgement_update.json()["status"] == "acknowledged"
    assert permit_request.status_code == 201
    assert permit_request.json()["requested_by_user_id"] == employee.id
    assert forbidden_dashboard.status_code == 403
    assert scoped_incidents.status_code == 200
    assert scoped_incidents.json()["total"] == 1
