from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.models.approval import (
    ApprovalActionType,
    ApprovalEntityType,
    ApprovalStatus,
    ApprovalWorkflow,
)
from app.models.corrective_action import CorrectiveAction, CorrectiveActionStatus
from app.models.document_control import DocumentControlRecord, DocumentStatus
from app.models.hazard import Hazard, HazardRiskLevel
from app.models.incident import Incident, IncidentStatus
from app.models.notification import NotificationSeverity, NotificationType, RelatedEntityType
from app.models.permit import PermitStatus, PermitToWork
from app.models.role import Role
from app.models.user import User
from app.schemas.approval import ApprovalDecisionUpdate, ApprovalRequestCreate
from app.schemas.notification import NotificationCreate
from app.services.audit_service import write_audit_log
from app.services.notification_service import create_notification_once
from app.services.query_utils import paginate
from app.services.rbac import (
    Permission,
    ROLE_ADMIN,
    ROLE_OHS_MANAGER,
    ensure_permission,
    ensure_site_access,
    has_any_role,
    is_site_scoped,
)
from app.services.document_control_service import sync_document_acknowledgements


class ApprovalServiceError(Exception):
    pass


class ApprovalNotFoundError(ApprovalServiceError):
    pass


class ApprovalEntityNotFoundError(ApprovalServiceError):
    pass


class ApprovalDuplicatePendingError(ApprovalServiceError):
    pass


class ApprovalValidationError(ApprovalServiceError):
    pass


ENTITY_MODEL_MAP = {
    ApprovalEntityType.incident: Incident,
    ApprovalEntityType.hazard: Hazard,
    ApprovalEntityType.corrective_action: CorrectiveAction,
    ApprovalEntityType.permit: PermitToWork,
    ApprovalEntityType.document_control: DocumentControlRecord,
}

ENTITY_VIEW_PERMISSION_MAP = {
    ApprovalEntityType.incident: Permission.INCIDENTS_VIEW,
    ApprovalEntityType.hazard: Permission.HAZARDS_VIEW,
    ApprovalEntityType.corrective_action: Permission.CORRECTIVE_ACTIONS_VIEW,
    ApprovalEntityType.permit: Permission.PERMITS_VIEW,
    ApprovalEntityType.document_control: Permission.DOCUMENTS_VIEW,
}

ENTITY_ACTION_TYPE_MAP = {
    ApprovalEntityType.incident: ApprovalActionType.incident_closure,
    ApprovalEntityType.hazard: ApprovalActionType.hazard_review,
    ApprovalEntityType.corrective_action: ApprovalActionType.corrective_action_verification,
    ApprovalEntityType.permit: ApprovalActionType.permit_approval,
    ApprovalEntityType.document_control: ApprovalActionType.document_approval,
}

ENTITY_NOTIFICATION_TYPE_MAP = {
    ApprovalEntityType.incident: RelatedEntityType.incident,
    ApprovalEntityType.hazard: RelatedEntityType.hazard,
    ApprovalEntityType.corrective_action: RelatedEntityType.corrective_action,
    ApprovalEntityType.permit: RelatedEntityType.permit,
    ApprovalEntityType.document_control: RelatedEntityType.document_control,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_entity(db: Session, entity_type: ApprovalEntityType, entity_id: int):
    entity = db.get(ENTITY_MODEL_MAP[entity_type], entity_id)
    if entity is None:
        raise ApprovalEntityNotFoundError(f"{entity_type.value} {entity_id} was not found")
    return entity


def _get_entity_site_id(entity) -> Optional[int]:
    return getattr(entity, "site_id", None)


def _ensure_entity_view_access(current_user: User, entity_type: ApprovalEntityType, entity) -> None:
    ensure_permission(current_user, ENTITY_VIEW_PERMISSION_MAP[entity_type])
    ensure_site_access(current_user, _get_entity_site_id(entity))


def _ensure_assigned_approver_is_valid(db: Session, assigned_approver_user_id: Optional[int]) -> None:
    if assigned_approver_user_id is None:
        return
    approver = db.get(User, assigned_approver_user_id)
    if approver is None:
        raise ApprovalValidationError("Assigned approver was not found")
    if not has_any_role(approver, ROLE_ADMIN, ROLE_OHS_MANAGER):
        raise ApprovalValidationError("Assigned approver must be an Admin or OHS Manager")


def _site_scope_clause(site_id: int):
    return or_(
        and_(
            ApprovalWorkflow.entity_type == ApprovalEntityType.incident,
            ApprovalWorkflow.entity_id.in_(select(Incident.id).where(Incident.site_id == site_id)),
        ),
        and_(
            ApprovalWorkflow.entity_type == ApprovalEntityType.hazard,
            ApprovalWorkflow.entity_id.in_(select(Hazard.id).where(Hazard.site_id == site_id)),
        ),
        and_(
            ApprovalWorkflow.entity_type == ApprovalEntityType.corrective_action,
            ApprovalWorkflow.entity_id.in_(
                select(CorrectiveAction.id).where(CorrectiveAction.site_id == site_id)
            ),
        ),
        and_(
            ApprovalWorkflow.entity_type == ApprovalEntityType.permit,
            ApprovalWorkflow.entity_id.in_(select(PermitToWork.id).where(PermitToWork.site_id == site_id)),
        ),
        and_(
            ApprovalWorkflow.entity_type == ApprovalEntityType.document_control,
            ApprovalWorkflow.entity_id.in_(
                select(DocumentControlRecord.id).where(DocumentControlRecord.site_id == site_id)
            ),
        ),
    )


def _default_approver_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(User.id)
            .join(User.roles)
            .where(Role.name.in_([ROLE_ADMIN, ROLE_OHS_MANAGER]), User.is_active.is_(True))
            .distinct()
        ).all()
    )


def _notification_recipients_for_request(
    db: Session,
    *,
    approval: ApprovalWorkflow,
) -> list[int]:
    if approval.assigned_approver_user_id is not None:
        return [approval.assigned_approver_user_id]
    return _default_approver_ids(db)


def _notify_approval_requested(db: Session, approval: ApprovalWorkflow) -> None:
    for recipient_user_id in _notification_recipients_for_request(db, approval=approval):
        create_notification_once(
            db,
            NotificationCreate(
                recipient_user_id=recipient_user_id,
                title="Approval requested",
                message=(
                    f"{approval.action_type.value.replace('_', ' ')} requested for "
                    f"{approval.entity_type.value} #{approval.entity_id}."
                ),
                notification_type=NotificationType.approval_requested,
                severity=NotificationSeverity.warning,
                related_entity_type=ENTITY_NOTIFICATION_TYPE_MAP[approval.entity_type],
                related_entity_id=approval.entity_id,
            ),
        )


def _notify_approval_decision(db: Session, approval: ApprovalWorkflow) -> None:
    notification_type = {
        ApprovalStatus.approved: NotificationType.approval_approved,
        ApprovalStatus.rejected: NotificationType.approval_rejected,
    }.get(approval.status)
    if notification_type is None or approval.requested_by_user_id is None:
        return

    create_notification_once(
        db,
        NotificationCreate(
            recipient_user_id=approval.requested_by_user_id,
            title=f"Approval {approval.status.value}",
            message=(
                f"{approval.action_type.value.replace('_', ' ')} was "
                f"{approval.status.value} for {approval.entity_type.value} #{approval.entity_id}."
            ),
            notification_type=notification_type,
            severity=(
                NotificationSeverity.info
                if approval.status == ApprovalStatus.approved
                else NotificationSeverity.warning
            ),
            related_entity_type=ENTITY_NOTIFICATION_TYPE_MAP[approval.entity_type],
            related_entity_id=approval.entity_id,
        ),
    )


def _validate_action_matches_entity(
    entity_type: ApprovalEntityType,
    action_type: ApprovalActionType,
) -> None:
    expected_action_type = ENTITY_ACTION_TYPE_MAP[entity_type]
    if action_type != expected_action_type:
        raise ApprovalValidationError(
            f"{entity_type.value} approvals only support {expected_action_type.value}"
        )


def _validate_entity_request_rules(
    entity_type: ApprovalEntityType,
    entity,
) -> None:
    if entity_type == ApprovalEntityType.incident and entity.status == IncidentStatus.closed:
        raise ApprovalValidationError("Closed incidents cannot request closure approval")

    if entity_type == ApprovalEntityType.hazard and entity.risk_level not in {
        HazardRiskLevel.high,
        HazardRiskLevel.critical,
    }:
        raise ApprovalValidationError("Only high or critical hazards can request hazard review")

    if entity_type == ApprovalEntityType.corrective_action and entity.status in {
        CorrectiveActionStatus.closed,
        CorrectiveActionStatus.cancelled,
    }:
        raise ApprovalValidationError("Closed or cancelled corrective actions cannot request verification")

    if entity_type == ApprovalEntityType.permit and entity.status in {
        PermitStatus.approved,
        PermitStatus.active,
        PermitStatus.closed,
        PermitStatus.cancelled,
    }:
        raise ApprovalValidationError("This permit is no longer eligible for approval workflow requests")
    if entity_type == ApprovalEntityType.document_control and entity.status in {
        DocumentStatus.approved,
        DocumentStatus.archived,
    }:
        raise ApprovalValidationError("Approved or archived documents cannot request approval")


def _apply_entity_pending_state(entity_type: ApprovalEntityType, entity, current_user: User) -> None:
    if entity_type == ApprovalEntityType.incident:
        entity.closure_requested = True
        return

    if entity_type == ApprovalEntityType.corrective_action:
        if entity.status not in {
            CorrectiveActionStatus.pending_verification,
            CorrectiveActionStatus.closed,
        }:
            entity.status = CorrectiveActionStatus.pending_verification
            if entity.completed_at is None:
                entity.completed_at = _now()
        return

    if entity_type == ApprovalEntityType.permit and entity.status != PermitStatus.pending_approval:
        entity.status = PermitStatus.pending_approval
        return

    if entity_type == ApprovalEntityType.document_control and entity.status != DocumentStatus.pending_approval:
        entity.status = DocumentStatus.pending_approval


def _apply_entity_approved_state(entity_type: ApprovalEntityType, entity, current_user: User) -> None:
    now = _now()

    if entity_type == ApprovalEntityType.incident:
        entity.closure_requested = False
        entity.status = IncidentStatus.closed
        entity.closed_at = now
        entity.closed_by_user_id = current_user.id
        return

    if entity_type == ApprovalEntityType.hazard:
        entity.reviewed_at = now
        entity.reviewed_by_user_id = current_user.id
        return

    if entity_type == ApprovalEntityType.corrective_action:
        entity.status = CorrectiveActionStatus.closed
        entity.verified_by_user_id = current_user.id
        entity.verified_at = entity.verified_at or now
        return

    if entity_type == ApprovalEntityType.permit:
        entity.status = PermitStatus.approved
        entity.approved_by_user_id = current_user.id
        entity.approved_at = now
        return

    if entity_type == ApprovalEntityType.document_control:
        entity.status = DocumentStatus.approved
        entity.approved_by_user_id = current_user.id
        entity.approved_at = now


def _apply_entity_rejected_or_cancelled_state(entity_type: ApprovalEntityType, entity) -> None:
    if entity_type == ApprovalEntityType.incident:
        entity.closure_requested = False
    if entity_type == ApprovalEntityType.document_control and entity.status == DocumentStatus.pending_approval:
        entity.status = DocumentStatus.draft


def _write_entity_transition_audit_log(
    db: Session,
    *,
    approval: ApprovalWorkflow,
    actor_id: Optional[int],
) -> None:
    action_by_approval = {
        ApprovalActionType.incident_closure: "incident.workflow_closed",
        ApprovalActionType.hazard_review: "hazard.workflow_reviewed",
        ApprovalActionType.corrective_action_verification: "corrective_action.workflow_verified",
        ApprovalActionType.permit_approval: "permit.workflow_approved",
        ApprovalActionType.document_approval: "document_control.workflow_approved",
    }
    if approval.status != ApprovalStatus.approved:
        return
    write_audit_log(
        db,
        actor_id=actor_id,
        action=action_by_approval[approval.action_type],
        resource_type=approval.entity_type.value,
        resource_id=approval.entity_id,
        details={"approval_id": approval.id, "status": approval.status.value},
    )


def list_approvals(
    db: Session,
    *,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    entity_type: Optional[ApprovalEntityType] = None,
    entity_id: Optional[int] = None,
    action_type: Optional[ApprovalActionType] = None,
    approval_status: Optional[ApprovalStatus] = None,
) -> dict:
    ensure_permission(current_user, Permission.APPROVALS_VIEW)

    statement: Select[tuple[ApprovalWorkflow]] = select(ApprovalWorkflow)
    if entity_type is not None:
        statement = statement.where(ApprovalWorkflow.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(ApprovalWorkflow.entity_id == entity_id)
    if action_type is not None:
        statement = statement.where(ApprovalWorkflow.action_type == action_type)
    if approval_status is not None:
        statement = statement.where(ApprovalWorkflow.status == approval_status)

    if is_site_scoped(current_user):
        assigned_site_id = getattr(current_user, "assigned_site_id", None)
        if assigned_site_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not assigned to a site",
            )
        statement = statement.where(_site_scope_clause(assigned_site_id))

    statement = statement.order_by(ApprovalWorkflow.created_at.desc(), ApprovalWorkflow.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_approval(db: Session, approval_id: int, *, current_user: User) -> ApprovalWorkflow:
    ensure_permission(current_user, Permission.APPROVALS_VIEW)
    approval = db.get(ApprovalWorkflow, approval_id)
    if approval is None:
        raise ApprovalNotFoundError(f"Approval {approval_id} was not found")

    entity = _get_entity(db, approval.entity_type, approval.entity_id)
    _ensure_entity_view_access(current_user, approval.entity_type, entity)
    return approval


def request_approval(
    db: Session,
    *,
    entity_type: ApprovalEntityType,
    entity_id: int,
    approval_in: ApprovalRequestCreate,
    current_user: User,
) -> ApprovalWorkflow:
    ensure_permission(current_user, Permission.APPROVALS_REQUEST)
    _validate_action_matches_entity(entity_type, approval_in.action_type)
    _ensure_assigned_approver_is_valid(db, approval_in.assigned_approver_user_id)

    entity = _get_entity(db, entity_type, entity_id)
    _ensure_entity_view_access(current_user, entity_type, entity)
    _validate_entity_request_rules(entity_type, entity)

    existing_pending = db.scalar(
        select(ApprovalWorkflow).where(
            ApprovalWorkflow.entity_type == entity_type,
            ApprovalWorkflow.entity_id == entity_id,
            ApprovalWorkflow.action_type == approval_in.action_type,
            ApprovalWorkflow.status == ApprovalStatus.pending,
        )
    )
    if existing_pending is not None:
        raise ApprovalDuplicatePendingError("A pending approval already exists for this record")

    approval = ApprovalWorkflow(
        entity_type=entity_type,
        entity_id=entity_id,
        requested_by_user_id=current_user.id,
        assigned_approver_user_id=approval_in.assigned_approver_user_id,
        action_type=approval_in.action_type,
        status=ApprovalStatus.pending,
        request_notes=approval_in.request_notes,
    )
    _apply_entity_pending_state(entity_type, entity, current_user)
    db.add_all([entity, approval])
    db.commit()
    db.refresh(approval)

    write_audit_log(
        db,
        actor_id=current_user.id,
        action="approval.requested",
        resource_type="approval",
        resource_id=approval.id,
        details={
            "entity_type": approval.entity_type.value,
            "entity_id": approval.entity_id,
            "action_type": approval.action_type.value,
        },
    )
    _notify_approval_requested(db, approval)
    return approval


def decide_approval(
    db: Session,
    *,
    approval_id: int,
    decision_in: ApprovalDecisionUpdate,
    current_user: User,
) -> ApprovalWorkflow:
    approval = db.get(ApprovalWorkflow, approval_id)
    if approval is None:
        raise ApprovalNotFoundError(f"Approval {approval_id} was not found")

    entity = _get_entity(db, approval.entity_type, approval.entity_id)
    if decision_in.status in {ApprovalStatus.approved, ApprovalStatus.rejected}:
        ensure_permission(current_user, Permission.APPROVALS_DECIDE)
    elif decision_in.status == ApprovalStatus.cancelled:
        if current_user.id != approval.requested_by_user_id:
            ensure_permission(current_user, Permission.APPROVALS_DECIDE)
    else:
        raise ApprovalValidationError("Only approved, rejected, or cancelled decisions are supported")

    _ensure_entity_view_access(current_user, approval.entity_type, entity)
    if approval.status != ApprovalStatus.pending:
        raise ApprovalValidationError("Only pending approvals can be decided")

    approval.status = decision_in.status
    approval.decision_notes = decision_in.decision_notes
    approval.decided_by_user_id = current_user.id
    approval.decided_at = _now()

    if approval.status == ApprovalStatus.approved:
        _apply_entity_approved_state(approval.entity_type, entity, current_user)
    else:
        _apply_entity_rejected_or_cancelled_state(approval.entity_type, entity)

    db.add_all([entity, approval])
    db.commit()
    db.refresh(approval)
    if approval.status == ApprovalStatus.approved and approval.entity_type == ApprovalEntityType.document_control:
        sync_document_acknowledgements(db, entity, actor_id=current_user.id)

    write_audit_log(
        db,
        actor_id=current_user.id,
        action=f"approval.{approval.status.value}",
        resource_type="approval",
        resource_id=approval.id,
        details={
            "entity_type": approval.entity_type.value,
            "entity_id": approval.entity_id,
            "action_type": approval.action_type.value,
            "decision_notes": approval.decision_notes,
        },
    )
    _write_entity_transition_audit_log(db, approval=approval, actor_id=current_user.id)
    _notify_approval_decision(db, approval)
    return approval
