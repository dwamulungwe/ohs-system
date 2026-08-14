from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    approvals,
    asset_register,
    attachments,
    audit_logs,
    audits,
    behaviour_observations,
    contractors,
    data_imports,
    departments,
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
    organisations,
    permits,
    ppe,
    roles,
    reporting,
    safety_communications,
    safety_kpis,
    sios,
    sites,
    training,
    users,
)
from app.services.tenancy import require_feature

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(attachments.router, prefix="/attachments", tags=["attachments"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(organisations.router, prefix="/organisations", tags=["organisations"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"], dependencies=[Depends(require_feature("incidents"))])
api_router.include_router(hazards.router, prefix="/hazards", tags=["hazards"], dependencies=[Depends(require_feature("hazards"))])
api_router.include_router(sios.router, prefix="/sios", tags=["sios"], dependencies=[Depends(require_feature("sios"))])
api_router.include_router(data_imports.router, prefix="/data-imports", tags=["data_imports"], dependencies=[Depends(require_feature("data_imports"))])
api_router.include_router(inspections.router, prefix="/inspections", tags=["inspections"], dependencies=[Depends(require_feature("inspections"))])
api_router.include_router(
    corrective_actions.router,
    prefix="/corrective-actions",
    tags=["corrective_actions"],
    dependencies=[Depends(require_feature("corrective_actions"))],
)
api_router.include_router(
    reporting.router,
    prefix="/reporting",
    tags=["reporting"],
    dependencies=[Depends(require_feature("reporting"))],
)
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit_logs"])
api_router.include_router(audits.router, prefix="/audits", tags=["audits"], dependencies=[Depends(require_feature("audits"))])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_feature("dashboard"))])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"], dependencies=[Depends(require_feature("document_control"))])
api_router.include_router(emergency_drills.router, prefix="/emergency-drills", tags=["emergency_drills"], dependencies=[Depends(require_feature("emergency_drills"))])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    notification_deliveries.router,
    prefix="/notification-deliveries",
    tags=["notification_deliveries"],
)
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(training.router, tags=["training_compliance"])
api_router.include_router(permits.router, prefix="/permits", tags=["permits"], dependencies=[Depends(require_feature("permits"))])
api_router.include_router(ppe.router, prefix="/ppe", tags=["ppe"], dependencies=[Depends(require_feature("ppe"))])
api_router.include_router(job_runs.router, prefix="/job-runs", tags=["job_runs"])
api_router.include_router(
    medical_surveillance.router,
    prefix="/medical-surveillance",
    tags=["medical_surveillance"],
    dependencies=[Depends(require_feature("medical_surveillance"))],
)
api_router.include_router(
    incident_investigations.router,
    prefix="/incident-investigations",
    tags=["incident_investigations"],
    dependencies=[Depends(require_feature("incident_investigations"))],
)
api_router.include_router(
    legal_compliance.router,
    prefix="/legal-compliance",
    tags=["legal_compliance"],
    dependencies=[Depends(require_feature("compliance"))],
)
api_router.include_router(jsas.router, prefix="/jsas", tags=["jsas"], dependencies=[Depends(require_feature("jsas"))])
api_router.include_router(contractors.router, prefix="/contractors", tags=["contractors"], dependencies=[Depends(require_feature("contractors"))])
api_router.include_router(asset_register.router, prefix="/asset-register", tags=["asset_register"], dependencies=[Depends(require_feature("assets"))])
api_router.include_router(safety_kpis.router, prefix="/safety-kpis", tags=["safety_kpis"], dependencies=[Depends(require_feature("safety_kpis"))])
api_router.include_router(
    safety_communications.router,
    prefix="/safety-communications",
    tags=["safety_communications"],
    dependencies=[Depends(require_feature("safety_communications"))],
)
api_router.include_router(
    behaviour_observations.router,
    prefix="/behaviour-observations",
    tags=["behaviour_observations"],
    dependencies=[Depends(require_feature("behaviour_observations"))],
)
