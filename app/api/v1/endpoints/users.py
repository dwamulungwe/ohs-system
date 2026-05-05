from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.crud import list_records
from app.services.rbac import Permission, ensure_permission
from app.services.user_service import (
    UserSiteNotFoundError,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
)

router = APIRouter()


@router.get("", response_model=list[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    ensure_permission(current_user, Permission.USERS_READ)
    return list_records(db, User, skip=skip, limit=limit)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    ensure_permission(current_user, Permission.USERS_MANAGE)
    if get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    try:
        return create_user(db, user_in)
    except UserSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned site not found")


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.id != user_id:
        ensure_permission(current_user, Permission.USERS_READ)
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def patch_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    ensure_permission(current_user, Permission.USERS_MANAGE)
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        return update_user(db, user=user, user_in=user_in)
    except UserSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned site not found")
