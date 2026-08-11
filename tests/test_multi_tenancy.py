from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.approval import ApprovalActionType, ApprovalEntityType, ApprovalStatus, ApprovalWorkflow
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.corrective_action import CorrectiveAction
from app.models.data_import import DataImportJob, ImportJobStatus
from app.models.department import Department
from app.models.hazard import Hazard, HazardRiskLevel
from app.models.incident import Incident, IncidentSeverity
from app.models.inspection import Inspection, InspectionOverallResult
from app.models.organisation import OrganisationFeature
from app.models.role import Role
from app.models.site import Site
from app.models.sio import SIOObservationNature, SafetyImprovementObservation
from app.models.user import User
from app.schemas.organisation import OrganisationCreate
from app.services.organisation_service import create_organisation_record
from app.services.tenancy import set_tenant_context
from app.services.tenancy import unscoped_session


@pytest.fixture
def tenant_b(db_session):
    organisation = create_organisation_record(
        db_session,
        OrganisationCreate(name="Tenant B", code="TENANT-B", slug="tenant-b"),
    )
    set_tenant_context(db_session, organisation.id)
    admin_role = db_session.scalar(select(Role).where(Role.name == "admin"))
    employee_role = db_session.scalar(select(Role).where(Role.name == "employee"))
    assert admin_role is not None
    assert employee_role is not None
    admin = User(
        email="admin@tenant-b.example",
        full_name="Tenant B Admin",
        hashed_password="not-used",
        roles=[admin_role],
    )
    employee = User(
        email="employee@tenant-b.example",
        full_name="Tenant B Employee",
        hashed_password="not-used",
        roles=[employee_role],
    )
    db_session.add_all([admin, employee])
    db_session.flush()
    assert admin.roles and admin.roles[0].name == "admin"
    site = Site(name="Tenant B Plant", code="MAIN", created_by_id=admin.id)
    second_site = Site(name="Tenant B Warehouse", code="WAREHOUSE", created_by_id=admin.id)
    db_session.add_all([site, second_site])
    db_session.flush()
    employee.assigned_site_id = site.id
    department = Department(name="Tenant B Operations", code="OPS", manager_user_id=admin.id)
    db_session.add(department)
    db_session.flush()

    incident = Incident(
        site_id=site.id,
        title="Tenant B confidential incident",
        description="Tenant B only",
        severity=IncidentSeverity.high,
        occurred_at=datetime.now(timezone.utc),
        reported_by_id=admin.id,
    )
    hazard = Hazard(
        site_id=site.id,
        title="Tenant B confidential hazard",
        description="Tenant B only",
        likelihood=4,
        impact=4,
        risk_score=16,
        risk_level=HazardRiskLevel.critical,
        reported_by_id=admin.id,
    )
    action = CorrectiveAction(
        site_id=site.id,
        title="Tenant B confidential action",
        description="Tenant B only",
        created_by_user_id=admin.id,
    )
    inspection = Inspection(
        site_id=site.id,
        title="Tenant B confidential inspection",
        inspection_type="workplace",
        area_location="Plant",
        inspection_date=datetime.now(timezone.utc),
        overall_result=InspectionOverallResult.compliant,
        inspector_user_id=admin.id,
    )
    sio = SafetyImprovementObservation(
        reference_number="SIO-2026-000001",
        external_reference_id="SHARED-REFERENCE",
        source_system="legacy",
        department="Operations",
        source_type="walkthrough",
        description="Tenant B confidential SIO",
        observation_nature=SIOObservationNature.negative,
        site_id=site.id,
        created_by_user_id=admin.id,
    )
    import_job = DataImportJob(
        importer_type="sio_excel",
        source_system="legacy",
        original_filename="tenant-b.xlsx",
        status=ImportJobStatus.previewed,
        created_by_user_id=admin.id,
    )
    db_session.add_all([incident, hazard, action, inspection, sio, import_job])
    db_session.flush()
    attachment = Attachment(
        entity_type=AttachmentEntityType.incident,
        entity_id=incident.id,
        uploaded_by_user_id=admin.id,
        original_filename="tenant-b-secret.txt",
        stored_filename="tenant-b-secret.txt",
        content_type="text/plain",
        file_size=10,
        storage_path="tenant-b-secret.txt",
    )
    approval = ApprovalWorkflow(
        entity_type=ApprovalEntityType.incident,
        entity_id=incident.id,
        requested_by_user_id=admin.id,
        assigned_approver_user_id=admin.id,
        action_type=ApprovalActionType.incident_closure,
        status=ApprovalStatus.pending,
    )
    db_session.add_all([attachment, approval])
    db_session.commit()

    set_tenant_context(db_session, 1, platform_admin=True)
    return {
        "organisation": organisation,
        "admin": admin,
        "employee": employee,
        "site": site,
        "second_site": second_site,
        "department": department,
        "incident": incident,
        "hazard": hazard,
        "action": action,
        "inspection": inspection,
        "sio": sio,
        "import_job": import_job,
        "attachment": attachment,
        "approval": approval,
    }


def test_tenant_a_cannot_list_or_retrieve_tenant_b_domain_records(client, tenant_b):
    list_paths = ("incidents", "hazards", "corrective-actions", "inspections", "sios")
    for path in list_paths:
        response = client.get(f"/api/v1/{path}")
        assert response.status_code == 200
        payload = response.json()
        items = payload.get("items", payload)
        assert all("Tenant B confidential" not in str(item) for item in items)

    detail_paths = {
        "incidents": tenant_b["incident"].id,
        "hazards": tenant_b["hazard"].id,
        "corrective-actions": tenant_b["action"].id,
        "inspections": tenant_b["inspection"].id,
        "sios": tenant_b["sio"].id,
    }
    for path, record_id in detail_paths.items():
        response = client.get(f"/api/v1/{path}/{record_id}")
        assert response.status_code == 404


def test_cross_tenant_mutation_attachment_approval_and_import_access_is_blocked(client, tenant_b):
    assert client.patch(
        f"/api/v1/incidents/{tenant_b['incident'].id}", json={"title": "tampered"}
    ).status_code == 404
    assert client.get(
        f"/api/v1/attachments/{tenant_b['attachment'].id}/download"
    ).status_code == 404
    assert client.delete(
        f"/api/v1/attachments/{tenant_b['attachment'].id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/approvals/{tenant_b['approval'].id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/data-imports/{tenant_b['import_job'].id}"
    ).status_code == 404


def test_dashboard_and_exports_are_tenant_local(client, tenant_b):
    overview = client.get("/api/v1/dashboard/overview")
    assert overview.status_code == 200
    assert overview.json()["total_incidents"] == 0

    export = client.get("/api/v1/exports/incidents.csv")
    assert export.status_code == 200
    assert "Tenant B confidential incident" not in export.text


def test_feature_entitlement_and_role_permission_both_apply(
    client, db_session, role_lookup, create_user_for_role, act_as
):
    feature = db_session.scalar(
        select(OrganisationFeature).where(OrganisationFeature.key == "incidents")
    )
    feature.is_enabled = False
    db_session.commit()
    assert client.get("/api/v1/incidents").status_code == 403
    assert client.get("/api/v1/exports/incidents.csv").status_code == 403

    feature.is_enabled = True
    db_session.commit()
    incident = Incident(
        site_id=1,
        title="Tenant A incident",
        description="Tenant A",
        severity=IncidentSeverity.low,
        occurred_at=datetime.now(timezone.utc),
        reported_by_id=1,
    )
    db_session.add(incident)
    db_session.commit()
    employee = create_user_for_role("employee", assigned_site_id=1)
    act_as(employee)
    assert client.get(f"/api/v1/incidents/{incident.id}").status_code == 200
    assert client.patch(
        f"/api/v1/incidents/{incident.id}", json={"title": "not allowed"}
    ).status_code == 403


def test_platform_admin_and_tenant_admin_boundaries(client, tenant_b, act_as):
    platform_response = client.get("/api/v1/organisations")
    assert platform_response.status_code == 200
    assert {row["code"] for row in platform_response.json()} == {"TEST", "TENANT-B"}
    assert client.get(f"/api/v1/departments/{tenant_b['department'].id}").status_code == 404

    act_as(tenant_b["admin"])
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert "admin" in me.json()["role_names"]
    assert client.get("/api/v1/organisations").status_code == 403
    assert client.get("/api/v1/organisations/1").status_code == 403
    assert client.get("/api/v1/sites/1").status_code in {403, 404}
    assert client.get(f"/api/v1/departments/{tenant_b['department'].id}").status_code == 200

    act_as(tenant_b["employee"])
    assert client.get(f"/api/v1/sites/{tenant_b['second_site'].id}").status_code == 403


def test_same_external_reference_is_unique_per_tenant(db_session, tenant_b):
    set_tenant_context(db_session, 1)
    sio = SafetyImprovementObservation(
        reference_number="SIO-2026-000001",
        external_reference_id="SHARED-REFERENCE",
        source_system="legacy",
        department="Operations",
        source_type="walkthrough",
        description="Tenant A SIO",
        observation_nature=SIOObservationNature.positive,
        site_id=1,
        created_by_user_id=1,
    )
    db_session.add(sio)
    db_session.commit()
    assert sio.id != tenant_b["sio"].id


def test_startup_superadmin_is_platform_admin_and_tenant_bound(monkeypatch, db_session):
    import app.main as main_module

    monkeypatch.setattr(main_module, "SessionLocal", lambda: db_session)
    main_module.ensure_superadmin_user()
    with unscoped_session(db_session):
        startup_admin = db_session.scalar(
            select(User).where(User.email == main_module.SUPERADMIN_EMAIL)
        )
    assert startup_admin is not None
    assert startup_admin.is_platform_admin is True
    assert startup_admin.organisation_id is not None
    assert "admin" in startup_admin.role_names
