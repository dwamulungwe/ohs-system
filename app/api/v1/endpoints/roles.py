from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services.crud import create_record, get_record_or_none, list_records, update_record
from app.services.rbac import Permission, ensure_permission

router = APIRouter()


@router.get("", response_model=list[RoleRead])
def list_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Role]:
    ensure_permission(current_user, Permission.ROLES_READ)
    return list_records(db, Role, skip=skip, limit=limit)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Role:
    ensure_permission(current_user, Permission.ROLES_MANAGE)
    return create_record(db, Role, role_in.model_dump())


@router.get("/{role_id}", response_model=RoleRead)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Role:
    ensure_permission(current_user, Permission.ROLES_READ)
    role = get_record_or_none(db, Role, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.patch("/{role_id}", response_model=RoleRead)
def patch_role(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Role:
    ensure_permission(current_user, Permission.ROLES_MANAGE)
    role = get_record_or_none(db, Role, role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return update_record(db, role, role_in.model_dump(exclude_unset=True))
