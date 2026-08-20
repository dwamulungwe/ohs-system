from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.medical_surveillance import (
    FitnessOutcome,
    MedicalClearanceStatus,
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
    SurveillanceComplianceStatus,
    SurveillanceProgramme,
)
from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.ppe import (
    PPECategory,
    PPECondition,
    PPEIssue,
    PPEIssueStatus,
    PPEItem,
    PPERecipientType,
    PPEStockLocation,
)
from app.models.reporting import (
    KPIDefinition,
    KPIDirection,
    ReportingPeriod,
    ReportingPeriodStatus,
    ReportingPeriodType,
)
from app.models.site import Site
from app.models.training import (
    AssessmentType,
    AttendanceStatus,
    AuthorizationStatus,
    Competency,
    CompetencyAward,
    CompetencyAwardStatus,
    DeliveryMode,
    TrainingAssessment,
    TrainingAssignment,
    TrainingAttendance,
    TrainingCertificate,
    TrainingCourse,
    TrainingRequest,
    TrainingRequirement,
    TrainingSession,
    TrainingType,
    VerificationStatus,
    WorkAuthorization,
)
from app.models.user import User
from app.services.reporting_calculations import CalculationContext, calculate_kpi
from app.services.training_competency_service import create_refresher_assignments
from app.services.tenancy import unscoped_session


def _simple_course(code: str, name: str, **overrides) -> dict:
    payload = {
        "name": name,
        "code": code,
        "category": "safety training",
        "training_type": "safety_training",
        "assessment_required": False,
        "certificate_required": False,
        "refresher_required": False,
        "medical_clearance_required": False,
        "ppe_prerequisite_required": False,
    }
    payload.update(overrides)
    return payload


def _complete_course(client: TestClient, course_id: int, worker_id: int = 1, *, site_id: int = 1) -> dict:
    assignment = client.post("/api/v1/training/assignments", json={
        "course_id": course_id,
        "assigned_user_id": worker_id,
        "site_id": site_id,
        "due_date": "2026-05-20",
        "mandatory": True,
    })
    assert assignment.status_code == 201, assignment.text
    completed = client.patch(
        f"/api/v1/training/assignments/{assignment.json()['id']}",
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


def _permit_payload(number: str, worker_id: int) -> dict:
    return {
        "permit_number": number,
        "permit_type": "confined_space",
        "title": "Confined space vessel entry",
        "description": "Internal vessel inspection.",
        "site_id": 1,
        "area_location": "Vessel 1",
        "requested_by_user_id": 1,
        "issued_by_user_id": 1,
        "approved_by_user_id": 1,
        "start_datetime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "end_datetime": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
        "status": "approved",
        "required_worker_user_ids": [worker_id],
        "eligibility_enforcement_enabled": True,
        "precautions_required": [],
        "gas_test_required": False,
    }


def test_medical_and_ppe_prerequisites_are_live_explainable_and_private(
    client: TestClient,
    db_session: Session,
) -> None:
    category = PPECategory(name="Respiratory", code="RESP", description="Respiratory PPE")
    db_session.add(category)
    db_session.flush()
    item = PPEItem(
        category_id=category.id,
        name="Full-face respirator",
        code="RESP-FF",
        is_reusable=True,
        inspection_required=True,
        expiry_tracking=True,
    )
    location = PPEStockLocation(name="Main store", code="MAIN", site_id=1)
    db_session.add_all([item, location])
    db_session.commit()

    course_response = client.post("/api/v1/training/courses", json=_simple_course(
        "CS-ENTRY",
        "Confined Space Entry",
        medical_clearance_required=True,
        medical_programme_codes=["CONFINED_SPACE"],
        ppe_prerequisite_required=True,
        ppe_item_ids=[item.id],
    ))
    assert course_response.status_code == 201, course_response.text
    course = course_response.json()
    _complete_course(client, course["id"])
    requirement = client.post("/api/v1/training/requirements", json={
        "name": "Confined space entry prerequisites",
        "course_id": course["id"],
        "task_activity": "Confined Space Entry",
        "site_id": 1,
        "level": "mandatory",
    })
    assert requirement.status_code == 201, requirement.text

    missing = client.post("/api/v1/training/eligibility", json={
        "worker_user_id": 1,
        "task_activity": "Confined Space Entry",
        "site_id": 1,
    })
    assert missing.status_code == 200
    assert missing.json()["status"] == "not_eligible"
    assert {reason["code"] for reason in missing.json()["reasons"]} >= {
        "medical_clearance_unknown",
        "ppe_invalid",
    }

    programme = SurveillanceProgramme(
        name="Confined Space Fitness",
        code="CONFINED_SPACE",
        active=True,
        validity_period_days=365,
    )
    db_session.add(programme)
    db_session.flush()
    db_session.add(MedicalSurveillanceRecord(
        employee_user_id=1,
        site_id=1,
        programme_id=programme.id,
        surveillance_type="Confined Space Fitness",
        due_date=date(2027, 4, 23),
        completed_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        status=MedicalSurveillanceStatus.completed,
        compliance_status=SurveillanceComplianceStatus.compliant,
        fitness_outcome=FitnessOutcome.fit,
        results_summary="Private diagnosis must never leave Occupational Health",
        medical_clearance_status=MedicalClearanceStatus.cleared,
        expiry_date=date(2027, 4, 23),
        created_by_user_id=1,
    ))
    db_session.add(PPEIssue(
        recipient_type=PPERecipientType.employee,
        recipient_user_id=1,
        recipient_name_snapshot="Admin User",
        site_id_snapshot=1,
        item_id=item.id,
        stock_location_id=location.id,
        quantity=1,
        returned_quantity=0,
        issue_date=date(2026, 4, 1),
        expiry_date=date(2027, 4, 1),
        next_inspection_date=date(2026, 12, 1),
        condition_at_issue=PPECondition.serviceable,
        status=PPEIssueStatus.issued,
        issued_by_user_id=1,
        item_name_snapshot=item.name,
        item_code_snapshot=item.code,
        stock_location_name_snapshot=location.name,
    ))
    db_session.commit()

    eligible = client.post("/api/v1/training/eligibility", json={
        "worker_user_id": 1,
        "task_activity": "Confined Space Entry",
        "site_id": 1,
    })
    assert eligible.status_code == 200
    assert eligible.json()["status"] == "eligible"
    assert eligible.json()["privacy"] == {"medical_detail_exposed": False}
    assert "diagnosis" not in eligible.text.casefold()


def test_jsa_and_opt_in_permit_hooks_validate_current_training(
    client: TestClient,
    create_user_for_role,
) -> None:
    worker = create_user_for_role("employee", assigned_site_id=1)
    course = client.post(
        "/api/v1/training/courses",
        json=_simple_course("CS-HOOK", "Confined Space Hook Training"),
    ).json()
    _complete_course(client, course["id"])
    jsa_response = client.post("/api/v1/jsas", json={
        "title": "Confined space inspection",
        "site_id": 1,
        "department_or_area": "Processing",
        "job_steps": ["Enter vessel"],
        "hazards": ["Atmosphere"],
        "controls": ["Gas testing"],
        "ppe_required": ["Respirator"],
        "required_course_ids": [course["id"]],
        "eligibility_enforcement_enabled": True,
        "residual_risk_level": "high",
        "status": "approved",
    })
    assert jsa_response.status_code == 201, jsa_response.text
    jsa_check = client.post("/api/v1/training/eligibility", json={
        "worker_user_id": 1,
        "jsa_id": jsa_response.json()["id"],
        "site_id": 1,
    })
    assert jsa_check.status_code == 200
    assert jsa_check.json()["status"] == "eligible"
    bad_jsa_ref = client.patch(
        f"/api/v1/jsas/{jsa_response.json()['id']}",
        json={"required_course_ids": [999999]},
    )
    assert bad_jsa_ref.status_code == 404

    requirement = client.post("/api/v1/training/requirements", json={
        "name": "Confined space permit training",
        "course_id": course["id"],
        "permit_type": "confined_space",
        "site_id": 1,
        "level": "mandatory",
    })
    assert requirement.status_code == 201
    blocked = client.post("/api/v1/permits", json=_permit_payload("PTW-2D-001", worker.id))
    assert blocked.status_code == 422, blocked.text
    assert "not eligible" in blocked.json()["detail"].casefold()

    _complete_course(client, course["id"], worker.id)
    allowed = client.post("/api/v1/permits", json=_permit_payload("PTW-2D-002", worker.id))
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["eligibility_validation"]["eligible"] is True


def test_refresher_automation_uses_certificate_and_competency_expiry_without_duplicates(
    client: TestClient,
    db_session: Session,
) -> None:
    course = client.post("/api/v1/training/courses", json=_simple_course(
        "REF-CERT",
        "Certificate Refresher",
        refresher_required=True,
        default_refresher_interval_days=365,
    )).json()
    certificate = client.post("/api/v1/training/certificates", json={
        "worker_user_id": 1,
        "course_id": course["id"],
        "certificate_number": "REF-001",
        "issue_date": "2025-05-01",
        "expiry_date": "2026-05-01",
    })
    assert certificate.status_code == 201, certificate.text
    assert create_refresher_assignments(db_session) == 1
    assert create_refresher_assignments(db_session) == 0
    refresher = db_session.scalar(select(TrainingAssignment).where(TrainingAssignment.source == "refresher"))
    assert refresher is not None
    assert refresher.due_date == date(2026, 5, 1)
    assert "certificate:" in refresher.reason

    settings = db_session.scalar(select(OrganisationSettings))
    settings.training_configuration = {**settings.training_configuration, "refresher_automation": True}
    db_session.add(settings)
    db_session.commit()
    reminder_run = client.post("/api/v1/training/reminders/run", json={})
    assert reminder_run.status_code == 200
    assert reminder_run.json().get("refresher_assignments", 0) == 0


def test_supervisor_site_scope_applies_to_lists_mutations_and_forward_view(
    client: TestClient,
    db_session: Session,
    create_user_for_role,
    act_as,
) -> None:
    second_site = Site(
        name="Remote Plant",
        code="REMOTE",
        address="Remote Area",
        created_by_id=1,
    )
    db_session.add(second_site)
    db_session.commit()
    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    remote_worker = create_user_for_role("employee", assigned_site_id=second_site.id)
    course = client.post(
        "/api/v1/training/courses",
        json=_simple_course("SITE-SCOPE", "Scoped Training", default_validity_period_days=365),
    ).json()
    remote_assignment = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"],
        "assigned_user_id": remote_worker.id,
        "due_date": "2026-04-20",
        "mandatory": True,
    })
    assert remote_assignment.status_code == 201
    client.post("/api/v1/training/certificates", json={
        "worker_user_id": remote_worker.id,
        "course_id": course["id"],
        "certificate_number": "REMOTE-001",
        "issue_date": "2026-04-01",
        "expiry_date": "2026-05-01",
    })

    act_as(supervisor)
    assignments = client.get("/api/v1/training/assignments")
    certificates = client.get("/api/v1/training/certificates")
    forward = client.get("/api/v1/training/forward-view?days=90")
    forbidden_patch = client.patch(
        f"/api/v1/training/assignments/{remote_assignment.json()['id']}",
        json={"priority": "critical"},
    )
    forbidden_create = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"],
        "assigned_user_id": remote_worker.id,
        "due_date": "2026-05-01",
    })
    assert assignments.status_code == 200 and assignments.json() == []
    assert certificates.status_code == 200 and certificates.json() == []
    assert forward.status_code == 200 and forward.json() == []
    assert forbidden_patch.status_code == 403
    assert forbidden_create.status_code == 403


def test_phase2d_kpis_use_applicable_workers_and_open_assignments(
    client: TestClient,
    db_session: Session,
) -> None:
    course = client.post(
        "/api/v1/training/courses",
        json=_simple_course("KPI-COURSE", "KPI Course"),
    ).json()
    requirement = client.post("/api/v1/training/requirements", json={
        "name": "KPI required course",
        "course_id": course["id"],
        "site_id": 1,
        "level": "mandatory",
    })
    assert requirement.status_code == 201
    client.post("/api/v1/training/assignments", json={
        "course_id": course["id"],
        "assigned_user_id": 1,
        "site_id": 1,
        "due_date": "2026-05-01",
    })
    period = ReportingPeriod(
        name="April 2026",
        period_type=ReportingPeriodType.monthly,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        status=ReportingPeriodStatus.draft,
        report_version=1,
    )
    db_session.add(period)
    db_session.commit()

    def definition(key: str) -> KPIDefinition:
        return KPIDefinition(
            key=key,
            name=key,
            description=key,
            category="Training",
            unit="count",
            calculation_method=key,
            direction=KPIDirection.informational,
            effective_from=date(2026, 1, 1),
        )

    context = CalculationContext(db_session, period, site_id=1)
    workers = calculate_kpi(context, definition("workers_requiring_training"))
    assignments = calculate_kpi(context, definition("training_assignments_open"))
    assert workers.value == 1.0
    assert assignments.value == 1.0


def test_all_phase2d_guessed_ids_and_aggregate_views_fail_closed(
    client: TestClient,
    db_session: Session,
) -> None:
    with unscoped_session(db_session, allow_writes=True):
        organisation = Organisation(
            id=2,
            name="Other Training Tenant",
            code="TRAIN-OTHER",
            slug="other-training-tenant",
            timezone="UTC",
        )
        db_session.add(organisation)
        db_session.flush()
        db_session.add(OrganisationSettings(organisation_id=2))
        db_session.add(OrganisationFeature(organisation_id=2, key="training", is_enabled=True))
        site = Site(
            id=99,
            organisation_id=2,
            name="Other Tenant Site",
            code="OTHER-TRAIN",
        )
        worker = User(
            id=99,
            organisation_id=2,
            email="other-training-worker@example.com",
            full_name="Other Tenant Training Worker",
            hashed_password="not-used",
            assigned_site_id=99,
        )
        db_session.add_all([site, worker])
        db_session.flush()
        course = TrainingCourse(
            organisation_id=2,
            name="Other Tenant Secret Course",
            code="OTHER-SECRET",
            category="secret",
            training_type=TrainingType.safety_training,
        )
        competency = Competency(
            organisation_id=2,
            name="Other Tenant Secret Competency",
            code="OTHER-COMP",
            category="secret",
        )
        db_session.add_all([course, competency])
        db_session.flush()
        requirement = TrainingRequirement(
            organisation_id=2,
            name="Other Tenant Requirement",
            course_id=course.id,
            site_id=site.id,
        )
        assignment = TrainingAssignment(
            organisation_id=2,
            course_id=course.id,
            assigned_user_id=worker.id,
            assigned_by_user_id=worker.id,
            site_id=site.id,
        )
        session = TrainingSession(
            organisation_id=2,
            course_id=course.id,
            starts_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            site_id=site.id,
            delivery_mode=DeliveryMode.classroom,
        )
        db_session.add_all([requirement, assignment, session])
        db_session.flush()
        attendance = TrainingAttendance(
            organisation_id=2,
            session_id=session.id,
            worker_user_id=worker.id,
            assignment_id=assignment.id,
            status=AttendanceStatus.attended,
        )
        assessment = TrainingAssessment(
            organisation_id=2,
            assignment_id=assignment.id,
            session_id=session.id,
            course_id=course.id,
            competency_id=competency.id,
            worker_user_id=worker.id,
            assessment_type=AssessmentType.theory,
            assessment_date=date(2026, 5, 1),
            passed=True,
        )
        certificate = TrainingCertificate(
            organisation_id=2,
            worker_user_id=worker.id,
            course_id=course.id,
            certificate_number="OTHER-TENANT-CERT",
            issue_date=date(2026, 5, 1),
            verification_status=VerificationStatus.pending,
        )
        award = CompetencyAward(
            organisation_id=2,
            competency_id=competency.id,
            worker_user_id=worker.id,
            achieved_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            status=CompetencyAwardStatus.competent,
        )
        authorization = WorkAuthorization(
            organisation_id=2,
            authorization_type="Other Tenant Authorization",
            worker_user_id=worker.id,
            site_id=site.id,
            valid_from=date(2026, 5, 1),
            status=AuthorizationStatus.active,
        )
        request = TrainingRequest(
            organisation_id=2,
            course_id=course.id,
            requester_user_id=worker.id,
            requested_for_user_id=worker.id,
            reason="Other tenant request",
        )
        db_session.add_all([attendance, assessment, certificate, award, authorization, request])
        db_session.commit()
        ids = {
            "course": course.id,
            "competency": competency.id,
            "requirement": requirement.id,
            "assignment": assignment.id,
            "session": session.id,
            "assessment": assessment.id,
            "certificate": certificate.id,
            "award": award.id,
            "authorization": authorization.id,
            "request": request.id,
            "worker": worker.id,
        }

    responses = [
        client.patch(f"/api/v1/training/courses/{ids['course']}", json={"name": "Guessed"}),
        client.patch(f"/api/v1/training/competencies/{ids['competency']}", json={"name": "Guessed"}),
        client.patch(f"/api/v1/training/requirements/{ids['requirement']}", json={"name": "Guessed"}),
        client.patch(f"/api/v1/training/assignments/{ids['assignment']}", json={"priority": "critical"}),
        client.patch(f"/api/v1/training/sessions/{ids['session']}", json={"location": "Guessed"}),
        client.get(f"/api/v1/training/sessions/{ids['session']}/attendance"),
        client.get("/api/v1/training/assessments", params={"worker_user_id": ids["worker"]}),
        client.post(f"/api/v1/training/certificates/{ids['certificate']}/verify", json={"verification_status": "verified"}),
        client.get(f"/api/v1/training/competency-awards/{ids['award']}/history"),
        client.patch(f"/api/v1/training/authorizations/{ids['authorization']}", json={"status": "suspended", "reason": "Guessed"}),
        client.post(f"/api/v1/training/requests/{ids['request']}/decision", json={"status": "rejected"}),
    ]
    assert all(response.status_code == 404 for response in responses), [
        (response.status_code, response.text) for response in responses
    ]
    courses = client.get("/api/v1/training/courses")
    matrix = client.get("/api/v1/training/competency-matrix")
    export = client.get("/api/v1/training/exports/certificate-register")
    assert "Other Tenant Secret Course" not in courses.text
    assert "Other Tenant Training Worker" not in matrix.text
    assert "OTHER-TENANT-CERT" not in export.text
