from fastapi import APIRouter

from app.api.v1.endpoints import (
    approvals,
    asset_register,
    attachments,
    audit_logs,
    audits,
    behaviour_observations,
    contractors,
    auth,
    corrective_actions,
    dashboard,
    documents,
    emergency_drills,
    exports,
    hazards,
    health,
    incidents,
    incident_investigations,
    inspections,
    jsas,
    job_runs,
    legal_compliance,
    medical_surveillance,
    notifications,
    notification_deliveries,
    permits,
    roles,
    safety_communications,
    safety_kpis,
    sites,
    training,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(attachments.router, prefix="/attachments", tags=["attachments"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(hazards.router, prefix="/hazards", tags=["hazards"])
api_router.include_router(inspections.router, prefix="/inspections", tags=["inspections"])
api_router.include_router(
    corrective_actions.router,
    prefix="/corrective-actions",
    tags=["corrective_actions"],
)
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit_logs"])
api_router.include_router(audits.router, prefix="/audits", tags=["audits"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(emergency_drills.router, prefix="/emergency-drills", tags=["emergency_drills"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    notification_deliveries.router,
    prefix="/notification-deliveries",
    tags=["notification_deliveries"],
)
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(training.router, tags=["training_compliance"])
api_router.include_router(permits.router, prefix="/permits", tags=["permits"])
api_router.include_router(job_runs.router, prefix="/job-runs", tags=["job_runs"])
api_router.include_router(
    medical_surveillance.router,
    prefix="/medical-surveillance",
    tags=["medical_surveillance"],
)
api_router.include_router(
    incident_investigations.router,
    prefix="/incident-investigations",
    tags=["incident_investigations"],
)
api_router.include_router(
    legal_compliance.router,
    prefix="/legal-compliance",
    tags=["legal_compliance"],
)
api_router.include_router(jsas.router, prefix="/jsas", tags=["jsas"])
api_router.include_router(contractors.router, prefix="/contractors", tags=["contractors"])
api_router.include_router(asset_register.router, prefix="/asset-register", tags=["asset_register"])
api_router.include_router(safety_kpis.router, prefix="/safety-kpis", tags=["safety_kpis"])
api_router.include_router(
    safety_communications.router,
    prefix="/safety-communications",
    tags=["safety_communications"],
)
api_router.include_router(
    behaviour_observations.router,
    prefix="/behaviour-observations",
    tags=["behaviour_observations"],
)
