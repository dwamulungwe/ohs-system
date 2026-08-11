from datetime import date, datetime, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.site import Site
from app.models.sio import SafetyImprovementObservation
from app.services.data_import_service import YALELO_SIO_COLUMNS, parse_excel_date


def _sio_payload(**overrides) -> dict:
    payload = {
        "observation_date": "2026-07-10",
        "department": "Operations",
        "source_type": "Walkabout",
        "description": "Guard was missing from the transfer pump coupling.",
        "incident_classification": "Near miss",
        "status": "open",
        "observation_nature": "negative",
        "responsible_department": "Maintenance",
        "site_id": 1,
        "urgency": "high",
        "category": "Machine guarding",
        "responsible_person_name": "Maintenance Lead",
    }
    payload.update(overrides)
    return payload


def _workbook_bytes(*rows: dict) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(YALELO_SIO_COLUMNS))
    for row in rows:
        sheet.append([row.get(column) for column in YALELO_SIO_COLUMNS])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _yalelo_row(**overrides) -> dict:
    row = {
        "ID": "SIO-1001",
        "Date": None,
        "Department": "Processing",
        "Source of Observation": "Inspection",
        "Description of SIO": "Positive isolation practice observed.",
        "Incident Classification": "Observation",
        "Status": "Assigned to Responsible Person",
        "Nature of Observation": "Positive",
        "Department Responsible for Corrective Action": "Processing",
        "Site": "Siavonga",
        "Responsible H&S Officer": "Safety Officer Exact",
        "Urgency": "N/A",
        "SIO Category": "Isolation",
        "Person Responsible for Corrective Action": "Unmapped Person",
        "Created": datetime(2025, 2, 3, 8, 15),
        "Property Damage": "No",
        "Created By": "Legacy Author",
        "Modified By": "Legacy Editor",
        "MonthY": "Feb-2025",
        "Item Type": "Item",
        "Path": "/legacy/sios/1001",
    }
    row.update(overrides)
    return row


def test_sio_crud_filters_and_duplicate_source_id(client: TestClient) -> None:
    created = client.post(
        "/api/v1/sios",
        json=_sio_payload(source_system="manual_test", external_reference_id="42"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["observation_date"] == "2026-07-10"
    assert body["source_created_at"] is None

    patched = client.patch(
        f"/api/v1/sios/{body['id']}",
        json={"status": "assigned_to_action_tracker", "urgency": "urgent"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "assigned_to_action_tracker"

    filtered = client.get(
        "/api/v1/sios?site_id=1&department=Operations&source_type=Walkabout"
        "&status=assigned_to_action_tracker&observation_nature=negative&urgency=urgent"
        "&category=Machine%20guarding&incident_classification=Near%20miss"
        "&date_from=2026-07-01&date_to=2026-07-31&search=pump"
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    duplicate = client.post(
        "/api/v1/sios",
        json=_sio_payload(source_system="manual_test", external_reference_id="42"),
    )
    assert duplicate.status_code == 409


def test_sio_rbac_and_site_scope(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Lusaka", code="LUS"))
    db_session.commit()
    client.post("/api/v1/sios", json=_sio_payload(site_id=1))
    client.post("/api/v1/sios", json=_sio_payload(site_id=2, description="Remote record"))
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    employee = create_user_for_role("employee", assigned_site_id=1)

    act_as(supervisor)
    scoped = client.get("/api/v1/sios")
    assert scoped.status_code == 200
    assert scoped.json()["total"] == 1
    assert client.get("/api/v1/sios?site_id=2").status_code == 403
    assert client.patch("/api/v1/sios/1", json={"status": "complete"}).status_code == 200

    act_as(employee)
    assert client.post("/api/v1/sios", json=_sio_payload(site_id=1)).status_code == 201
    assert client.post("/api/v1/sios", json=_sio_payload(site_id=2)).status_code == 403
    assert client.patch("/api/v1/sios/1", json={"status": "complete"}).status_code == 403


def test_sio_escalation_creates_one_linked_record_of_each_type(
    client: TestClient,
    db_session: Session,
) -> None:
    sio = client.post("/api/v1/sios", json=_sio_payload()).json()
    hazard_response = client.post(f"/api/v1/sios/{sio['id']}/create-hazard")
    incident_response = client.post(f"/api/v1/sios/{sio['id']}/create-incident")
    action_response = client.post(f"/api/v1/sios/{sio['id']}/create-corrective-action")
    assert hazard_response.status_code == 201
    assert incident_response.status_code == 201
    assert action_response.status_code == 201

    linked = action_response.json()
    hazard = db_session.get(Hazard, linked["linked_hazard_id"])
    incident = db_session.get(Incident, linked["linked_incident_id"])
    action = db_session.get(CorrectiveAction, linked["linked_corrective_action_id"])
    assert hazard.site_id == sio["site_id"] and hazard.risk_level.value == "critical"
    assert incident.occurred_at.date() == date(2026, 7, 10)
    assert action.source_type.value == "sio" and action.source_id == sio["id"]
    assert client.post(f"/api/v1/sios/{sio['id']}/create-hazard").status_code == 409


def test_incident_escalation_does_not_substitute_created_for_missing_observation_date(
    client: TestClient,
) -> None:
    sio = client.post(
        "/api/v1/sios",
        json=_sio_payload(observation_date=None, source_created_at="2026-07-10T10:00:00Z"),
    ).json()
    response = client.post(f"/api/v1/sios/{sio['id']}/create-incident")
    assert response.status_code == 422
    assert "observation date" in response.json()["detail"].lower()


def test_yalelo_import_preview_confirm_dates_site_and_name_preservation(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
) -> None:
    db_session.add(Site(id=2, name="Siavonga", code="SIA"))
    create_user_for_role(
        "safety_officer",
        assigned_site_id=2,
        full_name="Safety Officer Exact",
    )
    content = _workbook_bytes(_yalelo_row())
    preview = client.post(
        "/api/v1/data-imports/preview",
        data={"importer_type": "yalelo_sio"},
        files={"file": ("SIOs.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert preview.status_code == 201
    preview_body = preview.json()
    assert preview_body["is_dry_run"] is True
    assert preview_body["report"]["rows_detected"] == 1
    assert preview_body["report"]["rows_valid"] == 1
    assert preview_body["report"]["rows_imported"] == 0
    assert db_session.query(SafetyImprovementObservation).count() == 0

    confirmed = client.post(f"/api/v1/data-imports/{preview_body['id']}/confirm", json={})
    assert confirmed.status_code == 200
    report = confirmed.json()["report"]
    assert report["rows_imported"] == 1
    assert report["rows_failed"] == 0
    imported = db_session.query(SafetyImprovementObservation).one()
    assert imported.external_reference_id == "SIO-1001"
    assert imported.source_system == "yalelo_sharepoint"
    assert imported.observation_date is None
    assert imported.source_created_at.date() == date(2025, 2, 3)
    assert imported.responsible_hs_officer_user_id is not None
    assert imported.responsible_hs_officer_name == "Safety Officer Exact"
    assert imported.responsible_person_user_id is None
    assert imported.responsible_person_name == "Unmapped Person"
    assert imported.legacy_metadata["MonthY"] == "Feb-2025"


def test_yalelo_import_unresolved_site_can_be_created_and_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    content = _workbook_bytes(_yalelo_row(**{"ID": "NEW-1", "Site": "Third Party Premises"}))
    preview = client.post(
        "/api/v1/data-imports/preview",
        data={"importer_type": "yalelo_sio"},
        files={"file": ("SIOs.xlsx", content)},
    ).json()
    assert preview["report"]["unresolved_sites"] == ["Third Party Premises"]
    confirmed = client.post(
        f"/api/v1/data-imports/{preview['id']}/confirm",
        json={"create_sites": ["Third Party Premises"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["successful_rows"] == 1
    assert db_session.query(Site).filter(Site.name == "Third Party Premises").count() == 1

    second_preview = client.post(
        "/api/v1/data-imports/preview",
        data={"importer_type": "yalelo_sio"},
        files={"file": ("SIOs.xlsx", content)},
    ).json()
    assert second_preview["report"]["duplicates_skipped"] == 1
    second_confirm = client.post(f"/api/v1/data-imports/{second_preview['id']}/confirm", json={})
    assert second_confirm.status_code == 200
    assert second_confirm.json()["successful_rows"] == 0
    assert db_session.query(SafetyImprovementObservation).count() == 1


def test_import_is_admin_managed_and_malformed_rows_do_not_abort_job(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    content = _workbook_bytes(
        _yalelo_row(**{"ID": "GOOD", "Site": "Siavonga"}),
        _yalelo_row(**{"ID": "BAD", "Nature of Observation": "Unknown"}),
    )
    safety_officer = create_user_for_role("safety_officer", assigned_site_id=1)
    act_as(safety_officer)
    assert client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", content)},
    ).status_code == 403
    act_as(1)
    preview = client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", content)},
    )
    assert preview.status_code == 201
    assert preview.json()["report"]["rows_detected"] == 2
    assert preview.json()["report"]["rows_failed"] == 1


def test_excel_serial_date_conversion() -> None:
    parsed_date = parse_excel_date(45292, epoch=datetime(1899, 12, 30), as_datetime=False)
    parsed_datetime = parse_excel_date(45292.5, epoch=datetime(1899, 12, 30), as_datetime=True)
    assert parsed_date == date(2024, 1, 1)
    assert parsed_datetime == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_sio_dashboard_aggregation_respects_site_and_date_filters(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Site(id=2, name="Lusaka", code="LUS"))
    db_session.commit()
    client.post("/api/v1/sios", json=_sio_payload(category="Guarding"))
    client.post(
        "/api/v1/sios",
        json=_sio_payload(
            site_id=2,
            observation_date="2026-06-01",
            observation_nature="positive",
            urgency="low",
            category="Housekeeping",
            source_type="Audit",
        ),
    )
    response = client.get(
        "/api/v1/dashboard/sios?site_id=1&date_from=2026-07-01&date_to=2026-07-31"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_observations"] == 1
    assert body["negative_observations"] == 1
    assert body["urgent_high_priority_observations"] == 1
    assert body["observations_by_site"] == {"Main Plant": 1}
    assert body["observation_trend_by_month"] == {"2026-07": 1}
