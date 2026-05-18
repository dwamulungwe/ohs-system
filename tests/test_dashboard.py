from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.approval import ApprovalWorkflow
from app.models.hazard import Hazard
from app.models.site import Site


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Dashboard incident",
        "description": "Incident for dashboard aggregation.",
        "severity": "high",
        "status": "open",
        "occurred_at": "2026-04-10T08:30:00Z",
        "is_recordable": False,
        "is_lost_time": False,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Chemical spill - blending area",
        "description": "Hazard for dashboard aggregation.",
        "likelihood": 4,
        "impact": 5,
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
        "title": "Dashboard inspection",
        "inspection_type": "workplace",
        "area_location": "Workshop C",
        "inspector_user_id": 1,
        "inspection_date": "2026-04-12T09:00:00Z",
        "status": "completed",
        "notes": "Dashboard aggregation inspection.",
        "findings_summary": "No issues.",
        "checklist_items": [
            {
                "item_name": "Walkways clear",
                "result": "compliant",
                "comment": "Clear.",
                "action_required": False,
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
        "title": "Dashboard corrective action",
        "description": "Action for dashboard aggregation.",
        "source_type": "manual",
        "source_id": None,
        "assigned_to_user_id": 1,
        "created_by_user_id": None,
        "priority": "critical",
        "status": "open",
        "due_date": "2000-01-01",
        "closure_evidence_metadata": [],
    }
    payload.update(overrides)
    return payload


def _training_payload(**overrides):
    payload = {
        "title": "Forklift induction",
        "training_type": "equipment_training",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "due_date": (date.today() + timedelta(days=10)).isoformat(),
        "completed_at": None,
        "expiry_date": None,
        "status": "assigned",
        "certificate_metadata": [],
        "notes": "Training assignment for analytics.",
    }
    payload.update(overrides)
    return payload


def _ack_payload(**overrides):
    payload = {
        "document_title": "PPE Policy",
        "document_type": "policy",
        "version": "1.0",
        "site_id": 1,
        "assigned_to_user_id": 1,
        "assigned_by_user_id": None,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_at": None,
        "status": "assigned",
        "notes": "Review and acknowledge.",
    }
    payload.update(overrides)
    return payload


def _permit_payload(**overrides):
    payload = {
        "permit_number": "PTW-001",
        "permit_type": "hot_work",
        "title": "Welding repair",
        "description": "Welding repair on production line.",
        "site_id": 1,
        "area_location": "Workshop bay 2",
        "requested_by_user_id": 1,
        "issued_by_user_id": 1,
        "approved_by_user_id": None,
        "assigned_team_or_contractor": "Maintenance team",
        "start_datetime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "end_datetime": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        "status": "pending_approval",
        "risk_summary": "Fire and fume hazards.",
        "precautions_required": ["Fire watch", "Remove combustibles"],
        "ppe_required": ["Gloves", "Face shield"],
        "isolation_required": False,
        "gas_test_required": False,
        "gas_test_results": [],
        "emergency_controls": ["Extinguisher nearby"],
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
        "hours_worked": 200000,
        "reporting_label": "April 2026",
        "employees_count": 120,
        "contractors_count": 25,
        "notes": "Monthly KPI period.",
    }
    payload.update(overrides)
    return payload


def _communication_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Toolbox talk",
        "communication_type": "toolbox_talk",
        "status": "published",
        "summary": "Discuss line-of-fire exposures.",
        "details": "Focus on pedestrian separation and lifting zones.",
        "audience": "Operations team",
        "requires_acknowledgement": False,
        "issued_at": "2026-04-18T07:30:00Z",
        "expires_at": None,
        "owner_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _observation_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Unsafe exclusion zone entry",
        "observation_type": "unsafe_act",
        "status": "open",
        "severity": "high",
        "description": "Worker entered a lifting exclusion zone.",
        "immediate_action_taken": "Stopped the lift and reset the barricade.",
        "follow_up_notes": None,
        "person_involved_name": "Shift A crew",
        "action_required": True,
        "observed_at": "2026-04-19T10:00:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _investigation_payload(incident_id, **overrides):
    payload = {
        "incident_id": incident_id,
        "investigation_lead_user_id": 1,
        "investigation_team": ["Lead investigator", "Supervisor"],
        "witness_statements": [{"name": "Witness A", "statement": "Observed the incident."}],
        "immediate_causes": ["Barrier not in place"],
        "underlying_causes": ["Weak task planning"],
        "root_cause": "Inadequate pre-task controls",
        "five_whys": ["Why 1", "Why 2"],
        "contributing_factors": ["Time pressure"],
        "recommendations": ["Refresh the pre-start checklist"],
        "status": "pending_approval",
        "target_completion_date": "2026-04-30",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _legal_compliance_payload(**overrides):
    payload = {
        "title": "Hazardous substances register",
        "regulatory_body": "Labour Inspectorate",
        "legal_reference": "HSA-12",
        "requirement_summary": "Maintain and review the hazardous substances register.",
        "site_id": 1,
        "owner_user_id": 1,
        "compliance_status": "non_compliant",
        "review_frequency": "monthly",
        "next_review_date": "2026-04-20",
        "evidence_required": True,
        "notes": "Evidence pack missing.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _jsa_payload(**overrides):
    payload = {
        "title": "Confined space cleaning",
        "site_id": 1,
        "department_or_area": "Tank farm",
        "job_steps": ["Isolate vessel", "Ventilate", "Clean"],
        "hazards": ["Atmospheric hazard", "Slip hazard"],
        "controls": ["Gas test", "Standby watch"],
        "ppe_required": ["Respirator", "Harness"],
        "residual_risk_level": "high",
        "status": "pending_approval",
        "review_date": "2026-04-30",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _contractor_payload(**overrides):
    payload = {
        "contractor_name": "Prime Industrial Services",
        "contact_person": "Lydia Banda",
        "contact_email": "lydia@example.com",
        "contact_phone": "+260971000001",
        "site_id": 1,
        "work_scope": "Shutdown maintenance support",
        "onboarding_status": "in_progress",
        "induction_status": "pending",
        "insurance_expiry_date": "2026-04-15",
        "compliance_documents_status": "incomplete",
        "approved_for_work": False,
        "documents_expiry_date": "2026-04-18",
        "notes": "Missing final insurance certificate.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _asset_payload(**overrides):
    payload = {
        "asset_type": "equipment",
        "asset_name": "Portable gas detector",
        "asset_tag": "ASSET-001",
        "site_id": 1,
        "location": "Confined space locker",
        "assigned_to_user_id": 1,
        "inspection_frequency": "monthly",
        "next_inspection_date": "2026-04-18",
        "condition_status": "defective",
        "notes": "Sensor calibration failed.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _seed_dashboard_data(client: TestClient, db_session: Session) -> None:
    db_session.add(Site(id=2, name="Remote Depot", code="DEPOT", address="Depot Road", created_by_id=1))
    db_session.commit()

    critical_incident = client.post(
        "/api/v1/incidents",
        json=_incident_payload(
            title="Critical incident",
            severity="critical",
            status="open",
            occurred_at="2026-04-10T08:30:00Z",
            is_recordable=True,
        ),
    ).json()
    remote_incident = client.post(
        "/api/v1/incidents",
        json=_incident_payload(
            site_id=2,
            title="Remote incident",
            severity="low",
            status="closed",
            occurred_at="2026-03-05T08:30:00Z",
            is_lost_time=True,
        ),
    ).json()

    hazard_one = client.post("/api/v1/hazards", json=_hazard_payload(title="Chemical spill - blending area")).json()
    hazard_two = client.post("/api/v1/hazards", json=_hazard_payload(title="Chemical spill - loading bay")).json()
    client.post(
        "/api/v1/hazards",
        json=_hazard_payload(title="Unguarded edge - mezzanine", likelihood=3, impact=4),
    )
    client.post(
        "/api/v1/hazards",
        json=_hazard_payload(site_id=2, title="Remote hazard", likelihood=2, impact=2, status="controlled"),
    )

    hazard_record_one = db_session.get(Hazard, hazard_one["id"])
    hazard_record_two = db_session.get(Hazard, hazard_two["id"])
    hazard_record_one.created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
    hazard_record_two.created_at = datetime(2026, 4, 11, tzinfo=timezone.utc)
    db_session.add_all([hazard_record_one, hazard_record_two])
    db_session.commit()

    client.post("/api/v1/inspections", json=_inspection_payload())
    client.post(
        "/api/v1/inspections",
        json=_inspection_payload(
            site_id=2,
            title="Remote inspection",
            status="draft",
            inspection_date="2026-03-08T09:00:00Z",
            checklist_items=[],
        ),
    )

    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(title="Overdue action", priority="critical", due_date="2000-01-01"),
    )
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(
            title="Due soon action",
            priority="high",
            status="in_progress",
            due_date=(date.today() + timedelta(days=3)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(
            title="Pending verification action",
            priority="medium",
            status="pending_verification",
            due_date=(date.today() + timedelta(days=5)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/corrective-actions",
        json=_corrective_action_payload(site_id=2, title="Remote site action", priority="low"),
    )

    client.post(
        "/api/v1/training",
        json=_training_payload(
            title="Completed valid training",
            completed_at=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            status="completed",
            expiry_date=(date.today() + timedelta(days=30)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/training",
        json=_training_payload(
            title="Overdue training",
            due_date=(date.today() - timedelta(days=2)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/training",
        json=_training_payload(
            title="Expired training",
            completed_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
            expiry_date=(date.today() - timedelta(days=1)).isoformat(),
        ),
    )

    client.post(
        "/api/v1/compliance-acknowledgements",
        json=_ack_payload(document_title="Overdue acknowledgement", assigned_at=(datetime.now(timezone.utc) - timedelta(days=45)).isoformat()),
    )
    client.post(
        "/api/v1/compliance-acknowledgements",
        json=_ack_payload(
            document_title="Acknowledged policy",
            acknowledged_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        ),
    )

    client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-ACTIVE",
            status="active",
            end_datetime=(datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-PENDING",
            status="pending_approval",
            end_datetime=(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
        ),
    )
    client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-EXPIRED",
            status="approved",
            start_datetime=(datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
            end_datetime=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        ),
    )
    permit_for_approval = client.post(
        "/api/v1/permits",
        json=_permit_payload(
            permit_number="PTW-APPROVAL",
            status="draft",
            end_datetime=(datetime.now(timezone.utc) + timedelta(hours=96)).isoformat(),
        ),
    ).json()

    client.post("/api/v1/safety-kpis", json=_kpi_payload())
    client.post(
        "/api/v1/safety-kpis",
        json=_kpi_payload(
            site_id=2,
            period_start="2026-03-01",
            period_end="2026-03-31",
            reporting_label="March 2026",
            hours_worked=100000,
        ),
    )
    client.post("/api/v1/safety-communications", json=_communication_payload())
    client.post(
        "/api/v1/safety-communications",
        json=_communication_payload(
            site_id=2,
            title="Remote safety alert",
            communication_type="safety_alert",
            status="draft",
            issued_at="2026-03-20T09:00:00Z",
        ),
    )
    client.post("/api/v1/behaviour-observations", json=_observation_payload())
    client.post(
        "/api/v1/behaviour-observations",
        json=_observation_payload(
            site_id=2,
            title="Positive remote observation",
            observation_type="positive_observation",
            status="reviewed",
            severity="low",
            action_required=False,
            observed_at="2026-03-21T11:00:00Z",
        ),
    )
    client.post("/api/v1/incident-investigations", json=_investigation_payload(critical_incident["id"]))
    client.post(
        "/api/v1/incident-investigations",
        json=_investigation_payload(
            remote_incident["id"],
            status="approved",
            target_completion_date="2026-03-10",
        ),
    )
    client.post("/api/v1/legal-compliance", json=_legal_compliance_payload())
    client.post(
        "/api/v1/legal-compliance",
        json=_legal_compliance_payload(
            title="Remote compliance item",
            site_id=2,
            compliance_status="compliant",
            next_review_date="2026-05-20",
            evidence_required=False,
        ),
    )
    client.post("/api/v1/jsas", json=_jsa_payload())
    client.post(
        "/api/v1/jsas",
        json=_jsa_payload(
            title="Remote approved JSA",
            site_id=2,
            status="approved",
            review_date="2026-03-25",
            residual_risk_level="medium",
        ),
    )
    client.post("/api/v1/contractors", json=_contractor_payload())
    client.post(
        "/api/v1/contractors",
        json=_contractor_payload(
            contractor_name="Remote approved contractor",
            site_id=2,
            onboarding_status="completed",
            induction_status="completed",
            insurance_expiry_date="2026-05-30",
            compliance_documents_status="complete",
            documents_expiry_date="2026-05-30",
            approved_for_work=True,
        ),
    )
    client.post("/api/v1/asset-register", json=_asset_payload())
    client.post(
        "/api/v1/asset-register",
        json=_asset_payload(
            asset_name="Emergency eyewash station",
            asset_tag="ASSET-002",
            asset_type="emergency_equipment",
            site_id=2,
            condition_status="good",
            next_inspection_date="2026-05-15",
        ),
    )

    pending_approval = client.post(
        "/api/v1/approvals/incident/1/request",
        json={"action_type": "incident_closure", "request_notes": "Pending review for closure."},
    )
    approved_workflow = client.post(
        f"/api/v1/approvals/permit/{permit_for_approval['id']}/request",
        json={"action_type": "permit_approval", "request_notes": "Permit package complete."},
    ).json()
    client.patch(
        f"/api/v1/approvals/{approved_workflow['id']}/decision",
        json={"status": "approved", "decision_notes": "Approved for work."},
    )

    approval_record = db_session.get(ApprovalWorkflow, pending_approval.json()["id"])
    approval_record.created_at = datetime(2026, 4, 14, tzinfo=timezone.utc)
    approval_record.updated_at = datetime(2026, 4, 14, tzinfo=timezone.utc)
    db_session.add(approval_record)
    db_session.commit()


def test_dashboard_overview_returns_stable_counts(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["total_incidents"] == 2
    assert body["incidents_by_status"]["open"] == 1
    assert body["incidents_by_severity"]["critical"] == 1
    assert body["total_hazards"] == 4
    assert body["hazards_by_risk_level"]["critical"] == 2
    assert body["total_inspections"] == 2
    assert body["inspections_by_status"]["completed"] == 1
    assert body["total_corrective_actions"] == 4
    assert body["corrective_actions_by_priority"]["critical"] == 1
    assert body["overdue_corrective_actions_count"] == 2
    assert body["total_safety_kpi_records"] == 2
    assert body["total_safety_communications"] == 2
    assert body["total_behaviour_observations"] == 2
    assert body["total_incident_investigations"] == 2
    assert body["total_legal_compliance_items"] == 2
    assert body["total_jsas"] == 2
    assert body["total_contractors"] == 2
    assert body["total_asset_register_items"] == 2


def test_dashboard_overview_applies_site_and_date_filters(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/overview?site_id=1&date_from=2026-04-01&date_to=2026-04-30")

    assert response.status_code == 200
    body = response.json()
    assert body["total_incidents"] == 1
    assert body["total_hazards"] == 3
    assert body["total_inspections"] == 1
    assert body["total_corrective_actions"] == 3
    assert body["total_safety_kpi_records"] == 1
    assert body["total_safety_communications"] == 1
    assert body["total_behaviour_observations"] == 1
    assert body["total_incident_investigations"] == 1
    assert body["total_legal_compliance_items"] == 1
    assert body["total_jsas"] == 1
    assert body["total_contractors"] == 1
    assert body["total_asset_register_items"] == 1


def test_dashboard_sites_returns_per_site_summaries(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/sites")

    assert response.status_code == 200
    body = response.json()
    main_site = next(site for site in body if site["site_id"] == 1)
    depot_site = next(site for site in body if site["site_id"] == 2)
    assert main_site["site_name"] == "Main Plant"
    assert main_site["incidents_count"] == 1
    assert main_site["open_hazards_count"] == 3
    assert main_site["critical_hazards_count"] == 2
    assert main_site["inspections_count"] == 1
    assert main_site["hours_worked"] == 200000
    assert main_site["safety_communications_count"] == 1
    assert main_site["behaviour_observations_count"] == 1
    assert main_site["investigations_count"] == 1
    assert main_site["non_compliant_legal_items_count"] == 1
    assert main_site["jsas_count"] == 1
    assert main_site["contractors_count"] == 1
    assert main_site["defective_assets_count"] == 1
    assert depot_site["overdue_corrective_actions_count"] == 1


def test_dashboard_trends_returns_monthly_summaries(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/trends")

    assert response.status_code == 200
    body = response.json()
    assert body["incidents_by_month"] == {"2026-03": 1, "2026-04": 1}
    assert body["hazards_by_month"]["2026-04"] == 4
    assert body["inspections_by_month"] == {"2026-03": 1, "2026-04": 1}
    assert body["safety_communications_by_month"] == {"2026-03": 1, "2026-04": 1}
    assert body["behaviour_observations_by_month"] == {"2026-03": 1, "2026-04": 1}
    assert body["trifr_by_month"]["2026-04"] == 5.0
    assert body["ltifr_by_month"]["2026-03"] == 10.0


def test_dashboard_trends_applies_filters(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/trends?site_id=1&date_from=2026-04-01&date_to=2026-04-30")

    assert response.status_code == 200
    body = response.json()
    assert body["incidents_by_month"] == {"2026-04": 1}
    assert body["hazards_by_month"] == {"2026-04": 3}
    assert body["inspections_by_month"] == {"2026-04": 1}
    assert body["safety_communications_by_month"] == {"2026-04": 1}
    assert body["behaviour_observations_by_month"] == {"2026-04": 1}
    assert body["trifr_by_month"] == {"2026-04": 5.0}


def test_dashboard_risk_endpoint_returns_management_signals(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/risk")

    assert response.status_code == 200
    body = response.json()
    assert body["open_critical_hazards_count"] == 2
    assert body["open_high_hazards_count"] == 1
    assert body["hazards_pending_review_count"] == 3
    assert len(body["critical_hazards_pending_review"]) == 2
    assert body["top_risk_sites"][0]["site_id"] == 1
    assert body["recurring_hazard_categories"][0]["label"] == "chemical spill"
    assert body["risk_level_distribution"]["critical"] == 2


def test_dashboard_actions_endpoint_returns_due_and_overdue_views(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/actions")

    assert response.status_code == 200
    body = response.json()
    assert body["overdue_corrective_actions_count"] == 2
    assert body["corrective_actions_due_soon_count"] == 2
    assert body["pending_verification_count"] == 1
    assert body["overdue_corrective_actions"][0]["title"] == "Overdue action"
    assert body["corrective_action_status_distribution"]["pending_verification"] == 1


def test_dashboard_compliance_endpoint_returns_training_metrics(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/compliance")

    assert response.status_code == 200
    body = response.json()
    assert body["training_compliance_rate"] == 33.33
    assert body["overdue_training_count"] == 1
    assert body["expired_training_count"] == 1
    assert body["overdue_compliance_acknowledgements_count"] == 1
    assert body["training_status_distribution"]["completed"] == 1
    assert body["compliance_acknowledgement_status_distribution"]["acknowledged"] == 1


def test_dashboard_permits_endpoint_returns_expiry_and_distribution_views(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/permits")

    assert response.status_code == 200
    body = response.json()
    assert body["active_permits_count"] == 1
    assert body["pending_approval_permits_count"] == 1
    assert body["expiring_soon_permits_count"] == 1
    assert body["expired_permits_count"] == 1
    assert body["permit_status_distribution"]["pending_approval"] == 1
    assert body["permit_type_distribution"]["hot_work"] == 4


def test_dashboard_approvals_endpoint_returns_pending_and_distributions(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/approvals")

    assert response.status_code == 200
    body = response.json()
    assert body["pending_approvals_count"] == 1
    assert body["pending_approvals"][0]["action_type"] == "incident_closure"
    assert body["approvals_by_action_type"]["incident_closure"] == 1
    assert body["approvals_by_status"]["approved"] == 1


def test_dashboard_management_summary_returns_top_urgent_items(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    response = client.get("/api/v1/dashboard/management-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_snapshot"]["critical_open_incidents_count"] == 1
    assert body["risk_snapshot"]["hazards_pending_review_count"] == 3
    assert body["action_snapshot"]["overdue_corrective_actions_count"] == 2
    assert body["compliance_snapshot"]["training_compliance_rate"] == 33.33
    assert body["permit_snapshot"]["expired_permits_count"] == 1
    assert body["approval_snapshot"]["pending_approvals_count"] == 1
    assert body["kpi_snapshot"]["total_hours_worked"] == 300000
    assert body["kpi_snapshot"]["trifr"] == 6.67
    assert body["communication_snapshot"]["published_communications_count"] == 1
    assert body["behaviour_snapshot"]["open_behaviour_issues_count"] == 1
    assert body["investigation_snapshot"]["open_investigations_count"] == 1
    assert body["investigation_snapshot"]["pending_investigation_approvals_count"] == 1
    assert body["legal_compliance_snapshot"]["non_compliant_items_count"] == 1
    assert body["jsa_snapshot"]["pending_jsa_approvals_count"] == 1
    assert body["jsa_snapshot"]["jsas_expired_count"] == 1
    assert body["contractor_snapshot"]["contractor_compliance_gaps_count"] == 1
    assert body["asset_snapshot"]["defective_assets_count"] == 1
    assert body["asset_snapshot"]["overdue_asset_inspections_count"] == 1
    urgent_categories = {item["category"] for item in body["top_urgent_items"]}
    assert "overdue_corrective_action" in urgent_categories
    assert "critical_hazard_pending_review" in urgent_categories
    assert "expired_permit" in urgent_categories
    assert "pending_approval" in urgent_categories
    assert "critical_open_incident" in urgent_categories


def test_dashboard_advanced_endpoints_apply_site_and_date_filters(client: TestClient, db_session: Session) -> None:
    _seed_dashboard_data(client, db_session)

    risk_response = client.get("/api/v1/dashboard/risk?site_id=1&date_from=2026-04-01&date_to=2026-04-30")
    approvals_response = client.get("/api/v1/dashboard/approvals?date_from=2026-04-01&date_to=2026-04-30")

    assert risk_response.status_code == 200
    assert approvals_response.status_code == 200
    risk_body = risk_response.json()
    approvals_body = approvals_response.json()
    assert risk_body["top_risk_sites"][0]["site_id"] == 1
    assert risk_body["risk_level_distribution"]["critical"] == 2
    assert approvals_body["pending_approvals_count"] == 1
    assert approvals_body["pending_approvals"][0]["entity_type"] == "incident"


def test_dashboard_analytics_rbac_and_site_scope(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    _seed_dashboard_data(client, db_session)
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    employee = create_user_for_role("employee", assigned_site_id=1)

    act_as(supervisor)
    supervisor_forbidden_response = client.get("/api/v1/dashboard/risk?site_id=2")
    supervisor_scoped_response = client.get("/api/v1/dashboard/risk")

    act_as(employee)
    employee_response = client.get("/api/v1/dashboard/management-summary")

    assert supervisor_forbidden_response.status_code == 403
    assert supervisor_scoped_response.status_code == 200
    assert supervisor_scoped_response.json()["top_risk_sites"][0]["site_id"] == 1
    assert employee_response.status_code == 403
