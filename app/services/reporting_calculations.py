from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import cached_property
from statistics import median
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.audit_management import AuditManagementRecord, AuditStatus
from app.models.corrective_action import (
    ActionExtensionDecisionStatus,
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionStatus,
)
from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.incident import Incident, IncidentCauseAnalysis, IncidentSeverity, IncidentStatus
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.inspection import Inspection, InspectionOverallResult, InspectionStatus
from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.permit import PermitStatus, PermitToWork
from app.models.reporting import KPIDefinition, ReportingPeriod, WorkforceExposure
from app.models.sio import (
    SIOObservationNature,
    SIOStatus,
    SIOUrgency,
    SafetyImprovementObservation,
)
from app.models.training import TrainingRecord, TrainingStatus
from app.models.ppe import PPEIssueStatus
from app.services.ppe_service import ACTIVE_ISSUE_STATUSES, dashboard as ppe_dashboard, list_issues as list_ppe_issues
from app.services.occupational_health_service import dashboard as occupational_health_dashboard
from app.services.training_competency_service import (
    dashboard as training_competency_dashboard,
    forward_view as training_forward_view,
)


@dataclass(frozen=True)
class MetricValue:
    value: Optional[float]
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    metadata: Optional[dict] = None
    insufficient_reason: Optional[str] = None


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _enum(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _percent(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator * 100 / denominator, 2)


class CalculationContext:
    """A deterministic, date-anchored view of one period and one scope."""

    def __init__(
        self,
        db: Session,
        period: ReportingPeriod,
        *,
        site_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> None:
        self.db = db
        self.period = period
        self.site_id = site_id
        self.department_id = department_id
        self.start = period.start_date
        self.end = period.end_date
        self.end_dt = datetime.combine(self.end, time.max, tzinfo=timezone.utc)

    def _scoped(self, model, *, department_fields: tuple[str, ...] = ()) -> list:
        statement = select(model)
        if self.site_id is not None:
            if not hasattr(model, "site_id"):
                return []
            statement = statement.where(model.site_id == self.site_id)
        records = list(self.db.scalars(statement).all())
        if self.department_id is not None:
            if not department_fields:
                return []
            records = [
                record
                for record in records
                if any(getattr(record, field, None) == self.department_id for field in department_fields)
            ]
        return records

    def _in_period(self, value) -> bool:
        value = _as_date(value)
        return value is not None and self.start <= value <= self.end

    def _created_by_end(self, record) -> bool:
        return (_as_date(getattr(record, "created_at", None)) or self.end) <= self.end

    @cached_property
    def actions(self) -> list[CorrectiveAction]:
        return [
            item
            for item in self._scoped(
                CorrectiveAction,
                department_fields=("responsible_department_id", "department_id"),
            )
            if self._created_by_end(item)
        ]

    @cached_property
    def sios(self) -> list[SafetyImprovementObservation]:
        return [
            item
            for item in self._scoped(
                SafetyImprovementObservation,
                department_fields=("responsible_department_id", "department_id"),
            )
            if (_as_date(item.observation_date) or _as_date(item.source_created_at) or _as_date(item.created_at)) <= self.end
        ]

    @cached_property
    def incidents(self) -> list[Incident]:
        return [item for item in self._scoped(Incident, department_fields=("department_id",)) if self._in_period(item.occurred_at)]

    @cached_property
    def incident_causes(self) -> list[IncidentCauseAnalysis]:
        incident_ids = {item.id for item in self.incidents}
        if not incident_ids:
            return []
        return list(self.db.scalars(select(IncidentCauseAnalysis).where(IncidentCauseAnalysis.incident_id.in_(incident_ids))).all())

    @cached_property
    def investigations(self) -> list[IncidentInvestigation]:
        return [item for item in self._scoped(IncidentInvestigation) if self._created_by_end(item)]

    @cached_property
    def hazards(self) -> list[Hazard]:
        return [item for item in self._scoped(Hazard) if self._created_by_end(item)]

    @cached_property
    def inspections(self) -> list[Inspection]:
        return [item for item in self._scoped(Inspection) if self._in_period(item.inspection_date)]

    @cached_property
    def audits(self) -> list[AuditManagementRecord]:
        return [item for item in self._scoped(AuditManagementRecord) if self._in_period(item.audit_date)]

    @cached_property
    def training(self) -> list[TrainingRecord]:
        return [item for item in self._scoped(TrainingRecord) if self._created_by_end(item)]

    @cached_property
    def permits(self) -> list[PermitToWork]:
        return [item for item in self._scoped(PermitToWork) if _as_date(item.start_datetime) <= self.end]

    @cached_property
    def compliance(self) -> list[LegalComplianceItem]:
        return [item for item in self._scoped(LegalComplianceItem) if self._created_by_end(item)]

    def action_status_at_end(self, action: CorrectiveAction) -> str:
        state = CorrectiveActionStatus.open.value
        for activity in sorted(action.activities, key=lambda item: (item.created_at, item.id)):
            if _as_date(activity.created_at) > self.end:
                break
            metadata = activity.event_metadata or {}
            if metadata.get("to"):
                state = str(metadata["to"])
                continue
            state = {
                "assigned": "assigned",
                "reassigned": "assigned",
                "accepted": "accepted",
                "declined": "declined",
                "started": "in_progress",
                "resumed": "in_progress",
                "put_on_hold": "on_hold",
                "completion_requested": "completion_requested",
                "pending_verification": "pending_verification",
                "verification_rejected": "in_progress",
                "closed": "closed",
                "reopened": "reopened",
                "cancelled": "cancelled",
            }.get(activity.event_type, state)
        # Imported/legacy records may not have a corresponding closure event.
        if action.cancelled_at and _as_date(action.cancelled_at) <= self.end:
            state = "cancelled"
        if action.closed_at and _as_date(action.closed_at) <= self.end:
            reopened_after_close = any(
                activity.event_type == "reopened"
                and _as_date(action.closed_at) <= _as_date(activity.created_at) <= self.end
                for activity in action.activities
            )
            if not reopened_after_close:
                state = "closed"
        return state

    def action_due_date_at(self, action: CorrectiveAction, as_of: date) -> Optional[date]:
        due_date = action.current_due_date
        for extension in sorted(
            action.extensions,
            key=lambda item: (item.decided_at or item.requested_at, item.id),
            reverse=True,
        ):
            if (
                extension.decision_status == ActionExtensionDecisionStatus.approved
                and extension.decided_at
                and _as_date(extension.decided_at) > as_of
            ):
                due_date = extension.previous_due_date
        return due_date

    def action_close_dates(self, action: CorrectiveAction) -> list[date]:
        values = [
            _as_date(activity.created_at)
            for activity in action.activities
            if activity.event_type == "closed" and self._in_period(activity.created_at)
        ]
        if not values and action.closed_at and self._in_period(action.closed_at):
            values.append(_as_date(action.closed_at))
        return sorted(set(value for value in values if value is not None))

    def sio_status_at_end(self, sio: SafetyImprovementObservation) -> str:
        state = _enum(sio.status)
        events = [item for item in sio.activities if _as_date(item.created_at) <= self.end]
        if sio.closed_at and _as_date(sio.closed_at) <= self.end:
            state = SIOStatus.closed.value
        for activity in sorted(events, key=lambda item: (item.created_at, item.id)):
            if activity.event_type == "reopened":
                state = SIOStatus.reopened.value
            elif activity.event_type in {"closed", "closure_verified"}:
                state = SIOStatus.closed.value
        return state

    def exposure_hours(self) -> tuple[Optional[float], dict]:
        statement = select(WorkforceExposure).where(
            WorkforceExposure.period_start <= self.end,
            WorkforceExposure.period_end >= self.start,
        )
        if self.site_id is None:
            statement = statement.where(WorkforceExposure.site_id.is_(None))
        else:
            statement = statement.where(WorkforceExposure.site_id == self.site_id)
        if self.department_id is None:
            statement = statement.where(WorkforceExposure.department_id.is_(None))
        else:
            statement = statement.where(WorkforceExposure.department_id == self.department_id)
        records = list(self.db.scalars(statement).all())

        # If no organisation aggregate exists, non-overlapping site rows may be
        # used as the real organisation denominator. We never mix aggregate and
        # site rows, which would double count hours.
        source = "exact_scope"
        if not records and self.site_id is None and self.department_id is None:
            records = list(
                self.db.scalars(
                    select(WorkforceExposure).where(
                        WorkforceExposure.site_id.is_not(None),
                        WorkforceExposure.department_id.is_(None),
                        WorkforceExposure.period_start <= self.end,
                        WorkforceExposure.period_end >= self.start,
                    )
                ).all()
            )
            source = "site_rollup"
        metadata = {"exposure_record_count": len(records), "exposure_source": source}
        if not records:
            return None, metadata
        if any(item.total_hours_worked is None for item in records):
            metadata["missing_components"] = True
            return None, metadata
        return round(sum(item.total_hours_worked or 0 for item in records), 2), metadata


def _base_metadata(context: CalculationContext, *, source: str, formula: str) -> dict:
    return {
        "period_start": context.start.isoformat(),
        "period_end": context.end.isoformat(),
        "site_id": context.site_id,
        "department_id": context.department_id,
        "source": source,
        "formula": formula,
    }


def _action_metric(context: CalculationContext, key: str) -> MetricValue:
    open_states = {
        "open", "assigned", "accepted", "in_progress", "completion_requested",
        "pending_verification", "declined", "on_hold", "reopened", "overdue",
    }
    open_actions = [item for item in context.actions if context.action_status_at_end(item) in open_states]
    overdue = [
        item for item in open_actions
        if (context.action_due_date_at(item, context.end) or context.end) < context.end
        and context.action_due_date_at(item, context.end) is not None
    ]
    metadata = _base_metadata(context, source="corrective_actions + action lifecycle history", formula=key)
    metadata["source_count"] = len(context.actions)
    values = {
        "action_open": len(open_actions),
        "action_overdue": len(overdue),
        "action_high_critical_overdue": sum(
            item.priority in {CorrectiveActionPriority.high, CorrectiveActionPriority.critical}
            for item in overdue
        ),
        "action_awaiting_verification": sum(
            context.action_status_at_end(item) in {"completion_requested", "pending_verification"}
            for item in open_actions
        ),
        "action_due_7_days": sum(
            context.end < (context.action_due_date_at(item, context.end) or context.end)
            <= context.end + timedelta(days=7)
            for item in open_actions
        ),
        "action_due_30_days": sum(
            context.end < (context.action_due_date_at(item, context.end) or context.end)
            <= context.end + timedelta(days=30)
            for item in open_actions
        ),
        "action_reopened": sum(
            activity.event_type == "reopened" and context._in_period(activity.created_at)
            for item in context.actions for activity in item.activities
        ),
        "action_extension_requests": sum(
            context._in_period(extension.requested_at)
            for item in context.actions for extension in item.extensions
        ),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "action_overdue_rate":
        value = _percent(len(overdue), len(open_actions))
        return MetricValue(value, len(overdue), len(open_actions), metadata, "No open actions in scope" if value is None else None)

    closures: list[tuple[CorrectiveAction, date]] = []
    for action in context.actions:
        closures.extend((action, closed_on) for closed_on in context.action_close_dates(action))
    if key in {"action_average_closure_days", "action_median_closure_days"}:
        durations = [
            max(0, (closed_on - _as_date(action.created_at)).days)
            for action, closed_on in closures
        ]
        if not durations:
            return MetricValue(None, metadata=metadata, insufficient_reason="No action closures in the period")
        value = sum(durations) / len(durations) if key == "action_average_closure_days" else median(durations)
        return MetricValue(round(float(value), 2), metadata=metadata)
    if key in {"action_original_due_on_time_closure_rate", "action_current_due_on_time_closure_rate"}:
        eligible: list[tuple[CorrectiveAction, date, date]] = []
        for action, closed_on in closures:
            due_on = (
                action.original_due_date
                if key == "action_original_due_on_time_closure_rate"
                else context.action_due_date_at(action, closed_on)
            )
            if due_on is not None:
                eligible.append((action, closed_on, due_on))
        on_time = sum(closed_on <= due_on for _, closed_on, due_on in eligible)
        value = _percent(on_time, len(eligible))
        return MetricValue(value, on_time, len(eligible), metadata, "No eligible action closures with due dates" if value is None else None)
    if key == "action_verification_rejection_rate":
        decisions = [
            activity
            for item in context.actions
            for activity in item.activities
            if activity.event_type in {"verification_approved", "verification_rejected"}
            and context._in_period(activity.created_at)
        ]
        rejected = sum(item.event_type == "verification_rejected" for item in decisions)
        value = _percent(rejected, len(decisions))
        return MetricValue(value, rejected, len(decisions), metadata, "No verification decisions in the period" if value is None else None)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _sio_metric(context: CalculationContext, key: str) -> MetricValue:
    raised = [
        item for item in context.sios
        if context._in_period(item.observation_date or item.source_created_at or item.created_at)
    ]
    terminal = {SIOStatus.closed.value, SIOStatus.complete.value, SIOStatus.no_action_required.value}
    open_items = [item for item in context.sios if context.sio_status_at_end(item) not in terminal]
    closures = [item for item in context.sios if item.closed_at and context._in_period(item.closed_at)]
    metadata = _base_metadata(context, source="safety_improvement_observations", formula=key)
    metadata["source_count"] = len(context.sios)
    metadata["reporting_date_basis"] = (
        "observation_date; source_created_at fallback when observation_date is null; "
        "system created_at final fallback"
    )
    metadata["source_created_at_fallback_count"] = sum(
        item.observation_date is None and item.source_created_at is not None
        for item in raised
    )
    metadata["system_created_at_fallback_count"] = sum(
        item.observation_date is None and item.source_created_at is None
        for item in raised
    )
    values = {
        "sio_raised": len(raised),
        "sio_positive": sum(item.observation_nature == SIOObservationNature.positive for item in raised),
        "sio_negative": sum(item.observation_nature == SIOObservationNature.negative for item in raised),
        "sio_open": len(open_items),
        "sio_overdue": sum(bool(item.due_date and item.due_date < context.end) for item in open_items),
        "sio_high_urgent": sum(item.urgency in {SIOUrgency.high, SIOUrgency.urgent} for item in open_items),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "sio_closure_rate":
        value = _percent(len(closures), len(raised))
        return MetricValue(value, len(closures), len(raised), metadata, "No SIOs raised in the period" if value is None else None)
    if key == "sio_on_time_closure_rate":
        eligible = [item for item in closures if item.due_date is not None]
        on_time = sum(_as_date(item.closed_at) <= item.due_date for item in eligible)
        value = _percent(on_time, len(eligible))
        return MetricValue(value, on_time, len(eligible), metadata, "No closed SIOs with due dates" if value is None else None)
    if key == "sio_average_closure_days":
        durations = [
            max(0, (_as_date(item.closed_at) - (_as_date(item.observation_date) or _as_date(item.source_created_at) or _as_date(item.created_at))).days)
            for item in closures
        ]
        if not durations:
            return MetricValue(None, metadata=metadata, insufficient_reason="No SIO closures in the period")
        return MetricValue(round(sum(durations) / len(durations), 2), metadata=metadata)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _incident_metric(context: CalculationContext, definition: KPIDefinition) -> MetricValue:
    key = definition.key
    metadata = _base_metadata(context, source="incidents + incident_investigations", formula=key)
    metadata["source_count"] = len(context.incidents)
    classification_keys = {
        "near_miss_count": "near_miss", "near_misses": "near_miss",
        "first_aid_count": "first_aid_injury", "first_aid_incidents": "first_aid_injury",
        "medical_treatment_count": "medical_treatment_injury", "medical_treatment_incidents": "medical_treatment_injury",
        "restricted_work_count": "restricted_work_case", "restricted_work_incidents": "restricted_work_case",
        "lost_time_injury_count": "lost_time_injury", "lost_time_incidents": "lost_time_injury",
        "occupational_illness_count": "occupational_illness", "occupational_illness_incidents": "occupational_illness",
        "fatality_count": "fatality", "fatalities": "fatality",
        "property_damage_count": "property_damage", "property_damage_incidents": "property_damage",
        "environmental_incident_count": "environmental_incident", "environmental_incidents": "environmental_incident",
    }
    if key in classification_keys:
        code = classification_keys[key]
        value = sum(item.incident_type == code for item in context.incidents)
        # Historical incidents predate structured classification; preserve the
        # legacy lost-time indicator in the LTI numerator.
        if code == "lost_time_injury":
            value = sum(item.incident_type == code or item.is_lost_time for item in context.incidents)
        return MetricValue(float(value), metadata=metadata)
    if key == "total_incidents":
        return MetricValue(float(len(context.incidents)), metadata=metadata)
    if key == "high_critical_incidents":
        return MetricValue(float(sum(item.severity in {IncidentSeverity.high, IncidentSeverity.critical} for item in context.incidents)), metadata=metadata)
    if key in {"open_investigations", "overdue_investigations"}:
        open_statuses = {
            IncidentInvestigationStatus.draft, IncidentInvestigationStatus.assigned,
            IncidentInvestigationStatus.in_progress, IncidentInvestigationStatus.pending_review,
            IncidentInvestigationStatus.pending_approval,
        }
        open_items = [item for item in context.investigations if item.status in open_statuses]
        value = len(open_items) if key == "open_investigations" else sum(
            bool(item.target_completion_date and item.target_completion_date < context.end)
            for item in open_items
        )
        return MetricValue(float(value), metadata=metadata)
    if key == "average_investigation_closure_days":
        durations = [
            max(0, (_as_date(item.completed_at) - _as_date(item.created_at)).days)
            for item in context.investigations
            if item.completed_at and context._in_period(item.completed_at)
        ]
        if not durations:
            return MetricValue(None, metadata=metadata, insufficient_reason="No completed investigations in the period")
        return MetricValue(round(sum(durations) / len(durations), 2), metadata=metadata)
    if key == "average_incident_closure_days":
        durations = [
            max(0, (_as_date(item.closed_at) - _as_date(item.reported_at or item.created_at)).days)
            for item in context.incidents if item.closed_at and context._in_period(item.closed_at)
        ]
        if not durations:
            return MetricValue(None, metadata=metadata, insufficient_reason="No incident closures in the period")
        return MetricValue(round(sum(durations) / len(durations), 2), metadata=metadata)
    if key == "repeat_cause_categories":
        counts = {}
        for cause in context.incident_causes:
            category = cause.category_code or "uncategorised"
            counts[category] = counts.get(category, 0) + 1
        metadata["repeat_categories"] = {category: count for category, count in counts.items() if count > 1}
        return MetricValue(float(sum(count - 1 for count in counts.values() if count > 1)), metadata=metadata)
    if key == "days_since_last_lti":
        lti_dates = [_as_date(item.occurred_at) for item in context._scoped(Incident) if item.is_lost_time and _as_date(item.occurred_at) <= context.end]
        if not lti_dates:
            return MetricValue(None, metadata=metadata, insufficient_reason="No historical lost-time injury is available")
        return MetricValue(float((context.end - max(lti_dates)).days), metadata=metadata)
    if key in {"trir", "ltifr"}:
        numerator = sum(
            (item.is_recordable or item.is_lost_time) if key == "trir" else item.is_lost_time
            for item in context.incidents
        )
        hours, exposure_metadata = context.exposure_hours()
        metadata.update(exposure_metadata)
        multiplier = definition.multiplier
        if multiplier is None or multiplier <= 0:
            return MetricValue(None, float(numerator), hours, metadata, "The KPI multiplier is not configured")
        if hours is None or hours <= 0:
            return MetricValue(None, float(numerator), hours, metadata, "Actual workforce hours are unavailable")
        metadata["formula"] = f"{numerator} × {multiplier:g} / {hours:g}"
        return MetricValue(round(numerator * multiplier / hours, 2), float(numerator), hours, metadata)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _hazard_metric(context: CalculationContext, key: str) -> MetricValue:
    open_items = [item for item in context.hazards if item.status != HazardStatus.closed]
    metadata = _base_metadata(context, source="hazards", formula=key)
    metadata["source_count"] = len(context.hazards)
    values = {
        "open_hazards": len(open_items),
        "critical_hazards": sum(item.risk_level == HazardRiskLevel.critical for item in open_items),
        "high_risk_hazards": sum(item.risk_level == HazardRiskLevel.high for item in open_items),
        "uncontrolled_hazards": sum(item.status == HazardStatus.open for item in open_items),
        "overdue_controls": sum(bool(item.due_date and item.due_date < context.end) for item in open_items),
        "hazards_due_review": sum(bool(item.review_date and item.review_date <= context.end) for item in open_items),
        "new_hazards": sum(context._in_period(item.created_at) for item in context.hazards),
        "hazards_closed": sum(item.status == HazardStatus.closed and context._in_period(item.updated_at) for item in context.hazards),
        "residual_high_risk_hazards": sum(item.risk_level in {HazardRiskLevel.high, HazardRiskLevel.critical} and item.status == HazardStatus.controlled for item in context.hazards),
    }
    return MetricValue(float(values[key]), metadata=metadata) if key in values else MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _inspection_metric(context: CalculationContext, key: str) -> MetricValue:
    metadata = _base_metadata(context, source="inspections", formula=key)
    planned = context.inspections
    completed = [item for item in planned if item.status in {InspectionStatus.completed, InspectionStatus.archived}]
    values = {
        "inspections_planned": len(planned),
        "inspections_completed": len(completed),
        "inspections_missed": sum(item.status not in {InspectionStatus.completed, InspectionStatus.archived} and _as_date(item.inspection_date) < context.end for item in planned),
        "inspection_findings": sum(item.number_of_non_conformities + item.number_of_observations for item in completed),
        "critical_inspection_findings": sum(item.overall_result == InspectionOverallResult.critical_non_conformance for item in completed),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "inspection_completion_rate":
        value = _percent(len(completed), len(planned))
        return MetricValue(value, len(completed), len(planned), metadata, "No planned inspections in the period" if value is None else None)
    if key == "repeat_inspection_findings":
        return MetricValue(None, metadata=metadata, insufficient_reason="Repeat-finding lineage is not represented in the inspection schema")
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _audit_metric(context: CalculationContext, key: str) -> MetricValue:
    metadata = _base_metadata(context, source="audit_management_records", formula=key)
    planned = context.audits
    completed = [item for item in planned if item.status == AuditStatus.closed]
    values = {
        "audits_planned": len(planned),
        "audits_completed": len(completed),
        "open_audit_findings": sum(len(item.non_conformances) for item in planned if item.status == AuditStatus.open),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "audit_completion_rate":
        value = _percent(len(completed), len(planned))
        return MetricValue(value, len(completed), len(planned), metadata, "No planned audits in the period" if value is None else None)
    return MetricValue(None, metadata=metadata, insufficient_reason="The audit schema does not explicitly represent this finding attribute")


def _training_metric(context: CalculationContext, key: str) -> MetricValue:
    required = [item for item in context.training if item.status != TrainingStatus.cancelled]
    completed = [item for item in required if item.completed_at and _as_date(item.completed_at) <= context.end]
    metadata = _base_metadata(context, source="training_records", formula=key)
    def expiring(days: int) -> int:
        return sum(bool(item.expiry_date and context.end < item.expiry_date <= context.end + timedelta(days=days)) for item in required)
    values = {
        "training_required": len(required),
        "training_completed": len(completed),
        "training_overdue": sum(bool(item.due_date and item.due_date < context.end and item not in completed) for item in required),
        "training_expiring_30": expiring(30),
        "training_expiring_60": expiring(60),
        "training_expiring_90": expiring(90),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "training_compliance_rate":
        value = _percent(len(completed), len(required))
        return MetricValue(value, len(completed), len(required), metadata, "No required training assignments in scope" if value is None else None)
    summary = training_competency_dashboard(
        context.db, site_id=context.site_id, department_id=context.department_id, as_of=context.end
    )
    forward = training_forward_view(
        context.db, site_id=context.site_id, department_id=context.department_id, days=90, as_of=context.end
    )
    competency_expiries = [item for item in forward if item["type"] == "competency_expiry"]
    certificate_expiries = [item for item in forward if item["type"] == "certificate_expiry"]
    values = {
        "workers_requiring_training": summary["workers_requiring_training"],
        "training_assignments_open": summary["assigned_training"] + summary["overdue_training"],
        "competencies_required": summary["competencies_required"],
        "competency_gaps": summary["competency_gaps"],
        "competency_compliance_rate": summary["competency_compliance_rate"],
        "competencies_expiring_30": sum(item["date"] <= context.end + timedelta(days=30) for item in competency_expiries),
        "competencies_expiring_60": sum(item["date"] <= context.end + timedelta(days=60) for item in competency_expiries),
        "competencies_expiring_90": len(competency_expiries),
        "certificates_expiring": len(certificate_expiries),
        "authorizations_expired": summary["authorization_gaps"],
        "workers_not_eligible": summary["work_eligibility_failures"],
        "refresher_training_overdue": summary["refresher_backlog"],
        "failed_assessments": summary["failed_assessments"],
        "reassessment_backlog": summary["reassessment_backlog"],
    }
    if key == "authorizations_active":
        from app.models.training import AuthorizationStatus, WorkAuthorization
        statement = select(WorkAuthorization).where(
            WorkAuthorization.status == AuthorizationStatus.active,
            WorkAuthorization.valid_from <= context.end,
            or_(WorkAuthorization.valid_until.is_(None), WorkAuthorization.valid_until >= context.end),
        )
        if context.site_id is not None:
            statement = statement.where(WorkAuthorization.site_id == context.site_id)
        if context.department_id is not None:
            statement = statement.where(WorkAuthorization.department_id == context.department_id)
        return MetricValue(float(len(list(context.db.scalars(statement).all()))), metadata=metadata)
    if key == "expired_competencies":
        from app.models.training import CompetencyAward, CompetencyAwardStatus, ContractorWorker
        from app.models.user import User
        statement = select(CompetencyAward).where(
            or_(CompetencyAward.status == CompetencyAwardStatus.expired, CompetencyAward.valid_until < context.end)
        )
        if context.site_id is not None or context.department_id is not None:
            worker_statement = select(User.id).where(User.is_active.is_(True))
            if context.site_id is not None:
                worker_statement = worker_statement.where(User.assigned_site_id == context.site_id)
            if context.department_id is not None:
                worker_statement = worker_statement.where(User.department_id == context.department_id)
            subject_scope = CompetencyAward.worker_user_id.in_(worker_statement)
            # Contractor workers are site-scoped but do not carry a department.
            # Include them for site-only views and omit them from department views.
            if context.department_id is None:
                contractor_statement = select(ContractorWorker.id).where(ContractorWorker.active.is_(True))
                if context.site_id is not None:
                    contractor_statement = contractor_statement.where(ContractorWorker.site_id == context.site_id)
                subject_scope = or_(subject_scope, CompetencyAward.contractor_worker_id.in_(contractor_statement))
            statement = statement.where(subject_scope)
        return MetricValue(float(len(list(context.db.scalars(statement).all()))), metadata=metadata)
    if key in values:
        value = values[key]
        if value is None:
            return MetricValue(None, metadata=metadata, insufficient_reason="No applicable competency requirements in scope")
        return MetricValue(float(value), metadata=metadata)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _permit_compliance_metric(context: CalculationContext, key: str) -> MetricValue:
    metadata = _base_metadata(context, source="permits_to_work + legal_compliance_items", formula=key)
    active_statuses = {PermitStatus.approved, PermitStatus.active, PermitStatus.suspended}
    active = [item for item in context.permits if item.status in active_statuses and _as_date(item.end_datetime) >= context.end]
    def renewals(days: int) -> int:
        return sum(context.end <= _as_date(item.end_datetime) <= context.end + timedelta(days=days) for item in context.permits if item.status in active_statuses)
    applicable = [item for item in context.compliance if item.compliance_status != LegalComplianceStatus.not_applicable]
    compliant = [item for item in applicable if item.compliance_status == LegalComplianceStatus.compliant]
    values = {
        "active_permits": len(active),
        "permits_renewal_30": renewals(30),
        "permits_renewal_60": renewals(60),
        "permits_renewal_90": renewals(90),
        "expired_permits": sum(_as_date(item.end_datetime) < context.end and item.status not in {PermitStatus.closed, PermitStatus.cancelled} for item in context.permits),
        "permit_renewal_started": sum(item.status == PermitStatus.pending_approval for item in context.permits),
        "compliance_total": len(applicable),
        "compliance_compliant": len(compliant),
        "compliance_due_soon": sum(context.end <= item.next_review_date <= context.end + timedelta(days=30) for item in applicable if item.next_review_date),
        "compliance_overdue": sum(bool(item.next_review_date and item.next_review_date < context.end) for item in applicable),
    }
    if key in values:
        return MetricValue(float(values[key]), metadata=metadata)
    if key == "compliance_rate":
        value = _percent(len(compliant), len(applicable))
        return MetricValue(value, len(compliant), len(applicable), metadata, "No applicable compliance obligations in scope" if value is None else None)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _ppe_metric(context: CalculationContext, key: str) -> MetricValue:
    metadata = _base_metadata(context, source="ppe catalogue, inventory, issues, requirements and requests", formula=key)
    summary = ppe_dashboard(
        context.db,
        site_id=context.site_id,
        department_id=context.department_id,
        as_of=context.end,
    )
    issues = list_ppe_issues(
        context.db,
        site_id=context.site_id,
        department_id=context.department_id,
        limit=5000,
    )["items"]
    active = [item for item in issues if item.status in ACTIVE_ISSUE_STATUSES]
    period_issues = [item for item in issues if context.start <= item.issue_date <= context.end]

    def expiring(days: int) -> int:
        return sum(
            bool(item.expiry_date and context.end < item.expiry_date <= context.end + timedelta(days=days))
            for item in active
        )

    values = {
        "ppe_employees_requiring": summary["employees_requiring_ppe"],
        "ppe_employees_compliant": summary["fully_compliant_employees"],
        "ppe_employees_partially_compliant": summary["partially_compliant_employees"],
        "ppe_employees_non_compliant": summary["non_compliant_employees"],
        "ppe_compliance_rate": summary["compliance_rate"],
        "ppe_replacement_due": summary["replacements_due"],
        "ppe_replacement_overdue": summary["overdue_replacements"],
        "ppe_expiring_30": expiring(30),
        "ppe_expiring_60": expiring(60),
        "ppe_expiring_90": expiring(90),
        "ppe_inspections_overdue": summary["overdue_inspections"],
        "ppe_requests_outstanding": summary["pending_requests"],
        "ppe_low_stock_items": summary["low_stock_items"],
        "ppe_damaged": summary["damaged_ppe"],
        "ppe_lost": summary["lost_ppe"],
        "ppe_issued": sum(item.quantity for item in period_issues),
    }
    metadata["issue_count"] = len(period_issues)
    if key in values:
        value = values[key]
        if key == "ppe_compliance_rate" and value is None:
            return MetricValue(None, metadata=metadata, insufficient_reason="No employees have applicable PPE requirements")
        if key == "ppe_compliance_rate":
            return MetricValue(float(value), float(summary["fully_compliant_employees"]), float(summary["employees_requiring_ppe"]), metadata)
        return MetricValue(float(value), metadata=metadata)
    if key in {"ppe_issue_cost", "ppe_replacement_cost"}:
        cost_issues = period_issues if key == "ppe_issue_cost" else [item for item in period_issues if item.replacement_for_issue_id is not None]
        unavailable = sum(item.unit_cost_snapshot is None for item in cost_issues)
        metadata["unavailable_cost_records"] = unavailable
        if unavailable:
            return MetricValue(None, metadata=metadata, insufficient_reason="One or more PPE issues have no unit cost snapshot")
        return MetricValue(float(sum((item.unit_cost_snapshot or 0) * item.quantity for item in cost_issues)), metadata=metadata)
    return MetricValue(None, metadata=metadata, insufficient_reason="Calculation is not available")


def _occupational_health_metric(context: CalculationContext, key: str) -> MetricValue:
    metadata = _base_metadata(context, source="occupational health surveillance, appointments, certificates, restrictions and illness cases", formula=key)
    summary = occupational_health_dashboard(
        context.db, site_id=context.site_id, department_id=context.department_id, as_of=context.end,
    )
    values = {
        "medical_workers_requiring": summary["workers_requiring_surveillance"],
        "medical_surveillance_compliant": summary["compliant_workers"],
        "medical_surveillance_compliance_rate": summary["compliance_rate"],
        "medical_assessments_due_30": summary["due_30"],
        "medical_assessments_due_60": summary["due_60"],
        "medical_assessments_due_90": summary["due_90"],
        "medical_assessments_overdue": summary["overdue_assessments"],
        "medical_certificates_expired": summary["expired_certificates"],
        "medical_active_restrictions": summary["active_restrictions"],
        "medical_rtw_reviews_due": summary["return_to_work_reviews_due"],
        "occupational_illness_suspected": summary["occupational_illness_suspected"],
        "occupational_illness_confirmed": summary["occupational_illness_confirmed"],
        "medical_missed_appointments": summary["missed_appointments"],
    }
    if key == "medical_average_completion_delay":
        value = summary["average_completion_delay_days"]
        return MetricValue(float(value), metadata=metadata) if value is not None else MetricValue(None, metadata=metadata, insufficient_reason="No completed surveillance records in scope")
    value = values.get(key)
    if value is None:
        reason = "No workers require surveillance in scope" if key == "medical_surveillance_compliance_rate" else "Calculation is not available"
        return MetricValue(None, metadata=metadata, insufficient_reason=reason)
    if key == "medical_surveillance_compliance_rate":
        return MetricValue(float(value), float(summary["compliant_workers"]), float(summary["workers_requiring_surveillance"]), metadata)
    return MetricValue(float(value), metadata=metadata)


def calculate_kpi(context: CalculationContext, definition: KPIDefinition) -> MetricValue:
    key = definition.key
    if key.startswith("action_"):
        result = _action_metric(context, key)
    elif key.startswith("sio_"):
        result = _sio_metric(context, key)
    elif key in {
        "total_incidents", "near_miss_count", "first_aid_count", "medical_treatment_count",
        "restricted_work_count", "lost_time_injury_count", "occupational_illness_count",
        "fatality_count", "property_damage_count", "environmental_incident_count",
        "high_critical_incidents", "open_investigations", "overdue_investigations",
        "average_investigation_closure_days", "days_since_last_lti", "trir", "ltifr",
        "near_misses", "first_aid_incidents", "medical_treatment_incidents",
        "restricted_work_incidents", "lost_time_incidents", "occupational_illness_incidents",
        "fatalities", "property_damage_incidents", "environmental_incidents",
        "average_incident_closure_days", "repeat_cause_categories",
    }:
        result = _incident_metric(context, definition)
    elif key in {
        "open_hazards", "critical_hazards", "high_risk_hazards", "uncontrolled_hazards",
        "overdue_controls", "hazards_due_review", "new_hazards", "hazards_closed",
        "residual_high_risk_hazards",
    }:
        result = _hazard_metric(context, key)
    elif key.startswith("inspection") or key in {"critical_inspection_findings", "repeat_inspection_findings"}:
        result = _inspection_metric(context, key)
    elif key.startswith("audit") or key in {"major_findings", "minor_findings", "open_audit_findings", "overdue_audit_findings", "repeat_audit_findings", "audits_planned", "audits_completed"}:
        result = _audit_metric(context, key)
    elif key.startswith("training") or key in {
        "competency_gaps", "workers_requiring_training", "competencies_required",
        "competency_compliance_rate", "competencies_expiring_30", "competencies_expiring_60",
        "competencies_expiring_90", "expired_competencies", "certificates_expiring",
        "authorizations_active", "authorizations_expired", "workers_not_eligible",
        "refresher_training_overdue", "failed_assessments", "reassessment_backlog",
    }:
        result = _training_metric(context, key)
    elif key.startswith("permit") or key.startswith("compliance") or key in {"active_permits", "expired_permits"}:
        result = _permit_compliance_metric(context, key)
    elif key.startswith("ppe_"):
        result = _ppe_metric(context, key)
    elif key.startswith("medical_") or key.startswith("occupational_illness_"):
        result = _occupational_health_metric(context, key)
    else:
        result = MetricValue(
            None,
            metadata=_base_metadata(context, source="not configured", formula=definition.calculation_method),
            insufficient_reason="No calculator is registered for this KPI definition",
        )
    metadata = dict(result.metadata or {})
    metadata["kpi_definition_version"] = definition.version
    metadata["calculation_method"] = definition.calculation_method
    if result.insufficient_reason:
        metadata["insufficient_data_reason"] = result.insufficient_reason
    return MetricValue(
        value=result.value,
        numerator=result.numerator,
        denominator=result.denominator,
        metadata=metadata,
        insufficient_reason=result.insufficient_reason,
    )
