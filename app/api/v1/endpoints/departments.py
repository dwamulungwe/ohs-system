from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.rbac import Permission, ensure_permission

router = APIRouter()


def _get_department(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


def _validate_references(
    db: Session,
    *,
    parent_department_id: int | None,
    manager_user_id: int | None,
    department_id: int | None = None,
) -> None:
    if parent_department_id is not None:
        if parent_department_id == department_id:
            raise HTTPException(status_code=422, detail="A department cannot be its own parent")
        _get_department(db, parent_department_id)
    if manager_user_id is not None and db.get(User, manager_user_id) is None:
        raise HTTPException(status_code=404, detail="Department manager not found")


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    active_only: bool = False,
    parent_department_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DEPARTMENTS_READ)
    statement = select(Department)
    if active_only:
        statement = statement.where(Department.is_active.is_(True))
    if parent_department_id is not None:
        statement = statement.where(Department.parent_department_id == parent_department_id)
    return list(db.scalars(statement.order_by(Department.name)).all())


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    department_in: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DEPARTMENTS_MANAGE)
    _validate_references(
        db,
        parent_department_id=department_in.parent_department_id,
        manager_user_id=department_in.manager_user_id,
    )
    department = Department(**department_in.model_dump())
    db.add(department)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department name or code already exists")
    db.refresh(department)
    return department


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DEPARTMENTS_READ)
    return _get_department(db, department_id)


@router.patch("/{department_id}", response_model=DepartmentRead)
def patch_department(
    department_id: int,
    department_in: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.DEPARTMENTS_MANAGE)
    department = _get_department(db, department_id)
    data = department_in.model_dump(exclude_unset=True)
    _validate_references(
        db,
        parent_department_id=data.get("parent_department_id", department.parent_department_id),
        manager_user_id=data.get("manager_user_id", department.manager_user_id),
        department_id=department.id,
    )
    for field, value in data.items():
        setattr(department, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department name or code already exists")
    db.refresh(department)
    return department
