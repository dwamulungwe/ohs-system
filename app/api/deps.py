from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services.rbac import ensure_permission, get_normalized_role_names, normalize_role_name
from app.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_roles(*role_names: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_roles = get_normalized_role_names(current_user)
        required_roles = {normalize_role_name(role_name) for role_name in role_names}
        if not user_roles.intersection(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def require_permissions(*permissions: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        for permission in permissions:
            ensure_permission(current_user, permission)
        return current_user

    return dependency
