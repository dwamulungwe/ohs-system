from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.corrective_action import (
    ActionActivity,
    ActionReminderDelivery,
    ActionTask,
    CorrectiveAction,
    CorrectiveActionStatus,
)
from app.models.notification import Notification, NotificationType
from app.models.organisation import OrganisationFeature, OrganisationSettings
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.organisation import OrganisationCreate
from app.services.corrective_action_service import (
    create_corrective_action,
    generate_action_escalations,
)
from app.services.organisation_service import create_organisation_record
from app.services.tenancy import set_tenant_context


def action_payload(**overrides) -> dict:
    payload = {
        "site_id": 1,
        "title": "Unified tracker action",
        "description": "Complete the defined safety improvement.",
        "acceptance_criteria": "Evidence shows the control is effective.",
        "source_type": "manual",
        "priority": "high",
        "lifecycle_status": "open",
        "current_due_date": "2026-05-10",
    }
    payload.update(overrides)
    return payload


def test_reference_sequence_uses_prefix_existing_max_and_is_tenant_year_local(
    client: TestClient, db_session
) -> None:
    settings = db_session.scalar(select(OrganisationSettings))
    settings.numbering_prefixes = {"action": "SAFE"}
    db_session.add(
        CorrectiveAction(
            action_reference="SAFE-2026-000007",
            title="Existing imported action",
            description="Existing record that predates the sequence table.",
            lifecycle_status=CorrectiveActionStatus.open,
            created_by_user_id=1,
        )
    )
    db_session.commit()

    first = client.post("/api/v1/corrective-actions", json=action_payload())
    second = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(title="Second numbered action"),
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["action_reference"] == "SAFE-2026-000008"
    assert second.json()["action_reference"] == "SAFE-2026-000009"

    tenant_b = create_organisation_record(
        db_session,
        OrganisationCreate(name="Reference Tenant B", code="REF-B", slug="reference-tenant-b"),
    )
    set_tenant_context(db_session, tenant_b.id)
    tenant_b_action = create_corrective_action(
        db_session,
        CorrectiveActionCreate(title="Tenant B action", description="Independent sequence."),
        current_user_id=None,
    )
    assert tenant_b_action.action_reference == "ACT-2026-000001"
    set_tenant_context(db_session, 1, platform_admin=True)


def test_assignment_tasks_extensions_completion_verification_reopen_and_timeline(
    client: TestClient,
    db_session,
    create_user_for_role,
    act_as,
) -> None:
    owner = create_user_for_role("employee", assigned_site_id=1)
    verifier = create_user_for_role("safety_officer", assigned_site_id=1)
    settings = db_session.scalar(select(OrganisationSettings))
    settings.action_workflow_configuration = {
        "verification_required": True,
        "independent_verifier_required": True,
    }
    db_session.commit()

    created = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(owner_user_id=None, verifier_user_id=verifier.id),
    )
    action_id = created.json()["id"]
    assigned = client.post(
        f"/api/v1/corrective-actions/{action_id}/assign",
        json={
            "owner_user_id": owner.id,
            "verifier_user_id": verifier.id,
            "current_due_date": "2026-05-10",
            "note": "Assigned by the action manager.",
        },
    )
    assert assigned.status_code == 200
    assert assigned.json()["lifecycle_status"] == "assigned"

    act_as(owner)
    accepted = client.post(f"/api/v1/corrective-actions/{action_id}/assignment/accept")
    assert accepted.status_code == 200
    assert accepted.json()["accepted_at"] is not None
    started = client.post(
        f"/api/v1/corrective-actions/{action_id}/transition",
        json={"lifecycle_status": "in_progress"},
    )
    assert started.status_code == 200

    required_task = client.post(
        f"/api/v1/corrective-actions/{action_id}/tasks",
        json={
            "title": "Install control",
            "owner_user_id": owner.id,
            "status": "open",
            "is_required": True,
        },
    )
    optional_task = client.post(
        f"/api/v1/corrective-actions/{action_id}/tasks",
        json={"title": "Brief the team", "status": "open", "is_required": False},
    )
    assert required_task.status_code == optional_task.status_code == 201
    blocked = client.post(
        f"/api/v1/corrective-actions/{action_id}/request-completion",
        json={"completion_notes": "Work is complete."},
    )
    assert blocked.status_code in {400, 409, 422}

    completed_task = client.patch(
        f"/api/v1/corrective-actions/{action_id}/tasks/{required_task.json()['id']}",
        json={"status": "completed", "notes": "Installed and checked."},
    )
    assert completed_task.status_code == 200
    detail = client.get(f"/api/v1/corrective-actions/{action_id}").json()
    assert detail["progress_percent"] == 50

    extension = client.post(
        f"/api/v1/corrective-actions/{action_id}/extensions",
        json={
            "requested_due_date": "2026-05-20",
            "extension_reason": "Vendor verification slot moved.",
        },
    )
    assert extension.status_code == 201
    assert client.post(
        f"/api/v1/corrective-actions/{action_id}/comments",
        json={"body": "Control installed; external verification remains."},
    ).status_code == 201

    act_as(1)
    decision = client.post(
        f"/api/v1/corrective-actions/{action_id}/extensions/{extension.json()['id']}/decision",
        json={"approved": True, "decision_notes": "Approved against vendor evidence."},
    )
    assert decision.status_code == 200
    governed = client.get(f"/api/v1/corrective-actions/{action_id}").json()
    assert governed["original_due_date"] == "2026-05-10"
    assert governed["current_due_date"] == "2026-05-20"
    assert governed["number_of_extensions"] == 1
    direct_due_change = client.patch(
        f"/api/v1/corrective-actions/{action_id}",
        json={"current_due_date": "2026-06-01"},
    )
    assert direct_due_change.status_code in {400, 409, 422}

    act_as(owner)
    pending = client.post(
        f"/api/v1/corrective-actions/{action_id}/request-completion",
        json={"completion_notes": "Required task complete and acceptance criteria met."},
    )
    assert pending.status_code == 200
    assert pending.json()["lifecycle_status"] == "pending_verification"
    assert pending.json()["progress_percent"] == 100
    assert client.post(
        f"/api/v1/corrective-actions/{action_id}/verify",
        json={"approved": True, "notes": "Owner attempted self-verification."},
    ).status_code == 403

    act_as(1)
    maker_checker = client.post(
        f"/api/v1/corrective-actions/{action_id}/verify",
        json={"approved": True, "notes": "Creator attempted verification."},
    )
    assert maker_checker.status_code in {400, 409, 422}

    act_as(verifier)
    closed = client.post(
        f"/api/v1/corrective-actions/{action_id}/verify",
        json={"approved": True, "notes": "Acceptance criteria independently verified."},
    )
    assert closed.status_code == 200
    assert closed.json()["lifecycle_status"] == "closed"
    reopened = client.post(
        f"/api/v1/corrective-actions/{action_id}/reopen",
        json={"reason": "Control effectiveness degraded during follow-up."},
    )
    assert reopened.status_code == 200
    assert reopened.json()["lifecycle_status"] == "reopened"
    assert reopened.json()["closed_at"] is not None

    activity = client.get(f"/api/v1/corrective-actions/{action_id}/activity").json()
    event_types = {entry["event_type"] for entry in activity}
    assert {
        "created",
        "assigned",
        "accepted",
        "started",
        "task_added",
        "task_completed",
        "comment_added",
        "extension_requested",
        "extension_approved",
        "completion_requested",
        "verification_approved",
        "closed",
        "reopened",
    }.issubset(event_types)


def test_decline_reassignment_history_queues_bulk_export_and_dashboard(
    client: TestClient,
    create_user_for_role,
    act_as,
) -> None:
    first_owner = create_user_for_role("employee", assigned_site_id=1)
    second_owner = create_user_for_role("supervisor", assigned_site_id=1)
    created = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(owner_user_id=None, title="Reassignment action"),
    )
    action_id = created.json()["id"]
    assert client.post(
        f"/api/v1/corrective-actions/{action_id}/assign",
        json={"owner_user_id": first_owner.id},
    ).status_code == 200

    act_as(first_owner)
    declined = client.post(
        f"/api/v1/corrective-actions/{action_id}/assignment/decline",
        json={"reason": "The work belongs to the maintenance team."},
    )
    assert declined.status_code == 200
    assert declined.json()["lifecycle_status"] == "declined"
    assert declined.json()["owner_user_id"] is None

    act_as(1)
    reassigned = client.post(
        f"/api/v1/corrective-actions/{action_id}/assign",
        json={"owner_user_id": second_owner.id, "note": "Routed to maintenance supervision."},
    )
    assert reassigned.status_code == 200
    assert len(reassigned.json()["assignment_history"]) == 2

    act_as(second_owner)
    queue = client.get("/api/v1/corrective-actions?queue=my_actions")
    assert queue.status_code == 200
    assert [row["id"] for row in queue.json()["items"]] == [action_id]

    act_as(1)
    bulk_priority = client.post(
        "/api/v1/corrective-actions/bulk",
        json={
            "action_ids": [action_id],
            "operation": "change_priority",
            "priority": "critical",
            "note": "Escalated after reassignment.",
        },
    )
    assert bulk_priority.status_code == 200
    assert bulk_priority.json()["updated_ids"] == [action_id]
    export = client.post(
        "/api/v1/corrective-actions/bulk/export",
        json={"action_ids": [action_id]},
    )
    assert export.status_code == 200
    assert "Reassignment action" in export.text
    dashboard = client.get("/api/v1/corrective-actions/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["open_actions"] == 1
    assert dashboard.json()["by_priority"]["critical"] == 1


def test_overdue_is_derived_and_escalation_is_deduplicated(
    client: TestClient, db_session
) -> None:
    created = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(
            title="One day overdue action",
            owner_user_id=1,
            current_due_date="2026-04-22",
        ),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["lifecycle_status"] == "open"
    assert body["status"] == "overdue"
    assert body["is_overdue"] is True
    assert body["days_overdue"] == 1
    filtered = client.get("/api/v1/corrective-actions?overdue=true")
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == [body["id"]]

    first_run = generate_action_escalations(db_session)
    first_delivery_count = db_session.scalar(select(func.count(ActionReminderDelivery.id)))
    second_run = generate_action_escalations(db_session)
    second_delivery_count = db_session.scalar(select(func.count(ActionReminderDelivery.id)))
    assert first_run
    assert second_run == []
    assert first_delivery_count == second_delivery_count == 1
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.notification_type == NotificationType.action_overdue
        )
    ) == 1


def test_recurrence_is_single_shot_import_is_suppressed_and_feature_fails_closed(
    client: TestClient, db_session
) -> None:
    settings = db_session.scalar(select(OrganisationSettings))
    settings.action_workflow_configuration = {
        "verification_required": False,
        "recurrence_defaults": {"frequency": "weekly", "interval": 1},
    }
    db_session.commit()
    recurring = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(
            title="Weekly inspection follow-up",
            owner_user_id=1,
            priority="low",
            lifecycle_status="in_progress",
            current_due_date="2026-04-23",
            recurrence_enabled=True,
        ),
    )
    assert recurring.status_code == 201
    parent_id = recurring.json()["id"]
    assert recurring.json()["recurrence_frequency"] == "weekly"
    closed = client.post(
        f"/api/v1/corrective-actions/{parent_id}/request-completion",
        json={"completion_notes": "Weekly control confirmed."},
    )
    assert closed.status_code == 200
    assert closed.json()["lifecycle_status"] == "closed"
    successor = db_session.scalar(
        select(CorrectiveAction).where(CorrectiveAction.recurrence_parent_action_id == parent_id)
    )
    assert successor is not None
    assert successor.current_due_date == date(2026, 4, 30)
    assert successor.lifecycle_status == CorrectiveActionStatus.assigned
    assert client.post(
        f"/api/v1/corrective-actions/{parent_id}/request-completion",
        json={"completion_notes": "Duplicate request."},
    ).status_code in {400, 409, 422}
    assert db_session.scalar(
        select(func.count(CorrectiveAction.id)).where(
            CorrectiveAction.recurrence_parent_action_id == parent_id
        )
    ) == 1
    assert db_session.scalar(
        select(func.count(ActionActivity.id)).where(
            ActionActivity.action_id == parent_id,
            ActionActivity.event_type == "recurrence_generated",
        )
    ) == 1

    imported = create_corrective_action(
        db_session,
        CorrectiveActionCreate(
            title="Historical recurring import",
            description="Imported without automation side effects.",
            owner_user_id=1,
            current_due_date=date(2026, 4, 22),
            recurrence_enabled=True,
            recurrence_frequency="weekly",
        ),
        current_user_id=1,
        is_import=True,
    )
    assert imported.automation_suppressed is True
    generate_action_escalations(db_session)
    assert db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.related_entity_id == imported.id
        )
    ) == 0
    assert db_session.scalar(
        select(func.count(ActionReminderDelivery.id)).where(
            ActionReminderDelivery.action_id == imported.id
        )
    ) == 0

    feature = db_session.scalar(
        select(OrganisationFeature).where(OrganisationFeature.key == "corrective_actions")
    )
    feature.is_enabled = False
    db_session.commit()
    assert client.get("/api/v1/corrective-actions").status_code == 403
    assert client.get("/api/v1/corrective-actions/dashboard").status_code == 403
    assert client.get(f"/api/v1/corrective-actions/{parent_id}/activity").status_code == 403


def test_action_children_are_tenant_scoped_and_null_site_owner_remains_visible(
    client: TestClient,
    db_session,
    create_user_for_role,
    act_as,
) -> None:
    owner = create_user_for_role("employee", assigned_site_id=1)
    unscoped = client.post(
        "/api/v1/corrective-actions",
        json=action_payload(
            site_id=None,
            title="Owner-visible unscoped action",
            owner_user_id=owner.id,
        ),
    )
    assert unscoped.status_code == 201
    act_as(owner)
    employee_list = client.get("/api/v1/corrective-actions?queue=my_actions")
    assert employee_list.status_code == 200
    assert [row["id"] for row in employee_list.json()["items"]] == [unscoped.json()["id"]]
    assert client.get(
        f"/api/v1/corrective-actions/{unscoped.json()['id']}"
    ).status_code == 200

    act_as(1)
    tenant_b = create_organisation_record(
        db_session,
        OrganisationCreate(name="Child Tenant B", code="CHILD-B", slug="child-tenant-b"),
    )
    set_tenant_context(db_session, tenant_b.id)
    tenant_b_action = create_corrective_action(
        db_session,
        CorrectiveActionCreate(
            title="Tenant B private action",
            description="Child resources must not leak.",
            current_due_date=date(2026, 5, 1),
        ),
        current_user_id=None,
    )
    tenant_b_task = ActionTask(action_id=tenant_b_action.id, title="Tenant B private task")
    db_session.add(tenant_b_task)
    db_session.commit()
    tenant_b_action_id = tenant_b_action.id
    tenant_b_task_id = tenant_b_task.id
    set_tenant_context(db_session, 1, platform_admin=True)

    for suffix in ("comments", "activity", "extensions"):
        assert client.get(
            f"/api/v1/corrective-actions/{tenant_b_action_id}/{suffix}"
        ).status_code == 404
    assert client.patch(
        f"/api/v1/corrective-actions/{tenant_b_action_id}/tasks/{tenant_b_task_id}",
        json={"status": "completed"},
    ).status_code == 404
    assert client.post(
        "/api/v1/corrective-actions/bulk",
        json={
            "action_ids": [tenant_b_action_id],
            "operation": "change_priority",
            "priority": "critical",
        },
    ).status_code == 404
