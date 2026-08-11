from typing import Optional
import os
import sys
from collections.abc import Generator
from datetime import date as RealDate, datetime as RealDateTime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("ENVIRONMENT", "test")

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.db.session import TenantSession
from app.models.role import Role
from app.models.organisation import Organisation, OrganisationFeature, OrganisationSettings
from app.models.site import Site
from app.models.user import User
from app.services.rbac import STANDARD_ROLE_DESCRIPTIONS
from app.services.tenancy import MODULE_KEYS, set_tenant_context, set_user_tenant_context, unscoped_session

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=TenantSession)


class FrozenDateMeta(type):
    def __instancecheck__(cls, value):
        return isinstance(value, RealDate)


class FrozenDateTimeMeta(type):
    def __instancecheck__(cls, value):
        return isinstance(value, RealDateTime)


class FrozenTestDate(RealDate, metaclass=FrozenDateMeta):
    @classmethod
    def today(cls):
        return cls(2026, 4, 23)


class FrozenTestDateTime(RealDateTime, metaclass=FrozenDateTimeMeta):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 4, 23, 12, 0, 0)
        return value.replace(tzinfo=tz) if tz is not None else value

    @classmethod
    def utcnow(cls):
        return cls(2026, 4, 23, 12, 0, 0)


@pytest.fixture(autouse=True)
def stable_test_clock(monkeypatch) -> None:
    """Keep date-sensitive lifecycle tests deterministic as the real calendar advances."""
    for module_name, module in list(sys.modules.items()):
        if module is None or not (module_name.startswith("app.") or module_name.startswith("test_")):
            continue
        namespace = getattr(module, "__dict__", {})
        if namespace.get("date") is RealDate:
            monkeypatch.setattr(module, "date", FrozenTestDate)
        if namespace.get("datetime") is RealDateTime:
            monkeypatch.setattr(module, "datetime", FrozenTestDateTime)


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        organisation = Organisation(
            id=1,
            name="Test Organisation",
            code="TEST",
            slug="test-organisation",
            timezone="Africa/Lusaka",
            is_active=True,
        )
        db.add(organisation)
        db.flush()
        set_tenant_context(db, organisation.id, platform_admin=True)
        db.add(OrganisationSettings(organisation_id=organisation.id))
        db.add_all(
            OrganisationFeature(organisation_id=organisation.id, key=key, is_enabled=True)
            for key in MODULE_KEYS
        )
        roles = [
            Role(id=index, name=name, description=description)
            for index, (name, description) in enumerate(STANDARD_ROLE_DESCRIPTIONS.items(), start=1)
        ]
        user = User(
            id=1,
            email="admin@example.com",
            full_name="Admin User",
            hashed_password="not-used",
            is_active=True,
            is_platform_admin=True,
            organisation_id=organisation.id,
            assigned_site_id=1,
            roles=[roles[0]],
        )
        site = Site(id=1, organisation_id=organisation.id, name="Main Plant", code="MAIN", address="Industrial Area", created_by_id=1)
        db.add_all([*roles, user, site])
        db.commit()
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    auth_state = {"current_user_id": 1}

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_current_user() -> User:
        with unscoped_session(db_session):
            db_session.expire_all()
            user = db_session.scalar(
                select(User)
                .where(User.id == auth_state["current_user_id"])
                .options(selectinload(User.roles), selectinload(User.organisation))
                .execution_options(populate_existing=True)
            )
        set_user_tenant_context(db_session, user)
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        test_client.auth_state = auth_state
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def role_lookup(db_session: Session) -> dict[str, Role]:
    return {role.name: role for role in db_session.query(Role).all()}


@pytest.fixture
def create_user_for_role(db_session: Session, role_lookup: dict[str, Role]):
    next_user_id = {"value": 2}

    def factory(
        role_name: str,
        *,
        assigned_site_id: Optional[int] = None,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        extra_roles: Optional[list[str]] = None,
    ) -> User:
        user_id = next_user_id["value"]
        next_user_id["value"] += 1
        roles = [role_lookup[role_name]]
        for extra_role in extra_roles or []:
            roles.append(role_lookup[extra_role])

        user = User(
            id=user_id,
            email=email or f"{role_name}{user_id}@example.com",
            full_name=full_name or f"{role_name.replace('_', ' ').title()} {user_id}",
            hashed_password="not-used",
            is_active=True,
            assigned_site_id=assigned_site_id,
            roles=roles,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return factory


@pytest.fixture
def act_as(client: TestClient):
    def factory(user: User | int) -> None:
        client.auth_state["current_user_id"] = user.id if isinstance(user, User) else user

    return factory
