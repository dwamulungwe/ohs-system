from datetime import date
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction
from app.models.department import Department
from app.models.notification import Notification, NotificationType, RelatedEntityType
from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.role import Role
from app.models.site import Site
from app.models.sio import SIOActivity, SIOComment, SafetyImprovementObservation
from app.models.user import User
from app.services.data_import_service import YALELO_SIO_COLUMNS
from app.services.sio_service import generate_sio_due_notifications
from app.services.tenancy import MODULE_KEYS, unscoped_session


def _payload(**overrides) -> dict:
    payload = {
        "observation_date": "2026-04-10",
        "department": "Operations",
        "source_type": "Walkabout",
        "description": "An unsafe condition requires a tracked operational response.",
        "status": "open",
        "observation_nature": "negative",
        "site_id": 1,
        "urgency": "medium",
        "category": "Housekeeping",
    }
    payload.update(overrides)
    return payload


def _create_tenant_b(db: Session) -> User:
    with unscoped_session(db, allow_writes=True):
        organisation = Organisation(
            id=2,
            name="Tenant B",
            code="TENANT-B",
            slug="tenant-b",
            timezone="Africa/Lusaka",
            is_active=True,
        )
        settings = OrganisationSettings(
            organisation_id=2,
            numbering_prefixes={"sio": "OBS"},
        )
        features = [
            OrganisationFeature(organisation_id=2, key=key, is_enabled=True)
            for key in MODULE_KEYS
        ]
        role = Role(id=100, organisation_id=2, name="admin", description="Tenant B admin")
        user = User(
            id=100,
            organisation_id=2,
            email="admin@tenant-b.example",
            full_name="Tenant B Admin",
            hashed_password="not-used",
            is_active=True,
            roles=[role],
            assigned_site_id=100,
        )
        site = Site(
            id=100,
            organisation_id=2,
            name="Tenant B Site",
            code="TB",
            created_by_id=100,
        )
        db.add_all([organisation, settings, *features, role, user, site])
        db.commit()
    return user


def test_reference_number_is_unique_configurable_and_independent_per_tenant(
    client: TestClient, db_session: Session, act_as
) -> None:
    settings = db_session.scalar(select(OrganisationSettings))
    settings.numbering_prefixes = {"sio": "SAFE"}
    db_session.commit()

    first = client.post("/api/v1/sios", json=_payload()).json()
    second = client.post("/api/v1/sios", json=_payload(description="Second observation")).json()
    assert first["reference_number"] == "SAFE-2026-000001"
    assert second["reference_number"] == "SAFE-2026-000002"

    tenant_b_user = _create_tenant_b(db_session)
    act_as(tenant_b_user)
    tenant_b = client.post(
        "/api/v1/sios",
        json=_payload(site_id=100, department="Processing"),
    )
    assert tenant_b.status_code == 201
    assert tenant_b.json()["reference_number"] == "OBS-2026-000001"


def test_department_assignment_accept_decline_reassign_and_notifications(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    origin = Department(name="Operations", code="OPS")
    maintenance = Department(name="Maintenance", code="MNT")
    db_session.add_all([origin, maintenance])
    db_session.commit()
    first_user = create_user_for_role("employee", assigned_site_id=1, full_name="First Owner")
    second_user = create_user_for_role("employee", assigned_site_id=1, full_name="Second Owner")

    sio = client.post(
        "/api/v1/sios",
        json=_payload(department_id=origin.id, responsible_department_id=maintenance.id),
    ).json()
    assigned = client.post(
        f"/api/v1/sios/{sio['id']}/assign",
        json={
            "responsible_user_id": first_user.id,
            "responsible_department_id": maintenance.id,
            "due_date": "2026-04-30",
        },
    )
    assert assigned.status_code == 200
    assert assigned.json()["assignment_status"] == "assigned"
    assert assigned.json()["department"] == "Operations"
    assert assigned.json()["responsible_department"] == "Maintenance"

    act_as(first_user)
    accepted = client.post(f"/api/v1/sios/{sio['id']}/assignment/accept")
    assert accepted.status_code == 200
    assert accepted.json()["assignment_status"] == "accepted"

    act_as(1)
    reassigned = client.post(
        f"/api/v1/sios/{sio['id']}/assign",
        json={"responsible_user_id": second_user.id, "responsible_department_id": maintenance.id},
    )
    assert reassigned.json()["assignment_status"] == "reassigned"

    act_as(second_user)
    declined = client.post(
        f"/api/v1/sios/{sio['id']}/assignment/decline",
        json={"reason": "Workload conflict; reassign to the electrical team."},
    )
    assert declined.status_code == 200
    assert declined.json()["assignment_status"] == "declined"
    assert declined.json()["status"] == "unassigned"
    assert declined.json()["responsible_user_id"] is None

    act_as(1)
    events = [entry["event_type"] for entry in client.get(f"/api/v1/sios/{sio['id']}/activity").json()]
    assert {"assigned", "accepted", "reassigned", "declined"}.issubset(events)
    notification_types = set(
        db_session.scalars(
            select(Notification.notification_type).where(
                Notification.related_entity_type == RelatedEntityType.sio,
                Notification.related_entity_id == sio["id"],
            )
        ).all()
    )
    assert NotificationType.sio_assigned in notification_types
    assert NotificationType.sio_reassigned in notification_types
    assert NotificationType.sio_assignment_declined in notification_types


def test_transition_aging_closure_verification_and_reopen(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    employee = create_user_for_role("employee", assigned_site_id=1)
    sio = client.post(
        "/api/v1/sios",
        json=_payload(due_date="2026-04-20", urgency="high"),
    ).json()
    assert sio["age_days"] == 13
    assert sio["is_overdue"] is True
    assert sio["days_overdue"] == 3
    assert client.patch(f"/api/v1/sios/{sio['id']}", json={"status": "closed"}).status_code == 422

    assigned = client.post(
        f"/api/v1/sios/{sio['id']}/assign",
        json={"responsible_user_id": employee.id},
    ).json()
    act_as(employee)
    assert client.post(f"/api/v1/sios/{sio['id']}/assignment/accept").status_code == 200
    progress = client.post(
        f"/api/v1/sios/{sio['id']}/transition",
        json={"status": "in_progress", "reason": "Corrective work started."},
    )
    assert progress.status_code == 200
    requested = client.post(
        f"/api/v1/sios/{sio['id']}/request-closure",
        json={"notes": "Work completed and closure evidence uploaded."},
    )
    assert requested.status_code == 200
    assert requested.json()["status"] == "pending_verification"

    act_as(1)
    verified = client.post(
        f"/api/v1/sios/{sio['id']}/verify",
        json={"approved": True, "notes": "Controls verified in the field."},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "closed"
    assert verified.json()["closed_at"] is not None

    reopened = client.post(
        f"/api/v1/sios/{sio['id']}/reopen",
        json={"reason": "The control failed during follow-up inspection."},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "reopened"
    assert reopened.json()["reopen_reason"]


def test_no_action_requires_reason_and_authorised_role(
    client: TestClient, create_user_for_role, act_as
) -> None:
    sio = client.post("/api/v1/sios", json=_payload()).json()
    employee = create_user_for_role("employee", assigned_site_id=1)
    act_as(employee)
    assert client.post(
        f"/api/v1/sios/{sio['id']}/no-action-required",
        json={"reason": "Not applicable"},
    ).status_code == 403
    act_as(1)
    assert client.post(
        f"/api/v1/sios/{sio['id']}/no-action-required", json={"reason": ""}
    ).status_code == 422
    response = client.post(
        f"/api/v1/sios/{sio['id']}/no-action-required",
        json={"reason": "Positive observation captured for learning only."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_action_required"


def test_investigation_comments_activity_and_sio_evidence(
    client: TestClient, db_session: Session
) -> None:
    sio = client.post("/api/v1/sios", json=_payload()).json()
    investigation = client.patch(
        f"/api/v1/sios/{sio['id']}/investigation",
        json={
            "investigation_required": True,
            "investigator_user_id": 1,
            "immediate_cause": "Temporary access obstruction",
            "underlying_cause": "Poor material staging",
            "root_cause": "No defined laydown-area standard",
            "contributing_factors": ["Congested shift change", "Missing floor markings"],
            "investigation_summary": "Staging controls were absent.",
            "lessons_learned": "Define and inspect laydown areas.",
        },
    )
    assert investigation.status_code == 200
    assert investigation.json()["root_cause"] == "No defined laydown-area standard"

    comment = client.post(
        f"/api/v1/sios/{sio['id']}/comments",
        json={"body": "Supervisor confirmed the immediate control is in place."},
    )
    assert comment.status_code == 201
    assert client.patch(
        f"/api/v1/sios/{sio['id']}/comments/{comment.json()['id']}", json={"body": "edit"}
    ).status_code in {404, 405}

    attachment = client.post(
        f"/api/v1/attachments/sio/{sio['id']}",
        data={"description": "Closure photograph", "evidence_type": "closure"},
        files={"file": ("evidence.jpg", b"safe-image-bytes", "image/jpeg")},
    )
    assert attachment.status_code == 201
    assert attachment.json()["evidence_type"] == "closure"
    events = [entry["event_type"] for entry in client.get(f"/api/v1/sios/{sio['id']}/activity").json()]
    assert {"created", "investigation_updated", "comment_added", "attachment_added"}.issubset(events)
    assert db_session.query(SIOComment).count() == 1
    assert db_session.query(SIOActivity).count() >= 4


def test_linked_records_inherit_responsibility_department_and_due_date(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
) -> None:
    origin = Department(name="Processing", code="PROC")
    responsible = Department(name="Engineering", code="ENG")
    db_session.add_all([origin, responsible])
    db_session.commit()
    owner = create_user_for_role("employee", assigned_site_id=1)
    sio = client.post(
        "/api/v1/sios",
        json=_payload(
            department_id=origin.id,
            responsible_department_id=responsible.id,
            responsible_user_id=owner.id,
            due_date="2026-05-15",
        ),
    ).json()
    linked = client.post(f"/api/v1/sios/{sio['id']}/create-corrective-action")
    assert linked.status_code == 201
    action = db_session.get(CorrectiveAction, linked.json()["linked_corrective_action_id"])
    assert action.source_id == sio["id"]
    assert action.department_id == origin.id
    assert action.responsible_department_id == responsible.id
    assert action.assigned_to_user_id == owner.id
    assert action.due_date == date(2026, 5, 15)
    assert client.post(f"/api/v1/sios/{sio['id']}/create-corrective-action").status_code == 409


def test_bulk_operations_fail_safely_for_site_and_tenant_scope(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    db_session.add(Site(id=2, name="Remote", code="REMOTE"))
    db_session.commit()
    local = client.post("/api/v1/sios", json=_payload()).json()
    remote = client.post("/api/v1/sios", json=_payload(site_id=2, description="Remote SIO")).json()
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    act_as(supervisor)
    denied = client.post(
        "/api/v1/sios/bulk",
        json={
            "sio_ids": [local["id"], remote["id"]],
            "operation": "set_due_date",
            "due_date": "2026-05-01",
        },
    )
    assert denied.status_code == 403
    act_as(1)
    assert db_session.get(SafetyImprovementObservation, local["id"]).due_date is None

    tenant_b = _create_tenant_b(db_session)
    act_as(tenant_b)
    other = client.post("/api/v1/sios", json=_payload(site_id=100)).json()
    act_as(1)
    cross_tenant = client.post(
        "/api/v1/sios/bulk",
        json={
            "sio_ids": [local["id"], other["id"]],
            "operation": "set_due_date",
            "due_date": "2026-05-02",
        },
    )
    assert cross_tenant.status_code == 404
    assert db_session.get(SafetyImprovementObservation, local["id"]).due_date is None
    assert client.get(f"/api/v1/sios/{other['id']}/activity").status_code == 404


def test_sio_feature_rbac_personal_views_export_and_dashboard(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    employee = create_user_for_role("employee", assigned_site_id=1)
    sio = client.post(
        "/api/v1/sios",
        json=_payload(responsible_user_id=employee.id, due_date="2026-04-20", urgency="urgent"),
    ).json()
    act_as(employee)
    assigned = client.get("/api/v1/sios?view=assigned_to_me")
    assert assigned.status_code == 200 and assigned.json()["total"] == 1
    assert client.post(
        "/api/v1/sios/bulk",
        json={"sio_ids": [sio["id"]], "operation": "set_due_date", "due_date": "2026-05-01"},
    ).status_code == 403

    act_as(1)
    export = client.get("/api/v1/exports/sios.csv?overdue=true")
    assert export.status_code == 200
    assert "Reference Number" in export.text and sio["reference_number"] in export.text
    selected = client.post("/api/v1/sios/bulk/export", json={"sio_ids": [sio["id"]]})
    assert selected.status_code == 200 and sio["reference_number"] in selected.text
    analytics = client.get("/api/v1/dashboard/sios")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["total_observations"] == 1
    assert body["overdue_observations"] == 1
    assert body["urgent_high_priority_observations"] == 1
    assert body["most_overdue_sios"][0]["reference_number"] == sio["reference_number"]

    feature = db_session.scalar(select(OrganisationFeature).where(OrganisationFeature.key == "sios"))
    feature.is_enabled = False
    db_session.commit()
    assert client.get("/api/v1/sios").status_code == 403
    assert client.get("/api/v1/exports/sios.csv").status_code == 403


def test_due_notification_is_tenant_aware_and_deduplicated(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
) -> None:
    owner = create_user_for_role("employee", assigned_site_id=1)
    sio = client.post(
        "/api/v1/sios",
        json=_payload(responsible_user_id=owner.id, due_date="2026-04-20"),
    ).json()
    created = generate_sio_due_notifications(db_session)
    assert any(
        notification.notification_type == NotificationType.sio_overdue
        and notification.recipient_user_id == owner.id
        for notification in created
    )
    assert generate_sio_due_notifications(db_session) == []
    assert db_session.scalar(
        select(Notification.id).where(
            Notification.related_entity_type == RelatedEntityType.sio,
            Notification.related_entity_id == sio["id"],
            Notification.notification_type == NotificationType.sio_overdue,
        )
    ) is not None


def _workbook_bytes() -> bytes:
    row = {
        "ID": "LEGACY-2001",
        "Date": None,
        "Department": "Processing",
        "Source of Observation": "Inspection",
        "Description of SIO": "Historical imported observation.",
        "Incident Classification": "Observation",
        "Status": "Assigned to Responsible Person",
        "Nature of Observation": "Positive",
        "Department Responsible for Corrective Action": "Maintenance",
        "Site": "Main Plant",
        "Urgency": "N/A",
        "SIO Category": "Isolation",
        "Created By": "Legacy Author",
        "Person Responsible for Corrective Action": "Imported Owner",
    }
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(YALELO_SIO_COLUMNS))
    sheet.append([row.get(column) for column in YALELO_SIO_COLUMNS])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_import_maps_exact_departments_without_workflow_notifications(
    client: TestClient, db_session: Session, create_user_for_role
) -> None:
    processing = Department(name="Processing", code="PROC")
    maintenance = Department(name="Maintenance", code="MNT")
    db_session.add_all([processing, maintenance])
    db_session.commit()
    imported_owner = create_user_for_role(
        "employee", assigned_site_id=1, full_name="Imported Owner"
    )
    preview = client.post(
        "/api/v1/data-imports/preview",
        files={"file": ("SIOs.xlsx", _workbook_bytes())},
    )
    assert preview.status_code == 201
    confirmed = client.post(f"/api/v1/data-imports/{preview.json()['id']}/confirm", json={})
    assert confirmed.status_code == 200
    imported = db_session.scalar(select(SafetyImprovementObservation))
    assert imported.external_reference_id == "LEGACY-2001"
    assert imported.department_id == processing.id
    assert imported.responsible_department_id == maintenance.id
    assert imported.responsible_user_id == imported_owner.id
    assert imported.status.value == "assigned_to_responsible_person"
    assert imported.reference_number.startswith("SIO-2026-")
    assert db_session.scalar(
        select(Notification.id).where(
            Notification.related_entity_type == RelatedEntityType.sio,
            Notification.related_entity_id == imported.id,
        )
    ) is None
    events = db_session.scalars(
        select(SIOActivity.event_type).where(SIOActivity.sio_id == imported.id)
    ).all()
    assert events == ["imported"]
