from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.incident import (
    IncidentSeverity,
    IncidentStatus,
    RegulatoryNotificationStatus,
    ReturnToWorkStatus,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class IncidentBase(BaseModel):
    site_id: int
    department_id: Optional[int] = None
    area_location: Optional[str] = Field(default=None, max_length=255)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    incident_type: str = Field(default="other", min_length=1, max_length=80)
    severity: IncidentSeverity
    potential_severity: Optional[str] = Field(default=None, max_length=80)
    actual_consequence: Optional[str] = None
    occurred_at: datetime
    reported_at: Optional[datetime] = None
    supervisor_user_id: Optional[int] = None
    responsible_hs_officer_user_id: Optional[int] = None
    immediate_actions_taken: Optional[str] = None
    immediate_response: dict = Field(default_factory=dict)
    immediate_response_notes: Optional[str] = None
    scene_secured: bool = False
    work_stopped: bool = False
    emergency_services_called: bool = False
    regulator_notification_required: bool = False
    regulator_notification_status: RegulatoryNotificationStatus = RegulatoryNotificationStatus.not_required
    source_external_id: Optional[str] = Field(default=None, max_length=160)
    is_recordable: bool = False
    is_lost_time: bool = False
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class IncidentCreate(IncidentBase):
    # Existing clients historically create an `open` incident explicitly.
    status: IncidentStatus = IncidentStatus.reported


class IncidentUpdate(BaseModel):
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    area_location: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    incident_type: Optional[str] = Field(default=None, min_length=1, max_length=80)
    severity: Optional[IncidentSeverity] = None
    potential_severity: Optional[str] = Field(default=None, max_length=80)
    actual_consequence: Optional[str] = None
    status: Optional[IncidentStatus] = None
    occurred_at: Optional[datetime] = None
    reported_at: Optional[datetime] = None
    supervisor_user_id: Optional[int] = None
    responsible_hs_officer_user_id: Optional[int] = None
    immediate_actions_taken: Optional[str] = None
    immediate_response: Optional[dict] = None
    immediate_response_notes: Optional[str] = None
    scene_secured: Optional[bool] = None
    work_stopped: Optional[bool] = None
    emergency_services_called: Optional[bool] = None
    regulator_notification_required: Optional[bool] = None
    regulator_notification_status: Optional[RegulatoryNotificationStatus] = None
    source_external_id: Optional[str] = Field(default=None, max_length=160)
    is_recordable: Optional[bool] = None
    is_lost_time: Optional[bool] = None
    lessons_learned: Optional[dict] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class IncidentClassificationBase(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    is_recordable: bool = False
    investigation_required: bool = False
    is_active: bool = True


class IncidentClassificationCreate(IncidentClassificationBase):
    pass


class IncidentClassificationRead(IncidentClassificationBase):
    id: int
    organisation_id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentCauseCategoryBase(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    level: Literal["immediate", "underlying", "root", "contributing", "organisational"]
    description: Optional[str] = None
    is_active: bool = True


class IncidentCauseCategoryCreate(IncidentCauseCategoryBase):
    pass


class IncidentCauseCategoryRead(IncidentCauseCategoryBase):
    id: int
    organisation_id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentPersonBase(BaseModel):
    user_id: Optional[int] = None
    contractor_id: Optional[int] = None
    external_person_reference: Optional[str] = Field(default=None, max_length=160)
    external_name: Optional[str] = Field(default=None, max_length=180)
    employee_number: Optional[str] = Field(default=None, max_length=100)
    department_name: Optional[str] = Field(default=None, max_length=180)
    job_title: Optional[str] = Field(default=None, max_length=180)
    contact_details: Optional[str] = Field(default=None, max_length=255)
    involvement_role: Literal["injured_person", "witness", "person_involved", "supervisor", "contractor_worker", "visitor"]
    statement_provided: bool = False
    statement_reference: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def has_identity(self):
        if not any((self.user_id, self.contractor_id, self.external_name)):
            raise ValueError("A system user, contractor, or external name is required")
        return self


class IncidentPersonCreate(IncidentPersonBase):
    pass


class IncidentPersonRead(IncidentPersonBase):
    id: int
    organisation_id: int
    incident_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentInjuryBase(BaseModel):
    incident_person_id: int
    injury_present: bool = False
    illness_present: bool = False
    body_part: Optional[str] = Field(default=None, max_length=160)
    injury_type: Optional[str] = Field(default=None, max_length=160)
    diagnosis_description: Optional[str] = None
    treatment_required: bool = False
    treatment_location: Optional[str] = Field(default=None, max_length=255)
    treated_by: Optional[str] = Field(default=None, max_length=180)
    hospital_referral: bool = False
    admission_required: bool = False
    days_lost: int = Field(default=0, ge=0)
    restricted_work_days: int = Field(default=0, ge=0)
    first_day_absent: Optional[date] = None
    return_to_work_date: Optional[date] = None
    permanent_disability: bool = False
    fatality: bool = False
    notes: Optional[str] = None


class IncidentInjuryCreate(IncidentInjuryBase):
    pass


class IncidentInjuryRead(IncidentInjuryBase):
    id: int
    organisation_id: int
    incident_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentTreatmentBase(BaseModel):
    incident_person_id: int
    treatment_at: Optional[datetime] = None
    treatment_type: Literal["first_aid", "clinic_treatment", "hospital_treatment", "external_medical_provider", "other"]
    provider_name: Optional[str] = Field(default=None, max_length=180)
    treatment_summary: Optional[str] = None
    referral: Optional[str] = None
    medical_certificate_reference: Optional[str] = Field(default=None, max_length=255)
    restrictions: Optional[str] = None
    follow_up_required: bool = False
    medical_surveillance_record_id: Optional[int] = None


class IncidentTreatmentCreate(IncidentTreatmentBase):
    pass


class IncidentTreatmentRead(IncidentTreatmentBase):
    id: int
    organisation_id: int
    incident_id: int
    treatment_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentWitnessBase(BaseModel):
    incident_person_id: Optional[int] = None
    witness_user_id: Optional[int] = None
    witness_name: str = Field(min_length=1, max_length=180)
    statement_at: Optional[datetime] = None
    statement: str = Field(min_length=1)
    acknowledged: bool = False
    acknowledgement_reference: Optional[str] = Field(default=None, max_length=255)


class IncidentWitnessCreate(IncidentWitnessBase):
    pass


class IncidentWitnessRead(IncidentWitnessBase):
    id: int
    organisation_id: int
    incident_id: int
    statement_at: datetime
    taken_by_user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentEventBase(BaseModel):
    event_at: datetime
    event_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    source_reference: Optional[str] = Field(default=None, max_length=255)


class IncidentEventCreate(IncidentEventBase):
    pass


class IncidentEventRead(IncidentEventBase):
    id: int
    organisation_id: int
    incident_id: int
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WhyStep(BaseModel):
    sequence: int = Field(ge=1, le=20)
    question: str = Field(default="Why?", min_length=1, max_length=500)
    answer: str = Field(min_length=1)


class IncidentCauseBase(BaseModel):
    investigation_id: Optional[int] = None
    cause_level: Literal["immediate", "underlying", "root", "contributing", "organisational"]
    category_code: Optional[str] = Field(default=None, max_length=80)
    description: str = Field(min_length=1)
    methodology: Literal["structured", "five_whys"] = "structured"
    problem_statement: Optional[str] = None
    why_steps: list[WhyStep] = Field(default_factory=list, max_length=20)
    is_root_cause: bool = False


class IncidentCauseCreate(IncidentCauseBase):
    pass


class IncidentCauseRead(IncidentCauseBase):
    id: int
    organisation_id: int
    incident_id: int
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentFindingBase(BaseModel):
    investigation_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    finding_type: str = Field(min_length=1, max_length=80)
    severity: IncidentSeverity
    evidence: Optional[str] = None
    root_cause_id: Optional[int] = None
    action_required: bool = False


class IncidentFindingCreate(IncidentFindingBase):
    pass


class IncidentFindingRead(IncidentFindingBase):
    id: int
    organisation_id: int
    incident_id: int
    unified_action_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentActionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2)
    acceptance_criteria: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    owner_user_id: Optional[int] = None
    responsible_department_id: Optional[int] = None
    due_date: Optional[date] = None
    finding_id: Optional[int] = None
    source_type: Literal["incident", "incident_investigation"] = "incident_investigation"


class RegulatoryNotificationBase(BaseModel):
    notification_required: bool = True
    regulator_name: str = Field(min_length=1, max_length=180)
    legal_basis_reference: Optional[str] = Field(default=None, max_length=255)
    notification_deadline: Optional[datetime] = None
    status: RegulatoryNotificationStatus = RegulatoryNotificationStatus.required
    notified_at: Optional[datetime] = None
    regulator_reference: Optional[str] = Field(default=None, max_length=255)
    evidence_reference: Optional[str] = Field(default=None, max_length=255)
    follow_up_required: bool = False
    notes: Optional[str] = None


class RegulatoryNotificationCreate(RegulatoryNotificationBase):
    pass


class RegulatoryNotificationRead(RegulatoryNotificationBase):
    id: int
    organisation_id: int
    incident_id: int
    notified_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReturnToWorkBase(BaseModel):
    incident_person_id: int
    status: ReturnToWorkStatus = ReturnToWorkStatus.not_required
    medical_clearance_required: bool = False
    clearance_received: bool = False
    restrictions: Optional[str] = None
    restriction_start: Optional[date] = None
    restriction_end: Optional[date] = None
    planned_return_date: Optional[date] = None
    actual_return_date: Optional[date] = None
    review_due_date: Optional[date] = None
    notes: Optional[str] = None
    medical_surveillance_record_id: Optional[int] = None


class ReturnToWorkCreate(ReturnToWorkBase):
    pass


class ReturnToWorkUpdate(BaseModel):
    status: Optional[ReturnToWorkStatus] = None
    medical_clearance_required: Optional[bool] = None
    clearance_received: Optional[bool] = None
    restrictions: Optional[str] = None
    restriction_start: Optional[date] = None
    restriction_end: Optional[date] = None
    planned_return_date: Optional[date] = None
    actual_return_date: Optional[date] = None
    review_due_date: Optional[date] = None
    notes: Optional[str] = None
    medical_surveillance_record_id: Optional[int] = None


class ReturnToWorkRead(ReturnToWorkBase):
    id: int
    organisation_id: int
    incident_id: int
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentLinkCreate(BaseModel):
    linked_entity_type: Literal["hazard", "sio", "ppe_issue", "ppe_inspection", "asset"]
    linked_entity_id: int
    involvement: dict = Field(default_factory=dict)


class IncidentLinkRead(IncidentLinkCreate):
    id: int
    organisation_id: int
    incident_id: int
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PropertyDamageCreate(BaseModel):
    asset_id: Optional[int] = None
    property_name: Optional[str] = Field(default=None, max_length=180)
    description: str = Field(min_length=1)
    estimated_cost: Optional[Decimal] = Field(default=None, ge=0)
    actual_cost: Optional[Decimal] = Field(default=None, ge=0)
    insurance_claim: bool = False
    claim_reference: Optional[str] = Field(default=None, max_length=180)
    repair_status: Optional[str] = Field(default=None, max_length=80)


class PropertyDamageRead(PropertyDamageCreate):
    id: int
    organisation_id: int
    incident_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EnvironmentalDetailCreate(BaseModel):
    spill_release: bool = False
    material: Optional[str] = Field(default=None, max_length=180)
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=40)
    affected_area: Optional[str] = Field(default=None, max_length=255)
    impact_media: list[Literal["water", "soil", "air"]] = Field(default_factory=list)
    containment: Optional[str] = None
    cleanup: Optional[str] = None
    estimated_environmental_severity: Optional[str] = Field(default=None, max_length=80)


class EnvironmentalDetailRead(EnvironmentalDetailCreate):
    id: int
    organisation_id: int
    incident_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VehicleDetailCreate(BaseModel):
    vehicle_asset_id: Optional[int] = None
    driver_person_id: Optional[int] = None
    passenger_details: list[dict] = Field(default_factory=list)
    road_location: Optional[str] = Field(default=None, max_length=255)
    third_party_details: Optional[str] = None
    police_report_reference: Optional[str] = Field(default=None, max_length=180)
    damage_details: Optional[str] = None
    testing_status: Optional[str] = Field(default=None, max_length=80)


class VehicleDetailRead(VehicleDetailCreate):
    id: int
    organisation_id: int
    incident_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClosureRequest(BaseModel):
    closure_summary: str = Field(min_length=1)
    lessons_learned: dict = Field(default_factory=dict)
    verifier_user_id: Optional[int] = None


class ClosureDecision(BaseModel):
    approved: bool
    notes: str = Field(min_length=1)


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=1)


class IncidentActivityRead(BaseModel):
    id: int
    organisation_id: int
    incident_id: int
    actor_user_id: Optional[int] = None
    event_type: str
    summary: str
    event_metadata: dict = Field(default_factory=dict)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentRead(IncidentBase):
    id: int
    organisation_id: int
    incident_reference: Optional[str] = None
    status: IncidentStatus
    reported_at: datetime
    reported_by_id: Optional[int] = None
    closure_requested: bool = False
    closure_requested_by_user_id: Optional[int] = None
    closure_requested_at: Optional[datetime] = None
    closure_summary: Optional[str] = None
    closure_verifier_user_id: Optional[int] = None
    verification_notes: Optional[str] = None
    verified_at: Optional[datetime] = None
    lessons_learned: dict = Field(default_factory=dict)
    closed_at: Optional[datetime] = None
    closed_by_user_id: Optional[int] = None
    reopened_at: Optional[datetime] = None
    reopened_by_user_id: Optional[int] = None
    reopen_reason: Optional[str] = None
    persons_affected: int = 0
    age_days: int = 0
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentWorkspaceRead(IncidentRead):
    people: list[IncidentPersonRead] = Field(default_factory=list)
    witnesses: list[IncidentWitnessRead] = Field(default_factory=list)
    events: list[IncidentEventRead] = Field(default_factory=list)
    causes: list[IncidentCauseRead] = Field(default_factory=list)
    findings: list[IncidentFindingRead] = Field(default_factory=list)
    regulatory_notifications: list[RegulatoryNotificationRead] = Field(default_factory=list)
    return_to_work_records: list[ReturnToWorkRead] = Field(default_factory=list)
    links: list[IncidentLinkRead] = Field(default_factory=list)
    activities: list[IncidentActivityRead] = Field(default_factory=list)


class IncidentMedicalRead(BaseModel):
    injuries: list[IncidentInjuryRead] = Field(default_factory=list)
    treatments: list[IncidentTreatmentRead] = Field(default_factory=list)
    return_to_work_records: list[ReturnToWorkRead] = Field(default_factory=list)


class IncidentListRead(PaginatedResponse[IncidentRead]):
    pass


class IncidentDashboardRead(BaseModel):
    incidents_this_period: int
    open_incidents: int
    open_investigations: int
    overdue_investigations: int
    awaiting_closure: int
    days_since_last_lti: Optional[int] = None
    average_investigation_duration_days: float
    average_incident_closure_days: float
    by_classification: dict[str, int]
    by_severity: dict[str, int]
    by_status: dict[str, int]
    by_site: dict[str, int]
    by_department: dict[str, int]
    top_immediate_causes: dict[str, int]
    top_root_causes: dict[str, int]
    ppe_missing_incidents: int
    ppe_failed_incidents: int
