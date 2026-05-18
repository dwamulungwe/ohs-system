from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.approval import ApprovalActionType, ApprovalStatus, ApprovalWorkflow
from app.models.asset_register import AssetConditionStatus, AssetRegisterItem
from app.models.audit_management import AuditManagementRecord, AuditStatus
from app.models.behaviour_observation import (
    BehaviourObservation,
    BehaviourObservationStatus,
    BehaviourObservationType,
)
from app.models.contractor import (
    ContractorComplianceDocumentsStatus,
    ContractorInductionStatus,
    ContractorRecord,
)
from app.models.corrective_action import CorrectiveAction, CorrectiveActionPriority, CorrectiveActionStatus
from app.models.document_control import DocumentControlRecord, DocumentStatus
from app.models.emergency_drill import EmergencyDrillRecord, EmergencyDrillStatus
from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.inspection import Inspection, InspectionOverallResult, InspectionStatus
from app.models.jsa import JSAStatus, JobSafetyAnalysis
from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.medical_surveillance import (
    MedicalClearanceStatus,
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
)
from app.models.permit import PermitStatus, PermitToWork, PermitType
from app.models.safety_communication import (
    SafetyCommunication,
    SafetyCommunicationStatus,
    SafetyCommunicationType,
)
from app.models.safety_kpi import SafetyKPIRecord
from app.models.site import Site
from app.models.training import (
    ComplianceAcknowledgement,
    ComplianceAcknowledgementStatus,
    TrainingRecord,
    TrainingStatus,
)
from app.services.query_utils import is_corrective_action_overdue


DUE_SOON_DAYS = 7
TRIFR_LTIFR_MULTIPLIER = 1_000_000
ACTIVE_PERMIT_EXPIRY_STATUSES = {PermitStatus.approved, PermitStatus.active, PermitStatus.suspended}
OPEN_INCIDENT_STATUSES = {IncidentStatus.open, IncidentStatus.investigating}
OPEN_ACTION_STATUSES = {
    CorrectiveActionStatus.open,
    CorrectiveActionStatus.in_progress,
    CorrectiveActionStatus.pending_verification,
    CorrectiveActionStatus.overdue,
}
OPEN_BEHAVIOUR_ISSUE_TYPES = {
    BehaviourObservationType.unsafe_act,
    BehaviourObservationType.conduct_issue,
    BehaviourObservationType.event_safety_observation,
}
OPEN_INVESTIGATION_STATUSES = {
    IncidentInvestigationStatus.draft,
    IncidentInvestigationStatus.in_progress,
    IncidentInvestigationStatus.pending_approval,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _site_lookup(db: Session) -> dict[int, str]:
    return {site.id: site.name for site in db.scalars(select(Site)).all()}


def _site_name(site_lookup: dict[int, str], site_id: Optional[int]) -> Optional[str]:
    if site_id is None:
        return None
    return site_lookup.get(site_id)


def _record_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _within_date_range(value, date_from: Optional[date], date_to: Optional[date]) -> bool:
    record_date = _record_date(value)
    if record_date is None:
        return False
    if date_from is not None and record_date < date_from:
        return False
    if date_to is not None and record_date > date_to:
        return False
    return True


def _records(
    db: Session,
    model,
    *,
    site_id: Optional[int] = None,
    date_attr: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list:
    statement = select(model)
    if site_id is not None and hasattr(model, "site_id"):
        statement = statement.where(model.site_id == site_id)
    records = list(db.scalars(statement).all())
    if date_attr is None:
        return records
    return [
        record
        for record in records
        if _within_date_range(getattr(record, date_attr), date_from, date_to)
    ]


def _zero_counts(enum_cls) -> dict[str, int]:
    return {item.value: 0 for item in enum_cls}


def _count_by(records: Iterable, attr: str, enum_cls) -> dict[str, int]:
    counts = _zero_counts(enum_cls)
    for record in records:
        value = getattr(record, attr)
        key = value.value if hasattr(value, "value") else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _month_key(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%Y-%m")


def _month_counts(records: Iterable, attr: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        key = _month_key(getattr(record, attr))
        if key is not None:
            counts[key] += 1
    return dict(sorted(counts.items()))


def _frequency_rate(incidents_count: int, hours_worked: float) -> float:
    if hours_worked <= 0:
        return 0.0
    return round((incidents_count * TRIFR_LTIFR_MULTIPLIER) / hours_worked, 2)


def _incident_frequency_counts(incidents: list[Incident]) -> tuple[int, int]:
    recordable_incidents = sum(1 for incident in incidents if incident.is_recordable or incident.is_lost_time)
    lost_time_incidents = sum(1 for incident in incidents if incident.is_lost_time)
    return recordable_incidents, lost_time_incidents


def _kpi_snapshot(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    kpi_records = _records(
        db,
        SafetyKPIRecord,
        site_id=site_id,
        date_attr="period_end",
        date_from=date_from,
        date_to=date_to,
    )
    incidents = _records(
        db,
        Incident,
        site_id=site_id,
        date_attr="occurred_at",
        date_from=date_from,
        date_to=date_to,
    )
    total_hours_worked = round(sum(record.hours_worked for record in kpi_records), 2)
    recordable_incidents, lost_time_incidents = _incident_frequency_counts(incidents)
    return {
        "total_hours_worked": total_hours_worked,
        "recordable_incidents": recordable_incidents,
        "lost_time_incidents": lost_time_incidents,
        "trifr": _frequency_rate(recordable_incidents, total_hours_worked),
        "ltifr": _frequency_rate(lost_time_incidents, total_hours_worked),
    }


def _communication_item(communication: SafetyCommunication, site_lookup: dict[int, str]) -> dict:
    return {
        "id": communication.id,
        "title": communication.title,
        "site_id": communication.site_id,
        "site_name": _site_name(site_lookup, communication.site_id),
        "communication_type": communication.communication_type.value,
        "status": communication.status.value,
        "issued_at": communication.issued_at,
    }


def _communication_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    site_lookup = _site_lookup(db)
    communications = _records(
        db,
        SafetyCommunication,
        site_id=site_id,
        date_attr="issued_at",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "published_communications_count": sum(
            1 for item in communications if item.status == SafetyCommunicationStatus.published
        ),
        "active_campaigns_count": sum(
            1
            for item in communications
            if item.communication_type == SafetyCommunicationType.campaign
            and item.status == SafetyCommunicationStatus.published
        ),
        "toolbox_talks_count": sum(
            1 for item in communications if item.communication_type == SafetyCommunicationType.toolbox_talk
        ),
        "safety_alerts_count": sum(
            1 for item in communications if item.communication_type == SafetyCommunicationType.safety_alert
        ),
        "communication_status_distribution": _count_by(
            communications,
            "status",
            SafetyCommunicationStatus,
        ),
        "communication_type_distribution": _count_by(
            communications,
            "communication_type",
            SafetyCommunicationType,
        ),
        "recent_communications": [
            _communication_item(item, site_lookup)
            for item in sorted(communications, key=lambda entry: (entry.issued_at, entry.id), reverse=True)[:5]
        ],
    }


def _behaviour_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    observations = _records(
        db,
        BehaviourObservation,
        site_id=site_id,
        date_attr="observed_at",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "total_observations": len(observations),
        "unsafe_acts_count": sum(
            1 for item in observations if item.observation_type == BehaviourObservationType.unsafe_act
        ),
        "positive_observations_count": sum(
            1
            for item in observations
            if item.observation_type == BehaviourObservationType.positive_observation
        ),
        "open_behaviour_issues_count": sum(
            1
            for item in observations
            if item.observation_type in OPEN_BEHAVIOUR_ISSUE_TYPES
            and item.status != BehaviourObservationStatus.closed
        ),
        "behaviour_observation_type_distribution": _count_by(
            observations,
            "observation_type",
            BehaviourObservationType,
        ),
        "behaviour_observation_status_distribution": _count_by(
            observations,
            "status",
            BehaviourObservationStatus,
        ),
    }


def _investigation_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    investigations = _records(
        db,
        IncidentInvestigation,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "open_investigations_count": sum(
            1 for item in investigations if item.status in OPEN_INVESTIGATION_STATUSES
        ),
        "pending_investigation_approvals_count": sum(
            1 for item in investigations if item.status == IncidentInvestigationStatus.pending_approval
        ),
        "investigation_status_distribution": _count_by(
            investigations,
            "status",
            IncidentInvestigationStatus,
        ),
    }


def _legal_compliance_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    items = _records(
        db,
        LegalComplianceItem,
        site_id=site_id,
        date_attr="next_review_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    due_soon_by = today + timedelta(days=DUE_SOON_DAYS)
    return {
        "non_compliant_items_count": sum(
            1 for item in items if item.compliance_status == LegalComplianceStatus.non_compliant
        ),
        "legal_reviews_due_soon_count": sum(
            1
            for item in items
            if item.next_review_date is not None and today <= item.next_review_date <= due_soon_by
        ),
        "legal_reviews_overdue_count": sum(
            1 for item in items if item.next_review_date is not None and item.next_review_date < today
        ),
        "legal_compliance_status_distribution": _count_by(
            items,
            "compliance_status",
            LegalComplianceStatus,
        ),
    }


def _jsa_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    jsas = _records(
        db,
        JobSafetyAnalysis,
        site_id=site_id,
        date_attr="review_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    return {
        "pending_jsa_approvals_count": sum(1 for item in jsas if item.status == JSAStatus.pending_approval),
        "jsas_due_review_count": sum(
            1
            for item in jsas
            if item.review_date is not None and today <= item.review_date <= today + timedelta(days=DUE_SOON_DAYS)
        ),
        "jsas_expired_count": sum(
            1
            for item in jsas
            if item.status == JSAStatus.expired or (item.review_date is not None and item.review_date < today)
        ),
        "jsa_status_distribution": _count_by(jsas, "status", JSAStatus),
    }


def _contractor_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    contractors = _records(
        db,
        ContractorRecord,
        site_id=site_id,
        date_attr="insurance_expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    due_soon_by = today + timedelta(days=14)
    return {
        "contractor_compliance_gaps_count": sum(
            1
            for item in contractors
            if item.induction_status != ContractorInductionStatus.completed
            or item.compliance_documents_status != ContractorComplianceDocumentsStatus.complete
            or (item.insurance_expiry_date is not None and item.insurance_expiry_date < today)
            or (item.documents_expiry_date is not None and item.documents_expiry_date < today)
        ),
        "contractors_pending_approval_count": sum(1 for item in contractors if not item.approved_for_work),
        "insurance_expiring_soon_count": sum(
            1
            for item in contractors
            if item.insurance_expiry_date is not None and today <= item.insurance_expiry_date <= due_soon_by
        ),
        "documents_expiring_soon_count": sum(
            1
            for item in contractors
            if item.documents_expiry_date is not None and today <= item.documents_expiry_date <= due_soon_by
        ),
    }


def _asset_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    assets = _records(
        db,
        AssetRegisterItem,
        site_id=site_id,
        date_attr="next_inspection_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    due_soon_by = today + timedelta(days=DUE_SOON_DAYS)
    return {
        "defective_assets_count": sum(
            1 for item in assets if item.condition_status == AssetConditionStatus.defective
        ),
        "assets_due_inspection_count": sum(
            1
            for item in assets
            if item.next_inspection_date is not None and today <= item.next_inspection_date <= due_soon_by
        ),
        "overdue_asset_inspections_count": sum(
            1 for item in assets if item.next_inspection_date is not None and item.next_inspection_date < today
        ),
        "asset_condition_distribution": _count_by(
            assets,
            "condition_status",
            AssetConditionStatus,
        ),
    }


def _medical_surveillance_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    records = _records(
        db,
        MedicalSurveillanceRecord,
        site_id=site_id,
        date_attr="due_date",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "due_count": sum(1 for item in records if item.status == MedicalSurveillanceStatus.due),
        "overdue_count": sum(1 for item in records if item.status == MedicalSurveillanceStatus.overdue),
        "completed_count": sum(1 for item in records if item.status == MedicalSurveillanceStatus.completed),
        "medical_clearance_distribution": _count_by(
            records,
            "medical_clearance_status",
            MedicalClearanceStatus,
        ),
    }


def _emergency_drill_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    drills = _records(
        db,
        EmergencyDrillRecord,
        site_id=site_id,
        date_attr="drill_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    return {
        "upcoming_drills_count": sum(
            1
            for item in drills
            if item.status == EmergencyDrillStatus.scheduled
            and today <= item.drill_date <= today + timedelta(days=14)
        ),
        "overdue_drills_count": sum(1 for item in drills if item.status == EmergencyDrillStatus.overdue),
        "completed_drills_count": sum(1 for item in drills if item.status == EmergencyDrillStatus.completed),
        "drill_status_distribution": _count_by(drills, "status", EmergencyDrillStatus),
    }


def _document_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    documents = _records(
        db,
        DocumentControlRecord,
        site_id=site_id,
        date_attr="expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    due_soon_by = today + timedelta(days=14)
    return {
        "pending_document_approvals_count": sum(
            1 for item in documents if item.status == DocumentStatus.pending_approval
        ),
        "documents_expiring_soon_count": sum(
            1
            for item in documents
            if item.expiry_date is not None and today <= item.expiry_date <= due_soon_by
        ),
        "expired_documents_count": sum(
            1
            for item in documents
            if item.status == DocumentStatus.expired
            or (item.expiry_date is not None and item.expiry_date < today)
        ),
        "document_status_distribution": _count_by(documents, "status", DocumentStatus),
    }


def _audit_management_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    audits = _records(
        db,
        AuditManagementRecord,
        site_id=site_id,
        date_attr="audit_date",
        date_from=date_from,
        date_to=date_to,
    )
    audit_scores = [item.audit_score for item in audits if item.audit_score is not None]
    average_score = round(sum(audit_scores) / len(audit_scores), 2) if audit_scores else 0.0
    return {
        "open_audits_count": sum(1 for item in audits if item.status == AuditStatus.open),
        "closed_audits_count": sum(1 for item in audits if item.status == AuditStatus.closed),
        "average_audit_score": average_score,
        "audit_status_distribution": _count_by(audits, "status", AuditStatus),
    }


def _monthly_kpi_rates(
    db: Session,
    kpi_records: list[SafetyKPIRecord],
) -> tuple[dict[str, float], dict[str, float]]:
    per_month: dict[str, dict[str, float]] = {}
    for record in kpi_records:
        month = _month_key(
            datetime.combine(record.period_end, time.min, tzinfo=timezone.utc)
        )
        if month is None:
            continue
        metrics = _incident_frequency_counts(
            db.scalars(
                select(Incident).where(
                    Incident.site_id == record.site_id,
                    Incident.occurred_at >= datetime.combine(record.period_start, time.min, tzinfo=timezone.utc),
                    Incident.occurred_at <= datetime.combine(record.period_end, time.max, tzinfo=timezone.utc),
                )
            ).all()
        )
        month_bucket = per_month.setdefault(
            month,
            {"hours_worked": 0.0, "recordable_incidents": 0.0, "lost_time_incidents": 0.0},
        )
        month_bucket["hours_worked"] += record.hours_worked
        month_bucket["recordable_incidents"] += metrics[0]
        month_bucket["lost_time_incidents"] += metrics[1]

    trifr_by_month = {
        month: _frequency_rate(int(values["recordable_incidents"]), values["hours_worked"])
        for month, values in sorted(per_month.items())
    }
    ltifr_by_month = {
        month: _frequency_rate(int(values["lost_time_incidents"]), values["hours_worked"])
        for month, values in sorted(per_month.items())
    }
    return trifr_by_month, ltifr_by_month


def _derive_hazard_category(hazard: Hazard) -> str:
    title = (hazard.title or "").strip().lower()
    for delimiter in (":", " - ", "/", "|"):
        if delimiter in title:
            title = title.split(delimiter, 1)[0].strip()
            break
    tokens = [token for token in re.split(r"[\s_-]+", title) if token]
    if not tokens:
        return "uncategorized"
    return " ".join(tokens[:2])


def _risk_site_rankings(hazards: list[Hazard], site_lookup: dict[int, str]) -> list[dict]:
    per_site: dict[int, dict] = {}
    for hazard in hazards:
        if hazard.site_id is None:
            continue
        site_summary = per_site.setdefault(
            hazard.site_id,
            {
                "site_id": hazard.site_id,
                "site_name": _site_name(site_lookup, hazard.site_id) or f"Site #{hazard.site_id}",
                "open_critical_hazards_count": 0,
                "open_high_hazards_count": 0,
                "hazards_pending_review_count": 0,
                "aggregate_risk_score": 0,
            },
        )
        if hazard.status == HazardStatus.open and hazard.risk_level == HazardRiskLevel.critical:
            site_summary["open_critical_hazards_count"] += 1
        if hazard.status == HazardStatus.open and hazard.risk_level == HazardRiskLevel.high:
            site_summary["open_high_hazards_count"] += 1
        if (
            hazard.status != HazardStatus.closed
            and hazard.risk_level in {HazardRiskLevel.high, HazardRiskLevel.critical}
            and hazard.reviewed_at is None
        ):
            site_summary["hazards_pending_review_count"] += 1
        site_summary["aggregate_risk_score"] += hazard.risk_score

    return sorted(
        per_site.values(),
        key=lambda item: (
            -item["open_critical_hazards_count"],
            -item["open_high_hazards_count"],
            -item["hazards_pending_review_count"],
            -item["aggregate_risk_score"],
            item["site_name"],
        ),
    )[:5]


def _risk_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    site_lookup = _site_lookup(db)
    hazards = _records(
        db,
        Hazard,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    pending_review_hazards = [
        hazard
        for hazard in hazards
        if hazard.status != HazardStatus.closed
        and hazard.risk_level in {HazardRiskLevel.high, HazardRiskLevel.critical}
        and hazard.reviewed_at is None
    ]
    critical_pending_review = [
        {
            "id": hazard.id,
            "title": hazard.title,
            "site_id": hazard.site_id,
            "site_name": _site_name(site_lookup, hazard.site_id),
            "risk_level": hazard.risk_level.value,
            "status": hazard.status.value,
            "review_date": hazard.review_date,
            "created_at": hazard.created_at,
            "reviewed_at": hazard.reviewed_at,
        }
        for hazard in pending_review_hazards
        if hazard.risk_level == HazardRiskLevel.critical
    ]
    recurring_categories = Counter(_derive_hazard_category(hazard) for hazard in hazards)

    return {
        "open_critical_hazards_count": sum(
            1
            for hazard in hazards
            if hazard.status == HazardStatus.open and hazard.risk_level == HazardRiskLevel.critical
        ),
        "open_high_hazards_count": sum(
            1
            for hazard in hazards
            if hazard.status == HazardStatus.open and hazard.risk_level == HazardRiskLevel.high
        ),
        "hazards_pending_review_count": len(pending_review_hazards),
        "critical_hazards_pending_review": sorted(
            critical_pending_review,
            key=lambda item: ((item["review_date"] or date.max), item["created_at"], item["id"]),
        ),
        "top_risk_sites": _risk_site_rankings(hazards, site_lookup),
        "recurring_hazard_categories": [
            {"label": label, "count": count}
            for label, count in recurring_categories.most_common()
            if count > 1
        ][:5],
        "risk_level_distribution": _count_by(hazards, "risk_level", HazardRiskLevel),
    }


def _action_item(action: CorrectiveAction, site_lookup: dict[int, str]) -> dict:
    return {
        "id": action.id,
        "title": action.title,
        "site_id": action.site_id,
        "site_name": _site_name(site_lookup, action.site_id),
        "status": action.status.value,
        "priority": action.priority.value,
        "due_date": action.due_date,
        "assigned_to_user_id": action.assigned_to_user_id,
    }


def _action_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    site_lookup = _site_lookup(db)
    actions = _records(
        db,
        CorrectiveAction,
        site_id=site_id,
        date_attr="due_date",
        date_from=date_from,
        date_to=date_to,
    )
    today = _today()
    due_soon_by = today + timedelta(days=DUE_SOON_DAYS)
    overdue_actions = [action for action in actions if is_corrective_action_overdue(action)]
    due_soon_actions = [
        action
        for action in actions
        if action.due_date is not None
        and today <= action.due_date <= due_soon_by
        and action.status in OPEN_ACTION_STATUSES
        and not is_corrective_action_overdue(action)
    ]
    pending_verification = [
        action for action in actions if action.status == CorrectiveActionStatus.pending_verification
    ]

    sort_key = lambda action: (
        action.due_date or date.max,
        0 if action.priority == CorrectiveActionPriority.critical else 1,
        action.id,
    )

    return {
        "overdue_corrective_actions_count": len(overdue_actions),
        "overdue_corrective_actions": [_action_item(action, site_lookup) for action in sorted(overdue_actions, key=sort_key)[:10]],
        "corrective_actions_due_soon_count": len(due_soon_actions),
        "corrective_actions_due_soon": [_action_item(action, site_lookup) for action in sorted(due_soon_actions, key=sort_key)[:10]],
        "pending_verification_count": len(pending_verification),
        "corrective_action_status_distribution": _count_by(actions, "status", CorrectiveActionStatus),
        "corrective_action_priority_distribution": _count_by(actions, "priority", CorrectiveActionPriority),
    }


def _training_compliance_rate(training_records: list[TrainingRecord]) -> float:
    relevant_records = [
        record for record in training_records if record.status != TrainingStatus.cancelled
    ]
    if not relevant_records:
        return 0.0
    valid_completed = [
        record
        for record in relevant_records
        if record.status == TrainingStatus.completed
        and (record.expiry_date is None or record.expiry_date >= _today())
    ]
    return round((len(valid_completed) / len(relevant_records)) * 100, 2)


def _compliance_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    training_records = _records(
        db,
        TrainingRecord,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    acknowledgements = _records(
        db,
        ComplianceAcknowledgement,
        site_id=site_id,
        date_attr="assigned_at",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "training_compliance_rate": _training_compliance_rate(training_records),
        "overdue_training_count": sum(
            1 for record in training_records if record.status == TrainingStatus.overdue
        ),
        "expired_training_count": sum(
            1 for record in training_records if record.status == TrainingStatus.expired
        ),
        "overdue_compliance_acknowledgements_count": sum(
            1
            for acknowledgement in acknowledgements
            if acknowledgement.status == ComplianceAcknowledgementStatus.overdue
        ),
        "training_status_distribution": _count_by(training_records, "status", TrainingStatus),
        "compliance_acknowledgement_status_distribution": _count_by(
            acknowledgements,
            "status",
            ComplianceAcknowledgementStatus,
        ),
    }


def _permit_is_expiring_soon(permit: PermitToWork) -> bool:
    now = _now()
    end_datetime = _normalize_datetime(permit.end_datetime)
    return (
        permit.status in ACTIVE_PERMIT_EXPIRY_STATUSES
        and end_datetime is not None
        and now <= end_datetime <= now + timedelta(days=settings.PERMIT_EXPIRY_WARNING_DAYS)
    )


def _permit_is_expired(permit: PermitToWork) -> bool:
    end_datetime = _normalize_datetime(permit.end_datetime)
    return permit.status == PermitStatus.expired or (
        permit.status in ACTIVE_PERMIT_EXPIRY_STATUSES
        and end_datetime is not None
        and end_datetime < _now()
    )


def _permit_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    permits = _records(
        db,
        PermitToWork,
        site_id=site_id,
        date_attr="start_datetime",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "active_permits_count": sum(1 for permit in permits if permit.status == PermitStatus.active),
        "pending_approval_permits_count": sum(
            1 for permit in permits if permit.status == PermitStatus.pending_approval
        ),
        "expiring_soon_permits_count": sum(1 for permit in permits if _permit_is_expiring_soon(permit)),
        "expired_permits_count": sum(1 for permit in permits if _permit_is_expired(permit)),
        "permit_status_distribution": _count_by(permits, "status", PermitStatus),
        "permit_type_distribution": _count_by(permits, "permit_type", PermitType),
    }


def _approval_item(
    approval: ApprovalWorkflow,
    *,
    site_lookup: dict[int, str],
    approval_site_ids: dict[int, Optional[int]],
) -> dict:
    site_id = approval_site_ids.get(approval.id)
    return {
        "id": approval.id,
        "entity_type": approval.entity_type.value,
        "entity_id": approval.entity_id,
        "site_id": site_id,
        "site_name": _site_name(site_lookup, site_id),
        "action_type": approval.action_type.value,
        "status": approval.status.value,
        "requested_by_user_id": approval.requested_by_user_id,
        "assigned_approver_user_id": approval.assigned_approver_user_id,
        "created_at": approval.created_at,
    }


def _approval_site_ids(db: Session, approvals: list[ApprovalWorkflow]) -> dict[int, Optional[int]]:
    incident_ids = {approval.entity_id for approval in approvals if approval.entity_type.value == "incident"}
    hazard_ids = {approval.entity_id for approval in approvals if approval.entity_type.value == "hazard"}
    action_ids = {
        approval.entity_id for approval in approvals if approval.entity_type.value == "corrective_action"
    }
    permit_ids = {approval.entity_id for approval in approvals if approval.entity_type.value == "permit"}

    incident_sites = {
        incident.id: incident.site_id
        for incident in db.scalars(select(Incident).where(Incident.id.in_(incident_ids))).all()
    } if incident_ids else {}
    hazard_sites = {
        hazard.id: hazard.site_id
        for hazard in db.scalars(select(Hazard).where(Hazard.id.in_(hazard_ids))).all()
    } if hazard_ids else {}
    action_sites = {
        action.id: action.site_id
        for action in db.scalars(select(CorrectiveAction).where(CorrectiveAction.id.in_(action_ids))).all()
    } if action_ids else {}
    permit_sites = {
        permit.id: permit.site_id
        for permit in db.scalars(select(PermitToWork).where(PermitToWork.id.in_(permit_ids))).all()
    } if permit_ids else {}

    site_ids: dict[int, Optional[int]] = {}
    for approval in approvals:
        if approval.entity_type.value == "incident":
            site_ids[approval.id] = incident_sites.get(approval.entity_id)
        elif approval.entity_type.value == "hazard":
            site_ids[approval.id] = hazard_sites.get(approval.entity_id)
        elif approval.entity_type.value == "corrective_action":
            site_ids[approval.id] = action_sites.get(approval.entity_id)
        else:
            site_ids[approval.id] = permit_sites.get(approval.entity_id)
    return site_ids


def _approval_analytics(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    site_lookup = _site_lookup(db)
    approvals = _records(
        db,
        ApprovalWorkflow,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    approval_site_ids = _approval_site_ids(db, approvals)
    if site_id is not None:
        approvals = [approval for approval in approvals if approval_site_ids.get(approval.id) == site_id]
        approval_site_ids = {approval.id: approval_site_ids.get(approval.id) for approval in approvals}

    pending_approvals = [approval for approval in approvals if approval.status == ApprovalStatus.pending]
    return {
        "pending_approvals_count": len(pending_approvals),
        "pending_approvals": [
            _approval_item(approval, site_lookup=site_lookup, approval_site_ids=approval_site_ids)
            for approval in sorted(pending_approvals, key=lambda item: (item.created_at, item.id), reverse=True)[:10]
        ],
        "approvals_by_action_type": _count_by(approvals, "action_type", ApprovalActionType),
        "approvals_by_status": _count_by(approvals, "status", ApprovalStatus),
    }


def _incident_snapshot(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    incidents = _records(
        db,
        Incident,
        site_id=site_id,
        date_attr="occurred_at",
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "total_incidents": len(incidents),
        "open_incidents_count": sum(1 for incident in incidents if incident.status in OPEN_INCIDENT_STATUSES),
        "critical_open_incidents_count": sum(
            1
            for incident in incidents
            if incident.severity == IncidentSeverity.critical and incident.status in OPEN_INCIDENT_STATUSES
        ),
        "incidents_by_status": _count_by(incidents, "status", IncidentStatus),
        "incidents_by_severity": _count_by(incidents, "severity", IncidentSeverity),
    }


def _urgent_items(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    site_lookup = _site_lookup(db)
    items: list[tuple[int, dict]] = []

    overdue_actions = _action_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )["overdue_corrective_actions"]
    for action in overdue_actions:
        priority_rank = {
            "critical": 100,
            "high": 95,
            "medium": 90,
            "low": 85,
        }.get(action["priority"], 80)
        items.append(
            (
                priority_rank,
                {
                    "category": "overdue_corrective_action",
                    "entity_type": "corrective_action",
                    "entity_id": action["id"],
                    "title": action["title"],
                    "site_id": action["site_id"],
                    "site_name": action["site_name"],
                    "status": action["status"],
                    "priority": action["priority"],
                    "action_type": None,
                    "reason": "Corrective action is overdue.",
                    "due_date": action["due_date"],
                    "end_datetime": None,
                    "created_at": None,
                },
            )
        )

    behaviour_observations = _records(
        db,
        BehaviourObservation,
        site_id=site_id,
        date_attr="observed_at",
        date_from=date_from,
        date_to=date_to,
    )
    for observation in behaviour_observations:
        if (
            observation.observation_type not in OPEN_BEHAVIOUR_ISSUE_TYPES
            or observation.status == BehaviourObservationStatus.closed
        ):
            continue
        items.append(
            (
                93,
                {
                    "category": "open_behaviour_issue",
                    "entity_type": "behaviour_observation",
                    "entity_id": observation.id,
                    "title": observation.title,
                    "site_id": observation.site_id,
                    "site_name": _site_name(site_lookup, observation.site_id),
                    "status": observation.status.value,
                    "priority": observation.severity.value,
                    "action_type": None,
                    "reason": "Behaviour observation issue still requires follow-up.",
                    "due_date": None,
                    "end_datetime": None,
                    "created_at": observation.observed_at,
                },
            )
        )

    legal_items = _records(
        db,
        LegalComplianceItem,
        site_id=site_id,
        date_attr="next_review_date",
        date_from=date_from,
        date_to=date_to,
    )
    for item in legal_items:
        if item.compliance_status != LegalComplianceStatus.non_compliant:
            continue
        items.append(
            (
                97,
                {
                    "category": "non_compliant_legal_item",
                    "entity_type": "legal_compliance",
                    "entity_id": item.id,
                    "title": item.title,
                    "site_id": item.site_id,
                    "site_name": _site_name(site_lookup, item.site_id),
                    "status": item.compliance_status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Legal compliance item is marked non-compliant.",
                    "due_date": item.next_review_date,
                    "end_datetime": None,
                    "created_at": item.updated_at,
                },
            )
        )

    investigations = _records(
        db,
        IncidentInvestigation,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    for investigation in investigations:
        if investigation.status != IncidentInvestigationStatus.pending_approval:
            continue
        items.append(
            (
                91,
                {
                    "category": "pending_investigation_approval",
                    "entity_type": "incident_investigation",
                    "entity_id": investigation.id,
                    "title": f"Incident investigation #{investigation.id}",
                    "site_id": investigation.site_id,
                    "site_name": _site_name(site_lookup, investigation.site_id),
                    "status": investigation.status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Incident investigation is awaiting approval.",
                    "due_date": investigation.target_completion_date,
                    "end_datetime": None,
                    "created_at": investigation.created_at,
                },
            )
        )

    jsas = _records(
        db,
        JobSafetyAnalysis,
        site_id=site_id,
        date_attr="review_date",
        date_from=date_from,
        date_to=date_to,
    )
    for jsa in jsas:
        if jsa.status != JSAStatus.pending_approval:
            continue
        items.append(
            (
                89,
                {
                    "category": "pending_jsa_approval",
                    "entity_type": "jsa",
                    "entity_id": jsa.id,
                    "title": jsa.title,
                    "site_id": jsa.site_id,
                    "site_name": _site_name(site_lookup, jsa.site_id),
                    "status": jsa.status.value,
                    "priority": jsa.residual_risk_level.value,
                    "action_type": None,
                    "reason": "JSA is pending approval before use.",
                    "due_date": jsa.review_date,
                    "end_datetime": None,
                    "created_at": jsa.created_at,
                },
            )
        )

    contractors = _records(
        db,
        ContractorRecord,
        site_id=site_id,
        date_attr="insurance_expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    for contractor in contractors:
        if (
            contractor.induction_status == ContractorInductionStatus.completed
            and contractor.compliance_documents_status == ContractorComplianceDocumentsStatus.complete
            and (contractor.insurance_expiry_date is None or contractor.insurance_expiry_date >= _today())
            and (contractor.documents_expiry_date is None or contractor.documents_expiry_date >= _today())
        ):
            continue
        items.append(
            (
                90,
                {
                    "category": "contractor_compliance_gap",
                    "entity_type": "contractor",
                    "entity_id": contractor.id,
                    "title": contractor.contractor_name,
                    "site_id": contractor.site_id,
                    "site_name": _site_name(site_lookup, contractor.site_id),
                    "status": contractor.onboarding_status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Contractor has unresolved induction, document, or insurance gaps.",
                    "due_date": contractor.insurance_expiry_date or contractor.documents_expiry_date,
                    "end_datetime": None,
                    "created_at": contractor.updated_at,
                },
            )
        )

    assets = _records(
        db,
        AssetRegisterItem,
        site_id=site_id,
        date_attr="next_inspection_date",
        date_from=date_from,
        date_to=date_to,
    )
    for asset in assets:
        if asset.condition_status == AssetConditionStatus.defective:
            items.append(
                (
                    99,
                    {
                        "category": "defective_asset",
                        "entity_type": "asset_register",
                        "entity_id": asset.id,
                        "title": asset.asset_name,
                        "site_id": asset.site_id,
                        "site_name": _site_name(site_lookup, asset.site_id),
                        "status": asset.condition_status.value,
                        "priority": asset.asset_type.value,
                        "action_type": None,
                        "reason": "Asset is marked defective and requires attention.",
                        "due_date": asset.next_inspection_date,
                        "end_datetime": None,
                        "created_at": asset.updated_at,
                    },
                )
            )
        elif asset.next_inspection_date is not None and asset.next_inspection_date < _today():
            items.append(
                (
                    88,
                    {
                        "category": "overdue_asset_inspection",
                        "entity_type": "asset_register",
                        "entity_id": asset.id,
                        "title": asset.asset_name,
                        "site_id": asset.site_id,
                        "site_name": _site_name(site_lookup, asset.site_id),
                        "status": asset.condition_status.value,
                        "priority": asset.asset_type.value,
                        "action_type": None,
                        "reason": "Asset inspection is overdue.",
                        "due_date": asset.next_inspection_date,
                        "end_datetime": None,
                        "created_at": asset.updated_at,
                    },
                )
            )

    medical_records = _records(
        db,
        MedicalSurveillanceRecord,
        site_id=site_id,
        date_attr="due_date",
        date_from=date_from,
        date_to=date_to,
    )
    for record in medical_records:
        if record.status != MedicalSurveillanceStatus.overdue:
            continue
        items.append(
            (
                94,
                {
                    "category": "medical_surveillance_overdue",
                    "entity_type": "medical_surveillance",
                    "entity_id": record.id,
                    "title": record.surveillance_type,
                    "site_id": record.site_id,
                    "site_name": _site_name(site_lookup, record.site_id),
                    "status": record.status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Medical surveillance activity is overdue.",
                    "due_date": record.due_date,
                    "end_datetime": None,
                    "created_at": record.updated_at,
                },
            )
        )

    drills = _records(
        db,
        EmergencyDrillRecord,
        site_id=site_id,
        date_attr="drill_date",
        date_from=date_from,
        date_to=date_to,
    )
    for drill in drills:
        if drill.status != EmergencyDrillStatus.overdue:
            continue
        items.append(
            (
                87,
                {
                    "category": "overdue_emergency_drill",
                    "entity_type": "emergency_drill",
                    "entity_id": drill.id,
                    "title": drill.emergency_type,
                    "site_id": drill.site_id,
                    "site_name": _site_name(site_lookup, drill.site_id),
                    "status": drill.status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Emergency drill is overdue.",
                    "due_date": drill.drill_date,
                    "end_datetime": None,
                    "created_at": drill.updated_at,
                },
            )
        )

    documents = _records(
        db,
        DocumentControlRecord,
        site_id=site_id,
        date_attr="expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    for document in documents:
        if document.status == DocumentStatus.pending_approval:
            items.append(
                (
                    90,
                    {
                        "category": "pending_document_approval",
                        "entity_type": "document_control",
                        "entity_id": document.id,
                        "title": document.title,
                        "site_id": document.site_id,
                        "site_name": _site_name(site_lookup, document.site_id),
                        "status": document.status.value,
                        "priority": None,
                        "action_type": None,
                        "reason": "Controlled document is awaiting approval.",
                        "due_date": document.expiry_date,
                        "end_datetime": None,
                        "created_at": document.updated_at,
                    },
                )
            )
        elif document.status == DocumentStatus.expired:
            items.append(
                (
                    93,
                    {
                        "category": "expired_document",
                        "entity_type": "document_control",
                        "entity_id": document.id,
                        "title": document.title,
                        "site_id": document.site_id,
                        "site_name": _site_name(site_lookup, document.site_id),
                        "status": document.status.value,
                        "priority": None,
                        "action_type": None,
                        "reason": "Controlled document has expired.",
                        "due_date": document.expiry_date,
                        "end_datetime": None,
                        "created_at": document.updated_at,
                    },
                )
            )

    audits = _records(
        db,
        AuditManagementRecord,
        site_id=site_id,
        date_attr="audit_date",
        date_from=date_from,
        date_to=date_to,
    )
    for audit in audits:
        if audit.status != AuditStatus.open:
            continue
        items.append(
            (
                86,
                {
                    "category": "open_audit",
                    "entity_type": "audit_management",
                    "entity_id": audit.id,
                    "title": f"{audit.audit_type.value} audit",
                    "site_id": audit.site_id,
                    "site_name": _site_name(site_lookup, audit.site_id),
                    "status": audit.status.value,
                    "priority": None,
                    "action_type": None,
                    "reason": "Audit remains open and requires follow-through.",
                    "due_date": audit.audit_date,
                    "end_datetime": None,
                    "created_at": audit.updated_at,
                },
            )
        )

    risk_items = _risk_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )["critical_hazards_pending_review"]
    for hazard in risk_items:
        items.append(
            (
                98,
                {
                    "category": "critical_hazard_pending_review",
                    "entity_type": "hazard",
                    "entity_id": hazard["id"],
                    "title": hazard["title"],
                    "site_id": hazard["site_id"],
                    "site_name": hazard["site_name"],
                    "status": hazard["status"],
                    "priority": hazard["risk_level"],
                    "action_type": None,
                    "reason": "Critical hazard is still awaiting formal review.",
                    "due_date": hazard["review_date"],
                    "end_datetime": None,
                    "created_at": hazard["created_at"],
                },
            )
        )

    permits = _records(
        db,
        PermitToWork,
        site_id=site_id,
        date_attr="start_datetime",
        date_from=date_from,
        date_to=date_to,
    )
    for permit in permits:
        if not _permit_is_expired(permit):
            continue
        items.append(
            (
                94,
                {
                    "category": "expired_permit",
                    "entity_type": "permit",
                    "entity_id": permit.id,
                    "title": permit.title,
                    "site_id": permit.site_id,
                    "site_name": _site_name(site_lookup, permit.site_id),
                    "status": permit.status.value,
                    "priority": permit.permit_type.value,
                    "action_type": None,
                    "reason": "Permit is expired and requires follow-up.",
                    "due_date": None,
                    "end_datetime": permit.end_datetime,
                    "created_at": permit.created_at,
                },
            )
        )

    approvals = _approval_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )["pending_approvals"]
    for approval in approvals:
        items.append(
            (
                92,
                {
                    "category": "pending_approval",
                    "entity_type": approval["entity_type"],
                    "entity_id": approval["entity_id"],
                    "title": f"{approval['action_type'].replace('_', ' ')} request",
                    "site_id": approval["site_id"],
                    "site_name": approval["site_name"],
                    "status": approval["status"],
                    "priority": None,
                    "action_type": approval["action_type"],
                    "reason": "Workflow is pending final approval.",
                    "due_date": None,
                    "end_datetime": None,
                    "created_at": approval["created_at"],
                },
            )
        )

    incidents = _records(
        db,
        Incident,
        site_id=site_id,
        date_attr="occurred_at",
        date_from=date_from,
        date_to=date_to,
    )
    for incident in incidents:
        if incident.severity != IncidentSeverity.critical or incident.status not in OPEN_INCIDENT_STATUSES:
            continue
        items.append(
            (
                96,
                {
                    "category": "critical_open_incident",
                    "entity_type": "incident",
                    "entity_id": incident.id,
                    "title": incident.title,
                    "site_id": incident.site_id,
                    "site_name": _site_name(site_lookup, incident.site_id),
                    "status": incident.status.value,
                    "priority": incident.severity.value,
                    "action_type": None,
                    "reason": "Critical incident remains open.",
                    "due_date": None,
                    "end_datetime": None,
                    "created_at": incident.occurred_at,
                },
            )
        )

    def sort_key(value: tuple[int, dict]) -> tuple:
        priority, item = value
        return (
            -priority,
            item["due_date"] or date.max,
            item["end_datetime"] or datetime.max.replace(tzinfo=timezone.utc),
            item["created_at"] or datetime.max.replace(tzinfo=timezone.utc),
            item["title"],
        )

    sorted_items = sorted(items, key=sort_key)
    prioritized_categories = [
        "overdue_corrective_action",
        "critical_hazard_pending_review",
        "expired_permit",
        "medical_surveillance_overdue",
        "pending_approval",
        "critical_open_incident",
        "open_behaviour_issue",
        "defective_asset",
        "expired_document",
        "non_compliant_legal_item",
        "contractor_compliance_gap",
        "pending_document_approval",
        "pending_investigation_approval",
        "pending_jsa_approval",
        "overdue_asset_inspection",
        "overdue_emergency_drill",
        "open_audit",
    ]

    selected: list[dict] = []
    selected_keys: set[tuple[str, str, int]] = set()

    for category in prioritized_categories:
        match = next((item for _, item in sorted_items if item["category"] == category), None)
        if match is None:
            continue
        key = (match["category"], match["entity_type"], match["entity_id"])
        if key in selected_keys:
            continue
        selected.append(match)
        selected_keys.add(key)
        if len(selected) == 5:
            return selected

    for _, item in sorted_items:
        key = (item["category"], item["entity_type"], item["entity_id"])
        if key in selected_keys:
            continue
        selected.append(item)
        selected_keys.add(key)
        if len(selected) == 5:
            break

    return selected


def get_dashboard_overview(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    incidents = _records(db, Incident, site_id=site_id, date_attr="occurred_at", date_from=date_from, date_to=date_to)
    hazards = _records(db, Hazard, site_id=site_id)
    inspections = _records(db, Inspection, site_id=site_id, date_attr="inspection_date", date_from=date_from, date_to=date_to)
    corrective_actions = _records(
        db,
        CorrectiveAction,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    safety_kpi_records = _records(
        db,
        SafetyKPIRecord,
        site_id=site_id,
        date_attr="period_end",
        date_from=date_from,
        date_to=date_to,
    )
    safety_communications = _records(
        db,
        SafetyCommunication,
        site_id=site_id,
        date_attr="issued_at",
        date_from=date_from,
        date_to=date_to,
    )
    behaviour_observations = _records(
        db,
        BehaviourObservation,
        site_id=site_id,
        date_attr="observed_at",
        date_from=date_from,
        date_to=date_to,
    )
    investigations = _records(
        db,
        IncidentInvestigation,
        site_id=site_id,
        date_attr="created_at",
        date_from=date_from,
        date_to=date_to,
    )
    legal_compliance_items = _records(
        db,
        LegalComplianceItem,
        site_id=site_id,
        date_attr="next_review_date",
        date_from=date_from,
        date_to=date_to,
    )
    jsas = _records(
        db,
        JobSafetyAnalysis,
        site_id=site_id,
        date_attr="review_date",
        date_from=date_from,
        date_to=date_to,
    )
    contractors = _records(
        db,
        ContractorRecord,
        site_id=site_id,
        date_attr="insurance_expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    assets = _records(
        db,
        AssetRegisterItem,
        site_id=site_id,
        date_attr="next_inspection_date",
        date_from=date_from,
        date_to=date_to,
    )
    medical_surveillance_records = _records(
        db,
        MedicalSurveillanceRecord,
        site_id=site_id,
        date_attr="due_date",
        date_from=date_from,
        date_to=date_to,
    )
    emergency_drills = _records(
        db,
        EmergencyDrillRecord,
        site_id=site_id,
        date_attr="drill_date",
        date_from=date_from,
        date_to=date_to,
    )
    documents = _records(
        db,
        DocumentControlRecord,
        site_id=site_id,
        date_attr="expiry_date",
        date_from=date_from,
        date_to=date_to,
    )
    audits = _records(
        db,
        AuditManagementRecord,
        site_id=site_id,
        date_attr="audit_date",
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "total_incidents": len(incidents),
        "incidents_by_status": _count_by(incidents, "status", IncidentStatus),
        "incidents_by_severity": _count_by(incidents, "severity", IncidentSeverity),
        "total_hazards": len(hazards),
        "hazards_by_status": _count_by(hazards, "status", HazardStatus),
        "hazards_by_risk_level": _count_by(hazards, "risk_level", HazardRiskLevel),
        "total_inspections": len(inspections),
        "inspections_by_status": _count_by(inspections, "status", InspectionStatus),
        "inspections_by_overall_result": _count_by(inspections, "overall_result", InspectionOverallResult),
        "total_corrective_actions": len(corrective_actions),
        "corrective_actions_by_status": _count_by(corrective_actions, "status", CorrectiveActionStatus),
        "corrective_actions_by_priority": _count_by(corrective_actions, "priority", CorrectiveActionPriority),
        "overdue_corrective_actions_count": sum(1 for action in corrective_actions if is_corrective_action_overdue(action)),
        "total_safety_kpi_records": len(safety_kpi_records),
        "total_safety_communications": len(safety_communications),
        "total_behaviour_observations": len(behaviour_observations),
        "total_incident_investigations": len(investigations),
        "total_legal_compliance_items": len(legal_compliance_items),
        "total_jsas": len(jsas),
        "total_contractors": len(contractors),
        "total_asset_register_items": len(assets),
        "total_medical_surveillance_records": len(medical_surveillance_records),
        "total_emergency_drills": len(emergency_drills),
        "total_documents": len(documents),
        "total_audits": len(audits),
    }


def get_site_summaries(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    site_statement = select(Site)
    if site_id is not None:
        site_statement = site_statement.where(Site.id == site_id)
    sites = list(db.scalars(site_statement.order_by(Site.name)).all())

    summaries = []
    for site in sites:
        incidents = _records(db, Incident, site_id=site.id, date_attr="occurred_at", date_from=date_from, date_to=date_to)
        hazards = _records(db, Hazard, site_id=site.id, date_attr="created_at", date_from=date_from, date_to=date_to)
        inspections = _records(db, Inspection, site_id=site.id, date_attr="inspection_date", date_from=date_from, date_to=date_to)
        corrective_actions = _records(
            db,
            CorrectiveAction,
            site_id=site.id,
            date_attr="created_at",
            date_from=date_from,
            date_to=date_to,
        )
        safety_kpi_records = _records(
            db,
            SafetyKPIRecord,
            site_id=site.id,
            date_attr="period_end",
            date_from=date_from,
            date_to=date_to,
        )
        safety_communications = _records(
            db,
            SafetyCommunication,
            site_id=site.id,
            date_attr="issued_at",
            date_from=date_from,
            date_to=date_to,
        )
        behaviour_observations = _records(
            db,
            BehaviourObservation,
            site_id=site.id,
            date_attr="observed_at",
            date_from=date_from,
            date_to=date_to,
        )
        investigations = _records(
            db,
            IncidentInvestigation,
            site_id=site.id,
            date_attr="created_at",
            date_from=date_from,
            date_to=date_to,
        )
        legal_compliance_items = _records(
            db,
            LegalComplianceItem,
            site_id=site.id,
            date_attr="next_review_date",
            date_from=date_from,
            date_to=date_to,
        )
        jsas = _records(
            db,
            JobSafetyAnalysis,
            site_id=site.id,
            date_attr="review_date",
            date_from=date_from,
            date_to=date_to,
        )
        contractors = _records(
            db,
            ContractorRecord,
            site_id=site.id,
            date_attr="insurance_expiry_date",
            date_from=date_from,
            date_to=date_to,
        )
        assets = _records(
            db,
            AssetRegisterItem,
            site_id=site.id,
            date_attr="next_inspection_date",
            date_from=date_from,
            date_to=date_to,
        )
        medical_surveillance_records = _records(
            db,
            MedicalSurveillanceRecord,
            site_id=site.id,
            date_attr="due_date",
            date_from=date_from,
            date_to=date_to,
        )
        emergency_drills = _records(
            db,
            EmergencyDrillRecord,
            site_id=site.id,
            date_attr="drill_date",
            date_from=date_from,
            date_to=date_to,
        )
        documents = _records(
            db,
            DocumentControlRecord,
            site_id=site.id,
            date_attr="expiry_date",
            date_from=date_from,
            date_to=date_to,
        )
        audits = _records(
            db,
            AuditManagementRecord,
            site_id=site.id,
            date_attr="audit_date",
            date_from=date_from,
            date_to=date_to,
        )
        summaries.append(
            {
                "site_id": site.id,
                "site_name": site.name,
                "incidents_count": len(incidents),
                "open_hazards_count": sum(1 for hazard in hazards if hazard.status == HazardStatus.open),
                "critical_hazards_count": sum(1 for hazard in hazards if hazard.risk_level == HazardRiskLevel.critical),
                "inspections_count": len(inspections),
                "overdue_corrective_actions_count": sum(1 for action in corrective_actions if is_corrective_action_overdue(action)),
                "hours_worked": round(sum(record.hours_worked for record in safety_kpi_records), 2),
                "safety_communications_count": len(safety_communications),
                "behaviour_observations_count": len(behaviour_observations),
                "investigations_count": len(investigations),
                "non_compliant_legal_items_count": sum(
                    1
                    for item in legal_compliance_items
                    if item.compliance_status == LegalComplianceStatus.non_compliant
                ),
                "jsas_count": len(jsas),
                "contractors_count": len(contractors),
                "defective_assets_count": sum(
                    1
                    for asset in assets
                    if asset.condition_status == AssetConditionStatus.defective
                ),
                "medical_surveillance_due_count": sum(
                    1
                    for record in medical_surveillance_records
                    if record.status in {MedicalSurveillanceStatus.due, MedicalSurveillanceStatus.overdue}
                ),
                "emergency_drills_count": len(emergency_drills),
                "documents_expiring_count": sum(
                    1
                    for document in documents
                    if document.expiry_date is not None and document.expiry_date <= _today() + timedelta(days=14)
                ),
                "open_audits_count": sum(1 for audit in audits if audit.status == AuditStatus.open),
            }
        )
    return summaries


def get_dashboard_trends(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    incidents = _records(db, Incident, site_id=site_id, date_attr="occurred_at", date_from=date_from, date_to=date_to)
    hazards = _records(db, Hazard, site_id=site_id, date_attr="created_at", date_from=date_from, date_to=date_to)
    inspections = _records(db, Inspection, site_id=site_id, date_attr="inspection_date", date_from=date_from, date_to=date_to)
    closed_actions = [
        action
        for action in _records(
            db,
            CorrectiveAction,
            site_id=site_id,
            date_attr="completed_at",
            date_from=date_from,
            date_to=date_to,
        )
        if action.status == CorrectiveActionStatus.closed
    ]
    safety_communications = _records(
        db,
        SafetyCommunication,
        site_id=site_id,
        date_attr="issued_at",
        date_from=date_from,
        date_to=date_to,
    )
    behaviour_observations = _records(
        db,
        BehaviourObservation,
        site_id=site_id,
        date_attr="observed_at",
        date_from=date_from,
        date_to=date_to,
    )
    safety_kpi_records = _records(
        db,
        SafetyKPIRecord,
        site_id=site_id,
        date_attr="period_end",
        date_from=date_from,
        date_to=date_to,
    )
    emergency_drills = _records(
        db,
        EmergencyDrillRecord,
        site_id=site_id,
        date_attr="drill_date",
        date_from=date_from,
        date_to=date_to,
    )
    audits = _records(
        db,
        AuditManagementRecord,
        site_id=site_id,
        date_attr="audit_date",
        date_from=date_from,
        date_to=date_to,
    )
    trifr_by_month, ltifr_by_month = _monthly_kpi_rates(db, safety_kpi_records)

    return {
        "incidents_by_month": _month_counts(incidents, "occurred_at"),
        "hazards_by_month": _month_counts(hazards, "created_at"),
        "inspections_by_month": _month_counts(inspections, "inspection_date"),
        "corrective_actions_closed_by_month": _month_counts(closed_actions, "completed_at"),
        "safety_communications_by_month": _month_counts(safety_communications, "issued_at"),
        "behaviour_observations_by_month": _month_counts(behaviour_observations, "observed_at"),
        "trifr_by_month": trifr_by_month,
        "ltifr_by_month": ltifr_by_month,
        "emergency_drills_by_month": _month_counts(emergency_drills, "drill_date"),
        "audits_by_month": _month_counts(audits, "audit_date"),
    }


def get_dashboard_risk(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    return _risk_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)


def get_dashboard_actions(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    return _action_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)


def get_dashboard_compliance(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    return _compliance_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)


def get_dashboard_permits(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    return _permit_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)


def get_dashboard_approvals(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    return _approval_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)


def get_dashboard_management_summary(
    db: Session,
    *,
    site_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    risk_snapshot = _risk_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    action_details = _action_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    compliance_details = _compliance_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    permit_details = _permit_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    approval_details = _approval_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    kpi_details = _kpi_snapshot(db, site_id=site_id, date_from=date_from, date_to=date_to)
    communication_details = _communication_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    behaviour_details = _behaviour_analytics(db, site_id=site_id, date_from=date_from, date_to=date_to)
    investigation_details = _investigation_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    legal_compliance_details = _legal_compliance_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    jsa_details = _jsa_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    contractor_details = _contractor_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    asset_details = _asset_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    medical_surveillance_details = _medical_surveillance_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    emergency_drill_details = _emergency_drill_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    document_details = _document_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )
    audit_details = _audit_management_analytics(
        db,
        site_id=site_id,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "incident_snapshot": _incident_snapshot(
            db,
            site_id=site_id,
            date_from=date_from,
            date_to=date_to,
        ),
        "risk_snapshot": risk_snapshot,
        "action_snapshot": {
            "overdue_corrective_actions_count": action_details["overdue_corrective_actions_count"],
            "corrective_actions_due_soon_count": action_details["corrective_actions_due_soon_count"],
            "pending_verification_count": action_details["pending_verification_count"],
            "corrective_action_status_distribution": action_details["corrective_action_status_distribution"],
        },
        "compliance_snapshot": {
            "training_compliance_rate": compliance_details["training_compliance_rate"],
            "overdue_training_count": compliance_details["overdue_training_count"],
            "expired_training_count": compliance_details["expired_training_count"],
            "overdue_compliance_acknowledgements_count": compliance_details["overdue_compliance_acknowledgements_count"],
        },
        "permit_snapshot": {
            "active_permits_count": permit_details["active_permits_count"],
            "pending_approval_permits_count": permit_details["pending_approval_permits_count"],
            "expiring_soon_permits_count": permit_details["expiring_soon_permits_count"],
            "expired_permits_count": permit_details["expired_permits_count"],
        },
        "approval_snapshot": {
            "pending_approvals_count": approval_details["pending_approvals_count"],
            "approvals_by_action_type": approval_details["approvals_by_action_type"],
            "approvals_by_status": approval_details["approvals_by_status"],
        },
        "kpi_snapshot": kpi_details,
        "communication_snapshot": communication_details,
        "behaviour_snapshot": behaviour_details,
        "investigation_snapshot": investigation_details,
        "legal_compliance_snapshot": legal_compliance_details,
        "jsa_snapshot": jsa_details,
        "contractor_snapshot": contractor_details,
        "asset_snapshot": asset_details,
        "medical_surveillance_snapshot": medical_surveillance_details,
        "emergency_drill_snapshot": emergency_drill_details,
        "document_snapshot": document_details,
        "audit_snapshot": audit_details,
        "top_urgent_items": _urgent_items(
            db,
            site_id=site_id,
            date_from=date_from,
            date_to=date_to,
        ),
    }
