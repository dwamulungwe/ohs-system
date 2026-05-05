from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.models.role import Role
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserBootstrap, UserCreate, UserRead
from app.services.audit_service import write_audit_log
from app.services.role_service import ensure_default_roles
from app.services.user_service import authenticate_user, count_users, create_user, get_user_by_email

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    write_audit_log(
        db,
        actor_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/bootstrap-admin", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(user_in: UserBootstrap, db: Session = Depends(get_db)) -> User:
    if count_users(db) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap is only available before any users exist",
        )
    if get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    ensure_default_roles(db)
    admin_role = db.scalar(select(Role).where(Role.name == "admin"))
    role_ids = [admin_role.id] if admin_role else []
    return create_user(
        db,
        UserCreate(
            email=user_in.email,
            full_name=user_in.full_name,
            password=user_in.password,
            is_active=user_in.is_active,
            role_ids=role_ids,
        ),
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
