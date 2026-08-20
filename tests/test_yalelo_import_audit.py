from __future__ import annotations

import csv
from datetime import date, datetime
from io import BytesIO, StringIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction
from app.models.data_import import DataImportJob
from app.models.department import Department
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.organisation import Organisation, OrganisationSettings
from app.models.site import Site
from app.models.sio import SIOActivity, SIOStatus, SafetyImprovementObservation
from app.models.user import User
from app.schemas.data_import import ImportConfirmRequest
from app.services.data_import_service import (
    YALELO_SIO_COLUMNS,
    ImportJobNotFoundError,
    confirm_yalelo_sio_import,
    get_import_job,
    preview_yalelo_sio_import,
)
from app.services.tenancy import set_tenant_context, unscoped_session


def _row(**overrides) -> dict:
    row = {
        "ID": 2001,
        "Date": None,
        "Department": "Health & Safety",
        "Source of Observation": "Inspection",
        "Description of SIO": "  Unicode café\nline 2  ",
        "Incident Classification": "Property Damage",
        "Status": None,
        "Nature of Observation": "Positive Safety Observation",
        "Department Responsible for Corrective Action": "Unmapped Department",
        "Site": "Siavonga",
        "Responsible H&S Officer": "Ambiguous Person",
        "Urgency": "Urgent",
        "SIO Category": "Condition/Use of equipment",
        "Person Responsible for Corrective Action": "Unmapped Person",
        "Created": datetime(2025, 2, 3, 8, 15),
        "Property Damage": "Property Damage",
        "Created By": "Legacy Author",
        "Modified By": "Legacy Editor",
        "MonthY": "1899-12",
        "Item Type": "Item",
        "Path": "sites/OHS/Lists/YZ SIO Tracker",
    }
    row.update(overrides)
    return row


def _workbook_bytes(
    *rows: dict,
    headers: tuple[str, ...] = YALELO_SIO_COLUMNS,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append([row.get(column) for column in headers])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _seed_mapping_references(db: Session) -> None:
    db.add(Site(id=2, name="Siavonga", code="SIA"))
    db.add(Department(name="Health & Safety", code="H-S"))
    db.flush()
    db.add_all(
        [
            User(
                email="ambiguous-one@example.test",
                full_name="Ambiguous Person",
                hashed_password="not-used",
                is_active=True,
                assigned_site_id=2,
            ),
            User(
                email="ambiguous-two@example.test",
                full_name="Ambiguous Person",
                hashed_password="not-used",
                is_active=True,
                assigned_site_id=2,
            ),
        ]
    )
    settings = db.scalar(select(OrganisationSettings))
    settings.sio_workflow_configuration = {
        "default_due_days_by_urgency": {"urgent": 1}
    }
    db.commit()


def test_yalelo_actual_labels_preserve_all_fields_without_workflow_side_effects(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_mapping_references(db_session)
    content = _workbook_bytes(_row())

    preview = client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", content)},
    )
    assert preview.status_code == 201
    report = preview.json()["report"]
    assert report["rows_detected"] == 1
    assert report["rows_valid"] == 1
    assert report["rows_failed"] == 0
    assert report["column_contract"]["detected_columns"] == list(YALELO_SIO_COLUMNS)
    assert report["unresolved_departments"] == []
    assert report["unresolved_responsible_departments"] == ["Unmapped Department"]
    assert report["unresolved_users"] == ["Unmapped Person"]
    assert report["ambiguous_users"] == ["Ambiguous Person"]
    assert db_session.scalar(select(func.count()).select_from(SafetyImprovementObservation)) == 0

    confirmed = client.post(
        f"/api/v1/data-imports/{preview.json()['id']}/confirm",
        json={},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["report"]["rows_imported"] == 1
    sio = db_session.scalar(select(SafetyImprovementObservation))
    assert sio.external_reference_id == "2001"
    assert sio.observation_date is None
    assert sio.source_created_at.replace(tzinfo=None) == datetime(2025, 2, 3, 8, 15)
    assert sio.description == "  Unicode café\nline 2  "
    assert sio.status == SIOStatus.unassigned
    assert sio.observation_nature.value == "positive"
    assert sio.department_id is not None
    assert sio.responsible_department_id is None
    assert sio.responsible_department == "Unmapped Department"
    assert sio.responsible_hs_officer_user_id is None
    assert sio.responsible_hs_officer_name == "Ambiguous Person"
    assert sio.responsible_person_user_id is None
    assert sio.responsible_person_name == "Unmapped Person"
    assert sio.property_damage == "Property Damage"
    assert sio.due_date is None
    assert sio.legacy_metadata == {
        "MonthY": "1899-12",
        "Item Type": "Item",
        "source_status": None,
        "source_observation_nature": "Positive Safety Observation",
        "source_urgency": "Urgent",
    }
    assert sio.source_created_by == "Legacy Author"
    assert sio.source_modified_by == "Legacy Editor"
    assert sio.source_path == "sites/OHS/Lists/YZ SIO Tracker"

    assert db_session.scalar(select(func.count()).select_from(CorrectiveAction)) == 0
    assert db_session.scalar(select(func.count()).select_from(Incident)) == 0
    assert db_session.scalar(select(func.count()).select_from(Hazard)) == 0
    assert db_session.scalar(select(func.count()).select_from(Notification)) == 0
    activity = db_session.scalar(select(SIOActivity))
    assert activity.event_type == "imported"
    assert "without workflow side effects" in activity.message

    officer_search = client.get("/api/v1/sios?search=Ambiguous%20Person")
    assert officer_search.status_code == 200
    assert officer_search.json()["total"] == 1
    created_filter = client.get(
        "/api/v1/sios?source_created_from=2025-02-03&source_created_to=2025-02-03"
    )
    assert created_filter.status_code == 200
    assert created_filter.json()["total"] == 1
    analytics = client.get("/api/v1/dashboard/sios").json()
    assert analytics["total_observations"] == 1
    assert analytics["positive_observations"] == 1
    assert analytics["observations_using_source_created_at_fallback"] == 1
    assert analytics["observations_using_system_created_at_fallback"] == 0
    assert "source_created_at fallback" in analytics["reporting_date_basis"]

    export = client.get("/api/v1/exports/sios.csv")
    assert export.status_code == 200
    exported = list(csv.DictReader(StringIO(export.text)))
    assert len(exported) == 1
    exported_row = exported[0]
    assert exported_row["External Reference ID"] == "2001"
    assert exported_row["Site"] == "Siavonga"
    assert exported_row["Incident Classification"] == "Property Damage"
    assert exported_row["Responsible H&S Officer"] == "Ambiguous Person"
    assert exported_row["Source Created At"].startswith("2025-02-03T08:15:00")
    assert exported_row["Property Damage"] == "Property Damage"
    assert exported_row["Source Created By"] == "Legacy Author"
    assert exported_row["Source Modified By"] == "Legacy Editor"


def test_yalelo_contract_drift_is_reported_and_unexpected_values_are_preserved(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Site(id=2, name="Siavonga", code="SIA"))
    db_session.commit()
    headers = (*YALELO_SIO_COLUMNS, "Legacy Extra")
    row = _row(**{"Legacy Extra": "Preserve me", "Status": "Complete"})
    preview = client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", _workbook_bytes(row, headers=headers))},
    )
    assert preview.status_code == 201
    assert preview.json()["report"]["column_contract"]["additional_columns"] == [
        "Legacy Extra"
    ]
    confirmed = client.post(
        f"/api/v1/data-imports/{preview.json()['id']}/confirm",
        json={},
    )
    assert confirmed.status_code == 200
    sio = db_session.scalar(select(SafetyImprovementObservation))
    assert sio.legacy_metadata["unexpected_source_fields"] == {
        "Legacy Extra": "Preserve me"
    }

    duplicate_headers = list(YALELO_SIO_COLUMNS)
    duplicate_headers[-1] = "ID"
    duplicate = client.post(
        "/api/v1/data-imports/preview",
        files={
            "file": (
                "SIOs.xlsx",
                _workbook_bytes(_row(), headers=tuple(duplicate_headers)),
            )
        },
    )
    assert duplicate.status_code == 422
    assert "duplicate columns" in duplicate.json()["detail"].lower()


def test_yalelo_malformed_excel_zero_date_is_a_row_error_not_a_job_crash(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Site(id=2, name="Siavonga", code="SIA"))
    db_session.commit()
    preview = client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", _workbook_bytes(_row(Date=0)))},
    )
    assert preview.status_code == 201
    report = preview.json()["report"]
    assert report["rows_failed"] == 1
    assert report["malformed_dates"][0]["field"] == "Date"
    assert "time only" in report["malformed_dates"][0]["message"].lower()


def test_yalelo_import_is_idempotent_and_source_ids_are_tenant_aware(
    db_session: Session,
) -> None:
    db_session.add(Site(id=2, name="Siavonga", code="SIA"))
    db_session.commit()
    content = _workbook_bytes(_row(Status="Complete"))
    first = preview_yalelo_sio_import(
        db_session,
        content=content,
        filename="SIOs.xlsx",
        actor_id=1,
    )
    confirm_yalelo_sio_import(
        db_session,
        first,
        ImportConfirmRequest(),
        actor_id=1,
    )
    second = preview_yalelo_sio_import(
        db_session,
        content=content,
        filename="SIOs.xlsx",
        actor_id=1,
    )
    assert second.report["duplicates_skipped"] == 1
    confirm_yalelo_sio_import(
        db_session,
        second,
        ImportConfirmRequest(),
        actor_id=1,
    )
    assert db_session.scalar(select(func.count()).select_from(SafetyImprovementObservation)) == 1
    org1_job_id = first.id

    organisation2 = Organisation(
        id=2,
        name="Control Tenant",
        code="CONTROL",
        slug="control",
        timezone="Africa/Lusaka",
        is_active=True,
    )
    db_session.add(organisation2)
    db_session.flush()
    set_tenant_context(db_session, 2, platform_admin=True)
    db_session.add(OrganisationSettings())
    db_session.add(Site(id=3, name="Siavonga", code="SIA"))
    db_session.commit()
    tenant2_preview = preview_yalelo_sio_import(
        db_session,
        content=content,
        filename="SIOs.xlsx",
        actor_id=None,
    )
    tenant2_confirmed = confirm_yalelo_sio_import(
        db_session,
        tenant2_preview,
        ImportConfirmRequest(),
        actor_id=None,
    )
    assert tenant2_confirmed.report["rows_imported"] == 1
    assert db_session.scalar(select(func.count()).select_from(SafetyImprovementObservation)) == 1
    tenant2_job_id = tenant2_preview.id
    with pytest.raises(ImportJobNotFoundError):
        get_import_job(db_session, org1_job_id)

    set_tenant_context(db_session, 1, platform_admin=True)
    assert db_session.scalar(select(func.count()).select_from(SafetyImprovementObservation)) == 1
    with pytest.raises(ImportJobNotFoundError):
        get_import_job(db_session, tenant2_job_id)
    with unscoped_session(db_session):
        assert db_session.scalar(
            select(func.count()).select_from(SafetyImprovementObservation)
        ) == 2
        assert db_session.scalar(select(func.count()).select_from(DataImportJob)) == 3
