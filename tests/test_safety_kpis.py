from fastapi.testclient import TestClient


def _incident_payload(**overrides):
    payload = {
        "site_id": 1,
        "title": "KPI incident",
        "description": "Incident used for KPI calculations.",
        "severity": "high",
        "status": "open",
        "occurred_at": "2026-04-10T08:30:00Z",
        "is_recordable": False,
        "is_lost_time": False,
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
        "notes": "Monthly hours worked.",
    }
    payload.update(overrides)
    return payload


def test_create_safety_kpi_calculates_trifr_and_ltifr(client: TestClient) -> None:
    client.post("/api/v1/incidents", json=_incident_payload(title="Recordable", is_recordable=True))
    client.post("/api/v1/incidents", json=_incident_payload(title="Lost time", is_lost_time=True))

    response = client.post("/api/v1/safety-kpis", json=_kpi_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["recordable_incidents"] == 2
    assert body["lost_time_incidents"] == 1
    assert body["trifr"] == 10.0
    assert body["ltifr"] == 5.0


def test_list_safety_kpis_supports_site_scope_and_pagination(client: TestClient) -> None:
    client.post("/api/v1/safety-kpis", json=_kpi_payload(reporting_label="April"))
    client.post(
        "/api/v1/safety-kpis",
        json=_kpi_payload(reporting_label="May", period_start="2026-05-01", period_end="2026-05-31"),
    )

    response = client.get("/api/v1/safety-kpis?skip=0&limit=1&site_id=1")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["items"][0]["reporting_label"] == "May"


def test_update_safety_kpi_recalculates_rates(client: TestClient) -> None:
    client.post("/api/v1/incidents", json=_incident_payload(title="Lost time", is_lost_time=True))
    created = client.post("/api/v1/safety-kpis", json=_kpi_payload()).json()

    response = client.patch(
        f"/api/v1/safety-kpis/{created['id']}",
        json={"hours_worked": 100000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recordable_incidents"] == 1
    assert body["ltifr"] == 10.0


def test_duplicate_safety_kpi_period_is_rejected(client: TestClient) -> None:
    client.post("/api/v1/safety-kpis", json=_kpi_payload())

    response = client.post("/api/v1/safety-kpis", json=_kpi_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "A KPI record already exists for that site and period"
