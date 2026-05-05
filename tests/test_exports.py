import csv
import io

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Export incident",
        "description": "Incident for export tests.",
        "severity": "critical",
        "status": "open",
        "occurred_at": "2026-04-23T08:30:00Z",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _hazard_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "Export hazard",
        "description": "Hazard for export tests.",
        "likelihood": 5,
        "impact": 5,
        "status": "open",
        "existing_controls": ["Barrier"],
        "additional_controls": ["Install guard"],
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
        "title": "Export inspection",
        "inspection_type": "workplace",
        "area_location": "Workshop Export",
        "inspector_user_id": 1,
        "inspection_date": "2026-04-24T09:00:00Z",
        "status": "completed",
        "notes": "Inspection notes.",
        "findings_summary": "Inspection summary.",
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
        "title": "Export corrective action",
        "description": "Corrective action for export tests.",
        "source_type": "manual",
        "priority": "critical",
        "status": "open",
        "assigned_to_user_id": 1,
        "due_date": "2000-01-01",
        "closure_evidence_metadata": [],
    }
    payload.update(overrides)
    return payload


def _investigation_payload(incident_id, **overrides):
    payload = {
        "incident_id": incident_id,
        "investigation_lead_user_id": 1,
        "investigation_team": ["Investigator"],
        "witness_statements": [{"name": "Witness", "statement": "Observed event."}],
        "immediate_causes": ["Cause"],
        "underlying_causes": ["Underlying cause"],
        "root_cause": "Root cause",
        "five_whys": ["Why 1"],
        "contributing_factors": ["Factor"],
        "recommendations": ["Recommendation"],
        "status": "pending_approval",
        "target_completion_date": "2026-04-30",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _legal_compliance_payload(**overrides):
    payload = {
        "title": "Export legal item",
        "regulatory_body": "Regulator",
        "legal_reference": "REF-1",
        "requirement_summary": "Requirement summary.",
        "site_id": 1,
        "owner_user_id": 1,
        "compliance_status": "non_compliant",
        "review_frequency": "monthly",
        "next_review_date": "2026-04-20",
        "evidence_required": True,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _jsa_payload(**overrides):
    payload = {
        "title": "Export JSA",
        "site_id": 1,
        "department_or_area": "Workshop",
        "job_steps": ["Step 1"],
        "hazards": ["Hazard 1"],
        "controls": ["Control 1"],
        "ppe_required": ["Gloves"],
        "residual_risk_level": "high",
        "status": "pending_approval",
        "review_date": "2026-04-25",
        "approved_by_user_id": 1,
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _contractor_payload(**overrides):
    payload = {
        "contractor_name": "Export Contractor",
        "contact_person": "Jane Export",
        "contact_email": "jane@example.com",
        "contact_phone": "+260971000100",
        "site_id": 1,
        "work_scope": "Shutdown support",
        "onboarding_status": "pending",
        "induction_status": "pending",
        "insurance_expiry_date": "2026-04-15",
        "compliance_documents_status": "incomplete",
        "approved_for_work": False,
        "documents_expiry_date": "2026-04-16",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _asset_payload(**overrides):
    payload = {
        "asset_type": "equipment",
        "asset_name": "Export asset",
        "asset_tag": "EXPORT-ASSET-1",
        "site_id": 1,
        "location": "Stores",
        "assigned_to_user_id": 1,
        "inspection_frequency": "monthly",
        "next_inspection_date": "2026-04-20",
        "condition_status": "defective",
        "attachments_metadata": [],
    }
    payload.update(overrides)
    return payload


def _seed_exports(client: TestClient) -> dict[str, int]:
    incident_id = client.post("/api/v1/incidents", json=_incident_payload()).json()["id"]
    hazard_id = client.post("/api/v1/hazards", json=_hazard_payload()).json()["id"]
    inspection_id = client.post("/api/v1/inspections", json=_inspection_payload()).json()["id"]
    action_id = client.post("/api/v1/corrective-actions", json=_corrective_action_payload()).json()["id"]
    investigation_id = client.post("/api/v1/incident-investigations", json=_investigation_payload(incident_id)).json()["id"]
    legal_id = client.post("/api/v1/legal-compliance", json=_legal_compliance_payload()).json()["id"]
    jsa_id = client.post("/api/v1/jsas", json=_jsa_payload()).json()["id"]
    contractor_id = client.post("/api/v1/contractors", json=_contractor_payload()).json()["id"]
    asset_id = client.post("/api/v1/asset-register", json=_asset_payload()).json()["id"]
    client.post(
        "/api/v1/incidents",
        json=_incident_payload(title="Filtered out incident", severity="low", status="closed"),
    )
    client.post(
        "/api/v1/hazards",
        json=_hazard_payload(title="Filtered out hazard", likelihood=2, impact=2, status="controlled"),
    )
    return {
        "incident_id": incident_id,
        "hazard_id": hazard_id,
        "inspection_id": inspection_id,
        "action_id": action_id,
        "investigation_id": investigation_id,
        "legal_id": legal_id,
        "jsa_id": jsa_id,
        "contractor_id": contractor_id,
        "asset_id": asset_id,
    }


def _csv_rows(response):
    return list(csv.DictReader(io.StringIO(response.text)))


def test_record_level_html_reports(client: TestClient) -> None:
    ids = _seed_exports(client)

    endpoints = [
        (f"/api/v1/exports/incidents/{ids['incident_id']}/report", "Incident Report"),
        (f"/api/v1/exports/hazards/{ids['hazard_id']}/report", "Hazard Report"),
        (f"/api/v1/exports/inspections/{ids['inspection_id']}/report", "Inspection Report"),
        (f"/api/v1/exports/corrective-actions/{ids['action_id']}/report", "Corrective Action Report"),
        (f"/api/v1/exports/incident-investigations/{ids['investigation_id']}/report", "Incident Investigation Report"),
        (f"/api/v1/exports/legal-compliance/{ids['legal_id']}/report", "Legal Compliance Report"),
        (f"/api/v1/exports/jsas/{ids['jsa_id']}/report", "JSA Report"),
        (f"/api/v1/exports/contractors/{ids['contractor_id']}/report", "Contractor Report"),
        (f"/api/v1/exports/asset-register/{ids['asset_id']}/report", "Asset Register Report"),
    ]

    for endpoint, heading in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<!doctype html>" in response.text.lower()
        assert heading in response.text
        assert "<section>" in response.text


def test_csv_exports_have_stable_headers_and_filters(client: TestClient) -> None:
    _seed_exports(client)

    incidents = client.get("/api/v1/exports/incidents.csv?severity=critical")
    hazards = client.get("/api/v1/exports/hazards.csv?risk_level=critical")
    inspections = client.get("/api/v1/exports/inspections.csv?status=completed")
    actions = client.get("/api/v1/exports/corrective-actions.csv?priority=critical&assigned_to_user_id=1")
    investigations = client.get("/api/v1/exports/incident-investigations.csv?status=pending_approval")
    legal_items = client.get("/api/v1/exports/legal-compliance.csv?status=non_compliant")
    jsas = client.get("/api/v1/exports/jsas.csv?status=pending_approval")
    contractors = client.get("/api/v1/exports/contractors.csv?approved_for_work=false")
    assets = client.get("/api/v1/exports/asset-register.csv?condition_status=defective")

    assert incidents.status_code == 200
    assert incidents.text.splitlines()[0] == "ID,Site ID,Title,Status,Severity,Occurred At,Reported By User ID,Description"
    incident_rows = _csv_rows(incidents)
    assert len(incident_rows) == 1
    assert incident_rows[0]["Title"] == "Export incident"

    assert hazards.text.splitlines()[0] == "ID,Site ID,Title,Status,Risk Level,Risk Score,Likelihood,Impact,Owner User ID,Due Date"
    hazard_rows = _csv_rows(hazards)
    assert len(hazard_rows) == 1
    assert hazard_rows[0]["Risk Level"] == "critical"

    assert inspections.text.splitlines()[0] == "ID,Site ID,Title,Status,Inspection Type,Overall Result,Inspection Date,Inspector User ID,Non-Conformities,Observations"
    assert _csv_rows(inspections)[0]["Title"] == "Export inspection"

    assert actions.text.splitlines()[0] == "ID,Site ID,Title,Status,Priority,Source Type,Source ID,Assigned To User ID,Due Date,Completed At,Overdue"
    assert _csv_rows(actions)[0]["Title"] == "Export corrective action"

    assert investigations.text.splitlines()[0] == "ID,Incident ID,Site ID,Status,Investigation Lead User ID,Target Completion Date,Completed At,Approved By User ID"
    assert _csv_rows(investigations)[0]["Incident ID"] == "1"

    assert legal_items.text.splitlines()[0] == "ID,Site ID,Title,Regulatory Body,Legal Reference,Compliance Status,Owner User ID,Review Frequency,Next Review Date,Evidence Required"
    assert _csv_rows(legal_items)[0]["Title"] == "Export legal item"

    assert jsas.text.splitlines()[0] == "ID,Site ID,Title,Department Or Area,Status,Residual Risk Level,Review Date,Approved By User ID"
    assert _csv_rows(jsas)[0]["Title"] == "Export JSA"

    assert contractors.text.splitlines()[0] == "ID,Site ID,Contractor Name,Contact Person,Contact Email,Onboarding Status,Induction Status,Insurance Expiry Date,Compliance Documents Status,Approved For Work"
    assert _csv_rows(contractors)[0]["Contractor Name"] == "Export Contractor"

    assert assets.text.splitlines()[0] == "ID,Site ID,Asset Type,Asset Name,Asset Tag,Location,Assigned To User ID,Inspection Frequency,Next Inspection Date,Condition Status"
    assert _csv_rows(assets)[0]["Asset Name"] == "Export asset"


def test_management_summary_reports(client: TestClient) -> None:
    _seed_exports(client)

    endpoints = [
        ("/api/v1/exports/reports/executive-summary", "Executive Summary Report"),
        ("/api/v1/exports/reports/overdue-corrective-actions", "Overdue Corrective Actions Report"),
        ("/api/v1/exports/reports/critical-hazards", "Critical Hazards Report"),
        ("/api/v1/exports/reports/incidents-summary", "Incidents Summary Report"),
    ]

    for endpoint, title in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert title in response.text
        assert "<table>" in response.text


def test_exports_require_authentication(client: TestClient) -> None:
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get("/api/v1/exports/incidents.csv")

    assert response.status_code == 401
