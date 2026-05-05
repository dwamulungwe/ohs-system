from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permissions
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogRead
from app.services.crud import list_records
from app.services.rbac import Permission

router = APIRouter()


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions(Permission.AUDIT_LOGS_VIEW)),
) -> list[AuditLog]:
    return list_records(db, AuditLog, skip=skip, limit=limit)
