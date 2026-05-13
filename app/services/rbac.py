from __future__ import annotations

from typing import Optional
from fastapi import HTTPException, status

ROLE_ADMIN = "admin"
ROLE_OHS_MANAGER = "ohs_manager"
ROLE_SAFETY_OFFICER = "safety_officer"
ROLE_SUPERVISOR = "supervisor"
ROLE_EMPLOYEE = "employee"

STANDARD_ROLES = (
    ROLE_ADMIN,
    ROLE_OHS_MANAGER,
    ROLE_SAFETY_OFFICER,
    ROLE_SUPERVISOR,
    ROLE_EMPLOYEE,
)

STANDARD_ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Enterprise administrator with full system access.",
    ROLE_OHS_MANAGER: "Operational leader with enterprise-wide OHS workflow access.",
    ROLE_SAFETY_OFFICER: "Operational safety specialist for incidents, hazards, inspections, training, and permits.",
    ROLE_SUPERVISOR: "Site supervisor with assigned-site operational access.",
    ROLE_EMPLOYEE: "Employee with self-service and assigned-site reporting access.",
}

LEGACY_ROLE_RENAMES = {
    "safety_manager": ROLE_OHS_MANAGER,
    "worker": ROLE_EMPLOYEE,
    "auditor": ROLE_SAFETY_OFFICER,
}

ROLE_PRIORITY = [
    ROLE_ADMIN,
    ROLE_OHS_MANAGER,
    ROLE_SAFETY_OFFICER,
    ROLE_SUPERVISOR,
    ROLE_EMPLOYEE,
]


class Permission:
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    ROLES_READ = "roles.read"
    ROLES_MANAGE = "roles.manage"
    SITES_READ = "sites.read"
    SITES_MANAGE = "sites.manage"
    INCIDENTS_VIEW = "incidents.view"
    INCIDENTS_CREATE = "incidents.create"
    INCIDENTS_EDIT = "incidents.edit"
    INCIDENTS_CLOSE = "incidents.close"
    HAZARDS_VIEW = "hazards.view"
    HAZARDS_CREATE = "hazards.create"
    HAZARDS_EDIT = "hazards.edit"
    HAZARDS_CLOSE = "hazards.close"
    INSPECTIONS_VIEW = "inspections.view"
    INSPECTIONS_CREATE = "inspections.create"
    INSPECTIONS_EDIT = "inspections.edit"
    CORRECTIVE_ACTIONS_VIEW = "corrective_actions.view"
    CORRECTIVE_ACTIONS_CREATE = "corrective_actions.create"
    CORRECTIVE_ACTIONS_EDIT = "corrective_actions.edit"
    CORRECTIVE_ACTIONS_SELF_UPDATE = "corrective_actions.self_update"
    CORRECTIVE_ACTIONS_VERIFY = "corrective_actions.verify"
    DASHBOARD_VIEW = "dashboard.view"
    NOTIFICATIONS_VIEW = "notifications.view"
    NOTIFICATIONS_MANAGE = "notifications.manage"
    EXPORTS_VIEW = "exports.view"
    TRAINING_VIEW_ALL = "training.view_all"
    TRAINING_MANAGE = "training.manage"
    TRAINING_SELF_VIEW = "training.self_view"
    TRAINING_SELF_UPDATE = "training.self_update"
    COMPLIANCE_VIEW_ALL = "compliance.view_all"
    COMPLIANCE_MANAGE = "compliance.manage"
    COMPLIANCE_SELF_VIEW = "compliance.self_view"
    COMPLIANCE_SELF_UPDATE = "compliance.self_update"
    PERMITS_VIEW = "permits.view"
    PERMITS_REQUEST = "permits.request"
    PERMITS_MANAGE = "permits.manage"
    PERMITS_APPROVE = "permits.approve"
    SAFETY_KPIS_VIEW = "safety_kpis.view"
    SAFETY_KPIS_CREATE = "safety_kpis.create"
    SAFETY_KPIS_EDIT = "safety_kpis.edit"
    SAFETY_COMMUNICATIONS_VIEW = "safety_communications.view"
    SAFETY_COMMUNICATIONS_CREATE = "safety_communications.create"
    SAFETY_COMMUNICATIONS_EDIT = "safety_communications.edit"
    BEHAVIOUR_OBSERVATIONS_VIEW = "behaviour_observations.view"
    BEHAVIOUR_OBSERVATIONS_CREATE = "behaviour_observations.create"
    BEHAVIOUR_OBSERVATIONS_EDIT = "behaviour_observations.edit"
    INVESTIGATIONS_VIEW = "investigations.view"
    INVESTIGATIONS_CREATE = "investigations.create"
    INVESTIGATIONS_EDIT = "investigations.edit"
    INVESTIGATIONS_APPROVE = "investigations.approve"
    LEGAL_COMPLIANCE_VIEW = "legal_compliance.view"
    LEGAL_COMPLIANCE_CREATE = "legal_compliance.create"
    LEGAL_COMPLIANCE_EDIT = "legal_compliance.edit"
    JSA_VIEW = "jsa.view"
    JSA_CREATE = "jsa.create"
    JSA_EDIT = "jsa.edit"
    JSA_APPROVE = "jsa.approve"
    CONTRACTORS_VIEW = "contractors.view"
    CONTRACTORS_CREATE = "contractors.create"
    CONTRACTORS_EDIT = "contractors.edit"
    CONTRACTORS_APPROVE = "contractors.approve"
    ASSETS_VIEW = "assets.view"
    ASSETS_CREATE = "assets.create"
    ASSETS_EDIT = "assets.edit"
    MEDICAL_SURVEILLANCE_VIEW = "medical_surveillance.view"
    MEDICAL_SURVEILLANCE_CREATE = "medical_surveillance.create"
    MEDICAL_SURVEILLANCE_EDIT = "medical_surveillance.edit"
    EMERGENCY_DRILLS_VIEW = "emergency_drills.view"
    EMERGENCY_DRILLS_CREATE = "emergency_drills.create"
    EMERGENCY_DRILLS_EDIT = "emergency_drills.edit"
    DOCUMENTS_VIEW = "documents.view"
    DOCUMENTS_CREATE = "documents.create"
    DOCUMENTS_EDIT = "documents.edit"
    DOCUMENTS_APPROVE = "documents.approve"
    AUDITS_VIEW = "audits.view"
    AUDITS_CREATE = "audits.create"
    AUDITS_EDIT = "audits.edit"
    NOTIFICATION_DELIVERY_VIEW = "notification_delivery.view"
    JOB_RUNS_VIEW = "job_runs.view"
    JOB_RUNS_MANAGE = "job_runs.manage"
    APPROVALS_VIEW = "approvals.view"
    APPROVALS_REQUEST = "approvals.request"
    APPROVALS_DECIDE = "approvals.decide"
    AUDIT_LOGS_VIEW = "audit_logs.view"


ROLE_PERMISSIONS = {
    ROLE_ADMIN: {"*"},
    ROLE_OHS_MANAGER: {
        Permission.USERS_READ,
        Permission.ROLES_READ,
        Permission.SITES_READ,
        Permission.SITES_MANAGE,
        Permission.INCIDENTS_VIEW,
        Permission.INCIDENTS_CREATE,
        Permission.INCIDENTS_EDIT,
        Permission.INCIDENTS_CLOSE,
        Permission.HAZARDS_VIEW,
        Permission.HAZARDS_CREATE,
        Permission.HAZARDS_EDIT,
        Permission.HAZARDS_CLOSE,
        Permission.INSPECTIONS_VIEW,
        Permission.INSPECTIONS_CREATE,
        Permission.INSPECTIONS_EDIT,
        Permission.CORRECTIVE_ACTIONS_VIEW,
        Permission.CORRECTIVE_ACTIONS_CREATE,
        Permission.CORRECTIVE_ACTIONS_EDIT,
        Permission.CORRECTIVE_ACTIONS_VERIFY,
        Permission.DASHBOARD_VIEW,
        Permission.NOTIFICATIONS_VIEW,
        Permission.NOTIFICATIONS_MANAGE,
        Permission.EXPORTS_VIEW,
        Permission.TRAINING_VIEW_ALL,
        Permission.TRAINING_MANAGE,
        Permission.COMPLIANCE_VIEW_ALL,
        Permission.COMPLIANCE_MANAGE,
        Permission.PERMITS_VIEW,
        Permission.PERMITS_REQUEST,
        Permission.PERMITS_MANAGE,
        Permission.PERMITS_APPROVE,
        Permission.SAFETY_KPIS_VIEW,
        Permission.SAFETY_KPIS_CREATE,
        Permission.SAFETY_KPIS_EDIT,
        Permission.SAFETY_COMMUNICATIONS_VIEW,
        Permission.SAFETY_COMMUNICATIONS_CREATE,
        Permission.SAFETY_COMMUNICATIONS_EDIT,
        Permission.BEHAVIOUR_OBSERVATIONS_VIEW,
        Permission.BEHAVIOUR_OBSERVATIONS_CREATE,
        Permission.BEHAVIOUR_OBSERVATIONS_EDIT,
        Permission.INVESTIGATIONS_VIEW,
        Permission.INVESTIGATIONS_CREATE,
        Permission.INVESTIGATIONS_EDIT,
        Permission.INVESTIGATIONS_APPROVE,
        Permission.LEGAL_COMPLIANCE_VIEW,
        Permission.LEGAL_COMPLIANCE_CREATE,
        Permission.LEGAL_COMPLIANCE_EDIT,
        Permission.JSA_VIEW,
        Permission.JSA_CREATE,
        Permission.JSA_EDIT,
        Permission.JSA_APPROVE,
        Permission.CONTRACTORS_VIEW,
        Permission.CONTRACTORS_CREATE,
        Permission.CONTRACTORS_EDIT,
        Permission.CONTRACTORS_APPROVE,
        Permission.ASSETS_VIEW,
        Permission.ASSETS_CREATE,
        Permission.ASSETS_EDIT,
        Permission.MEDICAL_SURVEILLANCE_VIEW,
        Permission.MEDICAL_SURVEILLANCE_CREATE,
        Permission.MEDICAL_SURVEILLANCE_EDIT,
        Permission.EMERGENCY_DRILLS_VIEW,
        Permission.EMERGENCY_DRILLS_CREATE,
        Permission.EMERGENCY_DRILLS_EDIT,
        Permission.DOCUMENTS_VIEW,
        Permission.DOCUMENTS_CREATE,
        Permission.DOCUMENTS_EDIT,
        Permission.DOCUMENTS_APPROVE,
        Permission.AUDITS_VIEW,
        Permission.AUDITS_CREATE,
        Permission.AUDITS_EDIT,
        Permission.NOTIFICATION_DELIVERY_VIEW,
        Permission.JOB_RUNS_VIEW,
        Permission.JOB_RUNS_MANAGE,
        Permission.APPROVALS_VIEW,
        Permission.APPROVALS_REQUEST,
        Permission.APPROVALS_DECIDE,
    },
    ROLE_SAFETY_OFFICER: {
        Permission.USERS_READ,
        Permission.SITES_READ,
        Permission.INCIDENTS_VIEW,
        Permission.INCIDENTS_CREATE,
        Permission.INCIDENTS_EDIT,
        Permission.HAZARDS_VIEW,
        Permission.HAZARDS_CREATE,
        Permission.HAZARDS_EDIT,
        Permission.INSPECTIONS_VIEW,
        Permission.INSPECTIONS_CREATE,
        Permission.INSPECTIONS_EDIT,
        Permission.CORRECTIVE_ACTIONS_VIEW,
        Permission.CORRECTIVE_ACTIONS_CREATE,
        Permission.CORRECTIVE_ACTIONS_EDIT,
        Permission.DASHBOARD_VIEW,
        Permission.NOTIFICATIONS_VIEW,
        Permission.EXPORTS_VIEW,
        Permission.TRAINING_VIEW_ALL,
        Permission.TRAINING_MANAGE,
        Permission.COMPLIANCE_VIEW_ALL,
        Permission.COMPLIANCE_MANAGE,
        Permission.PERMITS_VIEW,
        Permission.PERMITS_REQUEST,
        Permission.PERMITS_MANAGE,
        Permission.SAFETY_KPIS_VIEW,
        Permission.SAFETY_KPIS_CREATE,
        Permission.SAFETY_KPIS_EDIT,
        Permission.SAFETY_COMMUNICATIONS_VIEW,
        Permission.SAFETY_COMMUNICATIONS_CREATE,
        Permission.SAFETY_COMMUNICATIONS_EDIT,
        Permission.BEHAVIOUR_OBSERVATIONS_VIEW,
        Permission.BEHAVIOUR_OBSERVATIONS_CREATE,
        Permission.BEHAVIOUR_OBSERVATIONS_EDIT,
        Permission.INVESTIGATIONS_VIEW,
        Permission.INVESTIGATIONS_CREATE,
        Permission.INVESTIGATIONS_EDIT,
        Permission.LEGAL_COMPLIANCE_VIEW,
        Permission.LEGAL_COMPLIANCE_CREATE,
        Permission.LEGAL_COMPLIANCE_EDIT,
        Permission.JSA_VIEW,
        Permission.JSA_CREATE,
        Permission.JSA_EDIT,
        Permission.CONTRACTORS_VIEW,
        Permission.CONTRACTORS_CREATE,
        Permission.CONTRACTORS_EDIT,
        Permission.ASSETS_VIEW,
        Permission.ASSETS_CREATE,
        Permission.ASSETS_EDIT,
        Permission.MEDICAL_SURVEILLANCE_VIEW,
        Permission.MEDICAL_SURVEILLANCE_CREATE,
        Permission.MEDICAL_SURVEILLANCE_EDIT,
        Permission.EMERGENCY_DRILLS_VIEW,
        Permission.EMERGENCY_DRILLS_CREATE,
        Permission.EMERGENCY_DRILLS_EDIT,
        Permission.DOCUMENTS_VIEW,
        Permission.DOCUMENTS_CREATE,
        Permission.DOCUMENTS_EDIT,
        Permission.AUDITS_VIEW,
        Permission.AUDITS_CREATE,
        Permission.AUDITS_EDIT,
        Permission.NOTIFICATION_DELIVERY_VIEW,
        Permission.JOB_RUNS_VIEW,
        Permission.APPROVALS_VIEW,
        Permission.APPROVALS_REQUEST,
    },
    ROLE_SUPERVISOR: {
        Permission.SITES_READ,
        Permission.INCIDENTS_VIEW,
        Permission.INCIDENTS_CREATE,
        Permission.HAZARDS_VIEW,
        Permission.HAZARDS_CREATE,
        Permission.INSPECTIONS_VIEW,
        Permission.CORRECTIVE_ACTIONS_VIEW,
        Permission.CORRECTIVE_ACTIONS_SELF_UPDATE,
        Permission.DASHBOARD_VIEW,
        Permission.NOTIFICATIONS_VIEW,
        Permission.PERMITS_VIEW,
        Permission.PERMITS_REQUEST,
        Permission.SAFETY_KPIS_VIEW,
        Permission.SAFETY_COMMUNICATIONS_VIEW,
        Permission.SAFETY_COMMUNICATIONS_CREATE,
        Permission.SAFETY_COMMUNICATIONS_EDIT,
        Permission.BEHAVIOUR_OBSERVATIONS_VIEW,
        Permission.BEHAVIOUR_OBSERVATIONS_CREATE,
        Permission.BEHAVIOUR_OBSERVATIONS_EDIT,
        Permission.INVESTIGATIONS_VIEW,
        Permission.LEGAL_COMPLIANCE_VIEW,
        Permission.JSA_VIEW,
        Permission.JSA_CREATE,
        Permission.JSA_EDIT,
        Permission.CONTRACTORS_VIEW,
        Permission.ASSETS_VIEW,
        Permission.ASSETS_CREATE,
        Permission.ASSETS_EDIT,
        Permission.EMERGENCY_DRILLS_VIEW,
        Permission.EMERGENCY_DRILLS_CREATE,
        Permission.EMERGENCY_DRILLS_EDIT,
        Permission.DOCUMENTS_VIEW,
        Permission.AUDITS_VIEW,
        Permission.APPROVALS_VIEW,
        Permission.APPROVALS_REQUEST,
    },
    ROLE_EMPLOYEE: {
        Permission.SITES_READ,
        Permission.INCIDENTS_VIEW,
        Permission.INCIDENTS_CREATE,
        Permission.HAZARDS_VIEW,
        Permission.HAZARDS_CREATE,
        Permission.NOTIFICATIONS_VIEW,
        Permission.TRAINING_SELF_VIEW,
        Permission.TRAINING_SELF_UPDATE,
        Permission.COMPLIANCE_SELF_VIEW,
        Permission.COMPLIANCE_SELF_UPDATE,
        Permission.PERMITS_VIEW,
        Permission.PERMITS_REQUEST,
        Permission.SAFETY_COMMUNICATIONS_VIEW,
        Permission.BEHAVIOUR_OBSERVATIONS_VIEW,
        Permission.BEHAVIOUR_OBSERVATIONS_CREATE,
        Permission.JSA_VIEW,
        Permission.ASSETS_VIEW,
        Permission.DOCUMENTS_VIEW,
    },
}

GLOBAL_SITE_ACCESS_ROLES = {ROLE_ADMIN, ROLE_OHS_MANAGER, ROLE_SAFETY_OFFICER}
SITE_SCOPED_ROLES = {ROLE_SUPERVISOR, ROLE_EMPLOYEE}


def normalize_role_name(role_name: str) -> str:
    return LEGACY_ROLE_RENAMES.get(role_name, role_name)


def get_normalized_role_names(user) -> set[str]:
    roles = getattr(user, "roles", None) or []
    return {
        normalize_role_name(role.name if hasattr(role, "name") else str(role))
        for role in roles
    }


def get_primary_role_name(user) -> Optional[str]:
    role_names = get_normalized_role_names(user)
    for role_name in ROLE_PRIORITY:
        if role_name in role_names:
            return role_name
    return None


def has_any_role(user, *role_names: str) -> bool:
    normalized = {normalize_role_name(role_name) for role_name in role_names}
    return bool(get_normalized_role_names(user).intersection(normalized))


def has_permission(user, permission: str) -> bool:
    role_names = get_normalized_role_names(user)
    if not role_names:
        return False

    effective_permissions = set()
    for role_name in role_names:
        effective_permissions.update(ROLE_PERMISSIONS.get(role_name, set()))

    return "*" in effective_permissions or permission in effective_permissions


def ensure_permission(user, permission: str, detail: str = "Not authorized") -> None:
    if not has_permission(user, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def is_site_scoped(user) -> bool:
    role_names = get_normalized_role_names(user)
    if role_names.intersection(GLOBAL_SITE_ACCESS_ROLES):
        return False
    return bool(role_names.intersection(SITE_SCOPED_ROLES))


def ensure_site_assignment(user) -> int:
    assigned_site_id = getattr(user, "assigned_site_id", None)
    if is_site_scoped(user) and assigned_site_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a site",
        )
    return assigned_site_id


def resolve_site_scope(user, requested_site_id: Optional[int] = None) -> Optional[int]:
    if not is_site_scoped(user):
        return requested_site_id

    assigned_site_id = ensure_site_assignment(user)
    if requested_site_id is not None and requested_site_id != assigned_site_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for the requested site",
        )
    return assigned_site_id


def ensure_site_access(user, site_id: Optional[int], detail: str = "Not authorized for this site") -> None:
    if site_id is None or not is_site_scoped(user):
        return

    assigned_site_id = ensure_site_assignment(user)
    if site_id != assigned_site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
