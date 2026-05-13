from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.corrective_action import (
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.hazard import Hazard, HazardStatus
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.inspection import Inspection, InspectionStatus, inspection_linked_hazards
from app.models.notification import (
    Notification,
    NotificationSeverity,
    NotificationType,
    RelatedEntityType,
)
from app.models.permit import PermitStatus, PermitToWork, PermitType
from app.models.role import Role, user_roles
from app.models.site import Site
from app.models.training import (
    ComplianceAcknowledgement,
    ComplianceAcknowledgementStatus,
    TrainingRecord,
    TrainingStatus,
    TrainingType,
)
from app.models.user import User
from app.services.corrective_action_service import notify_action_pending_verification
from app.services.hazard_service import calculate_risk_score, derive_risk_level
from app.services.inspection_service import calculate_checklist_counts, derive_overall_result
from app.services.notification_service import notify_critical_hazard, notify_critical_incident
from app.services.notification_service import (
    generate_corrective_action_due_soon_notifications,
    generate_corrective_action_overdue_notifications,
)
from app.services.permit_service import (
    generate_permit_expired_notifications,
    generate_permit_nearing_expiry_notifications,
    notify_permit_pending_approval,
)
from app.services.training_service import (
    generate_expired_training_notifications,
    generate_overdue_compliance_acknowledgement_notifications,
    generate_overdue_training_notifications,
)

DEMO_PASSWORD = "DemoPass123!"
DEMO_USER_DOMAIN = "@demo.ohs.local"
DEMO_SITE_CODE_PREFIX = "DEMO-"
DEMO_TITLE_PREFIX = "Demo:"
DEMO_PERMIT_PREFIX = "DEMO-PTW-"

REQUIRED_ROLE_NAMES = {"admin", "ohs_manager", "safety_officer", "supervisor", "employee"}


@dataclass(frozen=True)
class SeedSummary:
    sites: int
    users: int
    incidents: int
    hazards: int
    inspections: int
    corrective_actions: int
    training_records: int
    compliance_acknowledgements: int
    permits: int
    notifications: int


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _at_day(base: datetime, days: int, hour: int, minute: int = 0) -> datetime:
    target_day = (base + timedelta(days=days)).date()
    return datetime.combine(target_day, time(hour=hour, minute=minute), tzinfo=timezone.utc)


def _attachment(file_name: str, *, label: str) -> dict:
    return {
        "file_name": file_name,
        "content_type": "application/pdf",
        "url": f"https://demo.ohs.local/assets/{file_name}",
        "size_bytes": 1024 + len(file_name) * 17,
        "label": label,
    }


def _certificate(file_name: str) -> dict:
    return {
        "file_name": file_name,
        "content_type": "application/pdf",
        "url": f"https://demo.ohs.local/certificates/{file_name}",
        "size_bytes": 2048 + len(file_name) * 13,
    }


def _gas_test(gas: str, reading: float, unit: str = "%LEL") -> dict:
    return {"gas": gas, "reading": reading, "unit": unit, "tested_at": _now().isoformat()}


def _delete_demo_rows(db: Session) -> None:
    demo_user_ids = list(
        db.scalars(select(User.id).where(User.email.like(f"%{DEMO_USER_DOMAIN}"))).all()
    )
    demo_inspection_ids = list(
        db.scalars(select(Inspection.id).where(Inspection.title.like(f"{DEMO_TITLE_PREFIX}%"))).all()
    )

    if demo_user_ids:
        db.execute(delete(user_roles).where(user_roles.c.user_id.in_(demo_user_ids)))
        db.execute(delete(Notification).where(Notification.recipient_user_id.in_(demo_user_ids)))

    if demo_inspection_ids:
        db.execute(
            delete(inspection_linked_hazards).where(
                inspection_linked_hazards.c.inspection_id.in_(demo_inspection_ids)
            )
        )

    db.execute(delete(CorrectiveAction).where(CorrectiveAction.title.like(f"{DEMO_TITLE_PREFIX}%")))
    db.execute(delete(Inspection).where(Inspection.title.like(f"{DEMO_TITLE_PREFIX}%")))
    db.execute(delete(TrainingRecord).where(TrainingRecord.title.like(f"{DEMO_TITLE_PREFIX}%")))
    db.execute(
        delete(ComplianceAcknowledgement).where(
            ComplianceAcknowledgement.document_title.like(f"{DEMO_TITLE_PREFIX}%")
        )
    )
    db.execute(delete(PermitToWork).where(PermitToWork.permit_number.like(f"{DEMO_PERMIT_PREFIX}%")))
    db.execute(delete(Hazard).where(Hazard.title.like(f"{DEMO_TITLE_PREFIX}%")))
    db.execute(delete(Incident).where(Incident.title.like(f"{DEMO_TITLE_PREFIX}%")))
    db.execute(delete(Site).where(Site.code.like(f"{DEMO_SITE_CODE_PREFIX}%")))
    db.execute(delete(User).where(User.email.like(f"%{DEMO_USER_DOMAIN}")))
    db.commit()


def _load_roles(db: Session) -> dict[str, Role]:
    roles = {
        role.name: role
        for role in db.scalars(select(Role).where(Role.name.in_(sorted(REQUIRED_ROLE_NAMES)))).all()
    }
    missing = sorted(REQUIRED_ROLE_NAMES - set(roles))
    if missing:
        missing_roles = ", ".join(missing)
        raise RuntimeError(
            f"Required roles are missing: {missing_roles}. Run migrations before seeding demo data."
        )
    return roles


def _create_users(db: Session, roles: dict[str, Role]) -> dict[str, User]:
    password_hash = get_password_hash(DEMO_PASSWORD)
    users = [
        User(
            email=f"emma.ncube{DEMO_USER_DOMAIN}",
            full_name="Emma Ncube",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["admin"]],
        ),
        User(
            email=f"brian.phiri{DEMO_USER_DOMAIN}",
            full_name="Brian Phiri",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["ohs_manager"]],
        ),
        User(
            email=f"ruth.zulu{DEMO_USER_DOMAIN}",
            full_name="Ruth Zulu",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["supervisor"]],
        ),
        User(
            email=f"kelvin.mwila{DEMO_USER_DOMAIN}",
            full_name="Kelvin Mwila",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["employee"]],
        ),
        User(
            email=f"grace.tembo{DEMO_USER_DOMAIN}",
            full_name="Grace Tembo",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["safety_officer"]],
        ),
        User(
            email=f"chipo.lungu{DEMO_USER_DOMAIN}",
            full_name="Chipo Lungu",
            hashed_password=password_hash,
            is_active=True,
            roles=[roles["supervisor"], roles["employee"]],
        ),
    ]
    db.add_all(users)
    db.flush()
    return {user.email: user for user in users}


def _create_sites(db: Session, users: dict[str, User]) -> dict[str, Site]:
    admin_user = users[f"emma.ncube{DEMO_USER_DOMAIN}"]
    sites = [
        Site(
            name="Lusaka Blending Plant",
            code="DEMO-LSK-PLANT",
            address="Plot 218, Mungwi Road Industrial Area, Lusaka",
            created_by_id=admin_user.id,
        ),
        Site(
            name="Ndola Distribution Warehouse",
            code="DEMO-NDL-WH",
            address="Kafubu Road Logistics Park, Ndola",
            created_by_id=admin_user.id,
        ),
        Site(
            name="Solwezi Exploration Camp",
            code="DEMO-SLZ-CAMP",
            address="Chiefdom Access Road, Solwezi",
            created_by_id=admin_user.id,
        ),
    ]
    db.add_all(sites)
    db.flush()
    users[f"brian.phiri{DEMO_USER_DOMAIN}"].assigned_site_id = sites[0].id
    users[f"grace.tembo{DEMO_USER_DOMAIN}"].assigned_site_id = sites[1].id
    users[f"ruth.zulu{DEMO_USER_DOMAIN}"].assigned_site_id = sites[0].id
    users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].assigned_site_id = sites[2].id
    users[f"chipo.lungu{DEMO_USER_DOMAIN}"].assigned_site_id = sites[1].id
    db.flush()
    return {site.code: site for site in sites}


def _create_incidents(db: Session, sites: dict[str, Site], users: dict[str, User], base: datetime) -> dict[str, Incident]:
    incidents = [
        Incident(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Forklift near miss in dispatch bay",
            description="A pedestrian stepped into the forklift lane during a pallet transfer. No injury occurred, but the stop distance was less than one metre.",
            severity=IncidentSeverity.medium,
            status=IncidentStatus.investigating,
            occurred_at=_at_day(base, -10, 9, 20),
            attachments_metadata=[_attachment("forklift-nearmiss.pdf", label="Initial witness note")],
            reported_by_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Welding flash burn treated on site",
            description="A contractor received a minor flash burn while assisting on pipe spool fabrication and was treated at the clinic.",
            severity=IncidentSeverity.high,
            status=IncidentStatus.resolved,
            occurred_at=_at_day(base, -8, 14, 10),
            attachments_metadata=[_attachment("welding-flash-report.pdf", label="Treatment summary")],
            reported_by_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Chemical splash contained in reagent room",
            description="A hose coupling released during caustic transfer, causing a splash inside the bunded reagent room. The spill was contained immediately.",
            severity=IncidentSeverity.critical,
            status=IncidentStatus.open,
            occurred_at=_at_day(base, -6, 11, 45),
            attachments_metadata=[_attachment("reagent-room-response.pdf", label="Immediate response log")],
            reported_by_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Housekeeping slip at bagging line",
            description="An operator slipped on loose pallet wrap near the bagging line. No medical treatment was required.",
            severity=IncidentSeverity.low,
            status=IncidentStatus.closed,
            occurred_at=_at_day(base, -18, 7, 55),
            attachments_metadata=[],
            reported_by_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Vehicle reversing alarm failure",
            description="A reversing alarm on a loading vehicle failed during an outbound dispatch sequence and was reported before further movement.",
            severity=IncidentSeverity.high,
            status=IncidentStatus.investigating,
            occurred_at=_at_day(base, -5, 16, 5),
            attachments_metadata=[_attachment("fleet-defect-card.pdf", label="Fleet defect card")],
            reported_by_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Diesel spill during refuelling",
            description="A small diesel spill occurred during generator refuelling and was cleaned using the spill kit with no environmental release beyond the pad.",
            severity=IncidentSeverity.medium,
            status=IncidentStatus.resolved,
            occurred_at=_at_day(base, -9, 18, 30),
            attachments_metadata=[_attachment("diesel-spill-closeout.pdf", label="Closeout report")],
            reported_by_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Visitor tripped on uneven walkway",
            description="A visitor caught a shoe edge on an uneven paver at the reception approach. The visitor declined treatment and continued the visit.",
            severity=IncidentSeverity.low,
            status=IncidentStatus.closed,
            occurred_at=_at_day(base, -15, 10, 5),
            attachments_metadata=[],
            reported_by_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Fall protection anchor found loose",
            description="A maintenance technician identified movement on a fall-arrest anchor during pre-use checks on the gantry walkway.",
            severity=IncidentSeverity.critical,
            status=IncidentStatus.investigating,
            occurred_at=_at_day(base, -3, 8, 15),
            attachments_metadata=[_attachment("anchor-inspection-note.pdf", label="Inspection note")],
            reported_by_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Generator exhaust leak in camp kitchen",
            description="Kitchen staff reported exhaust fumes entering the prep area after a flexible duct separated from the standby generator stack.",
            severity=IncidentSeverity.high,
            status=IncidentStatus.open,
            occurred_at=_at_day(base, -2, 6, 40),
            attachments_metadata=[_attachment("generator-exhaust-checklist.pdf", label="Maintenance checklist")],
            reported_by_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
        ),
        Incident(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Bee sting during vegetation clearing",
            description="A grounds worker was stung while clearing brush near the perimeter fence and returned to work after first-aid treatment.",
            severity=IncidentSeverity.medium,
            status=IncidentStatus.resolved,
            occurred_at=_at_day(base, -12, 13, 25),
            attachments_metadata=[],
            reported_by_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
        ),
    ]
    db.add_all(incidents)
    db.flush()
    return {incident.title: incident for incident in incidents}


def _create_hazards(db: Session, sites: dict[str, Site], users: dict[str, User], incidents: dict[str, Incident], base: datetime) -> dict[str, Hazard]:
    hazard_specs = [
        {
            "title": "Demo: Unmarked forklift-pedestrian crossing risk",
            "site_code": "DEMO-LSK-PLANT",
            "likelihood": 4,
            "impact": 4,
            "status": HazardStatus.open,
            "description": "Pedestrians and forklifts share a blind corner between dispatch staging and finished goods storage.",
            "existing_controls": ["Forklift horn rules", "Painted travel lanes"],
            "additional_controls": ["Install barrier rails", "Add floor-mounted warning lights"],
            "owner_email": f"ruth.zulu{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Forklift near miss in dispatch bay",
            "reported_by_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=5),
            "review_date": base.date() + timedelta(days=30),
        },
        {
            "title": "Demo: Incomplete welding screen coverage",
            "site_code": "DEMO-LSK-PLANT",
            "likelihood": 3,
            "impact": 3,
            "status": HazardStatus.controlled,
            "description": "Fabrication screens do not fully shield adjacent walkways from arc flash exposure.",
            "existing_controls": ["Hot work permit", "Spotter present"],
            "additional_controls": ["Replace damaged screens", "Mark exclusion zone"],
            "owner_email": f"chipo.lungu{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Welding flash burn treated on site",
            "reported_by_email": f"ruth.zulu{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=7),
            "review_date": base.date() + timedelta(days=21),
        },
        {
            "title": "Demo: Caustic soda hose degradation at dosing skid",
            "site_code": "DEMO-LSK-PLANT",
            "likelihood": 4,
            "impact": 5,
            "status": HazardStatus.open,
            "description": "Visible crazing is present on the flexible hose used for caustic transfer at the dosing skid.",
            "existing_controls": ["Bund walls", "Face shields available"],
            "additional_controls": ["Replace hose immediately", "Add monthly hose register"],
            "owner_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Chemical splash contained in reagent room",
            "reported_by_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=2),
            "review_date": base.date() + timedelta(days=14),
        },
        {
            "title": "Demo: Pallet debris on bagging line walkway",
            "site_code": "DEMO-LSK-PLANT",
            "likelihood": 2,
            "impact": 2,
            "status": HazardStatus.closed,
            "description": "Discarded wrap and broken pallet boards create a slip and trip hazard beside the bagging conveyor.",
            "existing_controls": ["Daily housekeeping checks"],
            "additional_controls": ["Install dedicated waste bins"],
            "owner_email": f"kelvin.mwila{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Housekeeping slip at bagging line",
            "reported_by_email": f"kelvin.mwila{DEMO_USER_DOMAIN}",
            "due_date": base.date() - timedelta(days=7),
            "review_date": base.date() + timedelta(days=60),
        },
        {
            "title": "Demo: Reverse alarm inspection gap on loading fleet",
            "site_code": "DEMO-NDL-WH",
            "likelihood": 3,
            "impact": 4,
            "status": HazardStatus.open,
            "description": "Pre-start checks do not consistently include an audible reversing alarm verification for hired loading vehicles.",
            "existing_controls": ["Daily dispatch briefing"],
            "additional_controls": ["Add fleet checklist sign-off", "Escalate defects before loading"],
            "owner_email": f"chipo.lungu{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Vehicle reversing alarm failure",
            "reported_by_email": f"chipo.lungu{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=3),
            "review_date": base.date() + timedelta(days=28),
        },
        {
            "title": "Demo: Fuel bowser bonding clamp wear",
            "site_code": "DEMO-NDL-WH",
            "likelihood": 3,
            "impact": 3,
            "status": HazardStatus.controlled,
            "description": "The fuel bowser bonding clamp shows excessive wear and intermittent loss of spring tension.",
            "existing_controls": ["Spill kit nearby", "Refuelling SOP"],
            "additional_controls": ["Replace clamp", "Add weekly equipment inspection"],
            "owner_email": f"ruth.zulu{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Diesel spill during refuelling",
            "reported_by_email": f"kelvin.mwila{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=6),
            "review_date": base.date() + timedelta(days=20),
        },
        {
            "title": "Demo: Uneven paver edge at visitor route",
            "site_code": "DEMO-NDL-WH",
            "likelihood": 2,
            "impact": 2,
            "status": HazardStatus.controlled,
            "description": "A raised paver edge remains on the visitor route between reception and the outbound loading apron.",
            "existing_controls": ["Temporary warning cone"],
            "additional_controls": ["Repair pavers", "Review reception escort path"],
            "owner_email": f"grace.tembo{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Visitor tripped on uneven walkway",
            "reported_by_email": f"grace.tembo{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=4),
            "review_date": base.date() + timedelta(days=21),
        },
        {
            "title": "Demo: Loose fall-arrest anchor on maintenance gantry",
            "site_code": "DEMO-SLZ-CAMP",
            "likelihood": 4,
            "impact": 5,
            "status": HazardStatus.open,
            "description": "A fixed anchor on the maintenance gantry shows movement under manual pull test and is not fit for use.",
            "existing_controls": ["Area barricaded", "Temporary work stop"],
            "additional_controls": ["Engineer certification", "Replace anchor set"],
            "owner_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Fall protection anchor found loose",
            "reported_by_email": f"ruth.zulu{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=1),
            "review_date": base.date() + timedelta(days=7),
        },
        {
            "title": "Demo: Poor generator exhaust extraction at camp kitchen",
            "site_code": "DEMO-SLZ-CAMP",
            "likelihood": 4,
            "impact": 4,
            "status": HazardStatus.controlled,
            "description": "The temporary generator ductwork does not reliably vent exhaust away from the food preparation area.",
            "existing_controls": ["Carbon monoxide monitor", "Ventilation fan"],
            "additional_controls": ["Install rigid ducting", "Add maintenance hold point"],
            "owner_email": f"chipo.lungu{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Generator exhaust leak in camp kitchen",
            "reported_by_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=2),
            "review_date": base.date() + timedelta(days=10),
        },
        {
            "title": "Demo: Bee nest near perimeter clearing zone",
            "site_code": "DEMO-SLZ-CAMP",
            "likelihood": 3,
            "impact": 2,
            "status": HazardStatus.open,
            "description": "A nest is present in scrub vegetation within the planned brush-clearing work area near the perimeter fence.",
            "existing_controls": ["First-aid kit available"],
            "additional_controls": ["Remove nest", "Update pre-task briefing"],
            "owner_email": f"kelvin.mwila{DEMO_USER_DOMAIN}",
            "incident_title": "Demo: Bee sting during vegetation clearing",
            "reported_by_email": f"kelvin.mwila{DEMO_USER_DOMAIN}",
            "due_date": base.date() + timedelta(days=1),
            "review_date": base.date() + timedelta(days=14),
        },
    ]
    hazards = []
    for spec in hazard_specs:
        risk_score = calculate_risk_score(spec["likelihood"], spec["impact"])
        hazards.append(
            Hazard(
                site_id=sites[spec["site_code"]].id,
                title=spec["title"],
                description=spec["description"],
                likelihood=spec["likelihood"],
                impact=spec["impact"],
                risk_score=risk_score,
                risk_level=derive_risk_level(risk_score),
                status=spec["status"],
                existing_controls=spec["existing_controls"],
                additional_controls=spec["additional_controls"],
                owner_user_id=users[spec["owner_email"]].id,
                due_date=spec["due_date"],
                review_date=spec["review_date"],
                attachments_metadata=[_attachment(f"{spec['title'].lower().replace(' ', '-')[:24]}.pdf", label="Register attachment")],
                incident_id=incidents[spec["incident_title"]].id,
                reported_by_id=users[spec["reported_by_email"]].id,
            )
        )
    db.add_all(hazards)
    db.flush()
    return {hazard.title: hazard for hazard in hazards}


def _inspection_checklist(*items: tuple[str, str, Optional[int]]) -> list[dict]:
    checklist = []
    for prompt, result, linked_hazard_id in items:
        item = {"prompt": prompt, "result": result}
        if linked_hazard_id is not None:
            item["linked_hazard_id"] = linked_hazard_id
        checklist.append(item)
    return checklist


def _create_inspections(db: Session, sites: dict[str, Site], users: dict[str, User], hazards: dict[str, Hazard], base: datetime) -> dict[str, Inspection]:
    inspection_specs = [
        {
            "title": "Demo: Weekly warehouse safety walkdown",
            "site_code": "DEMO-NDL-WH",
            "inspection_type": "Weekly walkdown",
            "area_location": "Outbound loading apron",
            "inspection_date": _at_day(base, -1, 9, 0),
            "status": InspectionStatus.completed,
            "notes": "Team completed the weekly walkdown before the morning dispatch peak.",
            "findings_summary": "Minor housekeeping issues remain around the visitor route and fleet staging line.",
            "checklist_items": _inspection_checklist(
                ("Pedestrian walkways free from defects", "observation", hazards["Demo: Uneven paver edge at visitor route"].id),
                ("Vehicle pre-start checks completed", "non_compliant", hazards["Demo: Reverse alarm inspection gap on loading fleet"].id),
                ("Spill response equipment available", "compliant", None),
            ),
            "inspector_email": f"grace.tembo{DEMO_USER_DOMAIN}",
            "linked_hazards": [
                hazards["Demo: Reverse alarm inspection gap on loading fleet"],
                hazards["Demo: Uneven paver edge at visitor route"],
            ],
        },
        {
            "title": "Demo: Hot work permit readiness check",
            "site_code": "DEMO-LSK-PLANT",
            "inspection_type": "Permit readiness",
            "area_location": "Fabrication bay",
            "inspection_date": _at_day(base, -2, 13, 30),
            "status": InspectionStatus.completed,
            "notes": "Reviewed welding controls before contractor mobilisation.",
            "findings_summary": "Two non-conformities raised around shielding and chemical transfer area segregation.",
            "checklist_items": _inspection_checklist(
                ("Welding screens fully isolate adjacent walkways", "non_compliant", hazards["Demo: Incomplete welding screen coverage"].id),
                ("Chemical storage segregated from hot work", "non_compliant", hazards["Demo: Caustic soda hose degradation at dosing skid"].id),
                ("Fire watch equipment staged and tagged", "compliant", None),
            ),
            "inspector_email": f"brian.phiri{DEMO_USER_DOMAIN}",
            "linked_hazards": [
                hazards["Demo: Incomplete welding screen coverage"],
                hazards["Demo: Caustic soda hose degradation at dosing skid"],
            ],
        },
        {
            "title": "Demo: Camp emergency response inspection",
            "site_code": "DEMO-SLZ-CAMP",
            "inspection_type": "Emergency preparedness",
            "area_location": "Kitchen and workshop corridor",
            "inspection_date": _at_day(base, 0, 10, 0),
            "status": InspectionStatus.in_progress,
            "notes": "Inspection is still open pending verification of temporary controls.",
            "findings_summary": "Observations logged on exhaust extraction and muster-point visibility.",
            "checklist_items": _inspection_checklist(
                ("Emergency routes clearly marked", "observation", None),
                ("Ventilation controls effective in kitchen", "non_compliant", hazards["Demo: Poor generator exhaust extraction at camp kitchen"].id),
                ("Work-at-height access points isolated", "observation", hazards["Demo: Loose fall-arrest anchor on maintenance gantry"].id),
            ),
            "inspector_email": f"grace.tembo{DEMO_USER_DOMAIN}",
            "linked_hazards": [
                hazards["Demo: Poor generator exhaust extraction at camp kitchen"],
                hazards["Demo: Loose fall-arrest anchor on maintenance gantry"],
            ],
        },
        {
            "title": "Demo: Contractor pre-start verification",
            "site_code": "DEMO-SLZ-CAMP",
            "inspection_type": "Contractor mobilisation",
            "area_location": "Perimeter clearing workfront",
            "inspection_date": _at_day(base, 1, 7, 30),
            "status": InspectionStatus.draft,
            "notes": "Draft record prepared for the contractor mobilisation review.",
            "findings_summary": "Pre-start pack drafted with environmental and biodiversity checks.",
            "checklist_items": _inspection_checklist(
                ("Task risk assessment reviewed", "compliant", None),
                ("Area free from environmental hazards", "observation", hazards["Demo: Bee nest near perimeter clearing zone"].id),
            ),
            "inspector_email": f"ruth.zulu{DEMO_USER_DOMAIN}",
            "linked_hazards": [hazards["Demo: Bee nest near perimeter clearing zone"]],
        },
        {
            "title": "Demo: Bagging line ergonomics review",
            "site_code": "DEMO-LSK-PLANT",
            "inspection_type": "Ergonomics review",
            "area_location": "Bagging and palletising line",
            "inspection_date": _at_day(base, -14, 15, 0),
            "status": InspectionStatus.archived,
            "notes": "Archived after improvements were completed and verified.",
            "findings_summary": "Legacy housekeeping issue closed with no active ergonomics concerns.",
            "checklist_items": _inspection_checklist(
                ("Walkways clear and labelled", "compliant", hazards["Demo: Pallet debris on bagging line walkway"].id),
                ("Lift-assist tools available", "compliant", None),
            ),
            "inspector_email": f"grace.tembo{DEMO_USER_DOMAIN}",
            "linked_hazards": [hazards["Demo: Pallet debris on bagging line walkway"]],
        },
    ]
    inspections = []
    for spec in inspection_specs:
        non_conformities, observations = calculate_checklist_counts(spec["checklist_items"])
        inspections.append(
            Inspection(
                site_id=sites[spec["site_code"]].id,
                title=spec["title"],
                inspection_type=spec["inspection_type"],
                area_location=spec["area_location"],
                inspection_date=spec["inspection_date"],
                status=spec["status"],
                notes=spec["notes"],
                findings_summary=spec["findings_summary"],
                overall_result=derive_overall_result(spec["checklist_items"]),
                number_of_non_conformities=non_conformities,
                number_of_observations=observations,
                checklist_items=spec["checklist_items"],
                attachments_metadata=[_attachment(f"{spec['title'].lower().replace(' ', '-')[:24]}.pdf", label="Inspection attachment")],
                inspector_user_id=users[spec["inspector_email"]].id,
                linked_hazards=spec["linked_hazards"],
            )
        )
    db.add_all(inspections)
    db.flush()
    return {inspection.title: inspection for inspection in inspections}


def _create_corrective_actions(
    db: Session,
    sites: dict[str, Site],
    users: dict[str, User],
    incidents: dict[str, Incident],
    hazards: dict[str, Hazard],
    inspections: dict[str, Inspection],
    base: datetime,
) -> dict[str, CorrectiveAction]:
    actions = [
        CorrectiveAction(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Repaint forklift crossing and install barriers",
            description="Mark the pedestrian exclusion zone and install fixed barriers at the dispatch bay crossing.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Unmarked forklift-pedestrian crossing risk"].id,
            priority=CorrectiveActionPriority.high,
            status=CorrectiveActionStatus.open,
            due_date=base.date() + timedelta(days=5),
            assigned_to_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Replace welding screens on fabrication bay",
            description="Fit full-height welding curtains and repaint the exclusion boundary before the next contractor shift.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Incomplete welding screen coverage"].id,
            priority=CorrectiveActionPriority.medium,
            status=CorrectiveActionStatus.in_progress,
            due_date=base.date() + timedelta(days=3),
            started_at=_at_day(base, -1, 8, 0),
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Replace caustic transfer hose and add inspection tag",
            description="Swap out the degraded transfer hose, quarantine the failed unit, and add a visible inspection tag system.",
            source_type=CorrectiveActionSourceType.incident,
            source_id=incidents["Demo: Chemical splash contained in reagent room"].id,
            priority=CorrectiveActionPriority.critical,
            status=CorrectiveActionStatus.overdue,
            due_date=base.date() - timedelta(days=4),
            started_at=_at_day(base, -5, 10, 0),
            assigned_to_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Clear pallet debris and reinforce housekeeping checks",
            description="Close the housekeeping gap on the bagging line and update the shift-start housekeeping prompt sheet.",
            source_type=CorrectiveActionSourceType.incident,
            source_id=incidents["Demo: Housekeeping slip at bagging line"].id,
            priority=CorrectiveActionPriority.low,
            status=CorrectiveActionStatus.closed,
            due_date=base.date() - timedelta(days=10),
            completed_at=_at_day(base, -9, 16, 30),
            closure_notes="Housekeeping station installed and verified during shift handover.",
            closure_evidence_metadata=[_attachment("housekeeping-closeout.pdf", label="Closeout evidence")],
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            verified_at=_at_day(base, -8, 9, 0),
        ),
        CorrectiveAction(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Test reversing alarms on all loading vehicles",
            description="Complete a full alarm functionality sweep on warehouse loading vehicles and attach signed defect closeouts.",
            source_type=CorrectiveActionSourceType.incident,
            source_id=incidents["Demo: Vehicle reversing alarm failure"].id,
            priority=CorrectiveActionPriority.high,
            status=CorrectiveActionStatus.pending_verification,
            due_date=base.date() - timedelta(days=1),
            started_at=_at_day(base, -2, 7, 45),
            completed_at=_at_day(base, -1, 15, 40),
            verification_notes="Awaiting final fleet supervisor sign-off.",
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Replace bowser bonding clamp and retrain operator",
            description="Replace the worn bonding clamp and brief all refuelling operators on bonding verification before discharge.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Fuel bowser bonding clamp wear"].id,
            priority=CorrectiveActionPriority.medium,
            status=CorrectiveActionStatus.open,
            due_date=base.date() + timedelta(days=7),
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-NDL-WH"].id,
            title="Demo: Repair visitor walkway pavers",
            description="Lift and reset the uneven paver edge on the visitor route and remove temporary warning cones once complete.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Uneven paver edge at visitor route"].id,
            priority=CorrectiveActionPriority.low,
            status=CorrectiveActionStatus.closed,
            due_date=base.date() - timedelta(days=6),
            completed_at=_at_day(base, -5, 11, 10),
            closure_notes="Civil works team completed the repair and the route was reopened.",
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            verified_at=_at_day(base, -4, 14, 0),
        ),
        CorrectiveAction(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Isolate gantry anchor and certify replacements",
            description="Maintain isolation of the affected gantry and complete engineering certification for the replacement anchor set.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Loose fall-arrest anchor on maintenance gantry"].id,
            priority=CorrectiveActionPriority.critical,
            status=CorrectiveActionStatus.overdue,
            due_date=base.date() - timedelta(days=2),
            started_at=_at_day(base, -3, 9, 0),
            assigned_to_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Install temporary exhaust ducting in camp kitchen",
            description="Install rigid temporary ducting, verify airflow direction, and log daily checks until the permanent repair is complete.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Poor generator exhaust extraction at camp kitchen"].id,
            priority=CorrectiveActionPriority.high,
            status=CorrectiveActionStatus.in_progress,
            due_date=base.date() + timedelta(days=2),
            started_at=_at_day(base, -1, 6, 30),
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Remove bee nest and update clearing JSA",
            description="Use a licensed pest-control contractor to remove the nest and update the clearing task JSA before work resumes.",
            source_type=CorrectiveActionSourceType.hazard,
            source_id=hazards["Demo: Bee nest near perimeter clearing zone"].id,
            priority=CorrectiveActionPriority.medium,
            status=CorrectiveActionStatus.open,
            due_date=base.date() + timedelta(days=1),
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-LSK-PLANT"].id,
            title="Demo: Close out findings from hot work readiness check",
            description="Verify that shielding, area segregation, and permit pack updates are all complete before the next contractor visit.",
            source_type=CorrectiveActionSourceType.inspection,
            source_id=inspections["Demo: Hot work permit readiness check"].id,
            priority=CorrectiveActionPriority.high,
            status=CorrectiveActionStatus.pending_verification,
            due_date=base.date(),
            started_at=_at_day(base, -1, 12, 0),
            completed_at=_at_day(base, -1, 17, 15),
            verification_notes="Pending safety-manager review against the inspection checklist.",
            assigned_to_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
        ),
        CorrectiveAction(
            site_id=sites["DEMO-SLZ-CAMP"].id,
            title="Demo: Verify emergency muster board signage at camp",
            description="Replace faded muster-point boards and confirm legibility during a night-shift walkthrough.",
            source_type=CorrectiveActionSourceType.inspection,
            source_id=inspections["Demo: Camp emergency response inspection"].id,
            priority=CorrectiveActionPriority.medium,
            status=CorrectiveActionStatus.closed,
            due_date=base.date() - timedelta(days=1),
            completed_at=_at_day(base, -1, 18, 0),
            closure_notes="Temporary boards replaced with reflective signage.",
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            created_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            verified_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            verified_at=_at_day(base, 0, 7, 20),
        ),
    ]
    db.add_all(actions)
    db.flush()
    return {action.title: action for action in actions}


def _create_training_records(db: Session, sites: dict[str, Site], users: dict[str, User], base: datetime) -> dict[str, TrainingRecord]:
    records = [
        TrainingRecord(
            title="Demo: Contractor site induction",
            training_type=TrainingType.induction,
            site_id=sites["DEMO-LSK-PLANT"].id,
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() + timedelta(days=2),
            status=TrainingStatus.assigned,
            certificate_metadata=[],
            notes="Assigned before the next contractor mobilisation window.",
        ),
        TrainingRecord(
            title="Demo: Forklift operator refresher",
            training_type=TrainingType.equipment_training,
            site_id=sites["DEMO-NDL-WH"].id,
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() + timedelta(days=7),
            status=TrainingStatus.in_progress,
            certificate_metadata=[],
            notes="Practical assessment booked with the fleet trainer.",
        ),
        TrainingRecord(
            title="Demo: Hot work fire watch refresher",
            training_type=TrainingType.safety_training,
            site_id=sites["DEMO-LSK-PLANT"].id,
            assigned_to_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() - timedelta(days=14),
            completed_at=_at_day(base, -14, 15, 0),
            expiry_date=base.date() + timedelta(days=180),
            status=TrainingStatus.completed,
            certificate_metadata=[_certificate("fire-watch-refresher.pdf")],
            notes="Completed with practical extinguisher drill.",
        ),
        TrainingRecord(
            title="Demo: Hazard identification toolbox talk",
            training_type=TrainingType.toolbox_talk,
            site_id=sites["DEMO-SLZ-CAMP"].id,
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() - timedelta(days=3),
            status=TrainingStatus.overdue,
            certificate_metadata=[],
            notes="Still outstanding for the perimeter clearing crew.",
        ),
        TrainingRecord(
            title="Demo: First aider certification renewal",
            training_type=TrainingType.emergency_response,
            site_id=sites["DEMO-SLZ-CAMP"].id,
            assigned_to_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() - timedelta(days=45),
            completed_at=_at_day(base, -400, 10, 0),
            expiry_date=base.date() - timedelta(days=30),
            status=TrainingStatus.expired,
            certificate_metadata=[_certificate("first-aider-renewal.pdf")],
            notes="Renewal required before the next remote-camp rotation.",
        ),
        TrainingRecord(
            title="Demo: Permit issuer briefing",
            training_type=TrainingType.compliance_training,
            site_id=sites["DEMO-NDL-WH"].id,
            assigned_to_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            due_date=base.date() - timedelta(days=5),
            completed_at=_at_day(base, -5, 11, 0),
            status=TrainingStatus.completed,
            certificate_metadata=[_certificate("permit-issuer-briefing.pdf")],
            notes="Completed ahead of the permit module demo.",
        ),
    ]
    db.add_all(records)
    db.flush()
    return {record.title: record for record in records}


def _create_compliance_acknowledgements(
    db: Session, sites: dict[str, Site], users: dict[str, User], base: datetime
) -> dict[str, ComplianceAcknowledgement]:
    acknowledgements = [
        ComplianceAcknowledgement(
            document_title="Demo: PPE Standard",
            document_type="standard",
            version="3.2",
            site_id=sites["DEMO-LSK-PLANT"].id,
            assigned_to_user_id=users[f"kelvin.mwila{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_at=_at_day(base, -5, 8, 0),
            status=ComplianceAcknowledgementStatus.assigned,
            notes="Assigned after the PPE store relaunch.",
        ),
        ComplianceAcknowledgement(
            document_title="Demo: Hot Work SOP",
            document_type="procedure",
            version="2.1",
            site_id=sites["DEMO-LSK-PLANT"].id,
            assigned_to_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            assigned_at=_at_day(base, -7, 9, 0),
            acknowledged_at=_at_day(base, -2, 16, 30),
            status=ComplianceAcknowledgementStatus.acknowledged,
            notes="Acknowledged ahead of the fabrication contractor restart.",
        ),
        ComplianceAcknowledgement(
            document_title="Demo: Contractor Access Procedure",
            document_type="procedure",
            version="1.4",
            site_id=sites["DEMO-SLZ-CAMP"].id,
            assigned_to_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            assigned_at=_at_day(base, -40, 8, 15),
            status=ComplianceAcknowledgementStatus.overdue,
            notes="Still overdue before the scheduled audit visit.",
        ),
        ComplianceAcknowledgement(
            document_title="Demo: Fatigue Management Guideline",
            document_type="guideline",
            version="1.1",
            site_id=sites["DEMO-SLZ-CAMP"].id,
            assigned_to_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_at=_at_day(base, -12, 7, 50),
            acknowledged_at=_at_day(base, -10, 13, 45),
            status=ComplianceAcknowledgementStatus.acknowledged,
            notes="Acknowledged before the camp night-shift rotation.",
        ),
        ComplianceAcknowledgement(
            document_title="Demo: Permit to Work Standard",
            document_type="standard",
            version="4.0",
            site_id=sites["DEMO-NDL-WH"].id,
            assigned_to_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            assigned_at=_at_day(base, -18, 8, 30),
            status=ComplianceAcknowledgementStatus.superseded,
            notes="Superseded by the new digital permit workflow release.",
        ),
    ]
    db.add_all(acknowledgements)
    db.flush()
    return {ack.document_title: ack for ack in acknowledgements}


def _create_permits(db: Session, sites: dict[str, Site], users: dict[str, User], base: datetime) -> dict[str, PermitToWork]:
    permits = [
        PermitToWork(
            permit_number="DEMO-PTW-001",
            permit_type=PermitType.hot_work,
            title="Demo: Structural welding on transfer chute",
            description="Temporary hot work for chute bracket reinforcement during the scheduled day shift outage.",
            site_id=sites["DEMO-LSK-PLANT"].id,
            area_location="Transfer tower bay 2",
            requested_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            issued_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            approved_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_team_or_contractor="Atlas Fabrication Services",
            start_datetime=_at_day(base, 1, 8, 0),
            end_datetime=_at_day(base, 1, 17, 0),
            status=PermitStatus.pending_approval,
            risk_summary="Arc flash, falling sparks, and nearby reagent handling.",
            precautions_required=["Fire watch", "Gas-free confirmation", "Spark curtains"],
            ppe_required=["Welding visor", "Leather gloves", "Flame-resistant overalls"],
            isolation_required=True,
            gas_test_required=False,
            gas_test_results=[],
            emergency_controls=["Extinguishers staged", "Dedicated standby person"],
            attachments_metadata=[_attachment("ptw-001-pack.pdf", label="Permit pack")],
        ),
        PermitToWork(
            permit_number="DEMO-PTW-002",
            permit_type=PermitType.confined_space,
            title="Demo: Silo inspection entry",
            description="Internal inspection of the additive silo before liner replacement.",
            site_id=sites["DEMO-LSK-PLANT"].id,
            area_location="Additive silo 3",
            requested_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            issued_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            approved_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            assigned_team_or_contractor="Internal maintenance team",
            start_datetime=_at_day(base, 0, 14, 0),
            end_datetime=_at_day(base, 1, 6, 0),
            status=PermitStatus.approved,
            risk_summary="Confined space entry with dust and oxygen monitoring requirements.",
            precautions_required=["Standby attendant", "Continuous gas test", "Entry log"],
            ppe_required=["Harness", "Respirator", "Helmet"],
            isolation_required=True,
            gas_test_required=True,
            gas_test_results=[_gas_test("O2", 20.9, "%"), _gas_test("LEL", 0.0)],
            emergency_controls=["Rescue tripod ready", "Radio checks every 10 minutes"],
            attachments_metadata=[_attachment("ptw-002-pack.pdf", label="Permit pack")],
        ),
        PermitToWork(
            permit_number="DEMO-PTW-003",
            permit_type=PermitType.electrical,
            title="Demo: Warehouse MCC isolation",
            description="Electrical isolation for feeder panel fault investigation during live warehouse operations.",
            site_id=sites["DEMO-NDL-WH"].id,
            area_location="Main MCC room",
            requested_by_user_id=users[f"chipo.lungu{DEMO_USER_DOMAIN}"].id,
            issued_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            approved_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_team_or_contractor="VoltSafe Electrical",
            start_datetime=_at_day(base, 0, 7, 0),
            end_datetime=_at_day(base, 0, 23, 0),
            status=PermitStatus.active,
            risk_summary="Arc flash, isolation lock integrity, and limited access during troubleshooting.",
            precautions_required=["LOTO applied", "Insulated tools", "Restricted access"],
            ppe_required=["Arc-rated face shield", "Electrical gloves", "Safety boots"],
            isolation_required=True,
            gas_test_required=False,
            gas_test_results=[],
            emergency_controls=["Emergency shutdown contact posted", "Standby electrician"],
            attachments_metadata=[_attachment("ptw-003-pack.pdf", label="Permit pack")],
        ),
        PermitToWork(
            permit_number="DEMO-PTW-004",
            permit_type=PermitType.excavation,
            title="Demo: Drainage trench excavation",
            description="Short excavation for stormwater drainage improvement beside the workshop access road.",
            site_id=sites["DEMO-SLZ-CAMP"].id,
            area_location="Workshop access road",
            requested_by_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            issued_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            approved_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            assigned_team_or_contractor="Copperbelt Civils",
            start_datetime=_at_day(base, -3, 7, 0),
            end_datetime=_at_day(base, -1, 17, 0),
            status=PermitStatus.expired,
            risk_summary="Underground services, vehicle interaction, and edge protection.",
            precautions_required=["Permit drawing on site", "Service scan", "Barricades installed"],
            ppe_required=["High-vis vest", "Helmet", "Safety boots"],
            isolation_required=False,
            gas_test_required=False,
            gas_test_results=[],
            emergency_controls=["Spotter assigned", "Backfill plan agreed"],
            attachments_metadata=[_attachment("ptw-004-pack.pdf", label="Permit pack")],
        ),
        PermitToWork(
            permit_number="DEMO-PTW-005",
            permit_type=PermitType.work_at_height,
            title="Demo: Roof sheet inspection above stores",
            description="Completed work-at-height inspection to verify the roof leak source above the camp stores area.",
            site_id=sites["DEMO-SLZ-CAMP"].id,
            area_location="Camp stores roof",
            requested_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            issued_by_user_id=users[f"emma.ncube{DEMO_USER_DOMAIN}"].id,
            approved_by_user_id=users[f"brian.phiri{DEMO_USER_DOMAIN}"].id,
            assigned_team_or_contractor="SkyAccess Maintenance",
            start_datetime=_at_day(base, -6, 8, 0),
            end_datetime=_at_day(base, -5, 13, 0),
            status=PermitStatus.closed,
            risk_summary="Fall exposure, ladder stability, and dropped objects near the stores entrance.",
            precautions_required=["Full body harness", "Tool lanyards", "Drop zone barricade"],
            ppe_required=["Harness", "Helmet", "Gloves"],
            isolation_required=False,
            gas_test_required=False,
            gas_test_results=[],
            emergency_controls=["Rescue plan briefed", "Ground spotter assigned"],
            closure_notes="Roof leak source identified and temporary seal applied.",
            closed_at=_at_day(base, -5, 14, 0),
            attachments_metadata=[_attachment("ptw-005-pack.pdf", label="Permit pack")],
        ),
    ]
    db.add_all(permits)
    db.flush()
    return {permit.permit_number: permit for permit in permits}


def _create_manual_notifications(
    db: Session, users: dict[str, User], inspections: dict[str, Inspection], base: datetime
) -> None:
    notifications = [
        Notification(
            recipient_user_id=users[f"grace.tembo{DEMO_USER_DOMAIN}"].id,
            title="Demo: Inspection assigned",
            message="Camp emergency response inspection has been assigned for today and includes two follow-up observations.",
            notification_type=NotificationType.inspection_assigned,
            severity=NotificationSeverity.info,
            related_entity_type=RelatedEntityType.inspection,
            related_entity_id=inspections["Demo: Camp emergency response inspection"].id,
            created_at=_at_day(base, 0, 8, 10),
        ),
        Notification(
            recipient_user_id=users[f"ruth.zulu{DEMO_USER_DOMAIN}"].id,
            title="Demo: Draft inspection due soon",
            message="Contractor pre-start verification is still in draft and needs completion before tomorrow's mobilisation.",
            notification_type=NotificationType.inspection_due_soon,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.inspection,
            related_entity_id=inspections["Demo: Contractor pre-start verification"].id,
            is_read=True,
            read_at=_at_day(base, 0, 9, 0),
            created_at=_at_day(base, 0, 7, 45),
        ),
    ]
    db.add_all(notifications)
    db.commit()


def _count_demo_records(db: Session) -> SeedSummary:
    demo_user_ids = list(
        db.scalars(select(User.id).where(User.email.like(f"%{DEMO_USER_DOMAIN}"))).all()
    )
    notifications = 0
    if demo_user_ids:
        notifications = db.scalar(
            select(func.count(Notification.id)).where(Notification.recipient_user_id.in_(demo_user_ids))
        ) or 0

    return SeedSummary(
        sites=db.scalar(select(func.count(Site.id)).where(Site.code.like(f"{DEMO_SITE_CODE_PREFIX}%"))) or 0,
        users=db.scalar(select(func.count(User.id)).where(User.email.like(f"%{DEMO_USER_DOMAIN}"))) or 0,
        incidents=db.scalar(select(func.count(Incident.id)).where(Incident.title.like(f"{DEMO_TITLE_PREFIX}%"))) or 0,
        hazards=db.scalar(select(func.count(Hazard.id)).where(Hazard.title.like(f"{DEMO_TITLE_PREFIX}%"))) or 0,
        inspections=db.scalar(select(func.count(Inspection.id)).where(Inspection.title.like(f"{DEMO_TITLE_PREFIX}%"))) or 0,
        corrective_actions=db.scalar(
            select(func.count(CorrectiveAction.id)).where(CorrectiveAction.title.like(f"{DEMO_TITLE_PREFIX}%"))
        ) or 0,
        training_records=db.scalar(
            select(func.count(TrainingRecord.id)).where(TrainingRecord.title.like(f"{DEMO_TITLE_PREFIX}%"))
        ) or 0,
        compliance_acknowledgements=db.scalar(
            select(func.count(ComplianceAcknowledgement.id)).where(
                ComplianceAcknowledgement.document_title.like(f"{DEMO_TITLE_PREFIX}%")
            )
        ) or 0,
        permits=db.scalar(
            select(func.count(PermitToWork.id)).where(PermitToWork.permit_number.like(f"{DEMO_PERMIT_PREFIX}%"))
        ) or 0,
        notifications=notifications,
    )


def seed_demo_data(db: Session) -> SeedSummary:
    base = _now()
    _delete_demo_rows(db)

    roles = _load_roles(db)
    users = _create_users(db, roles)
    sites = _create_sites(db, users)
    incidents = _create_incidents(db, sites, users, base)
    hazards = _create_hazards(db, sites, users, incidents, base)
    inspections = _create_inspections(db, sites, users, hazards, base)
    corrective_actions = _create_corrective_actions(db, sites, users, incidents, hazards, inspections, base)
    _create_training_records(db, sites, users, base)
    _create_compliance_acknowledgements(db, sites, users, base)
    permits = _create_permits(db, sites, users, base)
    db.commit()

    _create_manual_notifications(db, users, inspections, base)

    for incident in incidents.values():
        notify_critical_incident(db, incident)
    for hazard in hazards.values():
        notify_critical_hazard(db, hazard)
    for action in corrective_actions.values():
        notify_action_pending_verification(db, action)
    notify_permit_pending_approval(db, permits["DEMO-PTW-001"])
    generate_corrective_action_due_soon_notifications(db, days_ahead=7)
    generate_corrective_action_overdue_notifications(db)
    generate_overdue_training_notifications(db)
    generate_expired_training_notifications(db)
    generate_overdue_compliance_acknowledgement_notifications(db)
    generate_permit_nearing_expiry_notifications(db, hours_ahead=24)
    generate_permit_expired_notifications(db)

    return _count_demo_records(db)


def collect_demo_counts(db: Session) -> SeedSummary:
    return _count_demo_records(db)
