from datetime import date, datetime

from pydantic import BaseModel


class DashboardOverviewRead(BaseModel):
    total_incidents: int
    incidents_by_status: dict[str, int]
    incidents_by_severity: dict[str, int]
    total_hazards: int
    hazards_by_status: dict[str, int]
    hazards_by_risk_level: dict[str, int]
    total_inspections: int
    inspections_by_status: dict[str, int]
    inspections_by_overall_result: dict[str, int]
    total_corrective_actions: int
    corrective_actions_by_status: dict[str, int]
    corrective_actions_by_priority: dict[str, int]
    overdue_corrective_actions_count: int
    total_safety_kpi_records: int
    total_safety_communications: int
    total_behaviour_observations: int
    total_incident_investigations: int
    total_legal_compliance_items: int
    total_jsas: int
    total_contractors: int
    total_asset_register_items: int
    total_medical_surveillance_records: int
    total_emergency_drills: int
    total_documents: int
    total_audits: int


class DashboardSiteSummaryRead(BaseModel):
    site_id: int
    site_name: str
    incidents_count: int
    open_hazards_count: int
    critical_hazards_count: int
    inspections_count: int
    overdue_corrective_actions_count: int
    hours_worked: float
    safety_communications_count: int
    behaviour_observations_count: int
    investigations_count: int
    non_compliant_legal_items_count: int
    jsas_count: int
    contractors_count: int
    defective_assets_count: int
    medical_surveillance_due_count: int
    emergency_drills_count: int
    documents_expiring_count: int
    open_audits_count: int


class DashboardTrendsRead(BaseModel):
    incidents_by_month: dict[str, int]
    hazards_by_month: dict[str, int]
    inspections_by_month: dict[str, int]
    corrective_actions_closed_by_month: dict[str, int]
    safety_communications_by_month: dict[str, int]
    behaviour_observations_by_month: dict[str, int]
    trifr_by_month: dict[str, float]
    ltifr_by_month: dict[str, float]
    emergency_drills_by_month: dict[str, int]
    audits_by_month: dict[str, int]


class DashboardNamedCountRead(BaseModel):
    label: str
    count: int


class DashboardSiteRiskRead(BaseModel):
    site_id: int
    site_name: str
    open_critical_hazards_count: int
    open_high_hazards_count: int
    hazards_pending_review_count: int
    aggregate_risk_score: int


class DashboardHazardAlertRead(BaseModel):
    id: int
    title: str
    site_id: int | None = None
    site_name: str | None = None
    risk_level: str
    status: str
    review_date: date | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class DashboardCorrectiveActionItemRead(BaseModel):
    id: int
    title: str
    site_id: int | None = None
    site_name: str | None = None
    status: str
    priority: str
    due_date: date | None = None
    assigned_to_user_id: int | None = None


class DashboardPermitItemRead(BaseModel):
    id: int
    permit_number: str
    title: str
    site_id: int | None = None
    site_name: str | None = None
    status: str
    permit_type: str
    end_datetime: datetime


class DashboardApprovalItemRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    site_id: int | None = None
    site_name: str | None = None
    action_type: str
    status: str
    requested_by_user_id: int | None = None
    assigned_approver_user_id: int | None = None
    created_at: datetime


class DashboardCommunicationItemRead(BaseModel):
    id: int
    title: str
    site_id: int | None = None
    site_name: str | None = None
    communication_type: str
    status: str
    issued_at: datetime


class DashboardUrgentItemRead(BaseModel):
    category: str
    entity_type: str
    entity_id: int
    title: str
    site_id: int | None = None
    site_name: str | None = None
    status: str | None = None
    priority: str | None = None
    action_type: str | None = None
    reason: str
    due_date: date | None = None
    end_datetime: datetime | None = None
    created_at: datetime | None = None


class DashboardRiskRead(BaseModel):
    open_critical_hazards_count: int
    open_high_hazards_count: int
    hazards_pending_review_count: int
    critical_hazards_pending_review: list[DashboardHazardAlertRead]
    top_risk_sites: list[DashboardSiteRiskRead]
    recurring_hazard_categories: list[DashboardNamedCountRead]
    risk_level_distribution: dict[str, int]


class DashboardActionsRead(BaseModel):
    overdue_corrective_actions_count: int
    overdue_corrective_actions: list[DashboardCorrectiveActionItemRead]
    corrective_actions_due_soon_count: int
    corrective_actions_due_soon: list[DashboardCorrectiveActionItemRead]
    pending_verification_count: int
    corrective_action_status_distribution: dict[str, int]
    corrective_action_priority_distribution: dict[str, int]


class DashboardComplianceRead(BaseModel):
    training_compliance_rate: float
    overdue_training_count: int
    expired_training_count: int
    overdue_compliance_acknowledgements_count: int
    training_status_distribution: dict[str, int]
    compliance_acknowledgement_status_distribution: dict[str, int]


class DashboardPermitsRead(BaseModel):
    active_permits_count: int
    pending_approval_permits_count: int
    expiring_soon_permits_count: int
    expired_permits_count: int
    permit_status_distribution: dict[str, int]
    permit_type_distribution: dict[str, int]


class DashboardApprovalsRead(BaseModel):
    pending_approvals_count: int
    pending_approvals: list[DashboardApprovalItemRead]
    approvals_by_action_type: dict[str, int]
    approvals_by_status: dict[str, int]


class DashboardIncidentSnapshotRead(BaseModel):
    total_incidents: int
    open_incidents_count: int
    critical_open_incidents_count: int
    incidents_by_status: dict[str, int]
    incidents_by_severity: dict[str, int]


class DashboardActionSnapshotRead(BaseModel):
    overdue_corrective_actions_count: int
    corrective_actions_due_soon_count: int
    pending_verification_count: int
    corrective_action_status_distribution: dict[str, int]


class DashboardComplianceSnapshotRead(BaseModel):
    training_compliance_rate: float
    overdue_training_count: int
    expired_training_count: int
    overdue_compliance_acknowledgements_count: int


class DashboardPermitSnapshotRead(BaseModel):
    active_permits_count: int
    pending_approval_permits_count: int
    expiring_soon_permits_count: int
    expired_permits_count: int


class DashboardApprovalSnapshotRead(BaseModel):
    pending_approvals_count: int
    approvals_by_action_type: dict[str, int]
    approvals_by_status: dict[str, int]


class DashboardKPISnapshotRead(BaseModel):
    total_hours_worked: float
    recordable_incidents: int
    lost_time_incidents: int
    trifr: float
    ltifr: float


class DashboardCommunicationSnapshotRead(BaseModel):
    published_communications_count: int
    active_campaigns_count: int
    toolbox_talks_count: int
    safety_alerts_count: int
    communication_status_distribution: dict[str, int]
    communication_type_distribution: dict[str, int]
    recent_communications: list[DashboardCommunicationItemRead]


class DashboardBehaviourSnapshotRead(BaseModel):
    total_observations: int
    unsafe_acts_count: int
    positive_observations_count: int
    open_behaviour_issues_count: int
    behaviour_observation_type_distribution: dict[str, int]
    behaviour_observation_status_distribution: dict[str, int]


class DashboardInvestigationSnapshotRead(BaseModel):
    open_investigations_count: int
    pending_investigation_approvals_count: int
    investigation_status_distribution: dict[str, int]


class DashboardLegalComplianceSnapshotRead(BaseModel):
    non_compliant_items_count: int
    legal_reviews_due_soon_count: int
    legal_reviews_overdue_count: int
    legal_compliance_status_distribution: dict[str, int]


class DashboardJSASnapshotRead(BaseModel):
    pending_jsa_approvals_count: int
    jsas_due_review_count: int
    jsas_expired_count: int
    jsa_status_distribution: dict[str, int]


class DashboardContractorSnapshotRead(BaseModel):
    contractor_compliance_gaps_count: int
    contractors_pending_approval_count: int
    insurance_expiring_soon_count: int
    documents_expiring_soon_count: int


class DashboardAssetSnapshotRead(BaseModel):
    defective_assets_count: int
    assets_due_inspection_count: int
    overdue_asset_inspections_count: int
    asset_condition_distribution: dict[str, int]


class DashboardMedicalSurveillanceSnapshotRead(BaseModel):
    due_count: int
    overdue_count: int
    completed_count: int
    medical_clearance_distribution: dict[str, int]


class DashboardEmergencyDrillSnapshotRead(BaseModel):
    upcoming_drills_count: int
    overdue_drills_count: int
    completed_drills_count: int
    drill_status_distribution: dict[str, int]


class DashboardDocumentSnapshotRead(BaseModel):
    pending_document_approvals_count: int
    documents_expiring_soon_count: int
    expired_documents_count: int
    document_status_distribution: dict[str, int]


class DashboardAuditSnapshotRead(BaseModel):
    open_audits_count: int
    closed_audits_count: int
    average_audit_score: float
    audit_status_distribution: dict[str, int]


class DashboardManagementSummaryRead(BaseModel):
    incident_snapshot: DashboardIncidentSnapshotRead
    risk_snapshot: DashboardRiskRead
    action_snapshot: DashboardActionSnapshotRead
    compliance_snapshot: DashboardComplianceSnapshotRead
    permit_snapshot: DashboardPermitSnapshotRead
    approval_snapshot: DashboardApprovalSnapshotRead
    kpi_snapshot: DashboardKPISnapshotRead
    communication_snapshot: DashboardCommunicationSnapshotRead
    behaviour_snapshot: DashboardBehaviourSnapshotRead
    investigation_snapshot: DashboardInvestigationSnapshotRead
    legal_compliance_snapshot: DashboardLegalComplianceSnapshotRead
    jsa_snapshot: DashboardJSASnapshotRead
    contractor_snapshot: DashboardContractorSnapshotRead
    asset_snapshot: DashboardAssetSnapshotRead
    medical_surveillance_snapshot: DashboardMedicalSurveillanceSnapshotRead
    emergency_drill_snapshot: DashboardEmergencyDrillSnapshotRead
    document_snapshot: DashboardDocumentSnapshotRead
    audit_snapshot: DashboardAuditSnapshotRead
    top_urgent_items: list[DashboardUrgentItemRead]
