from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.role import Role
from app.models.site import Site
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserServiceError(Exception):
    pass


class UserSiteNotFoundError(UserServiceError):
    pass


def _ensure_site_exists(db: Session, site_id: Optional[int]) -> None:
    if site_id is not None and db.get(Site, site_id) is None:
        raise UserSiteNotFoundError(f"Site {site_id} was not found")


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == email))


def count_users(db: Session) -> int:
    return len(db.scalars(select(User.id)).all())


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email=email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, user_in: UserCreate, *, default_role_name: Optional[str] = None) -> User:
    roles = []
    if user_in.role_ids:
        roles = list(db.scalars(select(Role).where(Role.id.in_(user_in.role_ids))).all())
    elif default_role_name:
        role = db.scalar(select(Role).where(Role.name == default_role_name))
        if role:
            roles = [role]

    _ensure_site_exists(db, user_in.assigned_site_id)
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        phone_number=user_in.phone_number,
        is_active=user_in.is_active,
        assigned_site_id=user_in.assigned_site_id,
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    role_ids = update_data.pop("role_ids", None)
    password = update_data.pop("password", None)
    if "assigned_site_id" in update_data:
        _ensure_site_exists(db, update_data["assigned_site_id"])

    for field, value in update_data.items():
        setattr(user, field, value)

    if password:
        user.hashed_password = get_password_hash(password)

    if role_ids is not None:
        user.roles = list(db.scalars(select(Role).where(Role.id.in_(role_ids))).all()) if role_ids else []

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
