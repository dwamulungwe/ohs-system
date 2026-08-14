from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.corrective_action import CorrectiveAction
from app.models.audit_log import AuditLog
from app.models.notification import Notification, NotificationType
from app.models.organisation import OrganisationFeature
from app.models.ppe import (
    PPEAsset,
    PPEAssetStatus,
    PPEInventory,
    PPEIssue,
    PPEIssueStatus,
    PPEStockMovement,
)
from app.models.reporting import KPIDefinition, ReportingPeriod, ReportingPeriodType
from app.models.role import Role
from app.models.site import Site
from app.models.user import User
from app.schemas.organisation import OrganisationCreate
from app.services.organisation_service import create_organisation_record
from app.services.reporting_calculations import CalculationContext, calculate_kpi
from app.services.reporting_catalogue import ensure_platform_kpi_catalogue
from app.services.tenancy import set_tenant_context


TODAY = date(2026, 4, 23)


def _create_category(client, name="Head Protection"):
    response = client.post("/api/v1/ppe/categories", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _create_item(client, category_id, *, name="Safety Helmet", code="HELMET-01", **overrides):
    payload = {
        "category_id": category_id,
        "name": name,
        "code": code,
        "is_reusable": True,
        "inspection_required": False,
        "expiry_tracking": True,
        "minimum_stock_level": 2,
        "reorder_level": 3,
        "unit_cost": "25.50",
        **overrides,
    }
    response = client.post("/api/v1/ppe/catalogue", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_location(client, name="Central Store", site_id=1):
    response = client.post("/api/v1/ppe/locations", json={"name": name, "site_id": site_id})
    assert response.status_code == 201, response.text
    return response.json()


def _receive(client, item_id, location_id, quantity, *, variant_id=None, unit_cost="25.50"):
    response = client.post(
        "/api/v1/ppe/inventory/receive",
        json={
            "item_id": item_id,
            "variant_id": variant_id,
            "location_id": location_id,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "reference": "PO-1001",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _issue(client, item_id, location_id, recipient_user_id, *, quantity=1, variant_id=None, **overrides):
    response = client.post(
        "/api/v1/ppe/issues",
        json={
            "recipient_type": "employee",
            "recipient_user_id": recipient_user_id,
            "item_id": item_id,
            "variant_id": variant_id,
            "stock_location_id": location_id,
            "quantity": quantity,
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _basic_stock(client, *, quantity=10, item_overrides=None):
    category = _create_category(client)
    item = _create_item(client, category["id"], **(item_overrides or {}))
    location = _create_location(client)
    inventory = _receive(client, item["id"], location["id"], quantity)
    return category, item, location, inventory


def test_catalogue_variants_locations_and_inventory_mutations_are_auditable(client, db_session):
    category = _create_category(client, "Foot Protection")
    item = _create_item(
        client,
        category["id"],
        name="Safety Boots",
        code="BOOT-01",
        size_applicable=True,
    )
    variant_response = client.post(
        "/api/v1/ppe/variants",
        json={"item_id": item["id"], "name": "Size 8", "size": "8", "sku_suffix": "-08"},
    )
    assert variant_response.status_code == 201, variant_response.text
    variant = variant_response.json()
    central = _create_location(client)
    workshop = _create_location(client, "Workshop")
    _receive(client, item["id"], central["id"], 10, variant_id=variant["id"])

    transfer = client.post(
        "/api/v1/ppe/inventory/transfer",
        json={
            "item_id": item["id"],
            "variant_id": variant["id"],
            "source_location_id": central["id"],
            "destination_location_id": workshop["id"],
            "quantity": 3,
            "reason": "Workshop allocation",
        },
    )
    assert transfer.status_code == 200, transfer.text
    assert [row["movement_type"] for row in transfer.json()] == ["transfer_out", "transfer_in"]
    assert transfer.json()[0]["transfer_reference"] == transfer.json()[1]["transfer_reference"]

    adjustment = client.post(
        "/api/v1/ppe/inventory/adjust",
        json={
            "item_id": item["id"],
            "variant_id": variant["id"],
            "location_id": workshop["id"],
            "quantity_delta": -1,
            "movement_type": "damaged_write_off",
            "reason": "Damaged carton",
        },
    )
    assert adjustment.status_code == 200, adjustment.text
    assert adjustment.json()["quantity_available"] == 2
    movements = list(db_session.scalars(select(PPEStockMovement).order_by(PPEStockMovement.id)).all())
    assert [row.quantity for row in movements] == [10, -3, 3, -1]
    assert movements[-1].balance_after == 2


def test_atomic_issue_blocks_negative_stock_and_reusable_return_restocks(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(client, quantity=4)
    issue = _issue(client, item["id"], location["id"], employee.id, quantity=3)
    inventory = db_session.scalar(select(PPEInventory).where(PPEInventory.item_id == item["id"]))
    assert inventory.quantity_available == 1

    insufficient = client.post(
        "/api/v1/ppe/issues",
        json={
            "recipient_type": "employee",
            "recipient_user_id": employee.id,
            "item_id": item["id"],
            "stock_location_id": location["id"],
            "quantity": 2,
        },
    )
    assert insufficient.status_code == 409
    db_session.refresh(inventory)
    assert inventory.quantity_available == 1
    assert db_session.scalar(select(PPEIssue).where(PPEIssue.id != issue["id"])) is None

    returned = client.post(
        f"/api/v1/ppe/issues/{issue['id']}/return",
        json={"quantity": 2, "condition": "serviceable", "outcome": "reusable", "notes": "Role change"},
    )
    assert returned.status_code == 201, returned.text
    db_session.refresh(inventory)
    assert inventory.quantity_available == 3
    issue_record = db_session.get(PPEIssue, issue["id"])
    assert issue_record.status == PPEIssueStatus.partially_returned
    assert issue_record.returned_quantity == 2


def test_negative_stock_override_requires_tenant_setting_explicit_flag_and_admin_audit(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(client, quantity=1)
    _issue(client, item["id"], location["id"], employee.id)
    blocked = client.post(
        "/api/v1/ppe/issues",
        json={
            "recipient_type": "employee", "recipient_user_id": employee.id,
            "item_id": item["id"], "stock_location_id": location["id"], "quantity": 1,
            "authorised_negative_override": True,
        },
    )
    assert blocked.status_code == 409
    configured = client.patch(
        "/api/v1/organisations/1/settings",
        json={"ppe_configuration": {"allow_negative_inventory": True}},
    )
    assert configured.status_code == 200, configured.text
    override = client.post(
        "/api/v1/ppe/issues",
        json={
            "recipient_type": "employee", "recipient_user_id": employee.id,
            "item_id": item["id"], "stock_location_id": location["id"], "quantity": 1,
            "authorised_negative_override": True,
        },
    )
    assert override.status_code == 201, override.text
    inventory = db_session.scalar(select(PPEInventory).where(PPEInventory.item_id == item["id"]))
    assert inventory.quantity_available == -1
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "ppe.issue").order_by(AuditLog.id.desc()))
    assert audit.details["override_requested"] is True


def test_requirements_matrix_derives_valid_expired_and_failed_compliance(client, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(
        client,
        quantity=3,
        item_overrides={
            "inspection_required": True,
            "default_inspection_interval_days": 30,
            "is_critical": True,
        },
    )
    requirement = client.post(
        "/api/v1/ppe/requirements",
        json={
            "item_id": item["id"],
            "role_name": "employee",
            "site_id": 1,
            "requirement_level": "mandatory",
            "quantity": 1,
            "inspection_required": True,
            "is_critical": True,
        },
    )
    assert requirement.status_code == 201, requirement.text
    missing = client.get(f"/api/v1/ppe/employees/{employee.id}").json()
    assert missing["compliance_status"] == "non_compliant"
    assert missing["missing"][0]["reason"] == "not issued"

    expired_issue = _issue(
        client,
        item["id"],
        location["id"],
        employee.id,
        expiry_date=(TODAY - timedelta(days=1)).isoformat(),
    )
    expired = client.get(f"/api/v1/ppe/employees/{employee.id}").json()
    assert expired["compliance_status"] == "non_compliant"
    assert expired["missing"][0]["reason"] == "expired"

    valid_issue = _issue(client, item["id"], location["id"], employee.id)
    compliant = client.get(f"/api/v1/ppe/employees/{employee.id}").json()
    assert compliant["compliance_status"] == "compliant"
    assert compliant["compliance_rate"] == 100

    failed = client.post(
        "/api/v1/ppe/inspections",
        json={
            "issue_id": valid_issue["id"],
            "condition": "unserviceable",
            "passed": False,
            "defects": "Cracked shell",
            "create_unified_action": True,
        },
    )
    assert failed.status_code == 201, failed.text
    assert failed.json()["unified_action_id"] is not None
    after_failure = client.get(f"/api/v1/ppe/employees/{employee.id}").json()
    assert after_failure["compliance_status"] == "non_compliant"


def test_serialized_ppe_requires_available_matching_asset(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    category = _create_category(client, "Fall Protection")
    item = _create_item(
        client,
        category["id"],
        name="Fall Arrest Harness",
        code="HARNESS-01",
        inspection_required=True,
        requires_individual_tracking=True,
        is_critical=True,
    )
    location = _create_location(client)
    _receive(client, item["id"], location["id"], 1)
    asset_response = client.post(
        "/api/v1/ppe/assets",
        json={
            "item_id": item["id"],
            "location_id": location["id"],
            "asset_tag": "HAR-0001",
            "serial_number": "SN-HAR-0001",
            "certification_reference": "EN 361",
            "expiry_date": "2028-04-23",
        },
    )
    assert asset_response.status_code == 201, asset_response.text
    asset = asset_response.json()
    without_asset = client.post(
        "/api/v1/ppe/issues",
        json={"recipient_type": "employee", "recipient_user_id": employee.id, "item_id": item["id"], "stock_location_id": location["id"], "quantity": 1},
    )
    assert without_asset.status_code == 422
    issue = _issue(client, item["id"], location["id"], employee.id, asset_id=asset["id"])
    assert issue["asset_id"] == asset["id"]
    assert db_session.get(PPEAsset, asset["id"]).status == PPEAssetStatus.issued


def test_request_approval_acknowledgement_loss_and_replacement_preserve_history(client, db_session, create_user_for_role, act_as):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(client, quantity=4)
    act_as(employee)
    request = client.post(
        "/api/v1/ppe/requests",
        json={"item_id": item["id"], "quantity": 1, "reason": "Mandatory PPE is worn", "urgency": "urgent"},
    )
    assert request.status_code == 201, request.text
    assert request.json()["status"] == "requested"
    act_as(1)
    approved = client.post(f"/api/v1/ppe/requests/{request.json()['id']}/decision", json={"approved": True})
    assert approved.status_code == 200
    issue = _issue(client, item["id"], location["id"], employee.id, request_id=request.json()["id"])
    assert issue["acknowledged_at"] is None
    act_as(employee)
    acknowledgement = client.post(f"/api/v1/ppe/issues/{issue['id']}/acknowledge", json={"method": "in_app"})
    assert acknowledgement.status_code == 200, acknowledgement.text
    loss = client.post(
        f"/api/v1/ppe/issues/{issue['id']}/loss-damage",
        json={"report_type": "lost", "event_date": TODAY.isoformat(), "reason": "Lost during field work"},
    )
    assert loss.status_code == 201, loss.text
    act_as(1)
    replacement = client.post(
        f"/api/v1/ppe/issues/{issue['id']}/replace",
        json={"reason": "lost", "stock_location_id": location["id"], "notes": "Approved replacement"},
    )
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["replacement_for_issue_id"] == issue["id"]
    old = db_session.get(PPEIssue, issue["id"])
    assert old.status == PPEIssueStatus.replaced
    assert old.acknowledged_at is not None
    assert db_session.get(PPEIssue, replacement.json()["id"]) is not None


def test_reminders_low_stock_and_notifications_are_deduplicated(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(client, quantity=1)
    _issue(
        client,
        item["id"],
        location["id"],
        employee.id,
        expected_replacement_date=(TODAY + timedelta(days=7)).isoformat(),
        expiry_date=(TODAY + timedelta(days=30)).isoformat(),
    )
    first = client.post("/api/v1/ppe/reminders/run")
    assert first.status_code == 200, first.text
    assert first.json()["replacement"] >= 1
    assert first.json()["expiry"] >= 1
    assert first.json()["low_stock"] >= 1
    count = len(db_session.scalars(select(Notification).where(Notification.notification_type.in_([NotificationType.ppe_replacement_due, NotificationType.ppe_expiring, NotificationType.ppe_low_stock]))).all())
    second = client.post("/api/v1/ppe/reminders/run")
    assert second.status_code == 200
    assert second.json() == {"replacement": 0, "inspection": 0, "expiry": 0, "low_stock": 0}
    assert len(db_session.scalars(select(Notification).where(Notification.notification_type.in_([NotificationType.ppe_replacement_due, NotificationType.ppe_expiring, NotificationType.ppe_low_stock]))).all()) == count


def test_ppe_dashboard_exports_and_kpi_costs_do_not_fabricate(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(client, quantity=2)
    client.post("/api/v1/ppe/requirements", json={"item_id": item["id"], "role_name": "employee", "requirement_level": "mandatory"})
    _issue(client, item["id"], location["id"], employee.id)
    dashboard_response = client.get("/api/v1/ppe/dashboard")
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard_payload = dashboard_response.json()
    assert dashboard_payload["employees_requiring_ppe"] == 1
    assert dashboard_payload["fully_compliant_employees"] == 1
    assert Decimal(dashboard_payload["issue_cost"]) == Decimal("25.50")
    for report in ("inventory", "issues", "replacement-schedule", "inspection-schedule", "compliance", "low-stock", "movements"):
        exported = client.get(f"/api/v1/ppe/exports/{report}")
        assert exported.status_code == 200, (report, exported.text)
        assert exported.headers["content-type"].startswith("text/csv")

    ensure_platform_kpi_catalogue(db_session)
    period = ReportingPeriod(name="April PPE", period_type=ReportingPeriodType.monthly, start_date=date(2026, 4, 1), end_date=date(2026, 4, 30), prepared_by_user_id=1)
    db_session.add(period)
    db_session.commit()
    definition = db_session.scalar(select(KPIDefinition).where(KPIDefinition.key == "ppe_issue_cost"))
    metric = calculate_kpi(CalculationContext(db_session, period), definition)
    assert metric.value == pytest.approx(25.5)
    issue = db_session.scalar(select(PPEIssue).where(PPEIssue.recipient_user_id == employee.id))
    issue.unit_cost_snapshot = None
    db_session.commit()
    unavailable = calculate_kpi(CalculationContext(db_session, period), definition)
    assert unavailable.value is None
    assert "unit cost" in unavailable.insufficient_reason


def test_ppe_rbac_site_scope_feature_entitlement_and_tenant_isolation(client, db_session, create_user_for_role, act_as):
    employee = create_user_for_role("employee", assigned_site_id=1)
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    second_site = Site(name="Second PPE Site", code="PPE-SECOND", created_by_id=1)
    db_session.add(second_site)
    db_session.commit()
    second_site_employee = create_user_for_role("employee", assigned_site_id=second_site.id)
    _, item, location, _ = _basic_stock(client, quantity=2)
    _issue(client, item["id"], location["id"], employee.id)
    other_site_issue = _issue(client, item["id"], location["id"], second_site_employee.id)
    act_as(employee)
    assert client.get("/api/v1/ppe/catalogue").status_code == 200
    assert client.get("/api/v1/ppe/dashboard").status_code == 403
    assert client.get(f"/api/v1/ppe/employees/{employee.id}").status_code == 200
    assert client.post("/api/v1/ppe/inventory/receive", json={"item_id": item["id"], "location_id": location["id"], "quantity": 1}).status_code == 403
    act_as(supervisor)
    assert client.get(f"/api/v1/ppe/employees/{employee.id}").status_code == 200
    assert client.get(f"/api/v1/ppe/issues/{other_site_issue['id']}").status_code == 403
    assert other_site_issue["id"] not in {row["id"] for row in client.get("/api/v1/ppe/issues").json()["items"]}

    act_as(1)
    feature = db_session.scalar(select(OrganisationFeature).where(OrganisationFeature.key == "ppe"))
    feature.is_enabled = False
    db_session.commit()
    assert client.get("/api/v1/ppe/catalogue").status_code == 403
    feature.is_enabled = True
    db_session.commit()

    tenant_b = create_organisation_record(db_session, OrganisationCreate(name="PPE Tenant B", code="PPE-B", slug="ppe-b"))
    set_tenant_context(db_session, tenant_b.id)
    admin_role = db_session.scalar(select(Role).where(Role.name == "admin"))
    tenant_admin = User(email="ppe-admin-b@example.com", full_name="PPE Admin B", hashed_password="unused", roles=[admin_role])
    db_session.add(tenant_admin)
    db_session.flush()
    tenant_site = Site(name="Tenant B PPE Site", code="PPE-B", created_by_id=tenant_admin.id)
    db_session.add(tenant_site)
    db_session.commit()
    act_as(tenant_admin)
    other_category = _create_category(client, "Tenant B Secret Category")
    other_item = _create_item(client, other_category["id"], name="Tenant B Secret PPE", code="SECRET-PPE")
    act_as(1)
    set_tenant_context(db_session, 1, platform_admin=True)
    assert client.get(f"/api/v1/ppe/catalogue/{other_item['id']}").status_code == 404
    assert "Tenant B Secret PPE" not in client.get("/api/v1/ppe/catalogue").text


def test_critical_inspection_can_link_unified_action_and_preserve_source(client, db_session, create_user_for_role):
    employee = create_user_for_role("employee", assigned_site_id=1)
    _, item, location, _ = _basic_stock(
        client,
        quantity=1,
        item_overrides={"inspection_required": True, "is_critical": True},
    )
    issue = _issue(client, item["id"], location["id"], employee.id)
    response = client.post(
        "/api/v1/ppe/inspections",
        json={"issue_id": issue["id"], "condition": "damaged", "passed": False, "defects": "Load-bearing webbing cut", "create_unified_action": True},
    )
    assert response.status_code == 201, response.text
    action = db_session.get(CorrectiveAction, response.json()["unified_action_id"])
    assert action is not None
    assert action.source_type.value == "ppe"
    assert action.source_id == response.json()["id"]
    assert action.source_metadata["ppe_entity_type"] == "PPEInspection"
