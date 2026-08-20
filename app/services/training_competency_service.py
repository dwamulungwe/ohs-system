from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.models.contractor import ContractorRecord
from app.models.corrective_action import CorrectiveAction, CorrectiveActionSourceType
from app.models.department import Department
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.jsa import JobSafetyAnalysis
from app.models.medical_surveillance import WorkRestriction, WorkRestrictionStatus
from app.models.organisation import OrganisationSettings
from app.models.ppe import PPEIssue, PPEItem
from app.models.site import Site
from app.models.training import (
    AssignmentStatus,
    AttendanceStatus,
    AuthorizationStatus,
    Competency,
    CompetencyAward,
    CompetencyAwardStatus,
    CompetencyStatusEvent,
    ContractorWorker,
    CourseCompetencyMapping,
    EligibilityStatus,
    RequirementLevel,
    TrainingAssessment,
    TrainingAssignment,
    TrainingCertificate,
    TrainingCourse,
    TrainingDeficiencyLink,
    TrainingRecord,
    TrainingReminderDelivery,
    TrainingRequest,
    TrainingRequestStatus,
    TrainingRequirement,
    TrainingSession,
    TrainingAttendance,
    TrainingStatus,
    VerificationStatus,
    WorkAuthorization,
)
from app.models.user import User
from app.schemas.corrective_action import CorrectiveActionCreate
from app.schemas.notification import NotificationCreate
from app.schemas.training import (
    ActionGenerationRequest,
    BulkTrainingAssignmentCreate,
    CertificateVerification,
    CompetencyAwardCreate,
    CompetencyCreate,
    CompetencyStatusChange,
    CompetencyUpdate,
    ContractorWorkerCreate,
    ContractorWorkerUpdate,
    CourseCompetencyMappingCreate,
    DeficiencyLinkCreate,
    EligibilityQuery,
    TrainingAssessmentCreate,
    TrainingAssignmentCreate,
    TrainingAssignmentUpdate,
    TrainingAttendanceCreate,
    TrainingCertificateCreate,
    TrainingCourseCreate,
    TrainingCourseUpdate,
    TrainingRequestCreate,
    TrainingRequestDecision,
    TrainingRequirementCreate,
    TrainingRequirementUpdate,
    TrainingSessionCreate,
    TrainingSessionUpdate,
    WorkAuthorizationCreate,
    WorkAuthorizationUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.corrective_action_service import create_corrective_action
from app.services.notification_service import create_notification
from app.services.occupational_health_service import prerequisite_status
from app.services.ppe_service import ACTIVE_ISSUE_STATUSES, employee_profile as ppe_employee_profile
from app.services.rbac import Permission, get_normalized_role_names, has_permission


class TrainingCompetencyError(Exception):
    pass


class TrainingCompetencyNotFound(TrainingCompetencyError):
    pass


class TrainingCompetencyValidation(TrainingCompetencyError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return date.today()


def _get(db: Session, model, record_id: Optional[int], label: str, *, optional: bool = False):
    if record_id is None and optional:
        return None
    record = db.get(model, record_id)
    if record is None:
        raise TrainingCompetencyNotFound(f"{label} {record_id} was not found")
    return record


def _subject(worker_user_id: Optional[int], contractor_worker_id: Optional[int]) -> tuple[str, int]:
    if bool(worker_user_id) == bool(contractor_worker_id):
        raise TrainingCompetencyValidation("Exactly one worker_user_id or contractor_worker_id is required")
    return ("worker", int(worker_user_id)) if worker_user_id else ("contractor", int(contractor_worker_id))


def _ensure_subject(db: Session, worker_user_id: Optional[int], contractor_worker_id: Optional[int]):
    kind, subject_id = _subject(worker_user_id, contractor_worker_id)
    return _get(db, User if kind == "worker" else ContractorWorker, subject_id, kind.title())


def _audit(db: Session, *, actor_id: Optional[int], action: str, resource: str, resource_id: Optional[int], details: Optional[dict] = None) -> None:
    write_audit_log(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource,
        resource_id=resource_id,
        details=details or {},
    )


def _commit(db: Session, record, *, actor_id: Optional[int], action: str, resource: str, details: Optional[dict] = None):
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TrainingCompetencyValidation("A record with the same tenant-scoped identifier already exists") from exc
    db.refresh(record)
    _audit(db, actor_id=actor_id, action=action, resource=resource, resource_id=record.id, details=details)
    return record


def _apply(record, payload) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)


def _config(db: Session) -> dict:
    settings = db.scalar(select(OrganisationSettings))
    defaults = {
        "default_reminder_windows": [90, 60, 30, 7],
        "refresher_automation": False,
        "certificate_verification_required": False,
        "medical_prerequisite_enforcement": True,
        "ppe_prerequisite_enforcement": True,
        "permit_jsa_eligibility_enforcement": False,
        "authorization_approval_required": True,
        "competency_validity_default_days": 365,
    }
    defaults.update(dict(getattr(settings, "training_configuration", {}) or {}) if settings else {})
    return defaults


def _subject_scope_ids(db: Session, *, site_id=None, department_id=None) -> tuple[set[int], set[int]]:
    """Resolve internal and external worker IDs for a reporting/access scope."""
    user_statement = select(User.id).where(User.is_active.is_(True))
    if site_id is not None:
        user_statement = user_statement.where(User.assigned_site_id == site_id)
    if department_id is not None:
        user_statement = user_statement.where(User.department_id == department_id)
    contractor_statement = select(ContractorWorker.id).where(ContractorWorker.active.is_(True))
    if site_id is not None:
        contractor_statement = contractor_statement.where(ContractorWorker.site_id == site_id)
    if department_id is not None:
        # External worker profiles do not carry an internal department.
        contractor_ids: set[int] = set()
    else:
        contractor_ids = set(db.scalars(contractor_statement).all())
    return set(db.scalars(user_statement).all()), contractor_ids


def _subject_scope_filter(model, worker_ids: set[int], contractor_ids: set[int]):
    return or_(
        model.worker_user_id.in_(worker_ids),
        model.contractor_worker_id.in_(contractor_ids),
    )


def _course_assessment_required(db: Session, course: TrainingCourse) -> bool:
    configured = _config(db).get("assessment_required_by_training_type", {}) or {}
    key = getattr(course.training_type, "value", course.training_type)
    return bool(course.assessment_required or configured.get(key, False))


def list_courses(db: Session, *, active: Optional[bool] = None, category: Optional[str] = None, training_type=None) -> list[TrainingCourse]:
    statement = select(TrainingCourse)
    if active is not None:
        statement = statement.where(TrainingCourse.active.is_(active))
    if category:
        statement = statement.where(TrainingCourse.category == category)
    if training_type:
        statement = statement.where(TrainingCourse.training_type == training_type)
    return list(db.scalars(statement.order_by(TrainingCourse.name)).all())


def create_course(db: Session, payload: TrainingCourseCreate, *, actor_id: int) -> TrainingCourse:
    for item_id in payload.ppe_item_ids:
        _get(db, PPEItem, item_id, "PPE item")
    return _commit(db, TrainingCourse(**payload.model_dump(), is_system=False), actor_id=actor_id, action="training.course.create", resource="training_course")


def update_course(db: Session, record_id: int, payload: TrainingCourseUpdate, *, actor_id: int) -> TrainingCourse:
    record = _get(db, TrainingCourse, record_id, "Course")
    if payload.ppe_item_ids is not None:
        for item_id in payload.ppe_item_ids:
            _get(db, PPEItem, item_id, "PPE item")
    _apply(record, payload)
    return _commit(db, record, actor_id=actor_id, action="training.course.update", resource="training_course")


def list_competencies(db: Session, *, active: Optional[bool] = None, category: Optional[str] = None) -> list[Competency]:
    statement = select(Competency)
    if active is not None:
        statement = statement.where(Competency.active.is_(active))
    if category:
        statement = statement.where(Competency.category == category)
    return list(db.scalars(statement.order_by(Competency.name)).all())


def create_competency(db: Session, payload: CompetencyCreate, *, actor_id: int) -> Competency:
    for item_id in payload.ppe_item_ids:
        _get(db, PPEItem, item_id, "PPE item")
    return _commit(db, Competency(**payload.model_dump(), is_system=False), actor_id=actor_id, action="training.competency.create", resource="competency")


def update_competency(db: Session, record_id: int, payload: CompetencyUpdate, *, actor_id: int) -> Competency:
    record = _get(db, Competency, record_id, "Competency")
    if payload.ppe_item_ids is not None:
        for item_id in payload.ppe_item_ids:
            _get(db, PPEItem, item_id, "PPE item")
    _apply(record, payload)
    return _commit(db, record, actor_id=actor_id, action="training.competency.update", resource="competency")


def list_course_mappings(db: Session, *, course_id: Optional[int] = None, competency_id: Optional[int] = None) -> list[CourseCompetencyMapping]:
    statement = select(CourseCompetencyMapping)
    if course_id:
        statement = statement.where(CourseCompetencyMapping.course_id == course_id)
    if competency_id:
        statement = statement.where(CourseCompetencyMapping.competency_id == competency_id)
    return list(db.scalars(statement.order_by(CourseCompetencyMapping.sequence, CourseCompetencyMapping.id)).all())


def create_course_mapping(db: Session, payload: CourseCompetencyMappingCreate, *, actor_id: int) -> CourseCompetencyMapping:
    _get(db, TrainingCourse, payload.course_id, "Course")
    _get(db, Competency, payload.competency_id, "Competency")
    return _commit(db, CourseCompetencyMapping(**payload.model_dump()), actor_id=actor_id, action="training.course_competency.map", resource="course_competency_mapping")


def _validate_requirement_refs(db: Session, data: dict) -> None:
    target_refs = (data.get("course_id"), data.get("competency_id"), data.get("authorization_type"))
    if not any(target_refs):
        raise TrainingCompetencyValidation("A requirement must specify a course, competency, or authorization type")
    refs = (
        (TrainingCourse, data.get("course_id"), "Course"),
        (Competency, data.get("competency_id"), "Competency"),
        (Department, data.get("department_id"), "Department"),
        (Site, data.get("site_id"), "Site"),
        (Hazard, data.get("hazard_id"), "Hazard"),
        (JobSafetyAnalysis, data.get("jsa_id"), "JSA"),
        (PPEItem, data.get("ppe_item_id"), "PPE item"),
    )
    for model, record_id, label in refs:
        if record_id is not None:
            _get(db, model, record_id, label)


def list_requirements(db: Session, *, site_id=None, department_id=None, role_name=None, job_title=None, course_id=None, competency_id=None, active: Optional[bool] = None) -> list[TrainingRequirement]:
    statement = select(TrainingRequirement)
    filters = {
        TrainingRequirement.site_id: site_id,
        TrainingRequirement.department_id: department_id,
        TrainingRequirement.role_name: role_name,
        TrainingRequirement.job_title: job_title,
        TrainingRequirement.course_id: course_id,
        TrainingRequirement.competency_id: competency_id,
    }
    for column, value in filters.items():
        if value is not None:
            statement = statement.where(column == value)
    if active is not None:
        statement = statement.where(TrainingRequirement.active.is_(active))
    return list(db.scalars(statement.order_by(TrainingRequirement.name)).all())


def create_requirement(db: Session, payload: TrainingRequirementCreate, *, actor_id: int) -> TrainingRequirement:
    data = payload.model_dump()
    _validate_requirement_refs(db, data)
    return _commit(db, TrainingRequirement(**data), actor_id=actor_id, action="training.requirement.create", resource="training_requirement")


def update_requirement(db: Session, record_id: int, payload: TrainingRequirementUpdate, *, actor_id: int) -> TrainingRequirement:
    record = _get(db, TrainingRequirement, record_id, "Requirement")
    data = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    data.update(payload.model_dump(exclude_unset=True))
    _validate_requirement_refs(db, data)
    _apply(record, payload)
    return _commit(db, record, actor_id=actor_id, action="training.requirement.update", resource="training_requirement")


def list_contractor_workers(db: Session, *, contractor_id=None, site_id=None, active: Optional[bool] = None) -> list[ContractorWorker]:
    statement = select(ContractorWorker)
    if contractor_id:
        statement = statement.where(ContractorWorker.contractor_id == contractor_id)
    if site_id:
        statement = statement.where(ContractorWorker.site_id == site_id)
    if active is not None:
        statement = statement.where(ContractorWorker.active.is_(active))
    return list(db.scalars(statement.order_by(ContractorWorker.full_name)).all())


def create_contractor_worker(db: Session, payload: ContractorWorkerCreate, *, actor_id: int) -> ContractorWorker:
    _get(db, ContractorRecord, payload.contractor_id, "Contractor")
    if payload.site_id:
        _get(db, Site, payload.site_id, "Site")
    return _commit(db, ContractorWorker(**payload.model_dump()), actor_id=actor_id, action="training.contractor_worker.create", resource="contractor_worker")


def update_contractor_worker(db: Session, record_id: int, payload: ContractorWorkerUpdate, *, actor_id: int) -> ContractorWorker:
    record = _get(db, ContractorWorker, record_id, "Contractor worker")
    if payload.site_id:
        _get(db, Site, payload.site_id, "Site")
    _apply(record, payload)
    return _commit(db, record, actor_id=actor_id, action="training.contractor_worker.update", resource="contractor_worker")


def _derive_assignment_status(assignment: TrainingAssignment, *, as_of: Optional[date] = None) -> AssignmentStatus:
    today = as_of or _today()
    if assignment.status in {AssignmentStatus.completed, AssignmentStatus.cancelled}:
        return assignment.status
    if assignment.due_date and assignment.due_date < today:
        return AssignmentStatus.overdue
    return assignment.status


def list_assignments(db: Session, *, worker_user_id=None, contractor_worker_id=None, course_id=None, site_id=None, department_id=None, status=None) -> list[TrainingAssignment]:
    statement = select(TrainingAssignment)
    for column, value in (
        (TrainingAssignment.assigned_user_id, worker_user_id),
        (TrainingAssignment.contractor_worker_id, contractor_worker_id),
        (TrainingAssignment.course_id, course_id),
        (TrainingAssignment.site_id, site_id),
        (TrainingAssignment.department_id, department_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    items = list(db.scalars(statement.order_by(TrainingAssignment.due_date, TrainingAssignment.id.desc())).all())
    changed = False
    for item in items:
        derived = _derive_assignment_status(item)
        if item.status != derived:
            item.status = derived
            db.add(item)
            changed = True
    if changed:
        db.commit()
    if status is not None:
        items = [item for item in items if item.status == status]
    return items


def _create_assignment(db: Session, payload: TrainingAssignmentCreate, *, actor_id: int, commit: bool = True) -> TrainingAssignment:
    course = _get(db, TrainingCourse, payload.course_id, "Course")
    subject = _ensure_subject(db, payload.assigned_user_id, payload.contractor_worker_id)
    if payload.site_id:
        _get(db, Site, payload.site_id, "Site")
    if payload.department_id:
        _get(db, Department, payload.department_id, "Department")
    if payload.requirement_id:
        _get(db, TrainingRequirement, payload.requirement_id, "Requirement")
    data = payload.model_dump()
    if payload.assigned_user_id:
        data["site_id"] = payload.site_id or subject.assigned_site_id
        data["department_id"] = payload.department_id or subject.department_id
        data["job_title"] = payload.job_title or subject.job_title
    else:
        data["site_id"] = payload.site_id or subject.site_id
        data["job_title"] = payload.job_title or subject.job_title
        data["contractor_group"] = payload.contractor_group or subject.category
    assignment = TrainingAssignment(**data, assigned_by_user_id=actor_id)
    db.add(assignment)
    db.flush()
    if payload.assigned_user_id:
        record = TrainingRecord(
            course_id=course.id,
            title=course.name,
            training_type=course.training_type,
            site_id=data["site_id"],
            assigned_to_user_id=subject.id,
            assigned_by_user_id=actor_id,
            due_date=payload.due_date,
            status=TrainingStatus.assigned,
            certificate_metadata=[],
            notes=payload.reason,
        )
        db.add(record)
        db.flush()
        assignment.training_record_id = record.id
        db.add(assignment)
    if commit:
        db.commit()
        db.refresh(assignment)
        _audit(db, actor_id=actor_id, action="training.assignment.create", resource="training_assignment", resource_id=assignment.id, details={"source": assignment.source})
    return assignment


def create_assignment(db: Session, payload: TrainingAssignmentCreate, *, actor_id: int) -> TrainingAssignment:
    return _create_assignment(db, payload, actor_id=actor_id)


def bulk_assign(db: Session, payload: BulkTrainingAssignmentCreate, *, actor_id: int) -> dict:
    _get(db, TrainingCourse, payload.course_id, "Course")
    user_ids = set(payload.user_ids)
    contractor_ids = set(payload.contractor_worker_ids)
    statement = select(User).where(User.is_active.is_(True))
    if payload.department_id:
        _get(db, Department, payload.department_id, "Department")
        statement = statement.where(User.department_id == payload.department_id)
    if payload.site_id:
        _get(db, Site, payload.site_id, "Site")
        statement = statement.where(User.assigned_site_id == payload.site_id)
    candidates = list(db.scalars(statement).all())
    for user in candidates:
        if payload.role_name and payload.role_name not in get_normalized_role_names(user):
            continue
        if payload.job_title and (user.job_title or "").casefold() != payload.job_title.casefold():
            continue
        if payload.department_id or payload.site_id or payload.role_name or payload.job_title:
            user_ids.add(user.id)
    if not user_ids and not contractor_ids:
        raise TrainingCompetencyValidation("Bulk assignment resolved to no workers")
    created: list[TrainingAssignment] = []
    skipped: list[dict] = []
    common = payload.model_dump(exclude={"user_ids", "contractor_worker_ids", "role_name", "job_title"})
    for kind, subject_ids in (("worker", user_ids), ("contractor", contractor_ids)):
        for subject_id in sorted(subject_ids):
            _get(db, User if kind == "worker" else ContractorWorker, subject_id, kind.title())
            duplicate = db.scalar(select(TrainingAssignment).where(
                TrainingAssignment.course_id == payload.course_id,
                TrainingAssignment.assigned_user_id == (subject_id if kind == "worker" else None),
                TrainingAssignment.contractor_worker_id == (subject_id if kind == "contractor" else None),
                TrainingAssignment.status.in_([AssignmentStatus.assigned, AssignmentStatus.in_progress, AssignmentStatus.overdue]),
            ))
            if duplicate:
                skipped.append({"subject_type": kind, "subject_id": subject_id, "reason": "open assignment exists"})
                continue
            item = TrainingAssignmentCreate(
                **common,
                assigned_user_id=subject_id if kind == "worker" else None,
                contractor_worker_id=subject_id if kind == "contractor" else None,
                role_name=payload.role_name,
                job_title=payload.job_title,
            )
            created.append(_create_assignment(db, item, actor_id=actor_id, commit=False))
    db.commit()
    for item in created:
        db.refresh(item)
    _audit(db, actor_id=actor_id, action="training.assignment.bulk", resource="training_assignment", resource_id=None, details={"created": len(created), "skipped": len(skipped)})
    return {"created": created, "skipped": skipped, "created_count": len(created), "skipped_count": len(skipped)}


def update_assignment(db: Session, record_id: int, payload: TrainingAssignmentUpdate, *, actor_id: int) -> TrainingAssignment:
    record = _get(db, TrainingAssignment, record_id, "Assignment")
    _apply(record, payload)
    if record.training_record_id:
        history = _get(db, TrainingRecord, record.training_record_id, "Training record")
        history.due_date = record.due_date
        mapped = {
            AssignmentStatus.assigned: TrainingStatus.assigned,
            AssignmentStatus.in_progress: TrainingStatus.in_progress,
            AssignmentStatus.completed: TrainingStatus.completed,
            AssignmentStatus.overdue: TrainingStatus.overdue,
            AssignmentStatus.cancelled: TrainingStatus.cancelled,
        }
        history.status = mapped[record.status]
        if record.status == AssignmentStatus.completed and history.completed_at is None:
            history.completed_at = _now()
        db.add(history)
    return _commit(db, record, actor_id=actor_id, action="training.assignment.update", resource="training_assignment")


def list_sessions(db: Session, *, course_id=None, site_id=None, department_id=None, status=None, starts_from=None, starts_to=None) -> list[TrainingSession]:
    statement = select(TrainingSession)
    for column, value in ((TrainingSession.course_id, course_id), (TrainingSession.site_id, site_id), (TrainingSession.department_id, department_id), (TrainingSession.status, status)):
        if value is not None:
            statement = statement.where(column == value)
    if starts_from:
        statement = statement.where(TrainingSession.starts_at >= starts_from)
    if starts_to:
        statement = statement.where(TrainingSession.starts_at <= starts_to)
    return list(db.scalars(statement.order_by(TrainingSession.starts_at)).all())


def create_session(db: Session, payload: TrainingSessionCreate, *, actor_id: int) -> TrainingSession:
    course = _get(db, TrainingCourse, payload.course_id, "Course")
    if course.provider_required and not payload.provider and not payload.trainer_user_id:
        raise TrainingCompetencyValidation("This course requires a trainer or provider")
    if payload.ends_at and payload.ends_at <= payload.starts_at:
        raise TrainingCompetencyValidation("Session end must be after its start")
    return _commit(db, TrainingSession(**payload.model_dump()), actor_id=actor_id, action="training.session.create", resource="training_session")


def update_session(db: Session, record_id: int, payload: TrainingSessionUpdate, *, actor_id: int) -> TrainingSession:
    record = _get(db, TrainingSession, record_id, "Session")
    _apply(record, payload)
    if record.ends_at and record.ends_at <= record.starts_at:
        raise TrainingCompetencyValidation("Session end must be after its start")
    return _commit(db, record, actor_id=actor_id, action="training.session.update", resource="training_session")


def list_attendance(db: Session, session_id: int) -> list[TrainingAttendance]:
    _get(db, TrainingSession, session_id, "Session")
    return list(db.scalars(select(TrainingAttendance).where(TrainingAttendance.session_id == session_id).order_by(TrainingAttendance.id)).all())


def record_attendance(db: Session, session_id: int, payload: TrainingAttendanceCreate, *, actor_id: int) -> TrainingAttendance:
    session = _get(db, TrainingSession, session_id, "Session")
    _ensure_subject(db, payload.worker_user_id, payload.contractor_worker_id)
    if payload.assignment_id:
        assignment = _get(db, TrainingAssignment, payload.assignment_id, "Assignment")
        if assignment.course_id != session.course_id:
            raise TrainingCompetencyValidation("Attendance assignment course does not match the session")
        if assignment.assigned_user_id != payload.worker_user_id or assignment.contractor_worker_id != payload.contractor_worker_id:
            raise TrainingCompetencyValidation("Attendance subject does not match the assignment")
    if session.duration_minutes and payload.minutes_attended and payload.minutes_attended > session.duration_minutes:
        raise TrainingCompetencyValidation("Attendance minutes cannot exceed the session duration")
    existing = db.scalar(select(TrainingAttendance).where(
        TrainingAttendance.session_id == session_id,
        TrainingAttendance.worker_user_id == payload.worker_user_id,
        TrainingAttendance.contractor_worker_id == payload.contractor_worker_id,
    ))
    if existing:
        _apply(existing, payload)
        record = existing
        action = "training.attendance.update"
    else:
        if session.capacity is not None:
            count = len(list_attendance(db, session_id))
            if count >= session.capacity:
                raise TrainingCompetencyValidation("Session capacity has been reached")
        record = TrainingAttendance(session_id=session_id, **payload.model_dump())
        action = "training.attendance.create"
    if payload.status != AttendanceStatus.invited:
        record.attendance_recorded_at = _now()
        record.attendance_recorded_by_user_id = actor_id
    return _commit(db, record, actor_id=actor_id, action=action, resource="training_attendance")


def list_assessments(db: Session, *, worker_user_id=None, contractor_worker_id=None, course_id=None, competency_id=None, session_id=None, passed=None, site_id=None, department_id=None) -> list[TrainingAssessment]:
    statement = select(TrainingAssessment)
    for column, value in (
        (TrainingAssessment.worker_user_id, worker_user_id),
        (TrainingAssessment.contractor_worker_id, contractor_worker_id),
        (TrainingAssessment.course_id, course_id),
        (TrainingAssessment.competency_id, competency_id),
        (TrainingAssessment.session_id, session_id),
        (TrainingAssessment.passed, passed),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if site_id is not None or department_id is not None:
        worker_ids, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
        statement = statement.where(_subject_scope_filter(TrainingAssessment, worker_ids, contractor_ids))
    return list(db.scalars(statement.order_by(TrainingAssessment.assessment_date.desc(), TrainingAssessment.id.desc())).all())


def create_assessment(db: Session, payload: TrainingAssessmentCreate, *, actor_id: int) -> TrainingAssessment:
    _ensure_subject(db, payload.worker_user_id, payload.contractor_worker_id)
    if payload.course_id is None and payload.competency_id is None and payload.session_id is None and payload.assignment_id is None:
        raise TrainingCompetencyValidation("An assessment must reference a course, competency, session, or assignment")
    if payload.reassessment_required and payload.reassessment_due_date is None:
        raise TrainingCompetencyValidation("Reassessment due date is required when reassessment is required")
    if payload.reassessment_due_date and payload.reassessment_due_date < payload.assessment_date:
        raise TrainingCompetencyValidation("Reassessment due date cannot precede the assessment")
    course = _get(db, TrainingCourse, payload.course_id, "Course", optional=True)
    if payload.competency_id:
        _get(db, Competency, payload.competency_id, "Competency")
    if payload.session_id:
        session = _get(db, TrainingSession, payload.session_id, "Session")
        if course and session.course_id != course.id:
            raise TrainingCompetencyValidation("Assessment course does not match the training session")
        course = course or session.course
    assignment = None
    if payload.assignment_id:
        assignment = _get(db, TrainingAssignment, payload.assignment_id, "Assignment")
        if assignment.assigned_user_id != payload.worker_user_id or assignment.contractor_worker_id != payload.contractor_worker_id:
            raise TrainingCompetencyValidation("Assessment subject does not match the training assignment")
        if course and assignment.course_id != course.id:
            raise TrainingCompetencyValidation("Assessment course does not match the training assignment")
        course = course or assignment.course
    if course and course.passing_score is not None and payload.passed and payload.score is None:
        raise TrainingCompetencyValidation("A score is required for a course with a configured passing score")
    if course and course.passing_score is not None and payload.score is not None:
        expected = payload.score >= course.passing_score
        if payload.passed != expected:
            raise TrainingCompetencyValidation("Pass/fail does not match the configured passing score")
    data = payload.model_dump()
    if course:
        data["course_id"] = course.id
    if assignment and data.get("training_record_id") is None:
        data["training_record_id"] = assignment.training_record_id
    record = TrainingAssessment(**data, assessor_user_id=actor_id)
    result = _commit(db, record, actor_id=actor_id, action="training.assessment.create", resource="training_assessment", details={"passed": payload.passed})
    if assignment and payload.passed:
        assignment.status = AssignmentStatus.completed
        db.add(assignment)
        if assignment.training_record_id:
            history = _get(db, TrainingRecord, assignment.training_record_id, "Training record")
            history.status = TrainingStatus.completed
            history.completed_at = _now()
            validity = course.default_validity_period_days if course else None
            if validity:
                history.expiry_date = _today() + timedelta(days=validity)
            db.add(history)
        db.commit()
    return result


def list_certificates(db: Session, *, worker_user_id=None, contractor_worker_id=None, course_id=None, competency_id=None, expiring_before=None, site_id=None, department_id=None) -> list[TrainingCertificate]:
    statement = select(TrainingCertificate)
    for column, value in (
        (TrainingCertificate.worker_user_id, worker_user_id),
        (TrainingCertificate.contractor_worker_id, contractor_worker_id),
        (TrainingCertificate.course_id, course_id),
        (TrainingCertificate.competency_id, competency_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if expiring_before:
        statement = statement.where(TrainingCertificate.expiry_date <= expiring_before)
    if site_id is not None or department_id is not None:
        worker_ids, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
        statement = statement.where(_subject_scope_filter(TrainingCertificate, worker_ids, contractor_ids))
    return list(db.scalars(statement.order_by(TrainingCertificate.issue_date.desc(), TrainingCertificate.id.desc())).all())


def create_certificate(db: Session, payload: TrainingCertificateCreate, *, actor_id: int) -> TrainingCertificate:
    _ensure_subject(db, payload.worker_user_id, payload.contractor_worker_id)
    if payload.course_id is None and payload.competency_id is None:
        raise TrainingCompetencyValidation("A certificate must reference a course or competency")
    if payload.course_id:
        _get(db, TrainingCourse, payload.course_id, "Course")
    if payload.competency_id:
        _get(db, Competency, payload.competency_id, "Competency")
    if payload.expiry_date and payload.expiry_date < payload.issue_date:
        raise TrainingCompetencyValidation("Certificate expiry cannot precede issue")
    if payload.training_record_id:
        history = _get(db, TrainingRecord, payload.training_record_id, "Training record")
        if payload.worker_user_id is None or history.assigned_to_user_id != payload.worker_user_id:
            raise TrainingCompetencyValidation("Certificate subject does not match the training record")
        if payload.course_id and history.course_id != payload.course_id:
            raise TrainingCompetencyValidation("Certificate course does not match the training record")
    snapshot = dict(payload.metadata_snapshot)
    snapshot.update({"certificate_number": payload.certificate_number, "issue_date": payload.issue_date.isoformat(), "expiry_date": payload.expiry_date.isoformat() if payload.expiry_date else None})
    data = payload.model_dump(exclude={"metadata_snapshot"})
    record = TrainingCertificate(**data, metadata_snapshot=snapshot)
    return _commit(db, record, actor_id=actor_id, action="training.certificate.create", resource="training_certificate")


def verify_certificate(db: Session, record_id: int, payload: CertificateVerification, *, actor_id: int) -> TrainingCertificate:
    record = _get(db, TrainingCertificate, record_id, "Certificate")
    record.verification_status = payload.verification_status
    record.verification_date = payload.verification_date or _today()
    record.verified_by_user_id = actor_id
    if payload.notes:
        record.metadata_snapshot = {**record.metadata_snapshot, "verification_notes": payload.notes}
    return _commit(db, record, actor_id=actor_id, action="training.certificate.verify", resource="training_certificate", details={"status": payload.verification_status.value})


def _valid_training_record(db: Session, *, worker_id: int, course_id: int, as_of: date) -> tuple[Optional[TrainingRecord], Optional[str]]:
    records = list(db.scalars(select(TrainingRecord).where(
        TrainingRecord.assigned_to_user_id == worker_id,
        TrainingRecord.course_id == course_id,
        TrainingRecord.status.in_([TrainingStatus.completed, TrainingStatus.expired]),
    ).order_by(TrainingRecord.completed_at.desc(), TrainingRecord.id.desc())).all())
    if not records:
        return None, "course missing"
    valid = next((item for item in records if item.status == TrainingStatus.completed and (item.expiry_date is None or item.expiry_date >= as_of)), None)
    if valid:
        return valid, None
    latest = records[0]
    return None, f"course expired{f' {latest.expiry_date.isoformat()}' if latest.expiry_date else ''}"


def _valid_certificate(db: Session, *, worker_id=None, contractor_worker_id=None, course_id=None, competency_id=None, as_of: date) -> tuple[Optional[TrainingCertificate], Optional[str]]:
    statement = select(TrainingCertificate).where(
        TrainingCertificate.worker_user_id == worker_id,
        TrainingCertificate.contractor_worker_id == contractor_worker_id,
    )
    if course_id:
        statement = statement.where(TrainingCertificate.course_id == course_id)
    if competency_id:
        statement = statement.where(TrainingCertificate.competency_id == competency_id)
    certificates = list(db.scalars(statement.order_by(TrainingCertificate.issue_date.desc())).all())
    if not certificates:
        return None, "certificate missing"
    verification_required = bool(_config(db).get("certificate_verification_required"))
    valid = next((item for item in certificates if (item.expiry_date is None or item.expiry_date >= as_of) and (not verification_required or item.verification_status == VerificationStatus.verified)), None)
    if valid:
        return valid, None
    return None, "certificate expired or unverified"


def _valid_award(db: Session, *, worker_id=None, contractor_worker_id=None, competency_id: int, as_of: date) -> tuple[Optional[CompetencyAward], Optional[str]]:
    awards = list(db.scalars(select(CompetencyAward).where(
        CompetencyAward.worker_user_id == worker_id,
        CompetencyAward.contractor_worker_id == contractor_worker_id,
        CompetencyAward.competency_id == competency_id,
    ).order_by(CompetencyAward.achieved_at.desc(), CompetencyAward.id.desc())).all())
    if not awards:
        return None, "competency missing"
    award = awards[0]
    if award.status in {CompetencyAwardStatus.suspended, CompetencyAwardStatus.revoked, CompetencyAwardStatus.pending_assessment}:
        return None, f"competency {award.status.value}"
    if award.valid_until and award.valid_until < as_of:
        return None, f"competency expired {award.valid_until.isoformat()}"
    return award, None


def _medical_result(db: Session, *, worker_id: Optional[int], contractor_worker: Optional[ContractorWorker], programme_codes: list[str], as_of: date) -> tuple[Optional[bool], list[str], bool]:
    if worker_id:
        result = prerequisite_status(db, worker_id, programme_codes=programme_codes or None, as_of=as_of)
        if not result["prerequisites"]:
            return None, ["Medical clearance: insufficient data"], False
        restrictions = list(db.scalars(select(WorkRestriction).where(
            WorkRestriction.worker_user_id == worker_id,
            WorkRestriction.status == WorkRestrictionStatus.active,
            WorkRestriction.effective_from <= as_of,
            or_(WorkRestriction.effective_to.is_(None), WorkRestriction.effective_to >= as_of),
        )).all())
        return bool(result["cleared"]), ([] if result["cleared"] else ["Medical clearance: invalid"]), bool(restrictions)
    if contractor_worker.medical_clearance_status is None:
        return None, ["Medical clearance: insufficient data"], False
    cleared = contractor_worker.medical_clearance_status in {"cleared", "fit", "fit_with_restrictions"} and (contractor_worker.medical_clearance_expiry is None or contractor_worker.medical_clearance_expiry >= as_of)
    restricted = contractor_worker.medical_clearance_status == "fit_with_restrictions"
    return cleared, ([] if cleared else ["Medical clearance: invalid"]), restricted


def _ppe_result(db: Session, *, worker_id: Optional[int], contractor_worker: Optional[ContractorWorker], item_ids: list[int], as_of: Optional[date] = None) -> tuple[Optional[bool], list[str]]:
    as_of = as_of or _today()
    if worker_id:
        if item_ids:
            issues = list(db.scalars(select(PPEIssue).where(
                PPEIssue.recipient_user_id == worker_id,
                PPEIssue.item_id.in_(item_ids),
                PPEIssue.status.in_(ACTIVE_ISSUE_STATUSES),
            )).all())
            valid_ids = {item.item_id for item in issues if item.active_quantity > 0 and (item.expiry_date is None or item.expiry_date >= as_of) and (item.next_inspection_date is None or item.next_inspection_date >= as_of)}
            missing = set(item_ids) - valid_ids
            return not missing, [f"Required PPE item #{item_id}: missing, expired, or inspection overdue" for item_id in sorted(missing)]
        profile = ppe_employee_profile(db, worker_id, as_of=as_of)
        if profile["compliance_status"].value == "not_applicable":
            return None, ["PPE compliance: insufficient data"]
        return not profile["missing"], [f"Required PPE {item['item_name']}: {item['reason']}" for item in profile["missing"]]
    if contractor_worker.ppe_compliant is None:
        return None, ["PPE compliance: insufficient data"]
    return contractor_worker.ppe_compliant, ([] if contractor_worker.ppe_compliant else ["Required PPE compliance incomplete"])


def competency_prerequisites(db: Session, competency: Competency, *, worker_user_id=None, contractor_worker_id=None, as_of: Optional[date] = None) -> dict:
    as_of = as_of or _today()
    subject = _ensure_subject(db, worker_user_id, contractor_worker_id)
    mappings = list_course_mappings(db, competency_id=competency.id)
    checks: list[dict] = []
    for mapping in mappings:
        if not mapping.required:
            continue
        if worker_user_id:
            record, reason = _valid_training_record(db, worker_id=worker_user_id, course_id=mapping.course_id, as_of=as_of)
            satisfied = record is not None
        else:
            assignment = db.scalar(select(TrainingAssignment).where(
                TrainingAssignment.contractor_worker_id == contractor_worker_id,
                TrainingAssignment.course_id == mapping.course_id,
                TrainingAssignment.status == AssignmentStatus.completed,
            ).order_by(TrainingAssignment.id.desc()))
            satisfied, reason = assignment is not None, None if assignment else "course missing"
        checks.append({"type": "course", "id": mapping.course_id, "name": mapping.course.name, "satisfied": satisfied, "reason": reason})
    rules = competency.assessment_rules or {}
    passing_assessments = list(db.scalars(select(TrainingAssessment).where(
        TrainingAssessment.worker_user_id == worker_user_id,
        TrainingAssessment.contractor_worker_id == contractor_worker_id,
        TrainingAssessment.competency_id == competency.id,
        TrainingAssessment.passed.is_(True),
        TrainingAssessment.competency_demonstrated.is_(True),
    ).order_by(TrainingAssessment.assessment_date.desc())).all())
    assessment_required = bool(rules["required"]) if "required" in rules else any(
        mapping.required and not mapping.completion_sufficient for mapping in mappings
    )
    if assessment_required:
        assessment = passing_assessments[0] if passing_assessments else None
        checks.append({"type": "assessment", "id": assessment.id if assessment else None, "satisfied": bool(assessment), "reason": None if assessment else "passing competency assessment missing"})
    if rules.get("certificate_required"):
        certificate, reason = _valid_certificate(db, worker_id=worker_user_id, contractor_worker_id=contractor_worker_id, competency_id=competency.id, as_of=as_of)
        checks.append({"type": "certificate", "id": certificate.id if certificate else None, "satisfied": bool(certificate), "reason": reason})
    restricted = False
    config = _config(db)
    if competency.minimum_experience_days:
        verified_days = max(
            (
                int(evidence.get("experience_days", 0))
                for assessment in passing_assessments
                for evidence in assessment.evidence
                if isinstance(evidence, dict)
            ),
            default=0,
        )
        checks.append({
            "type": "experience",
            "satisfied": verified_days >= competency.minimum_experience_days,
            "verified_days": verified_days,
            "required_days": competency.minimum_experience_days,
            "reason": None if verified_days >= competency.minimum_experience_days else f"minimum experience of {competency.minimum_experience_days} days is not verified",
        })
    if competency.medical_prerequisite and config.get("medical_prerequisite_enforcement", True):
        cleared, reasons, restricted = _medical_result(db, worker_id=worker_user_id, contractor_worker=subject if contractor_worker_id else None, programme_codes=competency.medical_programme_codes, as_of=as_of)
        checks.append({"type": "medical", "satisfied": cleared is True, "insufficient": cleared is None, "reason": reasons[0] if reasons else None})
    if competency.ppe_prerequisite and config.get("ppe_prerequisite_enforcement", True):
        compliant, reasons = _ppe_result(db, worker_id=worker_user_id, contractor_worker=subject if contractor_worker_id else None, item_ids=competency.ppe_item_ids, as_of=as_of)
        checks.append({"type": "ppe", "satisfied": compliant is True, "insufficient": compliant is None, "reason": reasons[0] if reasons else None})
    return {"competency_id": competency.id, "satisfied": all(item["satisfied"] for item in checks), "restricted": restricted, "checks": checks}


def list_awards(db: Session, *, worker_user_id=None, contractor_worker_id=None, competency_id=None, status=None, site_id=None, department_id=None) -> list[CompetencyAward]:
    statement = select(CompetencyAward)
    for column, value in ((CompetencyAward.worker_user_id, worker_user_id), (CompetencyAward.contractor_worker_id, contractor_worker_id), (CompetencyAward.competency_id, competency_id), (CompetencyAward.status, status)):
        if value is not None:
            statement = statement.where(column == value)
    if site_id is not None or department_id is not None:
        worker_ids, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
        statement = statement.where(_subject_scope_filter(CompetencyAward, worker_ids, contractor_ids))
    items = list(db.scalars(statement.order_by(CompetencyAward.achieved_at.desc(), CompetencyAward.id.desc())).all())
    changed = False
    for item in items:
        if item.valid_until and item.valid_until < _today() and item.status in {CompetencyAwardStatus.competent, CompetencyAwardStatus.conditionally_competent}:
            previous = item.status
            item.status = CompetencyAwardStatus.expired
            db.add_all([item, CompetencyStatusEvent(
                competency_award_id=item.id,
                previous_status=previous.value,
                new_status=CompetencyAwardStatus.expired.value,
                reason="Competency validity period expired",
                occurred_at=_now(),
            )])
            changed = True
    if changed:
        db.commit()
    return items


def award_competency(db: Session, payload: CompetencyAwardCreate, *, actor_id: int) -> CompetencyAward:
    competency = _get(db, Competency, payload.competency_id, "Competency")
    _ensure_subject(db, payload.worker_user_id, payload.contractor_worker_id)
    evaluation = competency_prerequisites(db, competency, worker_user_id=payload.worker_user_id, contractor_worker_id=payload.contractor_worker_id)
    if competency.supervisor_approval_required:
        actor = _get(db, User, actor_id, "Awarding user")
        approved = has_permission(actor, Permission.TRAINING_ASSESS) or has_permission(actor, Permission.TRAINING_MANAGE)
        evaluation["checks"].append({"type": "supervisor_or_assessor_approval", "satisfied": approved, "actor_user_id": actor_id, "reason": None if approved else "authorised assessor approval missing"})
        evaluation["satisfied"] = evaluation["satisfied"] and approved
    if not evaluation["satisfied"] and not payload.override_requirements:
        reasons = [item["reason"] for item in evaluation["checks"] if not item["satisfied"]]
        raise TrainingCompetencyValidation("Competency requirements are not satisfied: " + "; ".join(filter(None, reasons)))
    data = payload.model_dump(exclude={"override_requirements", "achieved_at", "valid_until"})
    if data["status"] == CompetencyAwardStatus.competent and evaluation["restricted"]:
        data["status"] = CompetencyAwardStatus.conditionally_competent
    achieved = payload.achieved_at or _now()
    valid_until = payload.valid_until
    if valid_until is None:
        validity_days = competency.validity_period_days or _config(db).get("competency_validity_default_days")
        if validity_days:
            valid_until = achieved.date() + timedelta(days=int(validity_days))
    record = CompetencyAward(**data, achieved_at=achieved, valid_until=valid_until, awarded_by_user_id=actor_id, requirements_snapshot=jsonable_encoder(evaluation))
    return _commit(db, record, actor_id=actor_id, action="training.competency.award", resource="competency_award", details={"override": payload.override_requirements})


def change_competency_status(db: Session, award_id: int, payload: CompetencyStatusChange, *, actor_id: int) -> CompetencyAward:
    if payload.status not in {CompetencyAwardStatus.suspended, CompetencyAwardStatus.revoked, CompetencyAwardStatus.pending_assessment}:
        raise TrainingCompetencyValidation("Status changes support suspension, revocation, or pending assessment")
    award = _get(db, CompetencyAward, award_id, "Competency award")
    previous = award.status
    event = CompetencyStatusEvent(
        competency_award_id=award.id,
        previous_status=previous.value,
        new_status=payload.status.value,
        reason=payload.reason,
        actor_user_id=actor_id,
        occurred_at=_now(),
        review_date=payload.review_date,
    )
    award.status = payload.status
    db.add_all([event, award])
    db.commit()
    db.refresh(award)
    _audit(db, actor_id=actor_id, action=f"training.competency.{payload.status.value}", resource="competency_award", resource_id=award.id, details={"reason": payload.reason})
    return award


def competency_history(db: Session, award_id: int) -> list[CompetencyStatusEvent]:
    _get(db, CompetencyAward, award_id, "Competency award")
    return list(db.scalars(select(CompetencyStatusEvent).where(CompetencyStatusEvent.competency_award_id == award_id).order_by(CompetencyStatusEvent.occurred_at, CompetencyStatusEvent.id)).all())


def _requirement_matches(requirement: TrainingRequirement, *, user: Optional[User], contractor: Optional[ContractorWorker], query: EligibilityQuery) -> bool:
    site_id = query.site_id or (user.assigned_site_id if user else contractor.site_id)
    department_id = query.department_id or (user.department_id if user else None)
    if requirement.site_id is not None and requirement.site_id != site_id:
        return False
    if requirement.department_id is not None and requirement.department_id != department_id:
        return False
    if user and requirement.role_name and requirement.role_name not in get_normalized_role_names(user):
        return False
    job_title = user.job_title if user else contractor.job_title
    if requirement.job_title and requirement.job_title.casefold() != (job_title or "").casefold():
        return False
    if contractor and requirement.contractor_category and requirement.contractor_category.casefold() != (contractor.category or "").casefold():
        return False
    context_pairs = (
        (requirement.task_activity, query.task_activity),
        (requirement.jsa_id, query.jsa_id),
        (requirement.permit_type, query.permit_type),
        (requirement.equipment_category, query.equipment_category),
    )
    for required, actual in context_pairs:
        if required is not None and (actual is None or str(required).casefold() != str(actual).casefold()):
            return False
    if requirement.authorization_type and query.authorization_type and requirement.authorization_type.casefold() != query.authorization_type.casefold():
        # A requirement for an authorization is applicable when evaluating the
        # matching authorization/activity, not every authorization globally.
        return False
    return True


def applicable_requirements(db: Session, query: EligibilityQuery) -> list[TrainingRequirement]:
    subject = _ensure_subject(db, query.worker_user_id, query.contractor_worker_id)
    user = subject if query.worker_user_id else None
    contractor = subject if query.contractor_worker_id else None
    return [item for item in db.scalars(select(TrainingRequirement).where(TrainingRequirement.active.is_(True))).all() if _requirement_matches(item, user=user, contractor=contractor, query=query)]


def _authorization_valid(db: Session, query: EligibilityQuery, authorization_type: str, as_of: date) -> tuple[Optional[WorkAuthorization], Optional[str]]:
    authorizations = list(db.scalars(select(WorkAuthorization).where(
        WorkAuthorization.worker_user_id == query.worker_user_id,
        WorkAuthorization.contractor_worker_id == query.contractor_worker_id,
        WorkAuthorization.authorization_type == authorization_type,
    ).order_by(WorkAuthorization.issued_at.desc(), WorkAuthorization.id.desc())).all())
    if not authorizations:
        return None, "authorization missing"
    auth = authorizations[0]
    if auth.status != AuthorizationStatus.active:
        return None, f"authorization {auth.status.value}"
    if auth.valid_from > as_of or (auth.valid_until and auth.valid_until < as_of):
        return None, f"authorization expired{f' {auth.valid_until.isoformat()}' if auth.valid_until else ''}"
    if query.site_id and auth.site_id and query.site_id != auth.site_id:
        return None, "authorization site restriction"
    if query.department_id and auth.department_id and query.department_id != auth.department_id:
        return None, "authorization department restriction"
    if auth.competency_id:
        award, reason = _valid_award(
            db,
            worker_id=query.worker_user_id,
            contractor_worker_id=query.contractor_worker_id,
            competency_id=auth.competency_id,
            as_of=as_of,
        )
        if not award:
            return None, f"authorization competency invalid: {reason}"
    return auth, None


def evaluate_eligibility(db: Session, query: EligibilityQuery) -> dict:
    as_of = query.as_of or _today()
    subject = _ensure_subject(db, query.worker_user_id, query.contractor_worker_id)
    requirements = applicable_requirements(db, query)
    reasons: list[dict] = []
    checks: list[dict] = []
    insufficient = False
    restricted = False
    config = _config(db)
    jsa = _get(db, JobSafetyAnalysis, query.jsa_id, "JSA", optional=True)
    for requirement in requirements:
        if requirement.level != RequirementLevel.mandatory:
            continue
        if requirement.course_id:
            if query.worker_user_id:
                record, reason = _valid_training_record(db, worker_id=query.worker_user_id, course_id=requirement.course_id, as_of=as_of)
                satisfied = bool(record)
            else:
                assignment = db.scalar(select(TrainingAssignment).where(
                    TrainingAssignment.contractor_worker_id == query.contractor_worker_id,
                    TrainingAssignment.course_id == requirement.course_id,
                    TrainingAssignment.status == AssignmentStatus.completed,
                ).order_by(TrainingAssignment.id.desc()))
                satisfied, reason = bool(assignment), None if assignment else "course missing"
            checks.append({"requirement_id": requirement.id, "type": "course", "reference_id": requirement.course_id, "satisfied": satisfied})
            if not satisfied:
                reasons.append({"code": reason.replace(" ", "_") if reason else "training_missing", "message": f"{requirement.course.name}: {reason}", "requirement_id": requirement.id})
            if satisfied and (requirement.assessment_required or _course_assessment_required(db, requirement.course)):
                assessment = db.scalar(select(TrainingAssessment).where(
                    TrainingAssessment.worker_user_id == query.worker_user_id,
                    TrainingAssessment.contractor_worker_id == query.contractor_worker_id,
                    TrainingAssessment.course_id == requirement.course_id,
                    TrainingAssessment.passed.is_(True),
                ).order_by(TrainingAssessment.assessment_date.desc()))
                checks.append({"requirement_id": requirement.id, "type": "assessment", "reference_id": assessment.id if assessment else None, "satisfied": bool(assessment)})
                if not assessment:
                    reasons.append({"code": "assessment_missing", "message": f"{requirement.course.name}: passing assessment missing", "requirement_id": requirement.id})
            if satisfied and (requirement.mandatory_certificate or requirement.course.certificate_required):
                certificate, reason = _valid_certificate(db, worker_id=query.worker_user_id, contractor_worker_id=query.contractor_worker_id, course_id=requirement.course_id, as_of=as_of)
                checks.append({"requirement_id": requirement.id, "type": "certificate", "reference_id": certificate.id if certificate else None, "satisfied": bool(certificate)})
                if not certificate:
                    reasons.append({"code": "certificate_invalid", "message": f"{requirement.course.name}: {reason}", "requirement_id": requirement.id})
        if requirement.competency_id:
            award, reason = _valid_award(db, worker_id=query.worker_user_id, contractor_worker_id=query.contractor_worker_id, competency_id=requirement.competency_id, as_of=as_of)
            checks.append({"requirement_id": requirement.id, "type": "competency", "reference_id": requirement.competency_id, "satisfied": bool(award)})
            if not award:
                reasons.append({"code": "competency_invalid", "message": f"{requirement.competency.name}: {reason}", "requirement_id": requirement.id})
            elif award.status == CompetencyAwardStatus.conditionally_competent:
                restricted = True
        medical_codes = list(requirement.medical_programme_codes)
        course_medical_required = bool(requirement.course_id and requirement.course.medical_clearance_required)
        if course_medical_required:
            medical_codes = sorted(set(medical_codes).union(requirement.course.medical_programme_codes))
        if (medical_codes or course_medical_required) and config.get("medical_prerequisite_enforcement", True):
            cleared, medical_reasons, medical_restricted = _medical_result(db, worker_id=query.worker_user_id, contractor_worker=subject if query.contractor_worker_id else None, programme_codes=medical_codes, as_of=as_of)
            restricted = restricted or medical_restricted
            checks.append({"requirement_id": requirement.id, "type": "medical", "reference_id": None, "satisfied": cleared is True, "insufficient": cleared is None})
            if cleared is None:
                insufficient = True
            if cleared is not True:
                reasons.extend({"code": "medical_clearance_invalid" if cleared is False else "medical_clearance_unknown", "message": message, "requirement_id": requirement.id} for message in medical_reasons)
        ppe_item_ids = {requirement.ppe_item_id} if requirement.ppe_item_id else set()
        course_ppe_required = bool(requirement.course_id and requirement.course.ppe_prerequisite_required)
        if course_ppe_required:
            ppe_item_ids.update(requirement.course.ppe_item_ids)
        if (ppe_item_ids or course_ppe_required) and config.get("ppe_prerequisite_enforcement", True):
            compliant, ppe_reasons = _ppe_result(db, worker_id=query.worker_user_id, contractor_worker=subject if query.contractor_worker_id else None, item_ids=sorted(ppe_item_ids), as_of=as_of)
            checks.append({"requirement_id": requirement.id, "type": "ppe", "reference_id": sorted(ppe_item_ids), "satisfied": compliant is True, "insufficient": compliant is None})
            if compliant is None:
                insufficient = True
            if compliant is not True:
                reasons.extend({"code": "ppe_invalid" if compliant is False else "ppe_unknown", "message": message, "requirement_id": requirement.id} for message in ppe_reasons)
        if query.include_authorization_requirement and requirement.authorization_type:
            auth, reason = _authorization_valid(db, query, requirement.authorization_type, as_of)
            if not auth:
                reasons.append({"code": "authorization_invalid", "message": f"{requirement.authorization_type}: {reason}", "requirement_id": requirement.id})
    if jsa:
        for course_id in jsa.required_course_ids:
            course = _get(db, TrainingCourse, course_id, "JSA course")
            if query.worker_user_id:
                record, reason = _valid_training_record(db, worker_id=query.worker_user_id, course_id=course_id, as_of=as_of)
                satisfied = bool(record)
            else:
                assignment = db.scalar(select(TrainingAssignment).where(
                    TrainingAssignment.contractor_worker_id == query.contractor_worker_id,
                    TrainingAssignment.course_id == course_id,
                    TrainingAssignment.status == AssignmentStatus.completed,
                ))
                satisfied, reason = bool(assignment), None if assignment else "course missing"
            if not satisfied:
                reasons.append({"code": "training_invalid", "message": f"{course.name}: {reason}", "requirement_id": None})
        for competency_id in jsa.required_competency_ids:
            competency = _get(db, Competency, competency_id, "JSA competency")
            award, reason = _valid_award(db, worker_id=query.worker_user_id, contractor_worker_id=query.contractor_worker_id, competency_id=competency_id, as_of=as_of)
            if not award:
                reasons.append({"code": "competency_invalid", "message": f"{competency.name}: {reason}", "requirement_id": None})
        for authorization_type in jsa.required_authorization_types:
            auth, reason = _authorization_valid(db, query, authorization_type, as_of)
            if not auth:
                reasons.append({"code": "authorization_invalid", "message": f"{authorization_type}: {reason}", "requirement_id": None})
        if jsa.required_medical_programme_codes and config.get("medical_prerequisite_enforcement", True):
            cleared, medical_reasons, medical_restricted = _medical_result(db, worker_id=query.worker_user_id, contractor_worker=subject if query.contractor_worker_id else None, programme_codes=jsa.required_medical_programme_codes, as_of=as_of)
            restricted = restricted or medical_restricted
            if cleared is None: insufficient = True
            if cleared is not True:
                reasons.extend({"code": "medical_clearance_invalid" if cleared is False else "medical_clearance_unknown", "message": message, "requirement_id": None} for message in medical_reasons)
        if jsa.required_ppe_item_ids and config.get("ppe_prerequisite_enforcement", True):
            compliant, ppe_reasons = _ppe_result(db, worker_id=query.worker_user_id, contractor_worker=subject if query.contractor_worker_id else None, item_ids=jsa.required_ppe_item_ids, as_of=as_of)
            if compliant is None: insufficient = True
            if compliant is not True:
                reasons.extend({"code": "ppe_invalid" if compliant is False else "ppe_unknown", "message": message, "requirement_id": None} for message in ppe_reasons)
    if query.authorization_type and query.include_authorization_requirement:
        auth, reason = _authorization_valid(db, query, query.authorization_type, as_of)
        if not auth:
            reasons.append({"code": "authorization_invalid", "message": f"{query.authorization_type}: {reason}", "requirement_id": None})
        elif auth.restrictions:
            restricted = True
    if query.worker_user_id:
        active_restrictions = list(db.scalars(select(WorkRestriction).where(
            WorkRestriction.worker_user_id == query.worker_user_id,
            WorkRestriction.status == WorkRestrictionStatus.active,
            WorkRestriction.effective_from <= as_of,
            or_(WorkRestriction.effective_to.is_(None), WorkRestriction.effective_to >= as_of),
        )).all())
        if active_restrictions:
            restricted = True
        if query.task_activity:
            activity = query.task_activity.casefold()
            prohibited = any(
                activity == item.casefold() or activity in item.casefold() or item.casefold() in activity
                for restriction in active_restrictions
                for item in restriction.prohibited_activities
            )
            if prohibited:
                reasons.append({"code": "medical_activity_restriction", "message": "Medical clearance: this activity is restricted", "requirement_id": None})
    # No applicable requirements for a concrete high-risk query is unknown,
    # while a general worker profile with no rules is not applicable/eligible.
    concrete_query = any([query.task_activity, query.authorization_type, query.jsa_id, query.permit_type, query.equipment_category])
    jsa_has_rules = bool(jsa and any((
        jsa.required_course_ids,
        jsa.required_competency_ids,
        jsa.required_authorization_types,
        jsa.required_ppe_item_ids,
        jsa.required_medical_programme_codes,
    )))
    if reasons:
        status = EligibilityStatus.insufficient_data if insufficient and all(item["code"].endswith("unknown") for item in reasons) else EligibilityStatus.not_eligible
    elif not requirements and concrete_query and not jsa_has_rules and not (query.authorization_type and query.include_authorization_requirement):
        status = EligibilityStatus.insufficient_data
        reasons.append({"code": "no_applicable_requirements", "message": "No applicable eligibility requirements are configured", "requirement_id": None})
    elif restricted:
        status = EligibilityStatus.eligible_with_restrictions
    else:
        status = EligibilityStatus.eligible
    return {
        "status": status.value,
        "eligible": status in {EligibilityStatus.eligible, EligibilityStatus.eligible_with_restrictions},
        "worker_user_id": query.worker_user_id,
        "contractor_worker_id": query.contractor_worker_id,
        "as_of": as_of,
        "context": query.model_dump(mode="json", exclude={"as_of"}),
        "reasons": reasons,
        "checks": checks,
        "applicable_requirement_ids": [item.id for item in requirements],
        "privacy": {"medical_detail_exposed": False},
    }


def list_authorizations(db: Session, *, worker_user_id=None, contractor_worker_id=None, authorization_type=None, site_id=None, department_id=None, status=None) -> list[WorkAuthorization]:
    statement = select(WorkAuthorization)
    for column, value in (
        (WorkAuthorization.worker_user_id, worker_user_id),
        (WorkAuthorization.contractor_worker_id, contractor_worker_id),
        (WorkAuthorization.authorization_type, authorization_type),
        (WorkAuthorization.site_id, site_id),
        (WorkAuthorization.department_id, department_id),
        (WorkAuthorization.status, status),
    ):
        if value is not None:
            statement = statement.where(column == value)
    items = list(db.scalars(statement.order_by(WorkAuthorization.issued_at.desc())).all())
    changed = False
    expired_items = []
    for item in items:
        if item.valid_until and item.valid_until < _today() and item.status == AuthorizationStatus.active:
            item.status = AuthorizationStatus.expired
            db.add(item)
            expired_items.append(item)
            changed = True
    if changed:
        db.commit()
        for item in expired_items:
            _audit(
                db,
                actor_id=None,
                action="training.authorization.expired",
                resource="work_authorization",
                resource_id=item.id,
                details={"valid_until": item.valid_until.isoformat()},
            )
    return items


def create_authorization(db: Session, payload: WorkAuthorizationCreate, *, actor_id: int) -> WorkAuthorization:
    _ensure_subject(db, payload.worker_user_id, payload.contractor_worker_id)
    if payload.valid_until and payload.valid_until < payload.valid_from:
        raise TrainingCompetencyValidation("Authorization expiry cannot precede its valid-from date")
    explicit_competency_check = None
    if payload.competency_id:
        competency = _get(db, Competency, payload.competency_id, "Competency")
        award, reason = _valid_award(
            db,
            worker_id=payload.worker_user_id,
            contractor_worker_id=payload.contractor_worker_id,
            competency_id=competency.id,
            as_of=payload.valid_from,
        )
        explicit_competency_check = {"type": "competency", "competency_id": competency.id, "satisfied": bool(award), "reason": reason}
    query = EligibilityQuery(
        worker_user_id=payload.worker_user_id,
        contractor_worker_id=payload.contractor_worker_id,
        task_activity=payload.task_activity,
        authorization_type=payload.authorization_type,
        site_id=payload.site_id,
        department_id=payload.department_id,
        equipment_category=payload.equipment_category,
        include_authorization_requirement=False,
    )
    evaluation = evaluate_eligibility(db, query)
    if explicit_competency_check:
        evaluation["checks"].append(explicit_competency_check)
        if not explicit_competency_check["satisfied"]:
            evaluation["eligible"] = False
            evaluation["status"] = EligibilityStatus.not_eligible.value
            evaluation["reasons"].append({"code": "competency_invalid", "message": f"Explicit authorization competency: {explicit_competency_check['reason']}", "requirement_id": None})
    if payload.status == AuthorizationStatus.active and not evaluation["eligible"] and not payload.override_requirements:
        raise TrainingCompetencyValidation("Authorization prerequisites are not satisfied: " + "; ".join(item["message"] for item in evaluation["reasons"]))
    data = payload.model_dump(exclude={"override_requirements"})
    status = data.pop("status")
    approval_required = bool(_config(db).get("authorization_approval_required", True))
    if status == AuthorizationStatus.active and approval_required:
        # The creator is an authorised approver at the API boundary.
        approved_by, approved_at = actor_id, _now()
    else:
        approved_by, approved_at = (actor_id, _now()) if status == AuthorizationStatus.active else (None, None)
    record = WorkAuthorization(
        **data,
        status=status,
        approved_by_user_id=approved_by,
        approved_at=approved_at,
        prerequisites_snapshot=jsonable_encoder(evaluation),
    )
    return _commit(db, record, actor_id=actor_id, action="training.authorization.create", resource="work_authorization", details={"override": payload.override_requirements})


def update_authorization(db: Session, record_id: int, payload: WorkAuthorizationUpdate, *, actor_id: int) -> WorkAuthorization:
    record = _get(db, WorkAuthorization, record_id, "Authorization")
    previous = record.status
    _apply(record, payload)
    if record.valid_until and record.valid_until < record.valid_from:
        raise TrainingCompetencyValidation("Authorization expiry cannot precede its valid-from date")
    if payload.status in {AuthorizationStatus.suspended, AuthorizationStatus.revoked} and not payload.reason:
        raise TrainingCompetencyValidation("A reason is required to suspend or revoke an authorization")
    if payload.status == AuthorizationStatus.active:
        query = EligibilityQuery(
            worker_user_id=record.worker_user_id,
            contractor_worker_id=record.contractor_worker_id,
            task_activity=record.task_activity,
            authorization_type=record.authorization_type,
            site_id=record.site_id,
            department_id=record.department_id,
            equipment_category=record.equipment_category,
            include_authorization_requirement=False,
        )
        evaluation = evaluate_eligibility(db, query)
        if record.competency_id:
            award, reason = _valid_award(
                db,
                worker_id=record.worker_user_id,
                contractor_worker_id=record.contractor_worker_id,
                competency_id=record.competency_id,
                as_of=record.valid_from,
            )
            if not award:
                evaluation["eligible"] = False
                evaluation["reasons"].append({"code": "competency_invalid", "message": f"Explicit authorization competency: {reason}", "requirement_id": None})
        if not evaluation["eligible"]:
            raise TrainingCompetencyValidation("Authorization prerequisites are not satisfied")
        record.prerequisites_snapshot = jsonable_encoder(evaluation)
        record.approved_by_user_id = actor_id
        record.approved_at = _now()
    return _commit(db, record, actor_id=actor_id, action=f"training.authorization.{record.status.value}", resource="work_authorization", details={"previous_status": previous.value, "reason": payload.reason})


def list_requests(db: Session, *, requester_user_id=None, requested_for_user_id=None, status=None, site_id=None, department_id=None) -> list[TrainingRequest]:
    statement = select(TrainingRequest)
    for column, value in ((TrainingRequest.requester_user_id, requester_user_id), (TrainingRequest.requested_for_user_id, requested_for_user_id), (TrainingRequest.status, status)):
        if value is not None:
            statement = statement.where(column == value)
    if site_id is not None or department_id is not None:
        worker_ids, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
        statement = statement.where(or_(
            TrainingRequest.requested_for_user_id.in_(worker_ids),
            TrainingRequest.contractor_worker_id.in_(contractor_ids),
        ))
    return list(db.scalars(statement.order_by(TrainingRequest.created_at.desc())).all())


def create_request(db: Session, payload: TrainingRequestCreate, *, requester_id: int) -> TrainingRequest:
    _get(db, TrainingCourse, payload.course_id, "Course")
    requested_for = payload.requested_for_user_id or (None if payload.contractor_worker_id else requester_id)
    _ensure_subject(db, requested_for, payload.contractor_worker_id)
    record = TrainingRequest(**payload.model_dump(exclude={"requested_for_user_id"}), requester_user_id=requester_id, requested_for_user_id=requested_for)
    return _commit(db, record, actor_id=requester_id, action="training.request.create", resource="training_request")


def decide_request(db: Session, record_id: int, payload: TrainingRequestDecision, *, actor_id: int) -> TrainingRequest:
    request = _get(db, TrainingRequest, record_id, "Training request")
    if payload.status not in {TrainingRequestStatus.reviewed, TrainingRequestStatus.approved, TrainingRequestStatus.rejected, TrainingRequestStatus.assigned}:
        raise TrainingCompetencyValidation("Invalid review decision")
    request.status = payload.status
    request.decision_notes = payload.decision_notes
    request.reviewed_by_user_id = actor_id
    request.reviewed_at = _now()
    if payload.status in {TrainingRequestStatus.approved, TrainingRequestStatus.assigned}:
        assignment = _create_assignment(db, TrainingAssignmentCreate(
            course_id=request.course_id,
            assigned_user_id=request.requested_for_user_id,
            contractor_worker_id=request.contractor_worker_id,
            due_date=payload.due_date,
            priority=request.urgency,
            mandatory=False,
            reason=request.reason,
            source="training_request",
        ), actor_id=actor_id, commit=False)
        request.resulting_assignment_id = assignment.id
        request.status = TrainingRequestStatus.assigned
    db.add(request)
    db.commit()
    db.refresh(request)
    _audit(db, actor_id=actor_id, action="training.request.decision", resource="training_request", resource_id=request.id, details={"status": request.status.value})
    return request


def worker_profile(db: Session, worker_user_id: int, *, as_of: Optional[date] = None) -> dict:
    worker = _get(db, User, worker_user_id, "Worker")
    as_of = as_of or _today()
    general = EligibilityQuery(worker_user_id=worker.id, site_id=worker.assigned_site_id, department_id=worker.department_id, as_of=as_of)
    requirements = applicable_requirements(db, general)
    course_rows = []
    compliance_rows = []
    competency_rows = []
    for requirement in requirements:
        if requirement.course_id:
            record, reason = _valid_training_record(db, worker_id=worker.id, course_id=requirement.course_id, as_of=as_of)
            course_rows.append({"requirement_id": requirement.id, "course_id": requirement.course_id, "course_name": requirement.course.name, "level": requirement.level.value, "status": "compliant" if record else "overdue" if reason and "expired" in reason else "missing", "reason": reason})
            open_assignments = list_assignments(db, worker_user_id=worker.id, course_id=requirement.course_id)
            open_assignment = next((item for item in open_assignments if item.status not in {AssignmentStatus.completed, AssignmentStatus.cancelled}), None)
            if record:
                requirement_query = EligibilityQuery(
                    worker_user_id=worker.id,
                    site_id=worker.assigned_site_id,
                    department_id=worker.department_id,
                    task_activity=requirement.task_activity,
                    authorization_type=requirement.authorization_type,
                    permit_type=requirement.permit_type,
                    equipment_category=requirement.equipment_category,
                    as_of=as_of,
                    include_authorization_requirement=False,
                )
                failures = [item for item in evaluate_eligibility(db, requirement_query)["reasons"] if item.get("requirement_id") == requirement.id]
                if failures:
                    compliance_status = "non_compliant"
                    compliance_reason = "; ".join(item["message"] for item in failures)
                elif record.expiry_date and record.expiry_date <= as_of + timedelta(days=90):
                    compliance_status, compliance_reason = "due_soon", f"Training expires {record.expiry_date}"
                else:
                    compliance_status, compliance_reason = "compliant", None
            elif open_assignment and open_assignment.status == AssignmentStatus.overdue:
                compliance_status, compliance_reason = "overdue", f"Training was due {open_assignment.due_date}"
            elif open_assignment and open_assignment.due_date and open_assignment.due_date <= as_of + timedelta(days=30):
                compliance_status, compliance_reason = "due_soon", f"Training is due {open_assignment.due_date}"
            elif open_assignment:
                compliance_status, compliance_reason = "pending", "Training is assigned"
            elif requirement.level == RequirementLevel.recommended:
                compliance_status, compliance_reason = "not_applicable", "Recommended training is not mandatory"
            else:
                compliance_status, compliance_reason = "non_compliant", reason
            compliance_rows.append({
                "requirement_id": requirement.id,
                "course_id": requirement.course_id,
                "course_name": requirement.course.name,
                "status": compliance_status,
                "reason": compliance_reason,
            })
        if requirement.competency_id:
            award, reason = _valid_award(db, worker_id=worker.id, competency_id=requirement.competency_id, as_of=as_of)
            competency_rows.append({"requirement_id": requirement.id, "competency_id": requirement.competency_id, "competency_name": requirement.competency.name, "level": requirement.level.value, "status": award.status.value if award else "missing", "reason": reason})
    assignments = list_assignments(db, worker_user_id=worker.id)
    awards = list_awards(db, worker_user_id=worker.id)
    certificates = list_certificates(db, worker_user_id=worker.id)
    authorizations = list_authorizations(db, worker_user_id=worker.id)
    return {
        "worker": {"id": worker.id, "full_name": worker.full_name, "job_title": worker.job_title, "site_id": worker.assigned_site_id, "department_id": worker.department_id},
        "required_courses": course_rows,
        "training_compliance": compliance_rows,
        "assignments": assignments,
        "completed_training": [item for item in db.scalars(select(TrainingRecord).where(TrainingRecord.assigned_to_user_id == worker.id, TrainingRecord.status == TrainingStatus.completed)).all()],
        "overdue_training": [item for item in assignments if item.status == AssignmentStatus.overdue],
        "expiring_training": [item for item in db.scalars(select(TrainingRecord).where(TrainingRecord.assigned_to_user_id == worker.id, TrainingRecord.expiry_date.between(as_of, as_of + timedelta(days=90)))).all()],
        "competencies": awards,
        "competency_gaps": [item for item in competency_rows if item["status"] in {"missing", "expired", "suspended", "revoked"}],
        "certificates": certificates,
        "authorizations": authorizations,
        "medical_prerequisite": {"cleared": _medical_result(db, worker_id=worker.id, contractor_worker=None, programme_codes=[], as_of=as_of)[0]},
        "ppe_prerequisite": {"compliant": _ppe_result(db, worker_id=worker.id, contractor_worker=None, item_ids=[], as_of=as_of)[0]},
        "work_eligibility": evaluate_eligibility(db, general),
        "training_history": list(db.scalars(select(TrainingRecord).where(TrainingRecord.assigned_to_user_id == worker.id).order_by(TrainingRecord.created_at.desc())).all()),
    }


def competency_matrix(db: Session, *, site_id=None, department_id=None, role_name=None, job_title=None, contractor_group=None, as_of: Optional[date] = None) -> dict:
    as_of = as_of or _today()
    users_statement = select(User).where(User.is_active.is_(True))
    if site_id:
        users_statement = users_statement.where(User.assigned_site_id == site_id)
    if department_id:
        users_statement = users_statement.where(User.department_id == department_id)
    if job_title:
        users_statement = users_statement.where(User.job_title == job_title)
    workers = list(db.scalars(users_statement.order_by(User.full_name)).all())
    if role_name:
        workers = [item for item in workers if role_name in get_normalized_role_names(item)]
    if contractor_group:
        workers = []
    contractor_statement = select(ContractorWorker).where(ContractorWorker.active.is_(True))
    if site_id:
        contractor_statement = contractor_statement.where(ContractorWorker.site_id == site_id)
    if department_id:
        contractors = []
    else:
        if job_title:
            contractor_statement = contractor_statement.where(ContractorWorker.job_title == job_title)
        if contractor_group:
            contractor_statement = contractor_statement.where(ContractorWorker.category == contractor_group)
        contractors = list(db.scalars(contractor_statement.order_by(ContractorWorker.full_name)).all())
    if role_name:
        contractors = []
    competencies = list_competencies(db, active=True)
    rows = []
    for worker in workers:
        cells = []
        query = EligibilityQuery(worker_user_id=worker.id, site_id=worker.assigned_site_id, department_id=worker.department_id)
        requirements = applicable_requirements(db, query)
        required_ids = {item.competency_id for item in requirements if item.competency_id}
        for competency in competencies:
            if competency.id not in required_ids:
                state = "not_applicable"
                reason = None
            else:
                award, reason = _valid_award(db, worker_id=worker.id, competency_id=competency.id, as_of=as_of)
                if not award:
                    state = "expired" if reason and "expired" in reason else "restricted" if reason and any(word in reason for word in ("suspended", "revoked")) else "missing"
                elif not (prerequisites := competency_prerequisites(db, competency, worker_user_id=worker.id, as_of=as_of))["satisfied"]:
                    state = "restricted"
                    reason = "; ".join(item["reason"] for item in prerequisites["checks"] if not item["satisfied"] and item.get("reason")) or "Competency prerequisites are no longer current"
                elif award.valid_until and award.valid_until <= as_of + timedelta(days=90):
                    state = "expiring_soon"
                else:
                    state = "valid"
            cells.append({"competency_id": competency.id, "state": state, "reason": reason})
        rows.append({"worker": {"id": worker.id, "subject_type": "worker", "full_name": worker.full_name, "job_title": worker.job_title, "site_id": worker.assigned_site_id, "department_id": worker.department_id}, "cells": cells})
    for worker in contractors:
        cells = []
        query = EligibilityQuery(contractor_worker_id=worker.id, site_id=worker.site_id)
        requirements = applicable_requirements(db, query)
        required_ids = {item.competency_id for item in requirements if item.competency_id}
        for competency in competencies:
            if competency.id not in required_ids:
                state, reason = "not_applicable", None
            else:
                award, reason = _valid_award(db, contractor_worker_id=worker.id, competency_id=competency.id, as_of=as_of)
                if not award:
                    state = "expired" if reason and "expired" in reason else "restricted" if reason and any(word in reason for word in ("suspended", "revoked")) else "missing"
                elif not (prerequisites := competency_prerequisites(db, competency, contractor_worker_id=worker.id, as_of=as_of))["satisfied"]:
                    state = "restricted"
                    reason = "; ".join(item["reason"] for item in prerequisites["checks"] if not item["satisfied"] and item.get("reason")) or "Competency prerequisites are no longer current"
                elif award.valid_until and award.valid_until <= as_of + timedelta(days=90):
                    state = "expiring_soon"
                else:
                    state = "valid"
            cells.append({"competency_id": competency.id, "state": state, "reason": reason})
        rows.append({"worker": {"id": worker.id, "contractor_worker_id": worker.id, "subject_type": "contractor", "full_name": worker.full_name, "job_title": worker.job_title, "site_id": worker.site_id, "department_id": None, "contractor_group": worker.category}, "cells": cells})
    return {"as_of": as_of, "competencies": [{"id": item.id, "name": item.name, "code": item.code} for item in competencies], "rows": rows}


def job_role_matrix(db: Session, *, site_id=None, department_id=None, as_of: Optional[date] = None) -> list[dict]:
    matrix = competency_matrix(db, site_id=site_id, department_id=department_id, as_of=as_of)
    groups: dict[str, dict] = {}
    for row in matrix["rows"]:
        title = row["worker"]["job_title"] or "Unassigned"
        group = groups.setdefault(title, {"job_title": title, "workers": 0, "compliant": 0, "expiring": 0, "non_compliant": 0, "required_competency_ids": set()})
        applicable = [cell for cell in row["cells"] if cell["state"] != "not_applicable"]
        group["workers"] += 1
        group["required_competency_ids"].update(cell["competency_id"] for cell in applicable)
        if applicable and all(cell["state"] == "valid" for cell in applicable):
            group["compliant"] += 1
        elif any(cell["state"] == "expiring_soon" for cell in applicable) and not any(cell["state"] in {"missing", "expired", "restricted"} for cell in applicable):
            group["expiring"] += 1
        elif applicable:
            group["non_compliant"] += 1
    for group in groups.values():
        group["required_competency_ids"] = sorted(group["required_competency_ids"])
    return list(groups.values())


def dashboard(db: Session, *, site_id=None, department_id=None, as_of: Optional[date] = None) -> dict:
    as_of = as_of or _today()
    user_statement = select(User).where(User.is_active.is_(True))
    if site_id:
        user_statement = user_statement.where(User.assigned_site_id == site_id)
    if department_id:
        user_statement = user_statement.where(User.department_id == department_id)
    workers = list(db.scalars(user_statement).all())
    worker_ids = {item.id for item in workers}
    _, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
    assignments = [item for item in list_assignments(db, site_id=site_id, department_id=department_id) if item.assigned_user_id in worker_ids or item.contractor_worker_id in contractor_ids]
    records = list(db.scalars(select(TrainingRecord)).all())
    records = [item for item in records if item.assigned_to_user_id in worker_ids]
    awards = list(db.scalars(select(CompetencyAward)).all())
    awards = [item for item in awards if item.worker_user_id in worker_ids or item.contractor_worker_id in contractor_ids]
    certificates = list(db.scalars(select(TrainingCertificate)).all())
    certificates = [item for item in certificates if item.worker_user_id in worker_ids or item.contractor_worker_id in contractor_ids]
    authorizations = list(db.scalars(select(WorkAuthorization)).all())
    authorizations = [item for item in authorizations if item.worker_user_id in worker_ids or item.contractor_worker_id in contractor_ids]
    assessment_rows = list(db.scalars(select(TrainingAssessment)).all())
    assessment_rows = [item for item in assessment_rows if item.worker_user_id in worker_ids or item.contractor_worker_id in contractor_ids]
    matrix = competency_matrix(db, site_id=site_id, department_id=department_id, as_of=as_of)
    required_cells = [cell for row in matrix["rows"] for cell in row["cells"] if cell["state"] != "not_applicable"]
    valid_cells = [cell for cell in required_cells if cell["state"] in {"valid", "expiring_soon"}]
    eligibility_failures = 0
    workers_requiring_training = 0
    for worker in workers:
        worker_query = EligibilityQuery(worker_user_id=worker.id, site_id=worker.assigned_site_id, department_id=worker.department_id)
        if any(item.course_id or item.competency_id for item in applicable_requirements(db, worker_query)):
            workers_requiring_training += 1
        result = evaluate_eligibility(db, worker_query)
        eligibility_failures += result["status"] == EligibilityStatus.not_eligible.value
    for contractor_id in contractor_ids:
        contractor = _get(db, ContractorWorker, contractor_id, "Contractor worker")
        contractor_query = EligibilityQuery(contractor_worker_id=contractor.id, site_id=contractor.site_id)
        if any(item.course_id or item.competency_id for item in applicable_requirements(db, contractor_query)):
            workers_requiring_training += 1
    site_breakdown: dict[Optional[int], Counter] = defaultdict(Counter)
    department_breakdown: dict[Optional[int], Counter] = defaultdict(Counter)
    course_breakdown: dict[int, Counter] = defaultdict(Counter)
    for assignment in assignments:
        state = assignment.status.value
        site_breakdown[assignment.site_id][state] += 1
        department_breakdown[assignment.department_id][state] += 1
        course_breakdown[assignment.course_id][state] += 1
    competency_breakdown: dict[int, Counter] = defaultdict(Counter)
    for row in matrix["rows"]:
        for cell in row["cells"]:
            if cell["state"] != "not_applicable":
                competency_breakdown[cell["competency_id"]][cell["state"]] += 1
    return {
        "workers_in_scope": len(workers) + len(contractor_ids),
        "workers_requiring_training": workers_requiring_training,
        "assigned_training": len([item for item in assignments if item.status in {AssignmentStatus.assigned, AssignmentStatus.in_progress}]),
        "overdue_training": len([item for item in assignments if item.status == AssignmentStatus.overdue]),
        "due_soon": len([item for item in assignments if item.due_date and as_of <= item.due_date <= as_of + timedelta(days=30)]),
        "completed_this_period": len([item for item in records if item.completed_at and as_of - timedelta(days=30) <= item.completed_at.date() <= as_of]),
        "competency_gaps": len([item for item in required_cells if item["state"] in {"missing", "expired", "restricted"}]),
        "competencies_required": len(required_cells),
        "competency_compliance_rate": round(len(valid_cells) * 100 / len(required_cells), 2) if required_cells else None,
        "expiring_competencies": len([item for item in awards if item.valid_until and as_of <= item.valid_until <= as_of + timedelta(days=90)]),
        "expired_certificates": len([item for item in certificates if item.expiry_date and item.expiry_date < as_of]),
        "suspended_competencies": len([item for item in awards if item.status == CompetencyAwardStatus.suspended]),
        "authorization_gaps": len([item for item in authorizations if item.status in {AuthorizationStatus.expired, AuthorizationStatus.suspended, AuthorizationStatus.revoked} or (item.valid_until and item.valid_until < as_of)]),
        "work_eligibility_failures": eligibility_failures,
        "refresher_backlog": len([item for item in assignments if item.source == "refresher" and item.status == AssignmentStatus.overdue]),
        "failed_assessments": len([item for item in assessment_rows if not item.passed]),
        "reassessment_backlog": len([item for item in assessment_rows if item.reassessment_required and item.reassessment_due_date and item.reassessment_due_date < as_of]),
        "by_job_role": job_role_matrix(db, site_id=site_id, department_id=department_id, as_of=as_of),
        "by_site": [{"site_id": key, **dict(counts)} for key, counts in sorted(site_breakdown.items(), key=lambda item: (item[0] is None, item[0] or 0))],
        "by_department": [{"department_id": key, **dict(counts)} for key, counts in sorted(department_breakdown.items(), key=lambda item: (item[0] is None, item[0] or 0))],
        "by_course": [{"course_id": key, **dict(counts)} for key, counts in sorted(course_breakdown.items())],
        "by_competency": [{"competency_id": key, **dict(counts)} for key, counts in sorted(competency_breakdown.items())],
        "by_worker_group": [
            {"worker_group": "employee", "workers": len(workers)},
            {"worker_group": "contractor", "workers": len(contractor_ids)},
        ],
    }


def forward_view(db: Session, *, site_id=None, department_id=None, days: int = 90, as_of: Optional[date] = None) -> list[dict]:
    as_of = as_of or _today()
    end = as_of + timedelta(days=days)
    rows: list[dict] = []
    worker_ids, contractor_ids = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
    record_statement = select(TrainingRecord).where(TrainingRecord.expiry_date.between(as_of, end))
    if site_id is not None or department_id is not None:
        record_statement = record_statement.where(TrainingRecord.assigned_to_user_id.in_(worker_ids))
    for record in db.scalars(record_statement).all():
        rows.append({"type": "training_expiry", "id": record.id, "worker_user_id": record.assigned_to_user_id, "date": record.expiry_date, "label": record.title})
    certificate_statement = select(TrainingCertificate).where(TrainingCertificate.expiry_date.between(as_of, end))
    award_statement = select(CompetencyAward).where(CompetencyAward.valid_until.between(as_of, end))
    authorization_statement = select(WorkAuthorization).where(WorkAuthorization.valid_until.between(as_of, end))
    assessment_statement = select(TrainingAssessment).where(TrainingAssessment.reassessment_due_date.between(as_of, end))
    if site_id is not None or department_id is not None:
        certificate_statement = certificate_statement.where(_subject_scope_filter(TrainingCertificate, worker_ids, contractor_ids))
        award_statement = award_statement.where(_subject_scope_filter(CompetencyAward, worker_ids, contractor_ids))
        authorization_statement = authorization_statement.where(_subject_scope_filter(WorkAuthorization, worker_ids, contractor_ids))
        assessment_statement = assessment_statement.where(_subject_scope_filter(TrainingAssessment, worker_ids, contractor_ids))
    for certificate in db.scalars(certificate_statement).all():
        rows.append({"type": "certificate_expiry", "id": certificate.id, "worker_user_id": certificate.worker_user_id, "contractor_worker_id": certificate.contractor_worker_id, "date": certificate.expiry_date, "label": certificate.certificate_number})
    for award in db.scalars(award_statement).all():
        rows.append({"type": "competency_expiry", "id": award.id, "worker_user_id": award.worker_user_id, "contractor_worker_id": award.contractor_worker_id, "date": award.valid_until, "label": award.competency.name})
    for auth in db.scalars(authorization_statement).all():
        rows.append({"type": "authorization_expiry", "id": auth.id, "worker_user_id": auth.worker_user_id, "contractor_worker_id": auth.contractor_worker_id, "date": auth.valid_until, "label": auth.authorization_type})
    for assessment in db.scalars(assessment_statement).all():
        rows.append({"type": "reassessment_due", "id": assessment.id, "worker_user_id": assessment.worker_user_id, "contractor_worker_id": assessment.contractor_worker_id, "date": assessment.reassessment_due_date, "label": assessment.assessment_type.value})
    return sorted(rows, key=lambda item: (item["date"], item["type"], item["id"]))


def management_exceptions(db: Session, *, site_id=None, department_id=None, as_of: Optional[date] = None) -> list[dict]:
    as_of = as_of or _today()
    exceptions = []
    matrix = competency_matrix(db, site_id=site_id, department_id=department_id, as_of=as_of)
    for row in matrix["rows"]:
        for cell in row["cells"]:
            if cell["state"] in {"missing", "expired", "restricted"}:
                exceptions.append({"type": "critical_competency_gap", "severity": "critical", "worker_user_id": row["worker"]["id"], "competency_id": cell["competency_id"], "reason": cell["reason"] or cell["state"]})
    for assignment in list_assignments(db, site_id=site_id, department_id=department_id, status=AssignmentStatus.overdue):
        if assignment.mandatory:
            exceptions.append({"type": "mandatory_training_overdue", "severity": "high", "worker_user_id": assignment.assigned_user_id, "assignment_id": assignment.id, "reason": "Mandatory training is overdue"})
    for authorization in list_authorizations(db, site_id=site_id, department_id=department_id):
        if authorization.status == AuthorizationStatus.active and authorization.valid_until and authorization.valid_until <= as_of + timedelta(days=30):
            exceptions.append({"type": "high_risk_authorization_expiring", "severity": "high", "worker_user_id": authorization.worker_user_id, "authorization_id": authorization.id, "reason": f"Authorization expires {authorization.valid_until}"})
    worker_ids, _ = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
    emitted: set[tuple[str, int, Optional[int]]] = set()
    for worker_id in worker_ids:
        worker = _get(db, User, worker_id, "Worker")
        candidate_requirements = list(db.scalars(select(TrainingRequirement).where(
            TrainingRequirement.active.is_(True),
            TrainingRequirement.level == RequirementLevel.mandatory,
        )).all())
        for requirement in candidate_requirements:
            query = EligibilityQuery(
                worker_user_id=worker.id,
                site_id=worker.assigned_site_id,
                department_id=worker.department_id,
                task_activity=requirement.task_activity,
                authorization_type=requirement.authorization_type,
                permit_type=requirement.permit_type,
                equipment_category=requirement.equipment_category,
                as_of=as_of,
            )
            if requirement.id not in {item.id for item in applicable_requirements(db, query)}:
                continue
            result = evaluate_eligibility(db, query)
            for reason in result["reasons"]:
                exception_type = None
                if reason["code"].startswith("medical_"):
                    exception_type = "medical_prerequisite_invalid"
                elif reason["code"].startswith("ppe_"):
                    exception_type = "required_ppe_missing"
                elif reason["code"] == "authorization_invalid" and requirement.task_activity:
                    exception_type = "task_assignment_without_authorization"
                if exception_type:
                    key = (exception_type, worker.id, requirement.id)
                    if key not in emitted:
                        exceptions.append({
                            "type": exception_type,
                            "severity": "critical" if requirement.is_critical else "high",
                            "worker_user_id": worker.id,
                            "requirement_id": requirement.id,
                            "reason": reason["message"],
                        })
                        emitted.add(key)
    return exceptions


def _deliver_reminder(db: Session, *, entity_type: str, entity_id: int, recipient_user_id: Optional[int], due_date: date, milestone: str, title: str, message: str, overdue: bool) -> bool:
    if recipient_user_id is None:
        return False
    exists = db.scalar(select(TrainingReminderDelivery.id).where(
        TrainingReminderDelivery.entity_type == entity_type,
        TrainingReminderDelivery.entity_id == entity_id,
        TrainingReminderDelivery.recipient_user_id == recipient_user_id,
        TrainingReminderDelivery.milestone_key == milestone,
        TrainingReminderDelivery.due_date_snapshot == due_date,
    ))
    if exists:
        return False
    db.add(TrainingReminderDelivery(entity_type=entity_type, entity_id=entity_id, recipient_user_id=recipient_user_id, milestone_key=milestone, due_date_snapshot=due_date))
    db.commit()
    from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
    create_notification(db, NotificationCreate(
        recipient_user_id=recipient_user_id,
        title=title,
        message=message,
        notification_type=NotificationType.training_expired if overdue else NotificationType.training_overdue,
        severity=NotificationSeverity.critical if overdue else NotificationSeverity.warning,
        related_entity_type=RelatedEntityType.training_record,
        related_entity_id=entity_id,
    ))
    return True


def generate_reminders(db: Session) -> dict[str, int]:
    today = _today()
    config = _config(db)
    default_windows = sorted(set(int(item) for item in config.get("default_reminder_windows", [90, 60, 30, 7])))
    counts = Counter()
    sources = []
    for assignment in list_assignments(db):
        if assignment.due_date and assignment.status not in {AssignmentStatus.completed, AssignmentStatus.cancelled}:
            sources.append(("assignment", assignment.id, assignment.assigned_user_id, assignment.due_date, f"Training assignment: {assignment.course.name}", assignment.course.reminder_windows or default_windows))
    for award in list_awards(db):
        if award.valid_until and award.status not in {CompetencyAwardStatus.revoked, CompetencyAwardStatus.suspended}:
            sources.append(("competency", award.id, award.worker_user_id, award.valid_until, f"Competency: {award.competency.name}", default_windows))
    for certificate in list_certificates(db):
        if certificate.expiry_date:
            sources.append(("certificate", certificate.id, certificate.worker_user_id, certificate.expiry_date, f"Certificate: {certificate.certificate_number}", default_windows))
    for authorization in list_authorizations(db):
        if authorization.valid_until and authorization.status not in {AuthorizationStatus.revoked, AuthorizationStatus.suspended}:
            sources.append(("authorization", authorization.id, authorization.worker_user_id, authorization.valid_until, f"Authorization: {authorization.authorization_type}", default_windows))
    for assessment in list_assessments(db):
        if assessment.reassessment_required and assessment.reassessment_due_date:
            sources.append(("reassessment", assessment.id, assessment.worker_user_id, assessment.reassessment_due_date, "Reassessment", default_windows))
    for entity_type, entity_id, recipient, due, label, windows in sources:
        days = (due - today).days
        milestone = "overdue" if days < 0 else next((f"due_{window}" for window in sorted(set(int(item) for item in windows)) if days <= window), None)
        if milestone and _deliver_reminder(db, entity_type=entity_type, entity_id=entity_id, recipient_user_id=recipient, due_date=due, milestone=milestone, title=f"{label} {'overdue' if days < 0 else 'due soon'}", message=f"{label} {'was due' if days < 0 else 'is due'} on {due}.", overdue=days < 0):
            counts[f"{entity_type}_{milestone}"] += 1
    if config.get("refresher_automation"):
        counts["refresher_assignments"] += create_refresher_assignments(db)
    return dict(counts)


def create_refresher_assignments(db: Session) -> int:
    today = _today()
    created = 0

    def create_once(*, course: TrainingCourse, worker_user_id=None, contractor_worker_id=None, due_date: date, source_key: str, actor_id: Optional[int], original_assignment_id=None) -> None:
        nonlocal created
        if not course.refresher_required:
            return
        reason = f"Automatic refresher before expiry ({source_key})"
        duplicate = db.scalar(select(TrainingAssignment.id).where(
            TrainingAssignment.course_id == course.id,
            TrainingAssignment.assigned_user_id == worker_user_id,
            TrainingAssignment.contractor_worker_id == contractor_worker_id,
            TrainingAssignment.source == "refresher",
            or_(TrainingAssignment.reason == reason, TrainingAssignment.due_date == due_date),
        ))
        if duplicate:
            return
        effective_actor = actor_id or worker_user_id
        if effective_actor is None:
            effective_actor = db.scalar(select(User.id).where(User.is_active.is_(True)).order_by(User.id))
        if effective_actor is None:
            return
        _create_assignment(db, TrainingAssignmentCreate(
            course_id=course.id,
            assigned_user_id=worker_user_id,
            contractor_worker_id=contractor_worker_id,
            due_date=due_date,
            mandatory=True,
            reason=reason,
            source="refresher",
            refresher_for_assignment_id=original_assignment_id,
        ), actor_id=effective_actor, commit=True)
        created += 1

    records = list(db.scalars(select(TrainingRecord).where(
        TrainingRecord.course_id.is_not(None),
        TrainingRecord.expiry_date.is_not(None),
        TrainingRecord.expiry_date <= today + timedelta(days=90),
    )).all())
    for record in records:
        original = db.scalar(select(TrainingAssignment).where(TrainingAssignment.training_record_id == record.id))
        create_once(
            course=_get(db, TrainingCourse, record.course_id, "Course"),
            worker_user_id=record.assigned_to_user_id,
            due_date=record.expiry_date,
            source_key=f"training_record:{record.id}",
            actor_id=record.assigned_by_user_id,
            original_assignment_id=original.id if original else None,
        )
    certificates = list(db.scalars(select(TrainingCertificate).where(
        TrainingCertificate.course_id.is_not(None),
        TrainingCertificate.expiry_date.is_not(None),
        TrainingCertificate.expiry_date <= today + timedelta(days=90),
    )).all())
    for certificate in certificates:
        create_once(
            course=_get(db, TrainingCourse, certificate.course_id, "Course"),
            worker_user_id=certificate.worker_user_id,
            contractor_worker_id=certificate.contractor_worker_id,
            due_date=certificate.expiry_date,
            source_key=f"certificate:{certificate.id}",
            actor_id=certificate.verified_by_user_id,
        )
    awards = list(db.scalars(select(CompetencyAward).where(
        CompetencyAward.valid_until.is_not(None),
        CompetencyAward.valid_until <= today + timedelta(days=90),
        CompetencyAward.status.in_([CompetencyAwardStatus.competent, CompetencyAwardStatus.conditionally_competent]),
    )).all())
    for award in awards:
        for mapping in list_course_mappings(db, competency_id=award.competency_id):
            if mapping.required:
                create_once(
                    course=mapping.course,
                    worker_user_id=award.worker_user_id,
                    contractor_worker_id=award.contractor_worker_id,
                    due_date=award.valid_until,
                    source_key=f"competency_award:{award.id}:course:{mapping.course_id}",
                    actor_id=award.awarded_by_user_id,
                )
    return created


EXPORT_COLUMNS = {
    "training-register": ("id", "course_id", "assigned_to_user_id", "site_id", "title", "training_type", "due_date", "completed_at", "expiry_date", "status"),
    "training-matrix": ("worker_user_id", "course_id", "course_name", "status", "reason"),
    "competency-matrix": ("worker_user_id", "competency_id", "state", "reason"),
    "certificate-register": ("id", "worker_user_id", "contractor_worker_id", "course_id", "competency_id", "certificate_number", "issue_date", "expiry_date", "verification_status"),
    "authorization-register": ("id", "worker_user_id", "contractor_worker_id", "authorization_type", "site_id", "department_id", "valid_from", "valid_until", "status"),
    "expiry-schedule": ("type", "id", "worker_user_id", "contractor_worker_id", "date", "label"),
    "assessment-outcomes": ("id", "worker_user_id", "contractor_worker_id", "course_id", "competency_id", "assessment_type", "assessment_date", "score", "passed", "reassessment_due_date"),
    "work-eligibility": ("worker_user_id", "status", "reasons"),
    "training-compliance": ("worker_user_id", "course_id", "course_name", "status", "reason"),
}


def export_csv(db: Session, export_type: str, *, site_id=None, department_id=None, actor_id: Optional[int] = None) -> str:
    if export_type not in EXPORT_COLUMNS:
        raise TrainingCompetencyValidation("Unsupported export type")
    rows: list[dict] = []
    if export_type == "training-register":
        statement = select(TrainingRecord)
        if site_id:
            statement = statement.where(TrainingRecord.site_id == site_id)
        if department_id:
            worker_ids, _ = _subject_scope_ids(db, site_id=site_id, department_id=department_id)
            statement = statement.where(TrainingRecord.assigned_to_user_id.in_(worker_ids))
        rows = [{field: getattr(item, field, None).value if hasattr(getattr(item, field, None), "value") else getattr(item, field, None) for field in EXPORT_COLUMNS[export_type]} for item in db.scalars(statement).all()]
    elif export_type in {"training-matrix", "training-compliance"}:
        users = list(db.scalars(select(User).where(User.is_active.is_(True))).all())
        for user in users:
            if site_id and user.assigned_site_id != site_id or department_id and user.department_id != department_id:
                continue
            profile = worker_profile(db, user.id)
            source_rows = profile["training_compliance"] if export_type == "training-compliance" else profile["required_courses"]
            rows.extend({"worker_user_id": user.id, **item} for item in source_rows)
    elif export_type == "competency-matrix":
        matrix = competency_matrix(db, site_id=site_id, department_id=department_id)
        for row in matrix["rows"]:
            rows.extend({"worker_user_id": row["worker"]["id"], **cell} for cell in row["cells"])
    elif export_type == "certificate-register":
        rows = [{field: getattr(item, field, None).value if hasattr(getattr(item, field, None), "value") else getattr(item, field, None) for field in EXPORT_COLUMNS[export_type]} for item in list_certificates(db, site_id=site_id, department_id=department_id)]
    elif export_type == "authorization-register":
        rows = [{field: getattr(item, field, None).value if hasattr(getattr(item, field, None), "value") else getattr(item, field, None) for field in EXPORT_COLUMNS[export_type]} for item in list_authorizations(db, site_id=site_id, department_id=department_id)]
    elif export_type == "expiry-schedule":
        rows = forward_view(db, site_id=site_id, department_id=department_id)
    elif export_type == "assessment-outcomes":
        rows = [{field: getattr(item, field, None).value if hasattr(getattr(item, field, None), "value") else getattr(item, field, None) for field in EXPORT_COLUMNS[export_type]} for item in list_assessments(db, site_id=site_id, department_id=department_id)]
    else:
        for user in db.scalars(select(User).where(User.is_active.is_(True))).all():
            if site_id and user.assigned_site_id != site_id or department_id and user.department_id != department_id:
                continue
            result = evaluate_eligibility(db, EligibilityQuery(worker_user_id=user.id, site_id=user.assigned_site_id, department_id=user.department_id))
            rows.append({"worker_user_id": user.id, "status": result["status"], "reasons": "; ".join(item["message"] for item in result["reasons"])})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS[export_type], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    _audit(db, actor_id=actor_id, action="training.export", resource="training_export", resource_id=None, details={"export_type": export_type, "row_count": len(rows)})
    return output.getvalue()


def generate_action(db: Session, payload: ActionGenerationRequest, *, actor_id: int):
    titles = {
        "critical_competency_gap": "Resolve critical competency gap",
        "overdue_mandatory_training": "Complete overdue mandatory training",
        "revoked_authorization": "Remediate revoked work authorization",
        "repeated_failed_assessment": "Address repeated failed assessment",
        "site_competency_deficiency": "Resolve site-wide competency deficiency",
    }
    if payload.issue_type not in titles:
        raise TrainingCompetencyValidation("Unsupported action issue type")
    source_models = {
        "critical_competency_gap": (Competency, "competency"),
        "overdue_mandatory_training": (TrainingRecord, "training_record"),
        "revoked_authorization": (WorkAuthorization, "work_authorization"),
        "repeated_failed_assessment": (TrainingAssessment, "training_assessment"),
        "site_competency_deficiency": (Site, "site"),
    }
    source_model, source_entity_type = source_models[payload.issue_type]
    _get(db, source_model, payload.source_id, "Training deficiency source")
    existing = db.scalar(select(TrainingDeficiencyLink).where(
        TrainingDeficiencyLink.deficiency_type == payload.issue_type,
        TrainingDeficiencyLink.worker_user_id == payload.worker_user_id,
        TrainingDeficiencyLink.source_entity_type == source_entity_type,
        TrainingDeficiencyLink.source_entity_id == payload.source_id,
        TrainingDeficiencyLink.corrective_action_id.is_not(None),
    ))
    if existing:
        return _get(db, CorrectiveAction, existing.corrective_action_id, "Corrective action")
    worker = _get(db, User, payload.worker_user_id, "Worker", optional=True)
    action = create_corrective_action(db, CorrectiveActionCreate(
        site_id=worker.assigned_site_id if worker else None,
        department_id=worker.department_id if worker else None,
        responsible_department_id=worker.department_id if worker else None,
        title=payload.title or titles[payload.issue_type],
        description=f"Training and competency remediation required ({payload.issue_type}).",
        acceptance_criteria="The applicable training, competency, or authorization gap is closed with current evidence.",
        source_type=CorrectiveActionSourceType.training,
        source_id=payload.source_id,
        source_metadata={"training_issue_type": payload.issue_type, "source_entity_type": source_entity_type, "backlink": "/training"},
        priority="critical" if "critical" in payload.issue_type else "high",
        owner_user_id=payload.owner_user_id,
        current_due_date=payload.due_date,
    ), current_user_id=actor_id)
    link = TrainingDeficiencyLink(
        deficiency_type=payload.issue_type,
        source_entity_type=source_entity_type,
        source_entity_id=payload.source_id,
        worker_user_id=payload.worker_user_id,
        competency_id=payload.source_id if "competency" in payload.issue_type else None,
        training_record_id=payload.source_id if "training" in payload.issue_type else None,
        corrective_action_id=action.id,
        created_by_user_id=actor_id,
    )
    db.add(link)
    db.commit()
    _audit(db, actor_id=actor_id, action="training.action.generate", resource="training_deficiency", resource_id=link.id)
    return action


def create_deficiency_link(db: Session, payload: DeficiencyLinkCreate, *, actor_id: int) -> TrainingDeficiencyLink:
    if payload.incident_id:
        _get(db, Incident, payload.incident_id, "Incident")
    if payload.worker_user_id:
        _get(db, User, payload.worker_user_id, "Worker")
    if payload.competency_id:
        _get(db, Competency, payload.competency_id, "Competency")
    if payload.training_record_id:
        _get(db, TrainingRecord, payload.training_record_id, "Training record")
    if payload.corrective_action_id:
        _get(db, CorrectiveAction, payload.corrective_action_id, "Corrective action")
    record = TrainingDeficiencyLink(**payload.model_dump(), created_by_user_id=actor_id)
    return _commit(db, record, actor_id=actor_id, action="training.deficiency.link", resource="training_deficiency")
