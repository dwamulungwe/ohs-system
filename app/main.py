import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.services.organisation_service import ensure_default_organisation
from app.services.role_service import ensure_default_roles
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.services.tenancy import set_tenant_context, unscoped_session


logger = logging.getLogger(__name__)

SUPERADMIN_EMAIL = "admin@ohs.local"
SUPERADMIN_PASSWORD = "Admin123!"
REQUIRED_ROLES = {
    "admin": "System administrator",
    "ohs_manager": "OHS manager",
    "safety_officer": "Safety officer",
    "supervisor": "Supervisor",
    "employee": "Employee",
}


def ensure_superadmin_user() -> None:
    db = SessionLocal()
    try:
        organisation = ensure_default_organisation(db)
        set_tenant_context(db, organisation.id, platform_admin=True)
        ensure_default_roles(db)
        roles = {
            role.name: role
            for role in db.scalars(select(Role).where(Role.name.in_(REQUIRED_ROLES))).all()
        }
        for role_name, description in REQUIRED_ROLES.items():
            if role_name not in roles:
                role = Role(name=role_name, description=description)
                db.add(role)
                roles[role_name] = role

        with unscoped_session(db):
            existing_user = db.scalar(select(User).where(User.email == SUPERADMIN_EMAIL))
        if existing_user is None:
            admin_user = User(
                email=SUPERADMIN_EMAIL,
                full_name="System Administrator",
                hashed_password=get_password_hash(SUPERADMIN_PASSWORD),
                is_active=True,
                is_platform_admin=True,
                organisation_id=organisation.id,
                roles=[roles["admin"]],
            )
            db.add(admin_user)
        else:
            existing_user.is_platform_admin = True
            if existing_user.organisation_id != organisation.id:
                existing_user.organisation_id = organisation.id
            if roles["admin"] not in existing_user.roles:
                existing_user.roles.append(roles["admin"])

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to ensure startup superadmin user exists")
        raise
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.on_event("startup")
    def startup_scheduler() -> None:
        if settings.ENVIRONMENT.lower() == "test":
            return
        ensure_superadmin_user()
        start_scheduler()

    @app.on_event("shutdown")
    def shutdown_scheduler() -> None:
        stop_scheduler()

    return app


app = create_app()
