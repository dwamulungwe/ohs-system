from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin, utcnow


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    draft = "draft"
    reported = "reported"
    triaged = "triaged"
    under_investigation = "under_investigation"
    actions_open = "actions_open"
    pending_closure = "pending_closure"
    closed = "closed"
    cancelled = "cancelled"
    reopened = "reopened"
    # Historical values remain first-class so old records and clients survive.
    open = "open"
    investigating = "investigating"
    resolved = "resolved"


class ReturnToWorkStatus(str, enum.Enum):
    not_required = "not_required"
    awaiting_assessment = "awaiting_assessment"
    restricted_duties = "restricted_duties"
    fit_to_return = "fit_to_return"
    returned_to_work = "returned_to_work"


class RegulatoryNotificationStatus(str, enum.Enum):
    not_required = "not_required"
    required = "required"
    pending = "pending"
    submitted = "submitted"
    acknowledged = "acknowledged"
    overdue = "overdue"


class IncidentReferenceSequence(OrganisationOwnedMixin, Base):
    __tablename__ = "incident_reference_sequences"
    __table_args__ = (UniqueConstraint("organisation_id", "year", name="uq_incident_reference_sequence_org_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class IncidentClassification(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_classifications"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_incident_classifications_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_recordable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    investigation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class IncidentCauseCategory(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_cause_categories"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_incident_cause_categories_org_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Incident(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("organisation_id", "incident_reference", name="uq_incidents_org_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_reference: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    source_external_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    area_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_type: Mapped[str] = mapped_column(String(80), default="other", index=True, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity), nullable=False)
    potential_severity: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    actual_consequence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.reported, index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    supervisor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    responsible_hs_officer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    immediate_actions_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    immediate_response: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    immediate_response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scene_secured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    work_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emergency_services_called: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regulator_notification_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regulator_notification_status: Mapped[RegulatoryNotificationStatus] = mapped_column(
        Enum(RegulatoryNotificationStatus, native_enum=False, length=40),
        default=RegulatoryNotificationStatus.not_required, index=True, nullable=False,
    )
    is_recordable: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_lost_time: Mapped[bool] = mapped_column(default=False, nullable=False)
    attachments_metadata: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    closure_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    closure_requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closure_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closure_verifier_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lessons_learned: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reopen_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship(lazy="selectin")
    department: Mapped[Optional["Department"]] = relationship(lazy="selectin")
    reported_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reported_by_id], lazy="selectin")
    closed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[closed_by_user_id], lazy="selectin")
    people: Mapped[list["IncidentPerson"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    witnesses: Mapped[list["IncidentWitnessStatement"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    events: Mapped[list["IncidentEvent"]] = relationship(back_populates="incident", cascade="all, delete-orphan", order_by="IncidentEvent.event_at", lazy="selectin")
    causes: Mapped[list["IncidentCauseAnalysis"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    findings: Mapped[list["IncidentFinding"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    regulatory_notifications: Mapped[list["IncidentRegulatoryNotification"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    return_to_work_records: Mapped[list["IncidentReturnToWork"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    links: Mapped[list["IncidentLink"]] = relationship(back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    activities: Mapped[list["IncidentActivity"]] = relationship(back_populates="incident", cascade="all, delete-orphan", order_by="IncidentActivity.created_at", lazy="selectin")

    @property
    def persons_affected(self) -> int:
        return sum(1 for person in self.people if person.involvement_role == "injured_person")

    @property
    def age_days(self) -> int:
        end = self.closed_at.date() if self.closed_at else date.today()
        return max(0, (end - self.occurred_at.date()).days)


class IncidentPerson(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_people"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id", ondelete="SET NULL"), nullable=True)
    external_person_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    external_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    employee_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    contact_details: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    involvement_role: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    statement_provided: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    statement_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="people")
    injuries: Mapped[list["IncidentInjury"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="selectin")
    treatments: Mapped[list["IncidentTreatment"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="selectin")


class IncidentInjury(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_injuries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_person_id: Mapped[int] = mapped_column(ForeignKey("incident_people.id", ondelete="CASCADE"), index=True, nullable=False)
    injury_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    illness_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    body_part: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    injury_type: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    diagnosis_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    treatment_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    treated_by: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    hospital_referral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admission_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    days_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    restricted_work_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_day_absent: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    return_to_work_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    permanent_disability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fatality: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    person: Mapped[IncidentPerson] = relationship(back_populates="injuries")


class IncidentTreatment(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_treatments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_person_id: Mapped[int] = mapped_column(ForeignKey("incident_people.id", ondelete="CASCADE"), index=True, nullable=False)
    treatment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    treatment_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    treatment_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referral: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medical_certificate_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    medical_surveillance_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_records.id", ondelete="SET NULL"), nullable=True)

    person: Mapped[IncidentPerson] = relationship(back_populates="treatments")


class IncidentWitnessStatement(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_witness_statements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_people.id", ondelete="SET NULL"), nullable=True)
    witness_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    witness_name: Mapped[str] = mapped_column(String(180), nullable=False)
    statement_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    taken_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledgement_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="witnesses")


class IncidentEvent(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="events")


class IncidentCauseAnalysis(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_cause_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    investigation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    cause_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    category_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    methodology: Mapped[str] = mapped_column(String(40), default="structured", nullable=False)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_steps: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    is_root_cause: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="causes")


class IncidentFinding(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_findings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    investigation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_investigations.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    finding_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity), nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_cause_analyses.id", ondelete="SET NULL"), nullable=True)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unified_action_id: Mapped[Optional[int]] = mapped_column(ForeignKey("corrective_actions.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="findings")


class IncidentRegulatoryNotification(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_regulatory_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    notification_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    regulator_name: Mapped[str] = mapped_column(String(180), nullable=False)
    legal_basis_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notification_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[RegulatoryNotificationStatus] = mapped_column(Enum(RegulatoryNotificationStatus, native_enum=False, length=40), default=RegulatoryNotificationStatus.required, index=True, nullable=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    regulator_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="regulatory_notifications")


class IncidentReturnToWork(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_return_to_work"
    __table_args__ = (UniqueConstraint("incident_id", "incident_person_id", name="uq_incident_rtw_person"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_person_id: Mapped[int] = mapped_column(ForeignKey("incident_people.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[ReturnToWorkStatus] = mapped_column(Enum(ReturnToWorkStatus, native_enum=False, length=40), default=ReturnToWorkStatus.not_required, index=True, nullable=False)
    medical_clearance_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    clearance_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    restrictions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    restriction_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    restriction_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    planned_return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    actual_return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medical_surveillance_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medical_surveillance_records.id", ondelete="SET NULL"), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="return_to_work_records")


class IncidentLink(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_links"
    __table_args__ = (UniqueConstraint("incident_id", "linked_entity_type", "linked_entity_id", name="uq_incident_links_entity"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    linked_entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    linked_entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    involvement: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="links")


class IncidentPropertyDamage(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_property_damage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_register_items.id", ondelete="SET NULL"), nullable=True)
    property_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    insurance_claim: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    claim_reference: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    repair_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)


class IncidentEnvironmentalDetail(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_environmental_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    spill_release: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    material: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    affected_area: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    impact_media: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    containment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cleanup: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_environmental_severity: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)


class IncidentVehicleDetail(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "incident_vehicle_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    vehicle_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_register_items.id", ondelete="SET NULL"), nullable=True)
    driver_person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_people.id", ondelete="SET NULL"), nullable=True)
    passenger_details: Mapped[list[dict]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    road_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    third_party_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    police_report_reference: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    damage_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    testing_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)


class IncidentClosureHistory(OrganisationOwnedMixin, Base):
    __tablename__ = "incident_closure_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verifier_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class IncidentActivity(OrganisationOwnedMixin, Base):
    __tablename__ = "incident_activities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="activities")


class IncidentReminderDelivery(OrganisationOwnedMixin, Base):
    __tablename__ = "incident_reminder_deliveries"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "recipient_user_id", "milestone_key", "due_date_snapshot", name="uq_incident_reminder_delivery"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    due_date_snapshot: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
