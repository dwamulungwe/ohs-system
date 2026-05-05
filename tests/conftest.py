import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.models.role import Role
from app.models.site import Site
from app.models.user import User
from app.services.rbac import STANDARD_ROLE_DESCRIPTIONS

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
            assigned_site_id=1,
            roles=[roles[0]],
        )
        site = Site(id=1, name="Main Plant", code="MAIN", address="Industrial Area", created_by_id=1)
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
        return db_session.get(User, auth_state["current_user_id"])

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
        assigned_site_id: int | None = None,
        email: str | None = None,
        full_name: str | None = None,
        extra_roles: list[str] | None = None,
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
