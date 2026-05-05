from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.site import Site


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Enterprise incident",
        "description": "Incident used by enterprise feature pack tests.",
        "severity": "high",
        "status": "open",
        "occurred_at": "2026-04-28T08:30:00Z",
        "is_recordable": True,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _investigation_payload(incident_id: int, **overrides):
    payload = {
        "incident_id": incident_id,
        "investigation_lead_user_id": 1,
        "investigation_team": ["Lead investigator"],
        "witness_statements": [{"name": "Witness One", "statement": "Saw the incident."}],
        "immediate_causes": ["Immediate cause"],
        "underlying_causes": ["Underlying cause"],
        "root_cause": "Root cause",
        "five_whys": ["Why 1"],
        "contributing_factors": ["Contributing factor"],
        "recommendations": ["Recommendation"],
        "status": "draft",
        "target_completion_date": "2026-05-01",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _legal_payload(**overrides):
    payload = {
        "title": "Legal register item",
        "regulatory_body": "Environmental Agency",
        "legal_reference": "EA-14",
        "requirement_summary": "Maintain emissions logs.",
        "site_id": 1,
        "owner_user_id": 1,
        "compliance_status": "pending_review",
        "review_frequency": "monthly",
        "next_review_date": (date.today() + timedelta(days=2)).isoformat(),
        "evidence_required": True,
        "notes": "Evidence due soon.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _jsa_payload(**overrides):
    payload = {
        "title": "Boiler maintenance JSA",
        "site_id": 1,
        "department_or_area": "Boiler house",
        "job_steps": ["Isolate system", "Inspect", "Repair"],
        "hazards": ["Pressure release"],
        "controls": ["Isolation lockout"],
        "ppe_required": ["Gloves", "Face shield"],
        "residual_risk_level": "medium",
        "status": "draft",
        "review_date": "2026-05-05",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _contractor_payload(**overrides):
    payload = {
        "contractor_name": "Atlas Services",
        "contact_person": "Mary Zulu",
        "contact_email": "mary@example.com",
        "contact_phone": "+260971123456",
        "site_id": 1,
        "work_scope": "Shutdown mechanical work",
        "onboarding_status": "pending",
        "induction_status": "pending",
        "insurance_expiry_date": (date.today() + timedelta(days=5)).isoformat(),
        "compliance_documents_status": "incomplete",
        "approved_for_work": False,
        "documents_expiry_date": (date.today() + timedelta(days=4)).isoformat(),
        "notes": "Awaiting compliance pack.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _asset_payload(**overrides):
    payload = {
        "asset_type": "equipment",
        "asset_name": "Rescue tripod",
        "asset_tag": "ASSET-TRIPOD-001",
        "site_id": 1,
        "location": "Rescue cage",
        "assigned_to_user_id": 1,
        "inspection_frequency": "monthly",
        "next_inspection_date": (date.today() - timedelta(days=1)).isoformat(),
        "condition_status": "defective",
        "notes": "Locking pin missing.",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def test_enterprise_feature_pack_crud_roundtrip(client: TestClient) -> None:
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()

    investigation = client.post(
        "/api/v1/incident-investigations",
        json=_investigation_payload(incident["id"]),
    )
    legal_item = client.post("/api/v1/legal-compliance", json=_legal_payload())
    jsa = client.post("/api/v1/jsas", json=_jsa_payload())
    contractor = client.post("/api/v1/contractors", json=_contractor_payload())
    asset = client.post("/api/v1/asset-register", json=_asset_payload())

    assert investigation.status_code == 201
    assert legal_item.status_code == 201
    assert jsa.status_code == 201
    assert contractor.status_code == 201
    assert asset.status_code == 201

    investigation_id = investigation.json()["id"]
    legal_id = legal_item.json()["id"]
    jsa_id = jsa.json()["id"]
    contractor_id = contractor.json()["id"]
    asset_id = asset.json()["id"]

    assert client.get(f"/api/v1/incident-investigations/{investigation_id}").status_code == 200
    assert client.get(f"/api/v1/legal-compliance/{legal_id}").status_code == 200
    assert client.get(f"/api/v1/jsas/{jsa_id}").status_code == 200
    assert client.get(f"/api/v1/contractors/{contractor_id}").status_code == 200
    assert client.get(f"/api/v1/asset-register/{asset_id}").status_code == 200

    updated_investigation = client.patch(
        f"/api/v1/incident-investigations/{investigation_id}",
        json={"status": "in_progress", "recommendations": ["Refresh procedure", "Add supervisor briefing"]},
    )
    updated_legal_item = client.patch(
        f"/api/v1/legal-compliance/{legal_id}",
        json={"compliance_status": "partial"},
    )
    updated_jsa = client.patch(
        f"/api/v1/jsas/{jsa_id}",
        json={"residual_risk_level": "high", "status": "pending_approval"},
    )
    updated_contractor = client.patch(
        f"/api/v1/contractors/{contractor_id}",
        json={"notes": "Insurance certificate requested again."},
    )
    updated_asset = client.patch(
        f"/api/v1/asset-register/{asset_id}",
        json={"condition_status": "needs_attention"},
    )

    assert updated_investigation.status_code == 200
    assert updated_investigation.json()["status"] == "in_progress"
    assert updated_legal_item.status_code == 200
    assert updated_legal_item.json()["compliance_status"] == "partial"
    assert updated_jsa.status_code == 200
    assert updated_jsa.json()["status"] == "pending_approval"
    assert updated_contractor.status_code == 200
    assert updated_contractor.json()["notes"] == "Insurance certificate requested again."
    assert updated_asset.status_code == 200
    assert updated_asset.json()["condition_status"] == "needs_attention"


def test_investigation_requires_existing_incident_and_high_incident_needs_completed_investigation_before_closure(
    client: TestClient,
) -> None:
    missing_incident_response = client.post(
        "/api/v1/incident-investigations",
        json=_investigation_payload(9999),
    )
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()
    blocked_close = client.patch(f"/api/v1/incidents/{incident['id']}", json={"status": "closed"})

    assert missing_incident_response.status_code == 404
    assert blocked_close.status_code == 422
    assert "require a completed investigation" in blocked_close.json()["detail"]

    approved_investigation = client.post(
        "/api/v1/incident-investigations",
        json=_investigation_payload(incident["id"], status="approved"),
    )
    successful_close = client.patch(f"/api/v1/incidents/{incident['id']}", json={"status": "closed"})

    assert approved_investigation.status_code == 201
    assert successful_close.status_code == 200
    assert successful_close.json()["status"] == "closed"


def test_enterprise_feature_pack_rbac_for_approval_actions(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    safety_officer = create_user_for_role("safety_officer")
    incident = client.post("/api/v1/incidents", json=_incident_payload()).json()

    act_as(safety_officer)
    investigation = client.post(
        "/api/v1/incident-investigations",
        json=_investigation_payload(incident["id"], approved_by_user_id=safety_officer.id),
    ).json()
    jsa = client.post(
        "/api/v1/jsas",
        json=_jsa_payload(approved_by_user_id=safety_officer.id),
    ).json()

    investigation_approve = client.patch(
        f"/api/v1/incident-investigations/{investigation['id']}",
        json={"status": "approved"},
    )
    jsa_approve = client.patch(
        f"/api/v1/jsas/{jsa['id']}",
        json={"status": "approved"},
    )
    contractor_approve = client.post(
        "/api/v1/contractors",
        json=_contractor_payload(
            induction_status="completed",
            compliance_documents_status="complete",
            approved_for_work=True,
        ),
    )

    assert investigation_approve.status_code == 403
    assert jsa_approve.status_code == 403
    assert contractor_approve.status_code == 403


def test_contractor_and_asset_business_rules_create_notifications(
    client: TestClient,
    db_session: Session,
) -> None:
    blocked_contractor = client.post(
        "/api/v1/contractors",
        json=_contractor_payload(approved_for_work=True),
    )
    due_soon_legal = client.post("/api/v1/legal-compliance", json=_legal_payload())
    valid_contractor = client.post("/api/v1/contractors", json=_contractor_payload())
    defective_asset = client.post("/api/v1/asset-register", json=_asset_payload())

    assert blocked_contractor.status_code == 422
    assert "cannot be approved" in blocked_contractor.json()["detail"]
    assert due_soon_legal.status_code == 201
    assert valid_contractor.status_code == 201
    assert defective_asset.status_code == 201

    notification_types = {item.notification_type for item in db_session.query(Notification).all()}
    assert NotificationType.legal_compliance_due_soon in notification_types
    assert NotificationType.contractor_insurance_due_soon in notification_types
    assert NotificationType.asset_defective in notification_types


def test_asset_tag_uniqueness_and_dashboard_asset_snapshot(client: TestClient) -> None:
    first_asset = client.post("/api/v1/asset-register", json=_asset_payload())
    duplicate_asset = client.post(
        "/api/v1/asset-register",
        json=_asset_payload(asset_name="Duplicate asset"),
    )
    summary = client.get("/api/v1/dashboard/management-summary")

    assert first_asset.status_code == 201
    assert duplicate_asset.status_code == 422
    assert duplicate_asset.json()["detail"] == "Asset tag already exists"
    assert summary.status_code == 200
    assert summary.json()["asset_snapshot"]["defective_assets_count"] == 1
    assert summary.json()["asset_snapshot"]["overdue_asset_inspections_count"] == 1


def test_site_scoping_for_enterprise_feature_pack_resources(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Remote Site", code="REMOTE", address="Remote address", created_by_id=1))
    db_session.commit()
    incident_one = client.post("/api/v1/incidents", json=_incident_payload(site_id=1)).json()
    incident_two = client.post("/api/v1/incidents", json=_incident_payload(site_id=2, title="Remote incident")).json()
    client.post("/api/v1/incident-investigations", json=_investigation_payload(incident_one["id"]))
    client.post("/api/v1/incident-investigations", json=_investigation_payload(incident_two["id"]))
    client.post("/api/v1/legal-compliance", json=_legal_payload(site_id=1))
    client.post("/api/v1/legal-compliance", json=_legal_payload(title="Remote legal", site_id=2))
    client.post("/api/v1/jsas", json=_jsa_payload(site_id=1))
    client.post("/api/v1/jsas", json=_jsa_payload(title="Remote JSA", site_id=2))
    client.post("/api/v1/asset-register", json=_asset_payload(asset_tag="ASSET-LOCAL", site_id=1))
    client.post(
        "/api/v1/asset-register",
        json=_asset_payload(asset_tag="ASSET-REMOTE", site_id=2, asset_name="Remote asset"),
    )

    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    act_as(supervisor)

    assert client.get("/api/v1/incident-investigations").json()["total"] == 1
    assert client.get("/api/v1/legal-compliance").json()["total"] == 1
    assert client.get("/api/v1/jsas").json()["total"] == 1
    assert client.get("/api/v1/asset-register").json()["total"] == 1
    assert client.get("/api/v1/legal-compliance?site_id=2").status_code == 403
    assert client.post("/api/v1/jsas", json=_jsa_payload(site_id=2, title="Forbidden JSA")).status_code == 403
    assert client.post(
        "/api/v1/asset-register",
        json=_asset_payload(asset_tag="ASSET-FORBIDDEN", site_id=2, asset_name="Forbidden asset"),
    ).status_code == 403
