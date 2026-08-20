from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contractor import ContractorRecord
from app.models.organisation import OrganisationFeature
from app.models.training import (
    CompetencyStatusEvent,
    TrainingAssignment,
    TrainingDeficiencyLink,
    TrainingReminderDelivery,
)
from app.models.user import User
from app.services.training_competency_service import generate_reminders


def _course(**overrides):
    payload = {
        "name": "Working at Height Theory",
        "code": "WAH-THEORY",
        "description": "Theory and practical preparation.",
        "category": "safety training",
        "training_type": "safety_training",
        "active": True,
        "provider_required": False,
        "assessment_required": True,
        "passing_score": 80,
        "certificate_required": True,
        "default_validity_period_days": 365,
        "refresher_required": True,
        "default_refresher_interval_days": 365,
        "practical_component_required": True,
        "medical_clearance_required": False,
        "medical_programme_codes": [],
        "ppe_prerequisite_required": False,
        "ppe_item_ids": [],
        "reminder_windows": [90, 60, 30, 7],
    }
    payload.update(overrides)
    return payload


def _competency(**overrides):
    payload = {
        "name": "Work at Height",
        "code": "WORK-AT-HEIGHT",
        "description": "Demonstrated capability for height work.",
        "category": "high risk work",
        "active": True,
        "evidence_requirements": ["practical assessment"],
        "assessment_rules": {"required": True, "certificate_required": True},
        "validity_period_days": 365,
        "renewal_rules": {"refresher_required": True},
        "medical_prerequisite": False,
        "medical_programme_codes": [],
        "ppe_prerequisite": False,
        "ppe_item_ids": [],
        "supervisor_approval_required": True,
        "minimum_experience_days": None,
    }
    payload.update(overrides)
    return payload


def _create_catalogue(client: TestClient):
    course = client.post("/api/v1/training/courses", json=_course())
    competency = client.post("/api/v1/training/competencies", json=_competency())
    assert course.status_code == 201, course.text
    assert competency.status_code == 201, competency.text
    mapping = client.post("/api/v1/training/course-competency-mappings", json={
        "course_id": course.json()["id"],
        "competency_id": competency.json()["id"],
        "required": True,
        "completion_sufficient": False,
        "sequence": 0,
    })
    assert mapping.status_code == 201, mapping.text
    return course.json(), competency.json()


def test_catalogues_mapping_requirements_and_worker_profile(client: TestClient) -> None:
    course, competency = _create_catalogue(client)
    requirement = client.post("/api/v1/training/requirements", json={
        "name": "Height worker competency",
        "course_id": course["id"],
        "competency_id": competency["id"],
        "authorization_type": "Work at Height Authorization",
        "level": "mandatory",
        "active": True,
        "job_title": None,
        "site_id": 1,
        "medical_programme_codes": [],
        "mandatory_certificate": True,
        "assessment_required": True,
        "is_critical": True,
    })
    assert requirement.status_code == 201, requirement.text

    profile = client.get("/api/v1/training/workers/1/profile")
    assert profile.status_code == 200, profile.text
    assert profile.json()["required_courses"][0]["status"] == "missing"
    assert profile.json()["competency_gaps"][0]["competency_id"] == competency["id"]

    matrix = client.get("/api/v1/training/competency-matrix?site_id=1")
    assert matrix.status_code == 200
    assert matrix.json()["rows"][0]["cells"][0]["state"] == "missing"


def test_assignment_session_attendance_assessment_certificate_award_and_authorization(client: TestClient) -> None:
    course, competency = _create_catalogue(client)
    requirement = client.post("/api/v1/training/requirements", json={
        "name": "Height authorization prerequisites",
        "course_id": course["id"],
        "competency_id": competency["id"],
        "authorization_type": "Work at Height Authorization",
        "level": "mandatory",
        "active": True,
        "site_id": 1,
        "medical_programme_codes": [],
        "mandatory_certificate": True,
        "assessment_required": True,
        "is_critical": True,
    }).json()
    assignment_response = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"], "assigned_user_id": 1, "site_id": 1,
        "due_date": "2026-05-10", "priority": "high", "mandatory": True,
        "reason": "Role requirement", "source": "requirement", "requirement_id": requirement["id"],
    })
    assert assignment_response.status_code == 201, assignment_response.text
    assignment = assignment_response.json()
    assert assignment["training_record_id"] is not None

    session_response = client.post("/api/v1/training/sessions", json={
        "course_id": course["id"], "starts_at": "2026-04-25T08:00:00Z",
        "ends_at": "2026-04-25T12:00:00Z", "duration_minutes": 240,
        "trainer_user_id": 1, "location": "Training room", "capacity": 10,
        "site_id": 1, "delivery_mode": "blended", "status": "scheduled",
    })
    assert session_response.status_code == 201, session_response.text
    session = session_response.json()
    attendance = client.post(f"/api/v1/training/sessions/{session['id']}/attendance", json={
        "worker_user_id": 1, "assignment_id": assignment["id"], "status": "attended", "minutes_attended": 240,
    })
    assert attendance.status_code == 200, attendance.text
    assert attendance.json()["attendance_recorded_by_user_id"] == 1

    bad_score = client.post("/api/v1/training/assessments", json={
        "assignment_id": assignment["id"], "session_id": session["id"],
        "course_id": course["id"], "competency_id": competency["id"], "worker_user_id": 1,
        "assessment_type": "practical", "assessment_date": "2026-04-25",
        "score": 70, "passed": True, "competency_demonstrated": True,
    })
    assert bad_score.status_code == 422

    assessment = client.post("/api/v1/training/assessments", json={
        "assignment_id": assignment["id"], "session_id": session["id"],
        "course_id": course["id"], "competency_id": competency["id"], "worker_user_id": 1,
        "assessment_type": "practical", "assessment_date": "2026-04-25",
        "score": 90, "passed": True, "competency_demonstrated": True,
        "evidence": [{"type": "checklist", "reference": "ATT-1"}],
    })
    assert assessment.status_code == 201, assessment.text

    certificate_response = client.post("/api/v1/training/certificates", json={
        "worker_user_id": 1, "course_id": course["id"], "competency_id": competency["id"],
        "training_record_id": assignment["training_record_id"], "certificate_number": "WAH-0001",
        "issue_date": "2026-04-25", "expiry_date": "2027-04-25", "provider": "SafeWork",
        "certificate_file_reference": "attachment://pending",
    })
    assert certificate_response.status_code == 201, certificate_response.text
    certificate = certificate_response.json()
    verified = client.post(f"/api/v1/training/certificates/{certificate['id']}/verify", json={
        "verification_status": "verified", "verification_date": "2026-04-25",
    })
    assert verified.status_code == 200

    award_response = client.post("/api/v1/training/competency-awards", json={
        "competency_id": competency["id"], "worker_user_id": 1,
        "achieved_at": "2026-04-25T12:00:00Z", "evidence": [{"assessment_id": assessment.json()["id"]}],
        "status": "competent",
    })
    assert award_response.status_code == 201, award_response.text
    award = award_response.json()
    assert award["requirements_snapshot"]["satisfied"] is True

    before_auth = client.post("/api/v1/training/eligibility", json={
        "worker_user_id": 1, "authorization_type": "Work at Height Authorization", "site_id": 1,
    })
    assert before_auth.status_code == 200
    assert before_auth.json()["status"] == "not_eligible"
    assert any("authorization" in item["code"] for item in before_auth.json()["reasons"])

    authorization = client.post("/api/v1/training/authorizations", json={
        "authorization_type": "Work at Height Authorization", "worker_user_id": 1,
        "competency_id": competency["id"], "site_id": 1, "task_activity": "Work at Height",
        "valid_from": "2026-04-23", "valid_until": "2027-04-25", "status": "active",
    })
    assert authorization.status_code == 201, authorization.text
    assert authorization.json()["prerequisites_snapshot"]["eligible"] is True

    eligible = client.post("/api/v1/training/eligibility", json={
        "worker_user_id": 1, "authorization_type": "Work at Height Authorization", "site_id": 1,
    })
    assert eligible.status_code == 200
    assert eligible.json()["status"] == "eligible"

    suspended = client.post(f"/api/v1/training/competency-awards/{award['id']}/status", json={
        "status": "suspended", "reason": "Failed reassessment", "review_date": "2026-05-20",
    })
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    history = client.get(f"/api/v1/training/competency-awards/{award['id']}/history")
    assert history.status_code == 200
    assert history.json()[0]["reason"] == "Failed reassessment"


def test_bulk_assignment_requests_and_duplicate_safety(client: TestClient, create_user_for_role) -> None:
    employee = create_user_for_role("employee", assigned_site_id=1)
    course = client.post("/api/v1/training/courses", json=_course(code="INDUCT", name="Contractor Induction", assessment_required=False, certificate_required=False)).json()
    bulk = client.post("/api/v1/training/assignments/bulk", json={
        "course_id": course["id"], "user_ids": [1, employee.id], "site_id": 1,
        "due_date": "2026-05-01", "priority": "normal", "mandatory": True,
    })
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["created_count"] == 2
    duplicate = client.post("/api/v1/training/assignments/bulk", json={
        "course_id": course["id"], "user_ids": [1, employee.id], "site_id": 1,
        "due_date": "2026-05-01", "priority": "normal", "mandatory": True,
    })
    assert duplicate.status_code == 200
    assert duplicate.json()["created_count"] == 0
    assert duplicate.json()["skipped_count"] == 2

    request = client.post("/api/v1/training/requests", json={
        "course_id": course["id"], "requested_for_user_id": 1,
        "reason": "Maintain induction", "urgency": "high",
    })
    assert request.status_code == 201, request.text
    decision = client.post(f"/api/v1/training/requests/{request.json()['id']}/decision", json={
        "status": "approved", "decision_notes": "Approved", "due_date": "2026-06-01",
    })
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "assigned"
    assert decision.json()["resulting_assignment_id"] is not None


def test_contractor_worker_competency_and_privacy(client: TestClient, db_session: Session) -> None:
    contractor = ContractorRecord(
        contractor_name="HeightSafe Ltd", contact_person="Contact", contact_email="safe@example.com",
        contact_phone="123", site_id=1, work_scope="High-risk maintenance",
    )
    db_session.add(contractor)
    db_session.commit()
    worker_response = client.post("/api/v1/training/contractor-workers", json={
        "contractor_id": contractor.id, "external_reference": "EXT-001", "full_name": "External Worker",
        "job_title": "Height Worker", "category": "specialist", "site_id": 1,
        "medical_clearance_status": "fit", "medical_clearance_expiry": "2027-01-01", "ppe_compliant": True,
    })
    assert worker_response.status_code == 201, worker_response.text
    contractor_worker = worker_response.json()
    course = client.post("/api/v1/training/courses", json=_course(code="EXT-IND", name="External Induction", assessment_required=False, certificate_required=False)).json()
    assignment = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"], "contractor_worker_id": contractor_worker["id"],
        "site_id": 1, "due_date": "2026-05-01", "mandatory": True,
    })
    assert assignment.status_code == 201, assignment.text
    assert assignment.json()["training_record_id"] is None

    eligibility = client.post("/api/v1/training/eligibility", json={
        "contractor_worker_id": contractor_worker["id"], "task_activity": "General maintenance", "site_id": 1,
    })
    assert eligibility.status_code == 200
    assert eligibility.json()["privacy"] == {"medical_detail_exposed": False}
    assert "diagnosis" not in eligibility.text.casefold()


def test_reminder_deduplication_exports_dashboard_and_exceptions(client: TestClient, db_session: Session) -> None:
    course = client.post("/api/v1/training/courses", json=_course(code="DUE", name="Due Course", assessment_required=False, certificate_required=False)).json()
    assignment = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"], "assigned_user_id": 1, "site_id": 1,
        "due_date": (date.today() + timedelta(days=7)).isoformat(), "mandatory": True,
    })
    assert assignment.status_code == 201
    first = generate_reminders(db_session)
    second = generate_reminders(db_session)
    assert sum(first.values()) >= 1
    assert sum(second.values()) == 0
    assert db_session.scalar(select(TrainingReminderDelivery)) is not None

    dashboard = client.get("/api/v1/training/dashboard?site_id=1")
    assert dashboard.status_code == 200
    assert dashboard.json()["assigned_training"] >= 1
    forward = client.get("/api/v1/training/forward-view?site_id=1&days=90")
    assert forward.status_code == 200
    exceptions = client.get("/api/v1/training/management-exceptions?site_id=1")
    assert exceptions.status_code == 200
    export = client.get("/api/v1/training/exports/training-register?site_id=1")
    assert export.status_code == 200
    assert "assigned_to_user_id" in export.text


def test_feature_entitlement_and_tenant_guessed_ids_fail_closed(client: TestClient, db_session: Session) -> None:
    course = client.post("/api/v1/training/courses", json=_course()).json()
    feature = db_session.scalar(select(OrganisationFeature).where(OrganisationFeature.key == "training"))
    feature.is_enabled = False
    db_session.add(feature)
    db_session.commit()
    disabled = client.get("/api/v1/training/courses")
    assert disabled.status_code == 403

    feature.is_enabled = True
    db_session.add(feature)
    db_session.commit()
    guessed = client.patch("/api/v1/training/courses/999999", json={"name": "Guessed"})
    assert guessed.status_code == 404
    assert course["organisation_id"] == 1


def test_incident_and_unified_action_deficiency_links(client: TestClient, db_session: Session) -> None:
    course = client.post("/api/v1/training/courses", json=_course(code="ACTION", name="Action Course", assessment_required=False, certificate_required=False)).json()
    assignment = client.post("/api/v1/training/assignments", json={
        "course_id": course["id"], "assigned_user_id": 1, "site_id": 1,
        "due_date": "2026-04-20", "mandatory": True,
    }).json()
    source_id = assignment["training_record_id"]
    action_request = client.post("/api/v1/training/actions", json={
        "issue_type": "overdue_mandatory_training", "source_id": source_id,
        "worker_user_id": 1, "owner_user_id": 1, "due_date": "2026-05-15",
    })
    assert action_request.status_code == 200, action_request.text
    action_id = action_request.json()["id"]
    duplicate = client.post("/api/v1/training/actions", json={
        "issue_type": "overdue_mandatory_training", "source_id": source_id,
        "worker_user_id": 1, "owner_user_id": 1, "due_date": "2026-05-15",
    })
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == action_id
    assert db_session.scalar(select(TrainingDeficiencyLink).where(TrainingDeficiencyLink.corrective_action_id == action_id)) is not None
