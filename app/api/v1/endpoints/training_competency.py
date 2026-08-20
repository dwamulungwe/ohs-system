from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.training import (
    AssignmentStatus,
    AuthorizationStatus,
    CompetencyAward,
    CompetencyAwardStatus,
    ContractorWorker,
    TrainingAssignment,
    TrainingCertificate,
    TrainingRequirement,
    TrainingRequestStatus,
    TrainingSession,
    TrainingSessionStatus,
    TrainingType,
    WorkAuthorization,
)
from app.models.user import User
from app.schemas.training import (
    ActionGenerationRequest,
    BulkTrainingAssignmentCreate,
    CertificateVerification,
    CompetencyAwardCreate,
    CompetencyAwardRead,
    CompetencyCreate,
    CompetencyRead,
    CompetencyStatusChange,
    CompetencyUpdate,
    ContractorWorkerCreate,
    ContractorWorkerRead,
    ContractorWorkerUpdate,
    CourseCompetencyMappingCreate,
    CourseCompetencyMappingRead,
    DeficiencyLinkCreate,
    EligibilityQuery,
    TrainingAssessmentCreate,
    TrainingAssessmentRead,
    TrainingAssignmentCreate,
    TrainingAssignmentRead,
    TrainingAssignmentUpdate,
    TrainingAttendanceCreate,
    TrainingAttendanceRead,
    TrainingCertificateCreate,
    TrainingCertificateRead,
    TrainingCourseCreate,
    TrainingCourseRead,
    TrainingCourseUpdate,
    TrainingRequestCreate,
    TrainingRequestDecision,
    TrainingRequestRead,
    TrainingRequirementCreate,
    TrainingRequirementRead,
    TrainingRequirementUpdate,
    TrainingSessionCreate,
    TrainingSessionRead,
    TrainingSessionUpdate,
    WorkAuthorizationCreate,
    WorkAuthorizationRead,
    WorkAuthorizationUpdate,
)
from app.schemas.corrective_action import CorrectiveActionRead
from app.services.rbac import Permission, ensure_permission, ensure_site_access, has_permission, resolve_site_scope
from app.services.tenancy import require_feature
from app.services.training_competency_service import (
    TrainingCompetencyError,
    TrainingCompetencyNotFound,
    award_competency,
    bulk_assign,
    change_competency_status,
    competency_history,
    competency_matrix,
    create_assessment,
    create_assignment,
    create_certificate,
    create_competency,
    create_contractor_worker,
    create_course,
    create_course_mapping,
    create_deficiency_link,
    create_request,
    create_requirement,
    create_session,
    create_authorization,
    dashboard,
    decide_request,
    evaluate_eligibility,
    export_csv,
    forward_view,
    generate_action,
    generate_reminders,
    job_role_matrix,
    list_assessments,
    list_assignments,
    list_attendance,
    list_authorizations,
    list_awards,
    list_certificates,
    list_competencies,
    list_contractor_workers,
    list_course_mappings,
    list_courses,
    list_requests,
    list_requirements,
    list_sessions,
    management_exceptions,
    record_attendance,
    update_assignment,
    update_authorization,
    update_competency,
    update_contractor_worker,
    update_course,
    update_requirement,
    update_session,
    verify_certificate,
    worker_profile,
)


router = APIRouter(dependencies=[Depends(require_feature("training"))])


def _error(exc: TrainingCompetencyError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND if isinstance(exc, TrainingCompetencyNotFound) else status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )


def _manage(user: User) -> None:
    ensure_permission(user, Permission.TRAINING_MANAGE)


def _assess(user: User) -> None:
    if not (has_permission(user, Permission.TRAINING_ASSESS) or has_permission(user, Permission.TRAINING_MANAGE)):
        raise HTTPException(status_code=403, detail="Not authorized")


def _assign(user: User) -> None:
    if not (has_permission(user, Permission.TRAINING_ASSIGN) or has_permission(user, Permission.TRAINING_MANAGE)):
        raise HTTPException(status_code=403, detail="Not authorized")


def _authorize(user: User) -> None:
    if not (has_permission(user, Permission.TRAINING_AUTHORIZE) or has_permission(user, Permission.TRAINING_MANAGE)):
        raise HTTPException(status_code=403, detail="Not authorized")


def _view(user: User) -> None:
    if not (has_permission(user, Permission.TRAINING_VIEW_ALL) or has_permission(user, Permission.TRAINING_SELF_VIEW)):
        raise HTTPException(status_code=403, detail="Not authorized")


def _worker_access(db: Session, user: User, worker_id: int) -> None:
    if worker_id == user.id and has_permission(user, Permission.TRAINING_SELF_VIEW):
        return
    ensure_permission(user, Permission.TRAINING_VIEW_ALL)
    target = db.get(User, worker_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    ensure_site_access(user, target.assigned_site_id)


def _ensure_assignment_subject_scope(db: Session, user: User, worker_user_id: Optional[int], contractor_worker_id: Optional[int]) -> None:
    if worker_user_id:
        target = db.get(User, worker_user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Worker not found")
        ensure_site_access(user, target.assigned_site_id)
    if contractor_worker_id:
        target = db.get(ContractorWorker, contractor_worker_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Contractor worker not found")
        ensure_site_access(user, target.site_id)


@router.get("/training/dashboard")
def read_dashboard(site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return dashboard(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id)


@router.get("/training/courses", response_model=list[TrainingCourseRead])
def read_courses(active: Optional[bool] = None, category: Optional[str] = None, training_type: Optional[TrainingType] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _view(current_user)
    return list_courses(db, active=active, category=category, training_type=training_type)


@router.post("/training/courses", response_model=TrainingCourseRead, status_code=201)
def add_course(payload: TrainingCourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_course(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/courses/{record_id}", response_model=TrainingCourseRead)
def patch_course(record_id: int, payload: TrainingCourseUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return update_course(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/competencies", response_model=list[CompetencyRead])
def read_competencies(active: Optional[bool] = None, category: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _view(current_user)
    return list_competencies(db, active=active, category=category)


@router.post("/training/competencies", response_model=CompetencyRead, status_code=201)
def add_competency(payload: CompetencyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_competency(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/competencies/{record_id}", response_model=CompetencyRead)
def patch_competency(record_id: int, payload: CompetencyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return update_competency(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/course-competency-mappings", response_model=list[CourseCompetencyMappingRead])
def read_mappings(course_id: Optional[int] = None, competency_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _view(current_user)
    return list_course_mappings(db, course_id=course_id, competency_id=competency_id)


@router.post("/training/course-competency-mappings", response_model=CourseCompetencyMappingRead, status_code=201)
def add_mapping(payload: CourseCompetencyMappingCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_course_mapping(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/requirements", response_model=list[TrainingRequirementRead])
def read_requirements(site_id: Optional[int] = None, department_id: Optional[int] = None, role_name: Optional[str] = None, job_title: Optional[str] = None, course_id: Optional[int] = None, competency_id: Optional[int] = None, active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return list_requirements(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id, role_name=role_name, job_title=job_title, course_id=course_id, competency_id=competency_id, active=active)


@router.post("/training/requirements", response_model=TrainingRequirementRead, status_code=201)
def add_requirement(payload: TrainingRequirementCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return create_requirement(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/requirements/{record_id}", response_model=TrainingRequirementRead)
def patch_requirement(record_id: int, payload: TrainingRequirementUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    existing = db.get(TrainingRequirement, record_id)
    if existing is not None: ensure_site_access(current_user, existing.site_id)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return update_requirement(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/contractor-workers", response_model=list[ContractorWorkerRead])
def read_contractor_workers(contractor_id: Optional[int] = None, site_id: Optional[int] = None, active: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return list_contractor_workers(db, contractor_id=contractor_id, site_id=resolve_site_scope(current_user, site_id), active=active)


@router.post("/training/contractor-workers", response_model=ContractorWorkerRead, status_code=201)
def add_contractor_worker(payload: ContractorWorkerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return create_contractor_worker(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/contractor-workers/{record_id}", response_model=ContractorWorkerRead)
def patch_contractor_worker(record_id: int, payload: ContractorWorkerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    existing = db.get(ContractorWorker, record_id)
    if existing is not None: ensure_site_access(current_user, existing.site_id)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return update_contractor_worker(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/assignments", response_model=list[TrainingAssignmentRead])
def read_assignments(worker_user_id: Optional[int] = None, contractor_worker_id: Optional[int] = None, course_id: Optional[int] = None, site_id: Optional[int] = None, department_id: Optional[int] = None, assignment_status: Optional[AssignmentStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if has_permission(current_user, Permission.TRAINING_VIEW_ALL):
        site_id = resolve_site_scope(current_user, site_id)
    else:
        ensure_permission(current_user, Permission.TRAINING_SELF_VIEW)
        if contractor_worker_id or worker_user_id not in {None, current_user.id}: raise HTTPException(status_code=403, detail="Not authorized")
        worker_user_id = current_user.id
    return list_assignments(db, worker_user_id=worker_user_id, contractor_worker_id=contractor_worker_id, course_id=course_id, site_id=site_id, department_id=department_id, status=assignment_status)


@router.post("/training/assignments", response_model=TrainingAssignmentRead, status_code=201)
def add_assignment(payload: TrainingAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assign(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    _ensure_assignment_subject_scope(db, current_user, payload.assigned_user_id, payload.contractor_worker_id)
    try: return create_assignment(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/assignments/bulk")
def add_assignments_bulk(payload: BulkTrainingAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assign(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    for worker_id in payload.user_ids: _ensure_assignment_subject_scope(db, current_user, worker_id, None)
    for contractor_worker_id in payload.contractor_worker_ids: _ensure_assignment_subject_scope(db, current_user, None, contractor_worker_id)
    try: return bulk_assign(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/assignments/{record_id}", response_model=TrainingAssignmentRead)
def patch_assignment(record_id: int, payload: TrainingAssignmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assign(current_user)
    existing = db.get(TrainingAssignment, record_id)
    if existing is not None:
        ensure_site_access(current_user, existing.site_id)
        _ensure_assignment_subject_scope(db, current_user, existing.assigned_user_id, existing.contractor_worker_id)
    try: return update_assignment(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/sessions", response_model=list[TrainingSessionRead])
def read_sessions(course_id: Optional[int] = None, site_id: Optional[int] = None, department_id: Optional[int] = None, session_status: Optional[TrainingSessionStatus] = Query(default=None, alias="status"), starts_from: Optional[datetime] = None, starts_to: Optional[datetime] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _view(current_user)
    return list_sessions(db, course_id=course_id, site_id=resolve_site_scope(current_user, site_id), department_id=department_id, status=session_status, starts_from=starts_from, starts_to=starts_to)


@router.post("/training/sessions", response_model=TrainingSessionRead, status_code=201)
def add_session(payload: TrainingSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return create_session(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/sessions/{record_id}", response_model=TrainingSessionRead)
def patch_session(record_id: int, payload: TrainingSessionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    existing = db.get(TrainingSession, record_id)
    if existing is not None: ensure_site_access(current_user, existing.site_id)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return update_session(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/sessions/{session_id}/attendance", response_model=list[TrainingAttendanceRead])
def read_session_attendance(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    existing = db.get(TrainingSession, session_id)
    if existing is not None: ensure_site_access(current_user, existing.site_id)
    try: return list_attendance(db, session_id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/sessions/{session_id}/attendance", response_model=TrainingAttendanceRead)
def add_attendance(session_id: int, payload: TrainingAttendanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    existing = db.get(TrainingSession, session_id)
    if existing is not None: ensure_site_access(current_user, existing.site_id)
    _ensure_assignment_subject_scope(db, current_user, payload.worker_user_id, payload.contractor_worker_id)
    try: return record_attendance(db, session_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/assessments", response_model=list[TrainingAssessmentRead])
def read_assessments(worker_user_id: Optional[int] = None, contractor_worker_id: Optional[int] = None, course_id: Optional[int] = None, competency_id: Optional[int] = None, session_id: Optional[int] = None, passed: Optional[bool] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if worker_user_id: _worker_access(db, current_user, worker_user_id)
    else: ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    scope_site = resolve_site_scope(current_user, None) if has_permission(current_user, Permission.TRAINING_VIEW_ALL) else None
    return list_assessments(db, worker_user_id=worker_user_id, contractor_worker_id=contractor_worker_id, course_id=course_id, competency_id=competency_id, session_id=session_id, passed=passed, site_id=scope_site)


@router.post("/training/assessments", response_model=TrainingAssessmentRead, status_code=201)
def add_assessment(payload: TrainingAssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    _ensure_assignment_subject_scope(db, current_user, payload.worker_user_id, payload.contractor_worker_id)
    try: return create_assessment(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/certificates", response_model=list[TrainingCertificateRead])
def read_certificates(worker_user_id: Optional[int] = None, contractor_worker_id: Optional[int] = None, course_id: Optional[int] = None, competency_id: Optional[int] = None, expiring_before: Optional[date] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if worker_user_id: _worker_access(db, current_user, worker_user_id)
    else: ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    scope_site = resolve_site_scope(current_user, None) if has_permission(current_user, Permission.TRAINING_VIEW_ALL) else None
    return list_certificates(db, worker_user_id=worker_user_id, contractor_worker_id=contractor_worker_id, course_id=course_id, competency_id=competency_id, expiring_before=expiring_before, site_id=scope_site)


@router.post("/training/certificates", response_model=TrainingCertificateRead, status_code=201)
def add_certificate(payload: TrainingCertificateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    _ensure_assignment_subject_scope(db, current_user, payload.worker_user_id, payload.contractor_worker_id)
    try: return create_certificate(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/certificates/{record_id}/verify", response_model=TrainingCertificateRead)
def verify_training_certificate(record_id: int, payload: CertificateVerification, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    existing = db.get(TrainingCertificate, record_id)
    if existing is not None: _ensure_assignment_subject_scope(db, current_user, existing.worker_user_id, existing.contractor_worker_id)
    try: return verify_certificate(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/competency-awards", response_model=list[CompetencyAwardRead])
def read_awards(worker_user_id: Optional[int] = None, contractor_worker_id: Optional[int] = None, competency_id: Optional[int] = None, award_status: Optional[CompetencyAwardStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if worker_user_id: _worker_access(db, current_user, worker_user_id)
    else: ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    scope_site = resolve_site_scope(current_user, None) if has_permission(current_user, Permission.TRAINING_VIEW_ALL) else None
    return list_awards(db, worker_user_id=worker_user_id, contractor_worker_id=contractor_worker_id, competency_id=competency_id, status=award_status, site_id=scope_site)


@router.post("/training/competency-awards", response_model=CompetencyAwardRead, status_code=201)
def add_award(payload: CompetencyAwardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _assess(current_user)
    _ensure_assignment_subject_scope(db, current_user, payload.worker_user_id, payload.contractor_worker_id)
    try: return award_competency(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/competency-awards/{award_id}/status", response_model=CompetencyAwardRead)
def change_award_status(award_id: int, payload: CompetencyStatusChange, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _authorize(current_user)
    existing = db.get(CompetencyAward, award_id)
    if existing is not None: _ensure_assignment_subject_scope(db, current_user, existing.worker_user_id, existing.contractor_worker_id)
    try: return change_competency_status(db, award_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/competency-awards/{award_id}/history")
def read_award_history(award_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    existing = db.get(CompetencyAward, award_id)
    if existing is not None: _ensure_assignment_subject_scope(db, current_user, existing.worker_user_id, existing.contractor_worker_id)
    try: return competency_history(db, award_id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/authorizations", response_model=list[WorkAuthorizationRead])
def read_authorizations(worker_user_id: Optional[int] = None, contractor_worker_id: Optional[int] = None, authorization_type: Optional[str] = None, site_id: Optional[int] = None, department_id: Optional[int] = None, authorization_status: Optional[AuthorizationStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if worker_user_id:
        _worker_access(db, current_user, worker_user_id)
        scoped_site = site_id
    else:
        ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
        scoped_site = resolve_site_scope(current_user, site_id)
    if contractor_worker_id: _ensure_assignment_subject_scope(db, current_user, None, contractor_worker_id)
    return list_authorizations(db, worker_user_id=worker_user_id, contractor_worker_id=contractor_worker_id, authorization_type=authorization_type, site_id=scoped_site, department_id=department_id, status=authorization_status)


@router.post("/training/authorizations", response_model=WorkAuthorizationRead, status_code=201)
def add_authorization(payload: WorkAuthorizationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _authorize(current_user)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    _ensure_assignment_subject_scope(db, current_user, payload.worker_user_id, payload.contractor_worker_id)
    try: return create_authorization(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.patch("/training/authorizations/{record_id}", response_model=WorkAuthorizationRead)
def patch_authorization(record_id: int, payload: WorkAuthorizationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _authorize(current_user)
    existing = db.get(WorkAuthorization, record_id)
    if existing is not None:
        ensure_site_access(current_user, existing.site_id)
        _ensure_assignment_subject_scope(db, current_user, existing.worker_user_id, existing.contractor_worker_id)
    try: return update_authorization(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/eligibility")
def check_eligibility(payload: EligibilityQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if payload.worker_user_id: _worker_access(db, current_user, payload.worker_user_id)
    else: ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    if payload.contractor_worker_id: _ensure_assignment_subject_scope(db, current_user, None, payload.contractor_worker_id)
    if payload.site_id is not None: ensure_site_access(current_user, payload.site_id)
    try: return evaluate_eligibility(db, payload)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/workers/{worker_id}/profile")
def read_worker_profile(worker_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _worker_access(db, current_user, worker_id)
    try:
        result = worker_profile(db, worker_id)
        ensure_site_access(current_user, result["worker"]["site_id"])
        return result
    except TrainingCompetencyError as exc: raise _error(exc)


@router.get("/training/competency-matrix")
def read_competency_matrix(site_id: Optional[int] = None, department_id: Optional[int] = None, role_name: Optional[str] = None, job_title: Optional[str] = None, contractor_group: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return competency_matrix(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id, role_name=role_name, job_title=job_title, contractor_group=contractor_group)


@router.get("/training/job-role-matrix")
def read_job_role_matrix(site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return job_role_matrix(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id)


@router.get("/training/requests", response_model=list[TrainingRequestRead])
def read_requests(requester_user_id: Optional[int] = None, requested_for_user_id: Optional[int] = None, request_status: Optional[TrainingRequestStatus] = Query(default=None, alias="status"), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_permission(current_user, Permission.TRAINING_VIEW_ALL):
        ensure_permission(current_user, Permission.TRAINING_SELF_VIEW)
        requester_user_id = current_user.id
    scope_site = resolve_site_scope(current_user, None) if has_permission(current_user, Permission.TRAINING_VIEW_ALL) else None
    return list_requests(db, requester_user_id=requester_user_id, requested_for_user_id=requested_for_user_id, status=request_status, site_id=scope_site)


@router.post("/training/requests", response_model=TrainingRequestRead, status_code=201)
def add_request(payload: TrainingRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_REQUEST)
    can_request_for_team = has_permission(current_user, Permission.TRAINING_MANAGE) or has_permission(current_user, Permission.TRAINING_ASSIGN)
    if payload.requested_for_user_id not in {None, current_user.id} and not can_request_for_team: raise HTTPException(status_code=403, detail="Not authorized")
    if payload.contractor_worker_id and not can_request_for_team: raise HTTPException(status_code=403, detail="Not authorized")
    _ensure_assignment_subject_scope(db, current_user, payload.requested_for_user_id or (None if payload.contractor_worker_id else current_user.id), payload.contractor_worker_id)
    try: return create_request(db, payload, requester_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/requests/{record_id}/decision", response_model=TrainingRequestRead)
def review_request(record_id: int, payload: TrainingRequestDecision, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return decide_request(db, record_id, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/reminders/run")
def run_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    return generate_reminders(db)


@router.get("/training/forward-view")
def read_forward_view(site_id: Optional[int] = None, department_id: Optional[int] = None, days: int = Query(default=90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return forward_view(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id, days=days)


@router.get("/training/management-exceptions")
def read_management_exceptions(site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_VIEW_ALL)
    return management_exceptions(db, site_id=resolve_site_scope(current_user, site_id), department_id=department_id)


@router.get("/training/exports/{export_type}")
def download_export(export_type: str, site_id: Optional[int] = None, department_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_permission(current_user, Permission.TRAINING_EXPORT)
    try:
        content = export_csv(db, export_type, site_id=resolve_site_scope(current_user, site_id), department_id=department_id, actor_id=current_user.id)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{export_type}.csv"'})
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/actions", response_model=CorrectiveActionRead)
def add_action(payload: ActionGenerationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return generate_action(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)


@router.post("/training/deficiency-links", status_code=201)
def add_deficiency_link(payload: DeficiencyLinkCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _manage(current_user)
    try: return create_deficiency_link(db, payload, actor_id=current_user.id)
    except TrainingCompetencyError as exc: raise _error(exc)
