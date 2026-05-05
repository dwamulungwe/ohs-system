from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo_seed import collect_demo_counts, seed_demo_data
from app.models.role import Role
from app.models.site import Site
from app.models.user import User


def _ensure_seed_roles(db_session: Session) -> None:
    existing = {role.name for role in db_session.scalars(select(Role)).all()}
    for name, description in [
        ("ohs_manager", "OHS manager"),
        ("safety_officer", "Safety officer"),
        ("supervisor", "Supervisor"),
        ("employee", "Employee"),
    ]:
        if name not in existing:
            db_session.add(Role(name=name, description=description))
    db_session.commit()


def test_seed_demo_data_is_idempotent_and_preserves_non_demo_records(db_session: Session) -> None:
    _ensure_seed_roles(db_session)

    seed_demo_data(db_session)
    first_counts = collect_demo_counts(db_session)

    seed_demo_data(db_session)
    second_counts = collect_demo_counts(db_session)

    assert first_counts.sites == 3
    assert first_counts.users == 6
    assert first_counts.incidents == 10
    assert first_counts.hazards == 10
    assert first_counts.inspections == 5
    assert first_counts.corrective_actions == 12
    assert first_counts.training_records == 6
    assert first_counts.compliance_acknowledgements == 5
    assert first_counts.permits == 5
    assert first_counts.notifications >= 10

    assert second_counts == first_counts

    assert db_session.scalar(select(User).where(User.email == "admin@example.com")) is not None
    assert db_session.scalar(select(Site).where(Site.code == "MAIN")) is not None
    assert db_session.scalar(select(User).where(User.assigned_site_id.is_not(None))) is not None
