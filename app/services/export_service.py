import csv
import html
import io
import json
from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.attachment import AttachmentEntityType
from app.models.asset_register import AssetConditionStatus, AssetRegisterItem, AssetType
from app.models.audit_management import AuditManagementRecord, AuditStatus, AuditType
from app.models.contractor import (
    ContractorComplianceDocumentsStatus,
    ContractorInductionStatus,
    ContractorOnboardingStatus,
    ContractorRecord,
)
from app.models.corrective_action import (
    CorrectiveAction,
    CorrectiveActionPriority,
    CorrectiveActionSourceType,
    CorrectiveActionStatus,
)
from app.models.document_control import DocumentControlRecord, DocumentStatus, DocumentType
from app.models.emergency_drill import EmergencyDrillRecord, EmergencyDrillStatus
from app.models.hazard import Hazard, HazardRiskLevel, HazardStatus
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.inspection import Inspection, InspectionOverallResult, InspectionStatus
from app.models.jsa import JSAStatus, JobSafetyAnalysis, ResidualRiskLevel
from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.medical_surveillance import (
    MedicalClearanceStatus,
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
)
from app.services.attachment_service import get_attachment_report_rows
from app.services.dashboard_service import get_dashboard_overview, get_site_summaries
from app.services.query_utils import apply_date_filters, is_corrective_action_overdue


class ExportNotFoundError(Exception):
    pass


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _date_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _json_value(value) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _csv(headers: list[str], rows: Iterable[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _apply_common_filters(statement: Select, model, *, site_id: Optional[int], date_field, date_from: Optional[date], date_to: Optional[date]):
    if site_id is not None:
        statement = statement.where(model.site_id == site_id)
    return apply_date_filters(statement, date_field, date_from=date_from, date_to=date_to)


def _render_html(title: str, sections: list[tuple[str, list[tuple[str, object]]]]) -> str:
    section_html = []
    for heading, rows in sections:
        row_html = "".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(_format_html_value(value))}</td></tr>"
            for label, value in rows
        )
        section_html.append(f"<section><h2>{html.escape(heading)}</h2><table>{row_html}</table></section>")
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #172033; margin: 32px; line-height: 1.45; }}
    h1 {{ font-size: 24px; margin-bottom: 8px; }}
    h2 {{ font-size: 16px; margin: 24px 0 8px; border-bottom: 1px solid #d7dde8; padding-bottom: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
    th, td {{ text-align: left; vertical-align: top; border: 1px solid #d7dde8; padding: 8px; font-size: 13px; }}
    th {{ width: 30%; background: #f4f6f9; }}
    @media print {{ body {{ margin: 16mm; }} }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>Generated report from the OHS Management System.</p>
  {''.join(section_html)}
</body>
</html>"""


def _format_html_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _get_or_404(db: Session, model, record_id: int, label: str):
    record = db.get(model, record_id)
    if record is None:
        raise ExportNotFoundError(f"{label} not found")
    return record


def render_incident_report(db: Session, incident_id: int) -> str:
    incident = _get_or_404(db, Incident, incident_id, "Incident")
    return _render_html(
        f"Incident Report #{incident.id}",
        [
            (
                "Incident Details",
                [
                    ("Title", incident.title),
                    ("Status", incident.status),
                    ("Severity", incident.severity),
                    ("Site ID", incident.site_id),
                    ("Occurred At", _date_value(incident.occurred_at)),
                    ("Reported By User ID", incident.reported_by_id),
                ],
            ),
            ("Description", [("Description", incident.description)]),
            (
                "Attachments",
                [
                    ("Metadata", incident.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.incident,
                            entity_id=incident.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_hazard_report(db: Session, hazard_id: int) -> str:
    hazard = _get_or_404(db, Hazard, hazard_id, "Hazard")
    return _render_html(
        f"Hazard Report #{hazard.id}",
        [
            (
                "Hazard Details",
                [
                    ("Title", hazard.title),
                    ("Status", hazard.status),
                    ("Risk Level", hazard.risk_level),
                    ("Risk Score", hazard.risk_score),
                    ("Likelihood", hazard.likelihood),
                    ("Impact", hazard.impact),
                    ("Site ID", hazard.site_id),
                    ("Owner User ID", hazard.owner_user_id),
                    ("Due Date", _date_value(hazard.due_date)),
                    ("Review Date", _date_value(hazard.review_date)),
                    ("Linked Incident ID", hazard.incident_id),
                ],
            ),
            ("Controls", [("Existing Controls", hazard.existing_controls), ("Additional Controls", hazard.additional_controls)]),
            ("Description", [("Description", hazard.description)]),
            (
                "Attachments",
                [
                    ("Metadata", hazard.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.hazard,
                            entity_id=hazard.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_inspection_report(db: Session, inspection_id: int) -> str:
    inspection = _get_or_404(db, Inspection, inspection_id, "Inspection")
    return _render_html(
        f"Inspection Report #{inspection.id}",
        [
            (
                "Inspection Details",
                [
                    ("Title", inspection.title),
                    ("Status", inspection.status),
                    ("Inspection Type", inspection.inspection_type),
                    ("Overall Result", inspection.overall_result),
                    ("Site ID", inspection.site_id),
                    ("Area/Location", inspection.area_location),
                    ("Inspector User ID", inspection.inspector_user_id),
                    ("Inspection Date", _date_value(inspection.inspection_date)),
                    ("Non-Conformities", inspection.number_of_non_conformities),
                    ("Observations", inspection.number_of_observations),
                ],
            ),
            ("Findings", [("Summary", inspection.findings_summary), ("Notes", inspection.notes)]),
            ("Checklist", [("Items", inspection.checklist_items)]),
            (
                "Attachments",
                [
                    ("Metadata", inspection.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.inspection,
                            entity_id=inspection.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_corrective_action_report(db: Session, action_id: int) -> str:
    action = _get_or_404(db, CorrectiveAction, action_id, "Corrective action")
    return _render_html(
        f"Corrective Action Report #{action.id}",
        [
            (
                "Corrective Action Details",
                [
                    ("Title", action.title),
                    ("Status", action.status),
                    ("Priority", action.priority),
                    ("Source Type", action.source_type),
                    ("Source ID", action.source_id),
                    ("Site ID", action.site_id),
                    ("Assigned To User ID", action.assigned_to_user_id),
                    ("Created By User ID", action.created_by_user_id),
                    ("Due Date", _date_value(action.due_date)),
                    ("Started At", _date_value(action.started_at)),
                    ("Completed At", _date_value(action.completed_at)),
                    ("Verified By User ID", action.verified_by_user_id),
                    ("Verified At", _date_value(action.verified_at)),
                    ("Overdue", is_corrective_action_overdue(action)),
                ],
            ),
            ("Description", [("Description", action.description)]),
            (
                "Closure",
                [
                    ("Closure Notes", action.closure_notes),
                    ("Evidence", action.closure_evidence_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.corrective_action,
                            entity_id=action.id,
                        ),
                    ),
                ],
            ),
            ("Verification", [("Verification Notes", action.verification_notes)]),
        ],
    )


def render_incident_investigation_report(db: Session, investigation_id: int) -> str:
    investigation = _get_or_404(db, IncidentInvestigation, investigation_id, "Incident investigation")
    return _render_html(
        f"Incident Investigation Report #{investigation.id}",
        [
            (
                "Investigation Details",
                [
                    ("Incident ID", investigation.incident_id),
                    ("Site ID", investigation.site_id),
                    ("Status", investigation.status),
                    ("Investigation Lead User ID", investigation.investigation_lead_user_id),
                    ("Target Completion Date", _date_value(investigation.target_completion_date)),
                    ("Completed At", _date_value(investigation.completed_at)),
                    ("Approved By User ID", investigation.approved_by_user_id),
                    ("Approved At", _date_value(investigation.approved_at)),
                ],
            ),
            (
                "Analysis",
                [
                    ("Investigation Team", investigation.investigation_team),
                    ("Witness Statements", investigation.witness_statements),
                    ("Immediate Causes", investigation.immediate_causes),
                    ("Underlying Causes", investigation.underlying_causes),
                    ("Root Cause", investigation.root_cause),
                    ("Five Whys", investigation.five_whys),
                    ("Contributing Factors", investigation.contributing_factors),
                    ("Recommendations", investigation.recommendations),
                ],
            ),
            (
                "Attachments",
                [
                    ("Metadata", investigation.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.incident_investigation,
                            entity_id=investigation.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_legal_compliance_report(db: Session, item_id: int) -> str:
    item = _get_or_404(db, LegalComplianceItem, item_id, "Legal compliance item")
    return _render_html(
        f"Legal Compliance Report #{item.id}",
        [
            (
                "Register Item",
                [
                    ("Title", item.title),
                    ("Regulatory Body", item.regulatory_body),
                    ("Legal Reference", item.legal_reference),
                    ("Compliance Status", item.compliance_status),
                    ("Site ID", item.site_id),
                    ("Owner User ID", item.owner_user_id),
                    ("Review Frequency", item.review_frequency),
                    ("Next Review Date", _date_value(item.next_review_date)),
                    ("Last Reviewed At", _date_value(item.last_reviewed_at)),
                    ("Evidence Required", item.evidence_required),
                ],
            ),
            ("Requirement Summary", [("Summary", item.requirement_summary), ("Notes", item.notes)]),
            (
                "Attachments",
                [
                    ("Metadata", item.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.legal_compliance,
                            entity_id=item.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_jsa_report(db: Session, jsa_id: int) -> str:
    jsa = _get_or_404(db, JobSafetyAnalysis, jsa_id, "JSA")
    return _render_html(
        f"JSA Report #{jsa.id}",
        [
            (
                "JSA Details",
                [
                    ("Title", jsa.title),
                    ("Site ID", jsa.site_id),
                    ("Department or Area", jsa.department_or_area),
                    ("Status", jsa.status),
                    ("Residual Risk Level", jsa.residual_risk_level),
                    ("Review Date", _date_value(jsa.review_date)),
                    ("Approved By User ID", jsa.approved_by_user_id),
                    ("Approved At", _date_value(jsa.approved_at)),
                ],
            ),
            (
                "Risk Assessment",
                [
                    ("Job Steps", jsa.job_steps),
                    ("Hazards", jsa.hazards),
                    ("Controls", jsa.controls),
                    ("PPE Required", jsa.ppe_required),
                ],
            ),
            (
                "Attachments",
                [
                    ("Metadata", jsa.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.jsa,
                            entity_id=jsa.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_contractor_report(db: Session, contractor_id: int) -> str:
    contractor = _get_or_404(db, ContractorRecord, contractor_id, "Contractor")
    return _render_html(
        f"Contractor Report #{contractor.id}",
        [
            (
                "Contractor Details",
                [
                    ("Contractor Name", contractor.contractor_name),
                    ("Contact Person", contractor.contact_person),
                    ("Contact Email", contractor.contact_email),
                    ("Contact Phone", contractor.contact_phone),
                    ("Site ID", contractor.site_id),
                    ("Onboarding Status", contractor.onboarding_status),
                    ("Induction Status", contractor.induction_status),
                    ("Insurance Expiry Date", _date_value(contractor.insurance_expiry_date)),
                    ("Compliance Documents Status", contractor.compliance_documents_status),
                    ("Documents Expiry Date", _date_value(contractor.documents_expiry_date)),
                    ("Approved For Work", contractor.approved_for_work),
                ],
            ),
            ("Work Scope", [("Scope", contractor.work_scope), ("Notes", contractor.notes)]),
            (
                "Attachments",
                [
                    ("Metadata", contractor.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.contractor,
                            entity_id=contractor.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_asset_register_report(db: Session, asset_id: int) -> str:
    asset = _get_or_404(db, AssetRegisterItem, asset_id, "Asset register item")
    return _render_html(
        f"Asset Register Report #{asset.id}",
        [
            (
                "Asset Details",
                [
                    ("Asset Type", asset.asset_type),
                    ("Asset Name", asset.asset_name),
                    ("Asset Tag", asset.asset_tag),
                    ("Site ID", asset.site_id),
                    ("Location", asset.location),
                    ("Assigned To User ID", asset.assigned_to_user_id),
                    ("Inspection Frequency", asset.inspection_frequency),
                    ("Next Inspection Date", _date_value(asset.next_inspection_date)),
                    ("Condition Status", asset.condition_status),
                    ("Last Inspected At", _date_value(asset.last_inspected_at)),
                ],
            ),
            ("Notes", [("Notes", asset.notes)]),
            (
                "Attachments",
                [
                    ("Metadata", asset.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.asset_register,
                            entity_id=asset.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_medical_surveillance_report(db: Session, record_id: int) -> str:
    record = _get_or_404(db, MedicalSurveillanceRecord, record_id, "Medical surveillance record")
    return _render_html(
        f"Medical Surveillance Report #{record.id}",
        [
            (
                "Surveillance Details",
                [
                    ("Employee User ID", record.employee_user_id),
                    ("Site ID", record.site_id),
                    ("Surveillance Type", record.surveillance_type),
                    ("Due Date", _date_value(record.due_date)),
                    ("Completed At", _date_value(record.completed_at)),
                    ("Status", record.status),
                    ("Medical Clearance Status", record.medical_clearance_status),
                    ("Next Due Date", _date_value(record.next_due_date)),
                ],
            ),
            ("Results", [("Results Summary", record.results_summary), ("Notes", record.notes)]),
            (
                "Attachments",
                [
                    ("Metadata", record.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.medical_surveillance,
                            entity_id=record.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_emergency_drill_report(db: Session, drill_id: int) -> str:
    drill = _get_or_404(db, EmergencyDrillRecord, drill_id, "Emergency drill")
    return _render_html(
        f"Emergency Drill Report #{drill.id}",
        [
            (
                "Drill Details",
                [
                    ("Emergency Type", drill.emergency_type),
                    ("Site ID", drill.site_id),
                    ("Drill Date", _date_value(drill.drill_date)),
                    ("Status", drill.status),
                    ("Next Drill Date", _date_value(drill.next_drill_date)),
                ],
            ),
            (
                "Attendance & Outcomes",
                [
                    ("Participants", drill.participants),
                    ("Attendance Records", drill.attendance_records),
                    ("Outcome", drill.outcome),
                    ("Issues Found", drill.issues_found),
                    ("Corrective Actions", drill.corrective_actions),
                ],
            ),
            (
                "Attachments",
                [
                    ("Metadata", drill.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.emergency_drill,
                            entity_id=drill.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_document_control_report(db: Session, document_id: int) -> str:
    document = _get_or_404(db, DocumentControlRecord, document_id, "Document")
    return _render_html(
        f"Document Control Report #{document.id}",
        [
            (
                "Document Details",
                [
                    ("Title", document.title),
                    ("Document Type", document.document_type),
                    ("Version", document.version),
                    ("Site ID", document.site_id),
                    ("Status", document.status),
                    ("Approved By User ID", document.approved_by_user_id),
                    ("Approved At", _date_value(document.approved_at)),
                    ("Expiry Date", _date_value(document.expiry_date)),
                    ("Acknowledgement Required", document.acknowledgement_required),
                    ("Acknowledgement User IDs", document.acknowledgement_user_ids),
                    ("Supersedes Document ID", document.supersedes_document_id),
                ],
            ),
            (
                "Attachments",
                [
                    ("Metadata", document.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.document_control,
                            entity_id=document.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def render_audit_management_report(db: Session, audit_id: int) -> str:
    audit = _get_or_404(db, AuditManagementRecord, audit_id, "Audit")
    return _render_html(
        f"Audit Report #{audit.id}",
        [
            (
                "Audit Details",
                [
                    ("Audit Type", audit.audit_type),
                    ("Site ID", audit.site_id),
                    ("Auditor User ID", audit.auditor_user_id),
                    ("Audit Date", _date_value(audit.audit_date)),
                    ("Status", audit.status),
                    ("Audit Score", audit.audit_score),
                ],
            ),
            (
                "Findings",
                [
                    ("Findings", audit.findings),
                    ("Non-Conformances", audit.non_conformances),
                    ("Recommendations", audit.recommendations),
                    ("Corrective Action IDs", audit.corrective_action_ids),
                ],
            ),
            (
                "Attachments",
                [
                    ("Metadata", audit.attachments_metadata),
                    (
                        "Stored Attachments",
                        get_attachment_report_rows(
                            db,
                            entity_type=AttachmentEntityType.audit_management,
                            entity_id=audit.id,
                        ),
                    ),
                ],
            ),
        ],
    )


def export_incidents_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[IncidentStatus] = None,
    severity: Optional[IncidentSeverity] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(select(Incident), Incident, site_id=site_id, date_field=Incident.occurred_at, date_from=date_from, date_to=date_to)
    if status is not None:
        statement = statement.where(Incident.status == status)
    if severity is not None:
        statement = statement.where(Incident.severity == severity)
    records = db.scalars(statement.order_by(Incident.occurred_at.desc(), Incident.id.desc())).all()
    headers = ["ID", "Site ID", "Title", "Status", "Severity", "Occurred At", "Reported By User ID", "Description"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Title": item.title,
            "Status": _enum_value(item.status),
            "Severity": _enum_value(item.severity),
            "Occurred At": _date_value(item.occurred_at),
            "Reported By User ID": item.reported_by_id or "",
            "Description": item.description,
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_hazards_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[HazardStatus] = None,
    risk_level: Optional[HazardRiskLevel] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(select(Hazard), Hazard, site_id=site_id, date_field=Hazard.created_at, date_from=date_from, date_to=date_to)
    if status is not None:
        statement = statement.where(Hazard.status == status)
    if risk_level is not None:
        statement = statement.where(Hazard.risk_level == risk_level)
    records = db.scalars(statement.order_by(Hazard.risk_score.desc(), Hazard.id.desc())).all()
    headers = ["ID", "Site ID", "Title", "Status", "Risk Level", "Risk Score", "Likelihood", "Impact", "Owner User ID", "Due Date"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Title": item.title,
            "Status": _enum_value(item.status),
            "Risk Level": _enum_value(item.risk_level),
            "Risk Score": item.risk_score,
            "Likelihood": item.likelihood,
            "Impact": item.impact,
            "Owner User ID": item.owner_user_id or "",
            "Due Date": _date_value(item.due_date),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_inspections_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[InspectionStatus] = None,
    overall_result: Optional[InspectionOverallResult] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(select(Inspection), Inspection, site_id=site_id, date_field=Inspection.inspection_date, date_from=date_from, date_to=date_to)
    if status is not None:
        statement = statement.where(Inspection.status == status)
    if overall_result is not None:
        statement = statement.where(Inspection.overall_result == overall_result)
    records = db.scalars(statement.order_by(Inspection.inspection_date.desc(), Inspection.id.desc())).all()
    headers = ["ID", "Site ID", "Title", "Status", "Inspection Type", "Overall Result", "Inspection Date", "Inspector User ID", "Non-Conformities", "Observations"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Title": item.title,
            "Status": _enum_value(item.status),
            "Inspection Type": item.inspection_type,
            "Overall Result": _enum_value(item.overall_result),
            "Inspection Date": _date_value(item.inspection_date),
            "Inspector User ID": item.inspector_user_id,
            "Non-Conformities": item.number_of_non_conformities,
            "Observations": item.number_of_observations,
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_corrective_actions_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[CorrectiveActionStatus] = None,
    priority: Optional[CorrectiveActionPriority] = None,
    assigned_to_user_id: Optional[int] = None,
    source_type: Optional[CorrectiveActionSourceType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(select(CorrectiveAction), CorrectiveAction, site_id=site_id, date_field=CorrectiveAction.created_at, date_from=date_from, date_to=date_to)
    if status is not None:
        statement = statement.where(CorrectiveAction.status == status)
    if priority is not None:
        statement = statement.where(CorrectiveAction.priority == priority)
    if assigned_to_user_id is not None:
        statement = statement.where(CorrectiveAction.assigned_to_user_id == assigned_to_user_id)
    if source_type is not None:
        statement = statement.where(CorrectiveAction.source_type == source_type)
    records = db.scalars(statement.order_by(CorrectiveAction.due_date.asc(), CorrectiveAction.id.desc())).all()
    headers = ["ID", "Site ID", "Title", "Status", "Priority", "Source Type", "Source ID", "Assigned To User ID", "Due Date", "Completed At", "Overdue"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Title": item.title,
            "Status": _enum_value(item.status),
            "Priority": _enum_value(item.priority),
            "Source Type": _enum_value(item.source_type),
            "Source ID": item.source_id or "",
            "Assigned To User ID": item.assigned_to_user_id or "",
            "Due Date": _date_value(item.due_date),
            "Completed At": _date_value(item.completed_at),
            "Overdue": is_corrective_action_overdue(item),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_incident_investigations_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[IncidentInvestigationStatus] = None,
    incident_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(IncidentInvestigation),
        IncidentInvestigation,
        site_id=site_id,
        date_field=IncidentInvestigation.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(IncidentInvestigation.status == status)
    if incident_id is not None:
        statement = statement.where(IncidentInvestigation.incident_id == incident_id)
    records = db.scalars(
        statement.order_by(IncidentInvestigation.created_at.desc(), IncidentInvestigation.id.desc())
    ).all()
    headers = [
        "ID",
        "Incident ID",
        "Site ID",
        "Status",
        "Investigation Lead User ID",
        "Target Completion Date",
        "Completed At",
        "Approved By User ID",
    ]
    rows = [
        {
            "ID": item.id,
            "Incident ID": item.incident_id,
            "Site ID": item.site_id,
            "Status": _enum_value(item.status),
            "Investigation Lead User ID": item.investigation_lead_user_id or "",
            "Target Completion Date": _date_value(item.target_completion_date),
            "Completed At": _date_value(item.completed_at),
            "Approved By User ID": item.approved_by_user_id or "",
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_legal_compliance_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    compliance_status: Optional[LegalComplianceStatus] = None,
    owner_user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(LegalComplianceItem),
        LegalComplianceItem,
        site_id=site_id,
        date_field=LegalComplianceItem.next_review_date,
        date_from=date_from,
        date_to=date_to,
    )
    if compliance_status is not None:
        statement = statement.where(LegalComplianceItem.compliance_status == compliance_status)
    if owner_user_id is not None:
        statement = statement.where(LegalComplianceItem.owner_user_id == owner_user_id)
    records = db.scalars(
        statement.order_by(LegalComplianceItem.next_review_date.asc().nullslast(), LegalComplianceItem.id.desc())
    ).all()
    headers = [
        "ID",
        "Site ID",
        "Title",
        "Regulatory Body",
        "Legal Reference",
        "Compliance Status",
        "Owner User ID",
        "Review Frequency",
        "Next Review Date",
        "Evidence Required",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id or "",
            "Title": item.title,
            "Regulatory Body": item.regulatory_body,
            "Legal Reference": item.legal_reference,
            "Compliance Status": _enum_value(item.compliance_status),
            "Owner User ID": item.owner_user_id,
            "Review Frequency": item.review_frequency,
            "Next Review Date": _date_value(item.next_review_date),
            "Evidence Required": item.evidence_required,
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_jsas_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[JSAStatus] = None,
    residual_risk_level: Optional[ResidualRiskLevel] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(JobSafetyAnalysis),
        JobSafetyAnalysis,
        site_id=site_id,
        date_field=JobSafetyAnalysis.review_date,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(JobSafetyAnalysis.status == status)
    if residual_risk_level is not None:
        statement = statement.where(JobSafetyAnalysis.residual_risk_level == residual_risk_level)
    records = db.scalars(
        statement.order_by(JobSafetyAnalysis.review_date.asc().nullslast(), JobSafetyAnalysis.id.desc())
    ).all()
    headers = [
        "ID",
        "Site ID",
        "Title",
        "Department Or Area",
        "Status",
        "Residual Risk Level",
        "Review Date",
        "Approved By User ID",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Title": item.title,
            "Department Or Area": item.department_or_area,
            "Status": _enum_value(item.status),
            "Residual Risk Level": _enum_value(item.residual_risk_level),
            "Review Date": _date_value(item.review_date),
            "Approved By User ID": item.approved_by_user_id or "",
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_contractors_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    approved_for_work: Optional[bool] = None,
    onboarding_status: Optional[ContractorOnboardingStatus] = None,
    induction_status: Optional[ContractorInductionStatus] = None,
    compliance_documents_status: Optional[ContractorComplianceDocumentsStatus] = None,
) -> str:
    statement = select(ContractorRecord)
    if site_id is not None:
        statement = statement.where(ContractorRecord.site_id == site_id)
    if approved_for_work is not None:
        statement = statement.where(ContractorRecord.approved_for_work == approved_for_work)
    if onboarding_status is not None:
        statement = statement.where(ContractorRecord.onboarding_status == onboarding_status)
    if induction_status is not None:
        statement = statement.where(ContractorRecord.induction_status == induction_status)
    if compliance_documents_status is not None:
        statement = statement.where(
            ContractorRecord.compliance_documents_status == compliance_documents_status
        )
    records = db.scalars(
        statement.order_by(ContractorRecord.contractor_name.asc(), ContractorRecord.id.desc())
    ).all()
    headers = [
        "ID",
        "Site ID",
        "Contractor Name",
        "Contact Person",
        "Contact Email",
        "Onboarding Status",
        "Induction Status",
        "Insurance Expiry Date",
        "Compliance Documents Status",
        "Approved For Work",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Contractor Name": item.contractor_name,
            "Contact Person": item.contact_person,
            "Contact Email": item.contact_email,
            "Onboarding Status": _enum_value(item.onboarding_status),
            "Induction Status": _enum_value(item.induction_status),
            "Insurance Expiry Date": _date_value(item.insurance_expiry_date),
            "Compliance Documents Status": _enum_value(item.compliance_documents_status),
            "Approved For Work": item.approved_for_work,
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_asset_register_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    asset_type: Optional[AssetType] = None,
    condition_status: Optional[AssetConditionStatus] = None,
    assigned_to_user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(AssetRegisterItem),
        AssetRegisterItem,
        site_id=site_id,
        date_field=AssetRegisterItem.next_inspection_date,
        date_from=date_from,
        date_to=date_to,
    )
    if asset_type is not None:
        statement = statement.where(AssetRegisterItem.asset_type == asset_type)
    if condition_status is not None:
        statement = statement.where(AssetRegisterItem.condition_status == condition_status)
    if assigned_to_user_id is not None:
        statement = statement.where(AssetRegisterItem.assigned_to_user_id == assigned_to_user_id)
    records = db.scalars(
        statement.order_by(AssetRegisterItem.asset_name.asc(), AssetRegisterItem.id.desc())
    ).all()
    headers = [
        "ID",
        "Site ID",
        "Asset Type",
        "Asset Name",
        "Asset Tag",
        "Location",
        "Assigned To User ID",
        "Inspection Frequency",
        "Next Inspection Date",
        "Condition Status",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Asset Type": _enum_value(item.asset_type),
            "Asset Name": item.asset_name,
            "Asset Tag": item.asset_tag,
            "Location": item.location,
            "Assigned To User ID": item.assigned_to_user_id or "",
            "Inspection Frequency": item.inspection_frequency,
            "Next Inspection Date": _date_value(item.next_inspection_date),
            "Condition Status": _enum_value(item.condition_status),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_medical_surveillance_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[MedicalSurveillanceStatus] = None,
    employee_user_id: Optional[int] = None,
    medical_clearance_status: Optional[MedicalClearanceStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(MedicalSurveillanceRecord),
        MedicalSurveillanceRecord,
        site_id=site_id,
        date_field=MedicalSurveillanceRecord.due_date,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(MedicalSurveillanceRecord.status == status)
    if employee_user_id is not None:
        statement = statement.where(MedicalSurveillanceRecord.employee_user_id == employee_user_id)
    if medical_clearance_status is not None:
        statement = statement.where(
            MedicalSurveillanceRecord.medical_clearance_status == medical_clearance_status
        )
    records = db.scalars(statement.order_by(MedicalSurveillanceRecord.due_date.asc(), MedicalSurveillanceRecord.id.desc())).all()
    headers = [
        "ID",
        "Site ID",
        "Employee User ID",
        "Surveillance Type",
        "Due Date",
        "Completed At",
        "Status",
        "Medical Clearance Status",
        "Next Due Date",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id or "",
            "Employee User ID": item.employee_user_id,
            "Surveillance Type": item.surveillance_type,
            "Due Date": _date_value(item.due_date),
            "Completed At": _date_value(item.completed_at),
            "Status": _enum_value(item.status),
            "Medical Clearance Status": _enum_value(item.medical_clearance_status),
            "Next Due Date": _date_value(item.next_due_date),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_emergency_drills_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[EmergencyDrillStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(EmergencyDrillRecord),
        EmergencyDrillRecord,
        site_id=site_id,
        date_field=EmergencyDrillRecord.drill_date,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(EmergencyDrillRecord.status == status)
    records = db.scalars(statement.order_by(EmergencyDrillRecord.drill_date.desc(), EmergencyDrillRecord.id.desc())).all()
    headers = ["ID", "Site ID", "Emergency Type", "Drill Date", "Status", "Next Drill Date"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Emergency Type": item.emergency_type,
            "Drill Date": _date_value(item.drill_date),
            "Status": _enum_value(item.status),
            "Next Drill Date": _date_value(item.next_drill_date),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_documents_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(DocumentControlRecord),
        DocumentControlRecord,
        site_id=site_id,
        date_field=DocumentControlRecord.expiry_date,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(DocumentControlRecord.status == status)
    if document_type is not None:
        statement = statement.where(DocumentControlRecord.document_type == document_type)
    records = db.scalars(statement.order_by(DocumentControlRecord.updated_at.desc(), DocumentControlRecord.id.desc())).all()
    headers = [
        "ID",
        "Site ID",
        "Title",
        "Document Type",
        "Version",
        "Status",
        "Approved By User ID",
        "Expiry Date",
    ]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id or "",
            "Title": item.title,
            "Document Type": _enum_value(item.document_type),
            "Version": item.version,
            "Status": _enum_value(item.status),
            "Approved By User ID": item.approved_by_user_id or "",
            "Expiry Date": _date_value(item.expiry_date),
        }
        for item in records
    ]
    return _csv(headers, rows)


def export_audits_csv(
    db: Session,
    *,
    site_id: Optional[int] = None,
    status: Optional[AuditStatus] = None,
    audit_type: Optional[AuditType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> str:
    statement = _apply_common_filters(
        select(AuditManagementRecord),
        AuditManagementRecord,
        site_id=site_id,
        date_field=AuditManagementRecord.audit_date,
        date_from=date_from,
        date_to=date_to,
    )
    if status is not None:
        statement = statement.where(AuditManagementRecord.status == status)
    if audit_type is not None:
        statement = statement.where(AuditManagementRecord.audit_type == audit_type)
    records = db.scalars(statement.order_by(AuditManagementRecord.audit_date.desc(), AuditManagementRecord.id.desc())).all()
    headers = ["ID", "Site ID", "Audit Type", "Auditor User ID", "Audit Date", "Status", "Audit Score"]
    rows = [
        {
            "ID": item.id,
            "Site ID": item.site_id,
            "Audit Type": _enum_value(item.audit_type),
            "Auditor User ID": item.auditor_user_id,
            "Audit Date": _date_value(item.audit_date),
            "Status": _enum_value(item.status),
            "Audit Score": item.audit_score if item.audit_score is not None else "",
        }
        for item in records
    ]
    return _csv(headers, rows)


def render_executive_summary_report(db: Session, *, site_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> str:
    overview = get_dashboard_overview(db, site_id=site_id, date_from=date_from, date_to=date_to)
    site_summaries = get_site_summaries(db, site_id=site_id, date_from=date_from, date_to=date_to)
    return _render_html(
        "Executive Summary Report",
        [
            ("Overview Totals", [(key.replace("_", " ").title(), value) for key, value in overview.items() if isinstance(value, int)]),
            ("Sites", [("Site Summaries", site_summaries)]),
        ],
    )


def render_overdue_corrective_actions_report(db: Session, *, site_id: Optional[int] = None) -> str:
    statement = select(CorrectiveAction)
    if site_id is not None:
        statement = statement.where(CorrectiveAction.site_id == site_id)
    actions = [action for action in db.scalars(statement).all() if is_corrective_action_overdue(action)]
    return _render_html(
        "Overdue Corrective Actions Report",
        [("Overdue Actions", [("Count", len(actions)), ("Records", [_corrective_action_summary(action) for action in actions])])],
    )


def render_critical_hazards_report(db: Session, *, site_id: Optional[int] = None) -> str:
    statement = select(Hazard).where(Hazard.risk_level == HazardRiskLevel.critical)
    if site_id is not None:
        statement = statement.where(Hazard.site_id == site_id)
    hazards = list(db.scalars(statement.order_by(Hazard.risk_score.desc(), Hazard.id.desc())).all())
    return _render_html(
        "Critical Hazards Report",
        [("Critical Hazards", [("Count", len(hazards)), ("Records", [_hazard_summary(hazard) for hazard in hazards])])],
    )


def render_incidents_summary_report(db: Session, *, site_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> str:
    overview = get_dashboard_overview(db, site_id=site_id, date_from=date_from, date_to=date_to)
    return _render_html(
        "Incidents Summary Report",
        [
            ("Incident Totals", [("Total Incidents", overview["total_incidents"])]),
            ("By Status", [(key, value) for key, value in overview["incidents_by_status"].items()]),
            ("By Severity", [(key, value) for key, value in overview["incidents_by_severity"].items()]),
        ],
    )


def _hazard_summary(hazard: Hazard) -> dict:
    return {
        "id": hazard.id,
        "title": hazard.title,
        "site_id": hazard.site_id,
        "status": _enum_value(hazard.status),
        "risk_level": _enum_value(hazard.risk_level),
        "risk_score": hazard.risk_score,
    }


def _corrective_action_summary(action: CorrectiveAction) -> dict:
    return {
        "id": action.id,
        "title": action.title,
        "site_id": action.site_id,
        "status": _enum_value(action.status),
        "priority": _enum_value(action.priority),
        "due_date": _date_value(action.due_date),
    }
