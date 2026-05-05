from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.asset_register import AssetConditionStatus, AssetRegisterItem, AssetType
from app.models.audit_management import AuditManagementRecord, AuditStatus, AuditType
from app.models.contractor import (
    ContractorComplianceDocumentsStatus,
    ContractorInductionStatus,
    ContractorOnboardingStatus,
    ContractorRecord,
)
from app.models.corrective_action import CorrectiveAction
from app.models.corrective_action import CorrectiveActionPriority, CorrectiveActionSourceType, CorrectiveActionStatus
from app.models.document_control import DocumentControlRecord, DocumentStatus, DocumentType
from app.models.emergency_drill import EmergencyDrillRecord, EmergencyDrillStatus
from app.models.hazard import Hazard
from app.models.hazard import HazardRiskLevel, HazardStatus
from app.models.incident import Incident
from app.models.incident import IncidentSeverity, IncidentStatus
from app.models.incident_investigation import IncidentInvestigation, IncidentInvestigationStatus
from app.models.inspection import Inspection
from app.models.inspection import InspectionOverallResult, InspectionStatus
from app.models.jsa import JSAStatus, JobSafetyAnalysis, ResidualRiskLevel
from app.models.legal_compliance import LegalComplianceItem, LegalComplianceStatus
from app.models.medical_surveillance import (
    MedicalClearanceStatus,
    MedicalSurveillanceRecord,
    MedicalSurveillanceStatus,
)
from app.models.user import User
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope
from app.services.export_service import (
    ExportNotFoundError,
    export_asset_register_csv,
    export_corrective_actions_csv,
    export_contractors_csv,
    export_hazards_csv,
    export_incident_investigations_csv,
    export_incidents_csv,
    export_inspections_csv,
    export_jsas_csv,
    export_legal_compliance_csv,
    export_medical_surveillance_csv,
    export_emergency_drills_csv,
    export_documents_csv,
    export_audits_csv,
    render_audit_management_report,
    render_asset_register_report,
    render_corrective_action_report,
    render_contractor_report,
    render_critical_hazards_report,
    render_document_control_report,
    render_emergency_drill_report,
    render_executive_summary_report,
    render_hazard_report,
    render_incident_investigation_report,
    render_incident_report,
    render_incidents_summary_report,
    render_inspection_report,
    render_jsa_report,
    render_legal_compliance_report,
    render_medical_surveillance_report,
    render_overdue_corrective_actions_report,
)

router = APIRouter()


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/incidents/{incident_id}/report", response_class=HTMLResponse)
def incident_report(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    ensure_site_access(current_user, incident.site_id)
    try:
        return render_incident_report(db, incident_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")


@router.get("/hazards/{hazard_id}/report", response_class=HTMLResponse)
def hazard_report(
    hazard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    hazard = db.get(Hazard, hazard_id)
    if hazard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard not found")
    ensure_site_access(current_user, hazard.site_id)
    try:
        return render_hazard_report(db, hazard_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard not found")


@router.get("/inspections/{inspection_id}/report", response_class=HTMLResponse)
def inspection_report(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    ensure_site_access(current_user, inspection.site_id)
    try:
        return render_inspection_report(db, inspection_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")


@router.get("/corrective-actions/{action_id}/report", response_class=HTMLResponse)
def corrective_action_report(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    action = db.get(CorrectiveAction, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")
    ensure_site_access(current_user, action.site_id)
    try:
        return render_corrective_action_report(db, action_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")


@router.get("/incident-investigations/{investigation_id}/report", response_class=HTMLResponse)
def incident_investigation_report(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    investigation = db.get(IncidentInvestigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident investigation not found")
    ensure_site_access(current_user, investigation.site_id)
    try:
        return render_incident_investigation_report(db, investigation_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident investigation not found")


@router.get("/legal-compliance/{item_id}/report", response_class=HTMLResponse)
def legal_compliance_report(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    item = db.get(LegalComplianceItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal compliance item not found")
    ensure_site_access(current_user, item.site_id)
    try:
        return render_legal_compliance_report(db, item_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal compliance item not found")


@router.get("/jsas/{jsa_id}/report", response_class=HTMLResponse)
def jsa_report(
    jsa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    jsa = db.get(JobSafetyAnalysis, jsa_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    ensure_site_access(current_user, jsa.site_id)
    try:
        return render_jsa_report(db, jsa_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")


@router.get("/contractors/{contractor_id}/report", response_class=HTMLResponse)
def contractor_report(
    contractor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    contractor = db.get(ContractorRecord, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
    ensure_site_access(current_user, contractor.site_id)
    try:
        return render_contractor_report(db, contractor_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")


@router.get("/asset-register/{asset_id}/report", response_class=HTMLResponse)
def asset_register_report(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    asset = db.get(AssetRegisterItem, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset register item not found")
    ensure_site_access(current_user, asset.site_id)
    try:
        return render_asset_register_report(db, asset_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset register item not found")


@router.get("/medical-surveillance/{record_id}/report", response_class=HTMLResponse)
def medical_surveillance_report(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    record = db.get(MedicalSurveillanceRecord, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical surveillance record not found")
    ensure_site_access(current_user, record.site_id)
    try:
        return render_medical_surveillance_report(db, record_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical surveillance record not found")


@router.get("/emergency-drills/{drill_id}/report", response_class=HTMLResponse)
def emergency_drill_report(
    drill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    drill = db.get(EmergencyDrillRecord, drill_id)
    if drill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency drill not found")
    ensure_site_access(current_user, drill.site_id)
    try:
        return render_emergency_drill_report(db, drill_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency drill not found")


@router.get("/documents/{document_id}/report", response_class=HTMLResponse)
def document_control_report(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    document = db.get(DocumentControlRecord, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    ensure_site_access(current_user, document.site_id)
    try:
        return render_document_control_report(db, document_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.get("/audits/{audit_id}/report", response_class=HTMLResponse)
def audit_management_report(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    audit = db.get(AuditManagementRecord, audit_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    ensure_site_access(current_user, audit.site_id)
    try:
        return render_audit_management_report(db, audit_id)
    except ExportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")


@router.get("/incidents.csv")
def incidents_csv(
    site_id: int | None = None,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_incidents_csv(db, site_id=site_id, status=status, severity=severity, date_from=date_from, date_to=date_to),
        "incidents.csv",
    )


@router.get("/hazards.csv")
def hazards_csv(
    site_id: int | None = None,
    status: HazardStatus | None = None,
    risk_level: HazardRiskLevel | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_hazards_csv(db, site_id=site_id, status=status, risk_level=risk_level, date_from=date_from, date_to=date_to),
        "hazards.csv",
    )


@router.get("/inspections.csv")
def inspections_csv(
    site_id: int | None = None,
    status: InspectionStatus | None = None,
    overall_result: InspectionOverallResult | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_inspections_csv(db, site_id=site_id, status=status, overall_result=overall_result, date_from=date_from, date_to=date_to),
        "inspections.csv",
    )


@router.get("/corrective-actions.csv")
def corrective_actions_csv(
    site_id: int | None = None,
    status: CorrectiveActionStatus | None = None,
    priority: CorrectiveActionPriority | None = None,
    assigned_to_user_id: int | None = None,
    source_type: CorrectiveActionSourceType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_corrective_actions_csv(
            db,
            site_id=site_id,
            status=status,
            priority=priority,
            assigned_to_user_id=assigned_to_user_id,
            source_type=source_type,
            date_from=date_from,
            date_to=date_to,
        ),
        "corrective-actions.csv",
    )


@router.get("/incident-investigations.csv")
def incident_investigations_csv(
    site_id: int | None = None,
    status: IncidentInvestigationStatus | None = None,
    incident_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_incident_investigations_csv(
            db,
            site_id=site_id,
            status=status,
            incident_id=incident_id,
            date_from=date_from,
            date_to=date_to,
        ),
        "incident-investigations.csv",
    )


@router.get("/legal-compliance.csv")
def legal_compliance_csv(
    site_id: int | None = None,
    status: LegalComplianceStatus | None = None,
    owner_user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_legal_compliance_csv(
            db,
            site_id=site_id,
            compliance_status=status,
            owner_user_id=owner_user_id,
            date_from=date_from,
            date_to=date_to,
        ),
        "legal-compliance.csv",
    )


@router.get("/jsas.csv")
def jsas_csv(
    site_id: int | None = None,
    status: JSAStatus | None = None,
    residual_risk_level: ResidualRiskLevel | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_jsas_csv(
            db,
            site_id=site_id,
            status=status,
            residual_risk_level=residual_risk_level,
            date_from=date_from,
            date_to=date_to,
        ),
        "jsas.csv",
    )


@router.get("/contractors.csv")
def contractors_csv(
    site_id: int | None = None,
    approved_for_work: bool | None = None,
    onboarding_status: ContractorOnboardingStatus | None = None,
    induction_status: ContractorInductionStatus | None = None,
    compliance_documents_status: ContractorComplianceDocumentsStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_contractors_csv(
            db,
            site_id=site_id,
            approved_for_work=approved_for_work,
            onboarding_status=onboarding_status,
            induction_status=induction_status,
            compliance_documents_status=compliance_documents_status,
        ),
        "contractors.csv",
    )


@router.get("/asset-register.csv")
def asset_register_csv(
    site_id: int | None = None,
    asset_type: AssetType | None = None,
    condition_status: AssetConditionStatus | None = None,
    assigned_to_user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_asset_register_csv(
            db,
            site_id=site_id,
            asset_type=asset_type,
            condition_status=condition_status,
            assigned_to_user_id=assigned_to_user_id,
            date_from=date_from,
            date_to=date_to,
        ),
        "asset-register.csv",
    )


@router.get("/medical-surveillance.csv")
def medical_surveillance_csv(
    site_id: int | None = None,
    status: MedicalSurveillanceStatus | None = None,
    employee_user_id: int | None = None,
    medical_clearance_status: MedicalClearanceStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_medical_surveillance_csv(
            db,
            site_id=site_id,
            status=status,
            employee_user_id=employee_user_id,
            medical_clearance_status=medical_clearance_status,
            date_from=date_from,
            date_to=date_to,
        ),
        "medical-surveillance.csv",
    )


@router.get("/emergency-drills.csv")
def emergency_drills_csv(
    site_id: int | None = None,
    status: EmergencyDrillStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_emergency_drills_csv(
            db,
            site_id=site_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        ),
        "emergency-drills.csv",
    )


@router.get("/documents.csv")
def documents_csv(
    site_id: int | None = None,
    status: DocumentStatus | None = None,
    document_type: DocumentType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_documents_csv(
            db,
            site_id=site_id,
            status=status,
            document_type=document_type,
            date_from=date_from,
            date_to=date_to,
        ),
        "documents.csv",
    )


@router.get("/audits.csv")
def audits_csv(
    site_id: int | None = None,
    status: AuditStatus | None = None,
    audit_type: AuditType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return _csv_response(
        export_audits_csv(
            db,
            site_id=site_id,
            status=status,
            audit_type=audit_type,
            date_from=date_from,
            date_to=date_to,
        ),
        "audits.csv",
    )


@router.get("/reports/executive-summary", response_class=HTMLResponse)
def executive_summary_report(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return render_executive_summary_report(db, site_id=site_id, date_from=date_from, date_to=date_to)


@router.get("/reports/overdue-corrective-actions", response_class=HTMLResponse)
def overdue_corrective_actions_report(
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return render_overdue_corrective_actions_report(db, site_id=site_id)


@router.get("/reports/critical-hazards", response_class=HTMLResponse)
def critical_hazards_report(
    site_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return render_critical_hazards_report(db, site_id=site_id)


@router.get("/reports/incidents-summary", response_class=HTMLResponse)
def incidents_summary_report(
    site_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    ensure_permission(current_user, Permission.EXPORTS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return render_incidents_summary_report(db, site_id=site_id, date_from=date_from, date_to=date_to)
