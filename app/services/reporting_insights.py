from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_register import AssetRegisterItem
from app.models.audit_management import AuditManagementRecord, AuditStatus
from app.models.contractor import ContractorRecord
from app.models.corrective_action import CorrectiveAction, CorrectiveActionPriority, CorrectiveActionStatus
from app.models.document_control import DocumentControlRecord
from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.inspection import Inspection, InspectionStatus
from app.models.legal_compliance import LegalComplianceItem
from app.models.medical_surveillance import MedicalSurveillanceRecord, MedicalSurveillanceStatus
from app.models.permit import PermitStatus, PermitToWork
from app.models.sio import SIOStatus, SafetyImprovementObservation
from app.models.training import TrainingRecord, TrainingStatus


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _scoped(db: Session, model, *, site_id: Optional[int], department_id: Optional[int] = None, department_fields: tuple[str, ...] = ()) -> list:
    statement = select(model)
    if site_id is not None:
        if not hasattr(model, "site_id"):
            return []
        statement = statement.where(model.site_id == site_id)
    records = list(db.scalars(statement).all())
    if department_id is not None:
        if not department_fields:
            return []
        records = [
            item for item in records
            if any(getattr(item, field, None) == department_id for field in department_fields)
        ]
    return records


def get_forward_view(
    db: Session,
    *,
    as_of: date,
    window_days: int = 90,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> list[dict]:
    if window_days not in {7, 30, 60, 90}:
        raise ValueError("Forward-view window must be 7, 30, 60, or 90 days")
    end = as_of + timedelta(days=window_days)
    items: list[dict] = []

    def add(source_type: str, source_id: int, title: str, obligation_date: Optional[date], *, item_site_id=None, item_department_id=None, route=None) -> None:
        if obligation_date is None or not (as_of <= obligation_date <= end):
            return
        days = (obligation_date - as_of).days
        milestone = next(value for value in (7, 30, 60, 90) if days <= value)
        items.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "title": title,
                "obligation_date": obligation_date,
                "days_until_due": days,
                "window_days": milestone,
                "site_id": item_site_id,
                "department_id": item_department_id,
                "route": route,
            }
        )

    for item in _scoped(db, PermitToWork, site_id=site_id):
        if item.status not in {PermitStatus.closed, PermitStatus.cancelled, PermitStatus.rejected}:
            add("permit", item.id, item.title, _as_date(item.end_datetime), item_site_id=item.site_id, route=f"/permits/{item.id}")
    for item in _scoped(db, TrainingRecord, site_id=site_id):
        due = item.expiry_date or item.due_date
        if item.status != TrainingStatus.cancelled:
            add("training", item.id, item.title, due, item_site_id=item.site_id, route=f"/training/{item.id}")
    for item in _scoped(db, MedicalSurveillanceRecord, site_id=site_id):
        add("medical_surveillance", item.id, item.surveillance_type, item.next_due_date or item.due_date, item_site_id=item.site_id, route=f"/medical-surveillance/{item.id}")
    for item in _scoped(db, LegalComplianceItem, site_id=site_id):
        add("legal_compliance", item.id, item.title, item.next_review_date, item_site_id=item.site_id, route=f"/legal-compliance/{item.id}")
    for item in _scoped(db, DocumentControlRecord, site_id=site_id):
        add("document", item.id, item.title, item.expiry_date, item_site_id=item.site_id, route=f"/documents/{item.id}")
    for item in _scoped(db, Inspection, site_id=site_id):
        if item.status in {InspectionStatus.draft, InspectionStatus.in_progress}:
            add("inspection", item.id, item.title, _as_date(item.inspection_date), item_site_id=item.site_id, route=f"/inspections/{item.id}")
    for item in _scoped(db, AuditManagementRecord, site_id=site_id):
        if item.status == AuditStatus.open:
            add("audit", item.id, f"{item.audit_type.value.title()} audit", item.audit_date, item_site_id=item.site_id, route=f"/audits/{item.id}")
    for item in _scoped(db, ContractorRecord, site_id=site_id):
        dates = [value for value in (item.insurance_expiry_date, item.documents_expiry_date) if value]
        if dates:
            add("contractor_certificate", item.id, item.contractor_name, min(dates), item_site_id=item.site_id, route=f"/contractors/{item.id}")
    for item in _scoped(
        db,
        CorrectiveAction,
        site_id=site_id,
        department_id=department_id,
        department_fields=("responsible_department_id", "department_id"),
    ):
        if item.recurrence_enabled and item.next_due_date:
            add("recurring_action", item.id, item.title, item.next_due_date, item_site_id=item.site_id, item_department_id=item.responsible_department_id or item.department_id, route=f"/corrective-actions/{item.id}")
    for item in _scoped(db, AssetRegisterItem, site_id=site_id):
        add("equipment_certification", item.id, item.asset_name, item.next_inspection_date, item_site_id=item.site_id, route=f"/asset-register/{item.id}")
    return sorted(items, key=lambda item: (item["obligation_date"], item["source_type"], item["source_id"]))


def get_management_exceptions(
    db: Session,
    *,
    as_of: date,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> list[dict]:
    items: list[dict] = []

    def add(source_type: str, source_id: int, title: str, severity: str, relevant_date: Optional[date], reason: str, *, item_site_id=None, item_department_id=None, route=None) -> None:
        age = max(0, (as_of - relevant_date).days) if relevant_date else 0
        items.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "title": title,
                "severity": severity,
                "age_days": age,
                "due_date": relevant_date,
                "site_id": item_site_id,
                "department_id": item_department_id,
                "reason": reason,
                "route": route,
            }
        )

    terminal_actions = {CorrectiveActionStatus.closed, CorrectiveActionStatus.cancelled, CorrectiveActionStatus.draft}
    for item in _scoped(db, CorrectiveAction, site_id=site_id, department_id=department_id, department_fields=("responsible_department_id", "department_id")):
        if item.priority in {CorrectiveActionPriority.high, CorrectiveActionPriority.critical} and item.lifecycle_status not in terminal_actions and item.current_due_date and item.current_due_date < as_of:
            add("action", item.id, item.title, item.priority.value, item.current_due_date, "High/critical action is overdue", item_site_id=item.site_id, item_department_id=item.responsible_department_id or item.department_id, route=f"/corrective-actions/{item.id}")
    for item in _scoped(db, Hazard, site_id=site_id):
        if item.risk_level in {HazardRiskLevel.high, HazardRiskLevel.critical} and item.status == HazardStatus.open:
            add("hazard", item.id, item.title, item.risk_level.value, item.due_date or _as_date(item.created_at), "High/critical hazard remains uncontrolled", item_site_id=item.site_id, route=f"/hazards/{item.id}")
    for item in _scoped(db, SafetyImprovementObservation, site_id=site_id, department_id=department_id, department_fields=("responsible_department_id", "department_id")):
        if item.status == SIOStatus.pending_verification:
            add("sio", item.id, item.description[:180], "high", item.due_date or _as_date(item.created_at), "SIO is awaiting verification", item_site_id=item.site_id, item_department_id=item.responsible_department_id or item.department_id, route=f"/sios/{item.id}")
    open_investigations = {IncidentInvestigationStatus.draft, IncidentInvestigationStatus.in_progress, IncidentInvestigationStatus.pending_approval}
    for item in _scoped(db, IncidentInvestigation, site_id=site_id):
        if item.status in open_investigations and item.target_completion_date and item.target_completion_date < as_of:
            add("investigation", item.id, f"Incident investigation #{item.id}", "high", item.target_completion_date, "Investigation is overdue", item_site_id=item.site_id, route=f"/incident-investigations/{item.id}")
    renewal_end = as_of + timedelta(days=30)
    for item in _scoped(db, PermitToWork, site_id=site_id):
        expiry = _as_date(item.end_datetime)
        if item.status in {PermitStatus.approved, PermitStatus.active, PermitStatus.suspended} and as_of <= expiry <= renewal_end:
            add("permit", item.id, item.title, "medium", expiry, "Permit is inside the 30-day renewal window", item_site_id=item.site_id, route=f"/permits/{item.id}")
    for item in _scoped(db, LegalComplianceItem, site_id=site_id):
        if item.next_review_date and item.next_review_date < as_of:
            add("legal_compliance", item.id, item.title, "high", item.next_review_date, "Statutory/compliance obligation is overdue", item_site_id=item.site_id, route=f"/legal-compliance/{item.id}")
    for item in _scoped(db, TrainingRecord, site_id=site_id):
        due = item.expiry_date or item.due_date
        if item.status in {TrainingStatus.overdue, TrainingStatus.expired} or (due and due < as_of and item.status != TrainingStatus.completed):
            add("training", item.id, item.title, "high" if item.status == TrainingStatus.expired else "medium", due, "Training is expired or overdue", item_site_id=item.site_id, route=f"/training/{item.id}")
    for item in _scoped(db, AuditManagementRecord, site_id=site_id):
        if item.status == AuditStatus.open and item.non_conformances and item.audit_date < as_of:
            add("audit", item.id, f"{item.audit_type.value.title()} audit", "medium", item.audit_date, "Audit findings remain outstanding", item_site_id=item.site_id, route=f"/audits/{item.id}")

    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return sorted(items, key=lambda item: (-rank.get(item["severity"], 0), -item["age_days"], item["source_type"], item["source_id"]))
