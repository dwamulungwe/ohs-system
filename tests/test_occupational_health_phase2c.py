from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.medical_surveillance import (
    ClinicEncounter,
    FitnessCertificate,
    FitnessOutcome,
    MedicalAppointment,
    MedicalAssessment,
    MedicalProvider,
    MedicalReminderDelivery,
    MedicalSurveillanceRecord,
    OccupationalExposureType,
    OccupationalIllnessCase,
    SurveillanceProgramme,
    SurveillanceRequirement,
    WorkerExposureAssignment,
    WorkRestriction,
    WorkRestrictionStatus,
)
from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.site import Site
from app.models.user import User
from app.services.tenancy import unscoped_session


def programmes(client):
    response = client.get("/api/v1/medical-surveillance/programmes")
    assert response.status_code == 200, response.text
    return {item["code"]: item for item in response.json()}


def create_worker(create_user_for_role, db_session, *, site_id=1, job_title="Welder"):
    worker = create_user_for_role("employee", assigned_site_id=site_id)
    worker.job_title = job_title
    db_session.add(worker); db_session.commit(); db_session.refresh(worker)
    return worker


def test_programme_catalogue_custom_programme_and_requirement_rules(client, create_user_for_role, db_session):
    catalogue = programmes(client)
    assert {"AUDIOMETRY", "SPIROMETRY", "RETURN_TO_WORK", "WORK_AT_HEIGHT"}.issubset(catalogue)
    custom = client.post("/api/v1/medical-surveillance/programmes", json={
        "name": "Lead Biological Monitoring", "code": "LEAD_BIO",
        "default_frequency_days": 180, "validity_period_days": 180,
        "reminder_windows": [90, 30, 7], "certificate_required": False,
    })
    assert custom.status_code == 201, custom.text
    requirement = client.post("/api/v1/medical-surveillance/requirements", json={
        "programme_id": catalogue["AUDIOMETRY"]["id"], "name": "Welders annual audiometry",
        "job_title": "Welder", "frequency_days": 365, "rationale": "Noise exposure",
    })
    assert requirement.status_code == 201, requirement.text
    worker = create_worker(create_user_for_role, db_session)
    profile = client.get(f"/api/v1/medical-surveillance/workers/{worker.id}/profile")
    assert profile.status_code == 200
    assert profile.json()["required_programmes"][0]["compliance_status"] == "pending_assessment"


def test_assessment_updates_assignment_and_redacts_clinical_detail(client, create_user_for_role, db_session, act_as):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["AUDIOMETRY"]
    assessment = client.post("/api/v1/medical-surveillance/assessments", json={
        "worker_user_id": worker.id, "programme_id": programme["id"],
        "assessment_type": "periodic", "assessment_date": "2026-04-23",
        "fitness_outcome": "fit_with_restrictions", "operational_restrictions": "Hearing protection required",
        "confidential_notes": "Sensitive clinician narrative", "clinical_results": {"threshold_shift": 5},
    })
    assert assessment.status_code == 201, assessment.text
    assert assessment.json()["confidential_notes"] == "Sensitive clinician narrative"
    assert assessment.json()["next_due_date"] == "2027-04-23"

    ohs_manager = create_user_for_role("ohs_manager")
    act_as(ohs_manager)
    listing = client.get("/api/v1/medical-surveillance/assessments", params={"worker_user_id": worker.id})
    assert listing.status_code == 200
    assert listing.json()[0]["fitness_outcome"] == "fit_with_restrictions"
    assert listing.json()[0]["operational_restrictions"] == "Hearing protection required"
    assert listing.json()[0]["confidential_notes"] is None
    assert listing.json()[0]["clinical_results"] == {}


def test_appointment_reschedule_preserves_history_and_missed_state(client, create_user_for_role, db_session):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["VISION"]
    appointment = client.post("/api/v1/medical-surveillance/appointments", json={
        "worker_user_id": worker.id, "programme_id": programme["id"],
        "appointment_at": "2026-05-01T08:00:00Z", "location": "Clinic A",
    })
    assert appointment.status_code == 201
    replacement = client.patch(f"/api/v1/medical-surveillance/appointments/{appointment.json()['id']}", json={
        "appointment_at": "2026-05-08T08:00:00Z", "location": "Clinic B",
    })
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["rescheduled_from_id"] == appointment.json()["id"]
    assert client.patch(f"/api/v1/medical-surveillance/appointments/{replacement.json()['id']}", json={"status": "missed"}).json()["status"] == "missed"
    records = client.get("/api/v1/medical-surveillance/appointments", params={"worker_user_id": worker.id}).json()
    assert {item["status"] for item in records} == {"rescheduled", "missed"}


def test_restriction_amendment_supersedes_without_overwrite(client, create_user_for_role, db_session):
    worker = create_worker(create_user_for_role, db_session)
    restriction = client.post("/api/v1/medical-surveillance/restrictions", json={
        "worker_user_id": worker.id, "restriction_type": "lifting",
        "description": "Light duty only", "effective_from": "2026-04-23",
        "lifting_limit_kg": 10, "review_date": "2026-05-23",
    })
    assert restriction.status_code == 201, restriction.text
    amended = client.patch(f"/api/v1/medical-surveillance/restrictions/{restriction.json()['id']}", json={
        "description": "Light duty, no repetitive lifting", "lifting_limit_kg": 5,
    })
    assert amended.status_code == 200, amended.text
    assert amended.json()["supersedes_restriction_id"] == restriction.json()["id"]
    prior = db_session.get(WorkRestriction, restriction.json()["id"])
    assert prior.status == WorkRestrictionStatus.superseded
    assert prior.description == "Light duty only"


def test_exposure_history_illness_dashboard_exports_and_reminder_deduplication(client, create_user_for_role, db_session):
    worker = create_worker(create_user_for_role, db_session)
    catalogue = programmes(client)
    exposure_type = next(item for item in client.get("/api/v1/medical-surveillance/exposure-types").json() if item["code"] == "NOISE")
    exposure = client.post("/api/v1/medical-surveillance/exposures", json={
        "worker_user_id": worker.id, "exposure_type_id": exposure_type["id"],
        "start_date": "2025-01-01", "risk_level": "high",
        "triggered_programme_ids": [catalogue["AUDIOMETRY"]["id"]],
    })
    assert exposure.status_code == 201
    assert client.patch(f"/api/v1/medical-surveillance/exposures/{exposure.json()['id']}", json={"end_date": "2026-04-01"}).status_code == 200
    assert client.post("/api/v1/medical-surveillance/occupational-illnesses", json={
        "worker_user_id": worker.id, "illness_category": "noise_induced_hearing_loss",
        "status": "confirmed", "date_identified": "2026-04-23",
        "symptoms_summary": "Sensitive symptom summary", "diagnosis_detail": "Sensitive diagnosis",
        "exposure_assignment_ids": [exposure.json()["id"]],
    }).status_code == 201
    record = client.post("/api/v1/medical-surveillance", json={
        "employee_user_id": worker.id, "programme_id": catalogue["SPIROMETRY"]["id"],
        "surveillance_type": "Spirometry", "due_date": "2026-04-20",
    })
    assert record.status_code == 201, record.text
    first = client.post("/api/v1/medical-surveillance/reminders/run").json()
    second = client.post("/api/v1/medical-surveillance/reminders/run").json()
    assert first["overdue"] == 1
    assert second == {}
    assert db_session.scalar(select(MedicalReminderDelivery.id)) is not None
    dashboard = client.get("/api/v1/medical-surveillance/dashboard").json()
    assert dashboard["overdue_assessments"] == 1
    assert dashboard["occupational_illness_confirmed"] == 1
    assert client.get("/api/v1/exports/occupational-health/compliance.csv").status_code == 200


def test_employee_self_view_supervisor_scope_and_feature_disabled(client, create_user_for_role, db_session, act_as):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["PERIODIC"]
    record = client.post("/api/v1/medical-surveillance", json={
        "employee_user_id": worker.id, "programme_id": programme["id"],
        "surveillance_type": "Periodic Medical", "due_date": "2026-06-01",
        "results_summary": "Confidential result", "notes": "Confidential note",
    })
    assert record.status_code == 201
    act_as(worker)
    own = client.get("/api/v1/medical-surveillance").json()["items"]
    assert len(own) == 1 and own[0]["results_summary"] is None

    other_site = Site(id=2, name="Remote", code="REMOTE", address="Elsewhere")
    db_session.add(other_site); db_session.commit()
    supervisor = create_user_for_role("supervisor", assigned_site_id=2)
    act_as(supervisor)
    assert client.get(f"/api/v1/medical-surveillance/workers/{worker.id}/profile").status_code == 403

    act_as(1)
    feature = db_session.scalar(select(OrganisationFeature).where(OrganisationFeature.key == "medical_surveillance"))
    feature.is_enabled = False; db_session.add(feature); db_session.commit()
    assert client.get("/api/v1/medical-surveillance/programmes").status_code == 403


def test_cross_tenant_occupational_health_ids_exports_and_dashboard_fail_closed(client, db_session):
    with unscoped_session(db_session, allow_writes=True):
        organisation = Organisation(id=2, name="Other Tenant", code="OTHER", slug="other", timezone="UTC")
        db_session.add(organisation); db_session.flush()
        db_session.add(OrganisationSettings(organisation_id=2))
        db_session.add(OrganisationFeature(organisation_id=2, key="medical_surveillance", is_enabled=True))
        site = Site(organisation_id=2, name="Other Site", code="OTHER-SITE")
        db_session.add(site); db_session.flush()
        worker = User(
            organisation_id=2, email="other-worker@example.com", full_name="Other Tenant Worker",
            hashed_password="not-used", assigned_site_id=site.id,
        )
        db_session.add(worker); db_session.flush()
        programme = SurveillanceProgramme(
            organisation_id=2, name="Other confidential programme", code="OTHER_PROGRAMME",
            reminder_windows=[30], provider_requirements={}, active=True,
        )
        exposure_type = OccupationalExposureType(organisation_id=2, name="Other exposure", code="OTHER_EXPOSURE")
        provider = MedicalProvider(organisation_id=2, name="Other private provider")
        db_session.add_all([programme, exposure_type, provider]); db_session.flush()
        requirement = SurveillanceRequirement(
            organisation_id=2, programme_id=programme.id, name="Other requirement", job_title="Other role",
        )
        surveillance = MedicalSurveillanceRecord(
            organisation_id=2, employee_user_id=worker.id, site_id=site.id,
            programme_id=programme.id, surveillance_type="Other surveillance", due_date=date(2026, 6, 1),
        )
        appointment = MedicalAppointment(
            organisation_id=2, worker_user_id=worker.id, programme_id=programme.id,
            provider_id=provider.id, site_id=site.id, appointment_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        db_session.add_all([requirement, surveillance, appointment]); db_session.flush()
        assessment = MedicalAssessment(
            organisation_id=2, worker_user_id=worker.id, surveillance_record_id=surveillance.id,
            programme_id=programme.id, appointment_id=appointment.id, assessment_type="periodic",
            assessment_date=date(2026, 4, 1), fitness_outcome=FitnessOutcome.fit,
        )
        db_session.add(assessment); db_session.flush()
        certificate = FitnessCertificate(
            organisation_id=2, worker_user_id=worker.id, assessment_id=assessment.id,
            programme_id=programme.id, provider_id=provider.id, certificate_number="OTHER-CERT",
            issued_date=date(2026, 4, 1), expiry_date=date(2027, 4, 1), fitness_outcome=FitnessOutcome.fit,
        )
        restriction = WorkRestriction(
            organisation_id=2, worker_user_id=worker.id, source_assessment_id=assessment.id,
            restriction_type="other", description="Other tenant restriction", effective_from=date(2026, 4, 1),
        )
        exposure = WorkerExposureAssignment(
            organisation_id=2, worker_user_id=worker.id, exposure_type_id=exposure_type.id,
            site_id=site.id, start_date=date(2025, 1, 1),
        )
        db_session.add_all([certificate, restriction, exposure]); db_session.flush()
        illness = OccupationalIllnessCase(
            organisation_id=2, worker_user_id=worker.id, site_id=site.id,
            illness_category="Other confidential illness", date_identified=date(2026, 4, 1),
            exposure_assignment_ids=[exposure.id],
        )
        encounter = ClinicEncounter(
            organisation_id=2, worker_user_id=worker.id, site_id=site.id,
            encounter_type="consultation", encountered_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            assessment_id=assessment.id,
        )
        db_session.add_all([illness, encounter]); db_session.commit()
        guessed_ids = {
            "programmes": programme.id, "requirements": requirement.id, "providers": provider.id,
            "appointments": appointment.id, "certificates": certificate.id, "restrictions": restriction.id,
            "exposures": exposure.id, "occupational-illnesses": illness.id,
            "clinic-encounters": encounter.id,
        }
        worker_id = worker.id; assessment_id = assessment.id

    for resource, record_id in guessed_ids.items():
        assert client.patch(f"/api/v1/medical-surveillance/{resource}/{record_id}", json={}).status_code == 404
    assert client.get("/api/v1/medical-surveillance/assessments", params={"worker_user_id": worker_id}).status_code == 404
    assert client.get(f"/api/v1/attachments/medical_assessment/{assessment_id}").status_code == 404
    export = client.get("/api/v1/exports/occupational-health/compliance.csv")
    assert export.status_code == 200 and "Other surveillance" not in export.text
    dashboard = client.get("/api/v1/medical-surveillance/dashboard")
    assert dashboard.status_code == 200 and dashboard.json()["workers_requiring_surveillance"] == 0


def test_return_to_work_assessment_updates_existing_phase2b_workflow(client, create_user_for_role, db_session):
    worker = create_worker(create_user_for_role, db_session)
    incident = client.post("/api/v1/incidents", json={
        "site_id": 1, "title": "Manual handling injury", "description": "Worker injured while lifting.",
        "incident_type": "lost_time_injury", "severity": "high", "status": "reported",
        "occurred_at": "2026-04-20T08:00:00Z",
    }).json()
    person = client.post(f"/api/v1/incidents/{incident['id']}/people", json={
        "user_id": worker.id, "involvement_role": "injured_person",
    }).json()
    rtw = client.post(f"/api/v1/incidents/{incident['id']}/return-to-work", json={
        "incident_person_id": person["id"], "status": "awaiting_assessment",
        "medical_clearance_required": True, "review_due_date": "2026-04-25",
    }).json()
    programme = programmes(client)["RETURN_TO_WORK"]
    assessed = client.post("/api/v1/medical-surveillance/assessments", json={
        "worker_user_id": worker.id, "programme_id": programme["id"],
        "return_to_work_record_id": rtw["id"], "incident_id": incident["id"],
        "assessment_type": "return_to_work", "assessment_date": "2026-04-23",
        "fitness_outcome": "fit_with_restrictions", "operational_restrictions": "No lifting above 5 kg",
    })
    assert assessed.status_code == 201, assessed.text
    medical = client.get(f"/api/v1/incidents/{incident['id']}/medical").json()
    assert medical["return_to_work_records"][0]["status"] == "restricted_duties"
    assert medical["return_to_work_records"][0]["restrictions"] == "No lifting above 5 kg"
    assert medical["return_to_work_records"][0]["medical_surveillance_record_id"] is not None


def test_medical_attachment_and_report_require_separate_detail_permission(client, create_user_for_role, db_session, act_as):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["VISION"]
    assessment = client.post("/api/v1/medical-surveillance/assessments", json={
        "worker_user_id": worker.id, "programme_id": programme["id"],
        "assessment_type": "vision", "assessment_date": "2026-04-23", "fitness_outcome": "fit",
    }).json()
    uploaded = client.post(
        f"/api/v1/attachments/medical_assessment/{assessment['id']}",
        files={"file": ("test-report.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"evidence_type": "medical_test_report"},
    )
    assert uploaded.status_code == 201, uploaded.text
    ohs_manager = create_user_for_role("ohs_manager")
    act_as(ohs_manager)
    assert client.get(f"/api/v1/attachments/medical_assessment/{assessment['id']}").status_code == 403
    assert client.get(f"/api/v1/attachments/{uploaded.json()['id']}/download").status_code == 403


def test_legacy_incident_medical_view_redacts_detail_for_ohs_manager(client, create_user_for_role, act_as):
    incident = client.post("/api/v1/incidents", json={
        "site_id": 1, "title": "Hand injury", "description": "Worker injured during maintenance.",
        "incident_type": "lost_time_injury", "severity": "high", "status": "reported",
        "occurred_at": "2026-04-20T08:00:00Z",
    }).json()
    person = client.post(f"/api/v1/incidents/{incident['id']}/people", json={
        "external_name": "Contract technician", "involvement_role": "injured_person",
    }).json()
    injury = client.post(f"/api/v1/incidents/{incident['id']}/injuries", json={
        "incident_person_id": person["id"], "injury_present": True, "body_part": "Hand",
        "injury_type": "Laceration", "diagnosis_description": "Confidential diagnosis",
        "treated_by": "Named clinician", "notes": "Confidential clinical note",
    })
    assert injury.status_code == 201, injury.text
    assert client.post(f"/api/v1/incidents/{incident['id']}/treatments", json={
        "incident_person_id": person["id"], "treatment_type": "clinic_treatment",
        "provider_name": "Private clinic", "treatment_summary": "Confidential treatment",
        "medical_certificate_reference": "private-certificate.pdf",
    }).status_code == 201

    ohs_manager = create_user_for_role("ohs_manager")
    act_as(ohs_manager)
    medical = client.get(f"/api/v1/incidents/{incident['id']}/medical")
    assert medical.status_code == 200, medical.text
    assert medical.json()["injuries"][0]["injury_type"] == "Laceration"
    assert medical.json()["injuries"][0]["diagnosis_description"] is None
    assert medical.json()["injuries"][0]["treated_by"] is None
    assert medical.json()["treatments"][0]["treatment_summary"] is None
    assert medical.json()["treatments"][0]["medical_certificate_reference"] is None
    assert client.post(f"/api/v1/incidents/{incident['id']}/injuries", json={
        "incident_person_id": person["id"], "injury_present": True,
    }).status_code == 403


def test_operational_manager_cannot_write_confidential_legacy_fields_and_supervisor_dashboard_is_site_scoped(client, create_user_for_role, db_session, act_as):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["PERIODIC"]
    ohs_manager = create_user_for_role("ohs_manager")
    act_as(ohs_manager)
    confidential = client.post("/api/v1/medical-surveillance", json={
        "employee_user_id": worker.id, "programme_id": programme["id"],
        "surveillance_type": "Periodic Medical", "due_date": "2026-06-01",
        "results_summary": "Confidential result",
    })
    assert confidential.status_code == 403
    operational = client.post("/api/v1/medical-surveillance", json={
        "employee_user_id": worker.id, "programme_id": programme["id"],
        "surveillance_type": "Periodic Medical", "due_date": "2026-06-01",
    })
    assert operational.status_code == 201, operational.text

    supervisor = create_user_for_role("supervisor", assigned_site_id=1)
    act_as(supervisor)
    scoped_dashboard = client.get("/api/v1/medical-surveillance/dashboard")
    assert scoped_dashboard.status_code == 200, scoped_dashboard.text
    assert scoped_dashboard.json()["workers_requiring_surveillance"] == 1


def test_kpis_forward_view_and_unified_action_hook(client, create_user_for_role, db_session):
    worker = create_worker(create_user_for_role, db_session)
    programme = programmes(client)["SPIROMETRY"]
    record = client.post("/api/v1/medical-surveillance", json={
        "employee_user_id": worker.id, "programme_id": programme["id"],
        "surveillance_type": "Spirometry", "due_date": "2026-04-25",
    }).json()
    forward = client.get("/api/v1/reporting/forward-view", params={"as_of": "2026-04-23", "window_days": 30})
    assert forward.status_code == 200
    assert any(item["source_type"] == "medical_surveillance" and item["source_id"] == record["id"] for item in forward.json())
    period = client.post("/api/v1/reporting/periods", json={
        "name": "April 2026 OH Report", "period_type": "monthly",
        "start_date": "2026-04-01", "end_date": "2026-04-30",
    }).json()
    generated = client.post(f"/api/v1/reporting/periods/{period['id']}/snapshots")
    assert generated.status_code == 200, generated.text
    rows = {item["kpi_key"]: item for item in client.get(f"/api/v1/reporting/periods/{period['id']}/scorecard").json()["rows"]}
    assert rows["medical_workers_requiring"]["actual"] == 1
    assert rows["medical_assessments_overdue"]["actual"] == 1
    action = client.post("/api/v1/medical-surveillance/actions", json={
        "issue_type": "overdue_surveillance", "source_id": record["id"], "owner_user_id": 1,
    })
    assert action.status_code == 201, action.text
    assert action.json()["source_type"] == "occupational_health"
