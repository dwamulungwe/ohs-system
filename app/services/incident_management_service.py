from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_register import AssetRegisterItem
from app.models.corrective_action import CorrectiveAction, CorrectiveActionPriority, CorrectiveActionSourceType, CorrectiveActionStatus
from app.models.hazard import Hazard
from app.models.incident import (
    Incident, IncidentActivity, IncidentCauseAnalysis, IncidentCauseCategory, IncidentClassification,
    IncidentClosureHistory, IncidentEnvironmentalDetail, IncidentEvent, IncidentFinding,
    IncidentInjury, IncidentLink, IncidentPerson, IncidentPropertyDamage,
    IncidentRegulatoryNotification, IncidentReminderDelivery, IncidentReturnToWork,
    IncidentSeverity, IncidentStatus, IncidentTreatment, IncidentVehicleDetail,
    IncidentWitnessStatement, RegulatoryNotificationStatus, ReturnToWorkStatus,
)
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.medical_surveillance import MedicalSurveillanceRecord
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.ppe import PPEInspection, PPEIssue
from app.models.sio import SafetyImprovementObservation
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.incident import (
    ClosureDecision, ClosureRequest, EnvironmentalDetailCreate, IncidentActionCreate,
    IncidentCauseCategoryCreate, IncidentCauseCreate, IncidentClassificationCreate,
    IncidentEventCreate, IncidentFindingCreate, IncidentInjuryCreate, IncidentLinkCreate,
    IncidentPersonCreate, IncidentTreatmentCreate, IncidentWitnessCreate,
    PropertyDamageCreate, RegulatoryNotificationCreate, ReopenRequest,
    ReturnToWorkCreate, ReturnToWorkUpdate, VehicleDetailCreate,
)
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.incident_service import add_activity, get_incident, incident_settings
from app.services.notification_service import create_notification_once
from app.services.tenancy import current_organisation_id


T = TypeVar("T")
COMPLETED_INVESTIGATION_STATUSES = {
    IncidentInvestigationStatus.completed, IncidentInvestigationStatus.approved,
    IncidentInvestigationStatus.closed, IncidentInvestigationStatus.not_required,
}
OPEN_INCIDENT_STATUSES = set(IncidentStatus) - {IncidentStatus.closed, IncidentStatus.cancelled}


class IncidentManagementError(Exception):
    pass


class IncidentClosureError(IncidentManagementError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _child(db: Session, model: type[T], record_id: int, incident_id: int) -> T:
    record = db.get(model, record_id)
    if record is None or getattr(record, "incident_id", None) != incident_id:
        raise IncidentManagementError("Incident child record not found")
    return record


def _audit_child(db: Session, incident: Incident, action: str, child, actor_id: Optional[int]) -> None:
    add_activity(db, incident, action, action.replace("_", " ").title(), actor_id=actor_id, metadata={"record_id": child.id})
    db.commit()
    db.refresh(child)
    write_audit_log(
        db, actor_id=actor_id, action=f"incident.{action}", resource_type="incident",
        resource_id=incident.id, details={"record_id": child.id},
    )


def list_classifications(db: Session) -> list[IncidentClassification]:
    return list(db.scalars(select(IncidentClassification).order_by(IncidentClassification.name)).all())


def create_classification(db: Session, payload: IncidentClassificationCreate) -> IncidentClassification:
    existing = db.scalar(select(IncidentClassification).where(IncidentClassification.code == payload.code))
    if existing:
        raise IncidentManagementError("Classification code already exists")
    record = IncidentClassification(**payload.model_dump(), is_system=False)
    db.add(record); db.commit(); db.refresh(record)
    return record


def list_cause_categories(db: Session) -> list[IncidentCauseCategory]:
    return list(db.scalars(select(IncidentCauseCategory).order_by(IncidentCauseCategory.level, IncidentCauseCategory.name)).all())


def create_cause_category(db: Session, payload: IncidentCauseCategoryCreate) -> IncidentCauseCategory:
    existing = db.scalar(select(IncidentCauseCategory).where(IncidentCauseCategory.code == payload.code))
    if existing:
        raise IncidentManagementError("Cause category code already exists")
    record = IncidentCauseCategory(**payload.model_dump(), is_system=False)
    db.add(record); db.commit(); db.refresh(record)
    return record


def create_person(db: Session, incident: Incident, payload: IncidentPersonCreate, actor_id: Optional[int]) -> IncidentPerson:
    data = payload.model_dump()
    for model, field in ((User, "user_id"),):
        if data.get(field) and db.get(model, data[field]) is None:
            raise IncidentManagementError("Referenced person not found")
    record = IncidentPerson(incident_id=incident.id, **data)
    db.add(record); db.flush(); _audit_child(db, incident, "person_added", record, actor_id)
    return record


def create_injury(db: Session, incident: Incident, payload: IncidentInjuryCreate, actor_id: Optional[int]) -> IncidentInjury:
    _child(db, IncidentPerson, payload.incident_person_id, incident.id)
    record = IncidentInjury(incident_id=incident.id, **payload.model_dump())
    db.add(record); db.flush()
    if payload.days_lost > 0:
        incident.is_lost_time = True; incident.is_recordable = True
    if payload.fatality:
        incident.incident_type = "fatality"; incident.severity = IncidentSeverity.critical; incident.is_recordable = True
    _audit_child(db, incident, "injury_recorded", record, actor_id)
    return record


def create_treatment(db: Session, incident: Incident, payload: IncidentTreatmentCreate, actor_id: Optional[int]) -> IncidentTreatment:
    _child(db, IncidentPerson, payload.incident_person_id, incident.id)
    data = payload.model_dump(exclude_none=True)
    if data.get("medical_surveillance_record_id") and db.get(MedicalSurveillanceRecord, data["medical_surveillance_record_id"]) is None:
        raise IncidentManagementError("Medical surveillance record not found")
    record = IncidentTreatment(incident_id=incident.id, **data)
    db.add(record); db.flush(); _audit_child(db, incident, "treatment_recorded", record, actor_id)
    return record


def create_witness(db: Session, incident: Incident, payload: IncidentWitnessCreate, actor_id: Optional[int]) -> IncidentWitnessStatement:
    data = payload.model_dump(exclude_none=True)
    if data.get("incident_person_id"):
        _child(db, IncidentPerson, data["incident_person_id"], incident.id)
    if data.get("witness_user_id") and db.get(User, data["witness_user_id"]) is None:
        raise IncidentManagementError("Witness user not found")
    data["statement_at"] = data.get("statement_at") or _now()
    if data.get("acknowledged"):
        data["acknowledged_at"] = _now()
    record = IncidentWitnessStatement(incident_id=incident.id, taken_by_user_id=actor_id, **data)
    db.add(record); db.flush(); _audit_child(db, incident, "witness_added", record, actor_id)
    return record


def create_event(db: Session, incident: Incident, payload: IncidentEventCreate, actor_id: Optional[int]) -> IncidentEvent:
    record = IncidentEvent(incident_id=incident.id, created_by_user_id=actor_id, **payload.model_dump())
    db.add(record); db.flush(); _audit_child(db, incident, "event_timeline_added", record, actor_id)
    return record


def create_cause(db: Session, incident: Incident, payload: IncidentCauseCreate, actor_id: Optional[int]) -> IncidentCauseAnalysis:
    data = payload.model_dump(mode="json")
    if data.get("investigation_id"):
        investigation = db.get(IncidentInvestigation, data["investigation_id"])
        if investigation is None or investigation.incident_id != incident.id:
            raise IncidentManagementError("Investigation not found")
    if data.get("category_code"):
        category = db.scalar(select(IncidentCauseCategory).where(IncidentCauseCategory.code == data["category_code"]))
        if category is None:
            raise IncidentManagementError("Cause category is not configured")
    if data.get("methodology") == "five_whys" and not data.get("why_steps"):
        raise IncidentManagementError("Five Whys requires at least one why step")
    record = IncidentCauseAnalysis(incident_id=incident.id, created_by_user_id=actor_id, **data)
    db.add(record); db.flush(); _audit_child(db, incident, "root_cause_added", record, actor_id)
    return record


def create_finding(db: Session, incident: Incident, payload: IncidentFindingCreate, actor_id: Optional[int]) -> IncidentFinding:
    data = payload.model_dump()
    if data.get("investigation_id"):
        investigation = db.get(IncidentInvestigation, data["investigation_id"])
        if investigation is None or investigation.incident_id != incident.id:
            raise IncidentManagementError("Investigation not found")
    if data.get("root_cause_id"):
        _child(db, IncidentCauseAnalysis, data["root_cause_id"], incident.id)
    record = IncidentFinding(incident_id=incident.id, created_by_user_id=actor_id, **data)
    db.add(record); db.flush(); _audit_child(db, incident, "finding_added", record, actor_id)
    return record


def create_incident_action(db: Session, incident: Incident, payload: IncidentActionCreate, actor_id: Optional[int]) -> CorrectiveAction:
    finding = None
    if payload.finding_id:
        finding = _child(db, IncidentFinding, payload.finding_id, incident.id)
    action = create_corrective_action(
        db,
        CorrectiveActionCreate(
            site_id=incident.site_id, department_id=incident.department_id,
            responsible_department_id=payload.responsible_department_id,
            title=payload.title, description=payload.description,
            acceptance_criteria=payload.acceptance_criteria,
            source_type=CorrectiveActionSourceType.incident, source_id=incident.id,
            source_metadata={
                "incident_reference": incident.incident_reference,
                "origin": payload.source_type,
                "finding_id": payload.finding_id,
                "backlink": f"/incidents/{incident.id}",
            },
            priority=CorrectiveActionPriority(payload.priority), owner_user_id=payload.owner_user_id,
            due_date=payload.due_date, current_due_date=payload.due_date,
        ),
        current_user_id=actor_id,
    )
    if finding:
        finding.unified_action_id = action.id; db.add(finding)
    add_activity(db, incident, "action_generated", f"Unified Action {action.action_reference} generated.", actor_id=actor_id, metadata={"action_id": action.id})
    db.commit()
    return action


def create_regulatory_notification(db: Session, incident: Incident, payload: RegulatoryNotificationCreate, actor_id: Optional[int]) -> IncidentRegulatoryNotification:
    data = payload.model_dump(exclude_none=True)
    if data.get("status") in {RegulatoryNotificationStatus.submitted, RegulatoryNotificationStatus.acknowledged}:
        data["notified_at"] = data.get("notified_at") or _now(); data["notified_by_user_id"] = actor_id
    record = IncidentRegulatoryNotification(incident_id=incident.id, **data)
    incident.regulator_notification_required = payload.notification_required
    incident.regulator_notification_status = payload.status
    db.add(record); db.add(incident); db.flush(); _audit_child(db, incident, "regulatory_notification_recorded", record, actor_id)
    return record


def create_return_to_work(db: Session, incident: Incident, payload: ReturnToWorkCreate, actor_id: Optional[int]) -> IncidentReturnToWork:
    _child(db, IncidentPerson, payload.incident_person_id, incident.id)
    existing = db.scalar(select(IncidentReturnToWork).where(IncidentReturnToWork.incident_id == incident.id, IncidentReturnToWork.incident_person_id == payload.incident_person_id))
    if existing:
        raise IncidentManagementError("Return-to-work record already exists for this person")
    data = payload.model_dump()
    if data.get("medical_surveillance_record_id") and db.get(MedicalSurveillanceRecord, data["medical_surveillance_record_id"]) is None:
        raise IncidentManagementError("Medical surveillance record not found")
    record = IncidentReturnToWork(incident_id=incident.id, reviewed_by_user_id=actor_id, reviewed_at=_now(), **data)
    db.add(record); db.flush(); _audit_child(db, incident, "return_to_work_created", record, actor_id)
    return record


def update_return_to_work(db: Session, incident: Incident, record_id: int, payload: ReturnToWorkUpdate, actor_id: Optional[int]) -> IncidentReturnToWork:
    record = _child(db, IncidentReturnToWork, record_id, incident.id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items(): setattr(record, field, value)
    if record.status == ReturnToWorkStatus.returned_to_work:
        record.actual_return_date = record.actual_return_date or date.today()
    record.reviewed_by_user_id = actor_id; record.reviewed_at = _now()
    db.add(record); db.flush(); _audit_child(db, incident, "return_to_work_updated", record, actor_id)
    return record


LINK_MODELS = {
    "hazard": Hazard, "sio": SafetyImprovementObservation, "ppe_issue": PPEIssue,
    "ppe_inspection": PPEInspection, "asset": AssetRegisterItem,
}


def create_link(db: Session, incident: Incident, payload: IncidentLinkCreate, actor_id: Optional[int]) -> IncidentLink:
    if db.get(LINK_MODELS[payload.linked_entity_type], payload.linked_entity_id) is None:
        raise IncidentManagementError("Linked record not found")
    record = IncidentLink(incident_id=incident.id, created_by_user_id=actor_id, **payload.model_dump())
    db.add(record); db.flush(); _audit_child(db, incident, "record_linked", record, actor_id)
    return record


def create_property_damage(db: Session, incident: Incident, payload: PropertyDamageCreate, actor_id: Optional[int]) -> IncidentPropertyDamage:
    if payload.asset_id and db.get(AssetRegisterItem, payload.asset_id) is None:
        raise IncidentManagementError("Asset not found")
    record = IncidentPropertyDamage(incident_id=incident.id, **payload.model_dump())
    db.add(record); db.flush(); _audit_child(db, incident, "property_damage_recorded", record, actor_id)
    return record


def upsert_environmental_detail(db: Session, incident: Incident, payload: EnvironmentalDetailCreate, actor_id: Optional[int]) -> IncidentEnvironmentalDetail:
    record = db.scalar(select(IncidentEnvironmentalDetail).where(IncidentEnvironmentalDetail.incident_id == incident.id))
    if record is None:
        record = IncidentEnvironmentalDetail(incident_id=incident.id, **payload.model_dump())
    else:
        for field, value in payload.model_dump().items(): setattr(record, field, value)
    db.add(record); db.flush(); _audit_child(db, incident, "environmental_detail_recorded", record, actor_id)
    return record


def upsert_vehicle_detail(db: Session, incident: Incident, payload: VehicleDetailCreate, actor_id: Optional[int]) -> IncidentVehicleDetail:
    if payload.vehicle_asset_id and db.get(AssetRegisterItem, payload.vehicle_asset_id) is None:
        raise IncidentManagementError("Vehicle asset not found")
    if payload.driver_person_id:
        _child(db, IncidentPerson, payload.driver_person_id, incident.id)
    record = db.scalar(select(IncidentVehicleDetail).where(IncidentVehicleDetail.incident_id == incident.id))
    if record is None:
        record = IncidentVehicleDetail(incident_id=incident.id, **payload.model_dump())
    else:
        for field, value in payload.model_dump().items(): setattr(record, field, value)
    db.add(record); db.flush(); _audit_child(db, incident, "vehicle_detail_recorded", record, actor_id)
    return record


def closure_blockers(db: Session, incident: Incident) -> list[str]:
    config = incident_settings(db)
    blockers = []
    investigation = db.scalar(select(IncidentInvestigation).where(IncidentInvestigation.incident_id == incident.id))
    required_severities = set(config.get("closure_require_investigation_for", ["high", "critical"]))
    classification = db.scalar(select(IncidentClassification).where(IncidentClassification.code == incident.incident_type))
    investigation_required = incident.severity.value in required_severities or bool(classification and classification.investigation_required)
    if investigation_required and (investigation is None or investigation.status not in COMPLETED_INVESTIGATION_STATUSES):
        blockers.append("investigation_not_completed")
    regulatory = list(db.scalars(select(IncidentRegulatoryNotification).where(IncidentRegulatoryNotification.incident_id == incident.id)).all())
    if incident.regulator_notification_required and not regulatory:
        blockers.append("regulatory_notification_missing")
    if any(item.notification_required and item.status not in {RegulatoryNotificationStatus.submitted, RegulatoryNotificationStatus.acknowledged} for item in regulatory):
        blockers.append("regulatory_notification_incomplete")
    injuries = list(db.scalars(select(IncidentInjury).where(IncidentInjury.incident_id == incident.id)).all())
    if config.get("require_medical_follow_up_completion", True):
        treatments = list(db.scalars(select(IncidentTreatment).where(IncidentTreatment.incident_id == incident.id)).all())
        for treatment in treatments:
            if not treatment.follow_up_required:
                continue
            follow_up = db.get(MedicalSurveillanceRecord, treatment.medical_surveillance_record_id) if treatment.medical_surveillance_record_id else None
            if follow_up is None or getattr(getattr(follow_up, "status", None), "value", getattr(follow_up, "status", None)) != "completed":
                blockers.append("medical_follow_up_incomplete")
                break
    rtw = list(db.scalars(select(IncidentReturnToWork).where(IncidentReturnToWork.incident_id == incident.id)).all())
    if any(item.days_lost > 0 or item.restricted_work_days > 0 for item in injuries):
        handled_ids = {item.incident_person_id for item in rtw if item.status in {ReturnToWorkStatus.not_required, ReturnToWorkStatus.returned_to_work}}
        if any(item.incident_person_id not in handled_ids for item in injuries if item.days_lost > 0 or item.restricted_work_days > 0):
            blockers.append("return_to_work_incomplete")
    actions = list(db.scalars(select(CorrectiveAction).where(CorrectiveAction.source_type == CorrectiveActionSourceType.incident, CorrectiveAction.source_id == incident.id)).all())
    requirement = config.get("action_closure_requirement", "critical_closed")
    if requirement == "all_closed" and any(a.status != CorrectiveActionStatus.closed for a in actions):
        blockers.append("actions_not_closed")
    elif requirement == "critical_closed" and any(a.priority == CorrectiveActionPriority.critical and a.status != CorrectiveActionStatus.closed for a in actions):
        blockers.append("critical_actions_not_closed")
    elif requirement == "assigned_plan" and any(a.owner_user_id is None or a.current_due_date is None for a in actions):
        blockers.append("action_closure_plan_incomplete")
    return blockers


def request_closure(db: Session, incident: Incident, payload: ClosureRequest, actor_id: Optional[int]) -> Incident:
    config = incident_settings(db)
    if config.get("require_lessons_learned", True) and not payload.lessons_learned:
        raise IncidentClosureError("Incident cannot be closed: lessons_learned_incomplete")
    blockers = closure_blockers(db, incident)
    if blockers:
        raise IncidentClosureError("Incident cannot be closed: " + ", ".join(blockers))
    incident.closure_requested_by_user_id = actor_id
    incident.closure_requested_at = _now(); incident.closure_summary = payload.closure_summary
    incident.lessons_learned = payload.lessons_learned; incident.closure_verifier_user_id = payload.verifier_user_id
    if not config.get("closure_verification_required", True):
        incident.closure_requested = False
        incident.status = IncidentStatus.closed
        incident.closed_at = _now(); incident.closed_by_user_id = actor_id
        incident.verified_at = incident.closed_at
        history = IncidentClosureHistory(
            incident_id=incident.id, decision="approved", requested_by_user_id=actor_id,
            verifier_user_id=actor_id, summary=payload.closure_summary,
            notes="Closure verification was disabled by organisation configuration.",
        )
        db.add_all([incident, history]); add_activity(db, incident, "incident_closed", "Incident closed under configured direct-closure policy.", actor_id=actor_id)
        db.commit(); db.refresh(incident)
        return incident
    incident.closure_requested = True
    incident.status = IncidentStatus.pending_closure
    history = IncidentClosureHistory(incident_id=incident.id, decision="requested", requested_by_user_id=actor_id, verifier_user_id=payload.verifier_user_id, summary=payload.closure_summary)
    db.add_all([incident, history]); add_activity(db, incident, "closure_requested", "Incident closure requested.", actor_id=actor_id)
    db.commit(); db.refresh(incident)
    if payload.verifier_user_id:
        create_notification_once(db, NotificationCreate(
            recipient_user_id=payload.verifier_user_id,
            title="Incident closure verification required",
            message=f"{incident.incident_reference} is awaiting closure verification.",
            notification_type=NotificationType.incident_closure_verification,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.incident,
            related_entity_id=incident.id,
        ))
    return incident


def verify_closure(db: Session, incident: Incident, payload: ClosureDecision, actor_id: Optional[int]) -> Incident:
    if not incident.closure_requested:
        raise IncidentClosureError("Incident closure has not been requested")
    config = incident_settings(db)
    if config.get("independent_closure_verifier", True) and actor_id == incident.closure_requested_by_user_id:
        raise IncidentClosureError("Closure must be independently verified")
    blockers = closure_blockers(db, incident) if payload.approved else []
    if blockers:
        raise IncidentClosureError("Incident cannot be closed: " + ", ".join(blockers))
    now = _now(); incident.verification_notes = payload.notes; incident.closure_verifier_user_id = actor_id; incident.verified_at = now
    if payload.approved:
        incident.status = IncidentStatus.closed; incident.closed_at = now; incident.closed_by_user_id = actor_id
        decision = "approved"; event = "incident_closed"
    else:
        incident.status = IncidentStatus.under_investigation; decision = "rejected"; event = "closure_rejected"
    incident.closure_requested = False
    db.add(IncidentClosureHistory(incident_id=incident.id, decision=decision, requested_by_user_id=incident.closure_requested_by_user_id, verifier_user_id=actor_id, summary=incident.closure_summary, notes=payload.notes))
    db.add(incident); add_activity(db, incident, event, f"Closure {decision}.", actor_id=actor_id)
    db.commit(); db.refresh(incident)
    write_audit_log(db, actor_id=actor_id, action=f"incident.closure.{decision}", resource_type="incident", resource_id=incident.id, details={})
    recipient = incident.reported_by_id if payload.approved else incident.closure_requested_by_user_id
    if recipient:
        create_notification_once(db, NotificationCreate(
            recipient_user_id=recipient,
            title="Incident closed" if payload.approved else "Incident closure rejected",
            message=f"Closure for {incident.incident_reference} was {decision}.",
            notification_type=NotificationType.incident_closed if payload.approved else NotificationType.incident_closure_rejected,
            severity=NotificationSeverity.info if payload.approved else NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.incident,
            related_entity_id=incident.id,
        ))
    return incident


def reopen_incident(db: Session, incident: Incident, payload: ReopenRequest, actor_id: Optional[int]) -> Incident:
    if incident.status != IncidentStatus.closed:
        raise IncidentClosureError("Only closed incidents can be reopened")
    incident.status = IncidentStatus.reopened; incident.reopen_reason = payload.reason
    incident.reopened_by_user_id = actor_id; incident.reopened_at = _now()
    db.add(IncidentClosureHistory(incident_id=incident.id, decision="reopened", verifier_user_id=actor_id, notes=payload.reason))
    db.add(incident); add_activity(db, incident, "incident_reopened", "Incident reopened.", actor_id=actor_id, metadata={"reason": payload.reason})
    db.commit(); db.refresh(incident)
    if incident.reported_by_id:
        create_notification_once(db, NotificationCreate(
            recipient_user_id=incident.reported_by_id,
            title="Incident reopened", message=f"{incident.incident_reference} was reopened.",
            notification_type=NotificationType.incident_reopened,
            severity=NotificationSeverity.warning,
            related_entity_type=RelatedEntityType.incident, related_entity_id=incident.id,
        ))
    return incident


def incident_dashboard(db: Session, *, site_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
    statement = select(Incident)
    if site_id: statement = statement.where(Incident.site_id == site_id)
    if date_from: statement = statement.where(Incident.occurred_at >= datetime.combine(date_from, datetime.min.time(), timezone.utc))
    if date_to: statement = statement.where(Incident.occurred_at <= datetime.combine(date_to, datetime.max.time(), timezone.utc))
    incidents = list(db.scalars(statement).all())
    ids = [i.id for i in incidents]
    investigations = list(db.scalars(select(IncidentInvestigation).where(IncidentInvestigation.incident_id.in_(ids))).all()) if ids else []
    causes = list(db.scalars(select(IncidentCauseAnalysis).where(IncidentCauseAnalysis.incident_id.in_(ids))).all()) if ids else []
    links = list(db.scalars(select(IncidentLink).where(IncidentLink.incident_id.in_(ids), IncidentLink.linked_entity_type.in_(["ppe_issue", "ppe_inspection"]))).all()) if ids else []
    closed_durations = [(i.closed_at - i.reported_at).total_seconds() / 86400 for i in incidents if i.closed_at and i.reported_at]
    investigation_durations = [(i.completed_at - (i.investigation_started_at or i.assigned_at or i.created_at)).total_seconds() / 86400 for i in investigations if i.completed_at]
    lti_dates = [i.occurred_at.date() for i in incidents if i.is_lost_time]
    def counts(items, getter): return dict(Counter(str(getter(item) or "unassigned") for item in items))
    ppe_missing = {link.incident_id for link in links if (link.involvement or {}).get("ppe_missing")}
    ppe_failed = {link.incident_id for link in links if (link.involvement or {}).get("ppe_failed")}
    return {
        "incidents_this_period": len(incidents), "open_incidents": sum(i.status in OPEN_INCIDENT_STATUSES for i in incidents),
        "open_investigations": sum(i.status not in COMPLETED_INVESTIGATION_STATUSES for i in investigations),
        "overdue_investigations": sum(i.is_overdue for i in investigations),
        "awaiting_closure": sum(i.status == IncidentStatus.pending_closure for i in incidents),
        "days_since_last_lti": (date.today() - max(lti_dates)).days if lti_dates else None,
        "average_investigation_duration_days": round(mean(investigation_durations), 2) if investigation_durations else 0,
        "average_incident_closure_days": round(mean(closed_durations), 2) if closed_durations else 0,
        "by_classification": counts(incidents, lambda x: x.incident_type),
        "by_severity": counts(incidents, lambda x: x.severity.value), "by_status": counts(incidents, lambda x: x.status.value),
        "by_site": counts(incidents, lambda x: x.site_id), "by_department": counts(incidents, lambda x: x.department_id),
        "top_immediate_causes": counts([c for c in causes if c.cause_level == "immediate"], lambda x: x.category_code or x.description),
        "top_root_causes": counts([c for c in causes if c.is_root_cause or c.cause_level == "root"], lambda x: x.category_code or x.description),
        "ppe_missing_incidents": len(ppe_missing), "ppe_failed_incidents": len(ppe_failed),
    }


def generate_incident_reminders(db: Session) -> dict[str, int]:
    now = _now(); today = now.date(); counts = Counter()
    investigations = list(db.scalars(select(IncidentInvestigation).where(IncidentInvestigation.target_completion_date.is_not(None))).all())
    for inv in investigations:
        if inv.status in COMPLETED_INVESTIGATION_STATUSES or not inv.investigation_lead_user_id: continue
        days = (inv.target_completion_date - today).days
        milestone = "investigation_overdue" if days < 0 else "investigation_due" if days in set(incident_settings(db).get("investigation_reminder_days", [7, 3, 1])) else None
        if milestone and _deliver_reminder(db, "investigation", inv.id, inv.investigation_lead_user_id, milestone, inv.target_completion_date):
            create_notification_once(db, NotificationCreate(recipient_user_id=inv.investigation_lead_user_id, title="Investigation overdue" if days < 0 else "Investigation due soon", message=f"Incident investigation #{inv.id} is due {inv.target_completion_date}.", notification_type=NotificationType.investigation_overdue if days < 0 else NotificationType.investigation_due, severity=NotificationSeverity.critical if days < 0 else NotificationSeverity.warning, related_entity_type=RelatedEntityType.incident_investigation, related_entity_id=inv.id)); counts[milestone] += 1
    regulatory = list(db.scalars(select(IncidentRegulatoryNotification).where(IncidentRegulatoryNotification.notification_deadline.is_not(None))).all())
    for item in regulatory:
        if item.status in {RegulatoryNotificationStatus.submitted, RegulatoryNotificationStatus.acknowledged, RegulatoryNotificationStatus.not_required}: continue
        incident = get_incident(db, item.incident_id); recipient = incident.responsible_hs_officer_user_id or incident.supervisor_user_id
        if not recipient: continue
        due = item.notification_deadline.date(); days = (due - today).days
        milestone = "regulator_overdue" if days < 0 else "regulator_due" if days in set(incident_settings(db).get("regulator_reminder_days", [7, 3, 1])) else None
        if days < 0 and item.status != RegulatoryNotificationStatus.overdue:
            item.status = RegulatoryNotificationStatus.overdue
            incident.regulator_notification_status = RegulatoryNotificationStatus.overdue
            db.add_all([item, incident]); db.commit()
        if milestone and _deliver_reminder(db, "regulatory", item.id, recipient, milestone, due):
            create_notification_once(db, NotificationCreate(recipient_user_id=recipient, title="Regulator notification overdue" if days < 0 else "Regulator notification due soon", message=f"{item.regulator_name} notification for {incident.incident_reference} is due {due}.", notification_type=NotificationType.regulator_notification_overdue if days < 0 else NotificationType.regulator_notification_due, severity=NotificationSeverity.critical if days < 0 else NotificationSeverity.warning, related_entity_type=RelatedEntityType.incident, related_entity_id=incident.id)); counts[milestone] += 1
    rtw_records = list(db.scalars(select(IncidentReturnToWork).where(IncidentReturnToWork.review_due_date.is_not(None))).all())
    for item in rtw_records:
        if item.status in {ReturnToWorkStatus.not_required, ReturnToWorkStatus.returned_to_work} or not item.reviewed_by_user_id:
            continue
        due = item.review_due_date
        if due > today + timedelta(days=3):
            continue
        if _deliver_reminder(db, "return_to_work", item.id, item.reviewed_by_user_id, "return_to_work_review_due", due):
            create_notification_once(db, NotificationCreate(
                recipient_user_id=item.reviewed_by_user_id,
                title="Return-to-work review required",
                message=f"Return-to-work record #{item.id} requires review by {due}.",
                notification_type=NotificationType.return_to_work_review_due,
                severity=NotificationSeverity.critical if due < today else NotificationSeverity.warning,
                related_entity_type=RelatedEntityType.incident,
                related_entity_id=item.incident_id,
            ))
            counts["return_to_work_review_due"] += 1
    return dict(counts)


def _deliver_reminder(db: Session, entity_type: str, entity_id: int, recipient_id: int, milestone: str, due: date) -> bool:
    exists = db.scalar(select(IncidentReminderDelivery).where(IncidentReminderDelivery.entity_type == entity_type, IncidentReminderDelivery.entity_id == entity_id, IncidentReminderDelivery.recipient_user_id == recipient_id, IncidentReminderDelivery.milestone_key == milestone, IncidentReminderDelivery.due_date_snapshot == due))
    if exists: return False
    db.add(IncidentReminderDelivery(entity_type=entity_type, entity_id=entity_id, recipient_user_id=recipient_id, milestone_key=milestone, due_date_snapshot=due)); db.commit()
    return True
