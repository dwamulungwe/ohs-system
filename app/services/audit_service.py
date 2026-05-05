from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log
