from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.role import user_roles
from app.services.rbac import LEGACY_ROLE_RENAMES, STANDARD_ROLE_DESCRIPTIONS

DEFAULT_ROLE_NAMES = list(STANDARD_ROLE_DESCRIPTIONS)


def ensure_default_roles(db: Session) -> None:
    existing = {
        role.name: role
        for role in db.scalars(select(Role).order_by(Role.id)).all()
    }

    for legacy_name, standard_name in LEGACY_ROLE_RENAMES.items():
        legacy_role = existing.get(legacy_name)
        if legacy_role is None:
            continue

        target_role = existing.get(standard_name)
        if target_role is None:
            legacy_role.name = standard_name
            legacy_role.description = STANDARD_ROLE_DESCRIPTIONS[standard_name]
            existing[standard_name] = legacy_role
            existing.pop(legacy_name, None)
            continue

        user_ids = list(
            db.execute(
                select(user_roles.c.user_id).where(user_roles.c.role_id == legacy_role.id)
            ).scalars()
        )
        existing_pairs = set(
            db.execute(
                select(user_roles.c.user_id, user_roles.c.role_id).where(
                    user_roles.c.role_id == target_role.id
                )
            ).all()
        )
        for user_id in user_ids:
            if (user_id, target_role.id) not in existing_pairs:
                db.execute(
                    insert(user_roles).values(user_id=user_id, role_id=target_role.id)
                )

        db.execute(delete(user_roles).where(user_roles.c.role_id == legacy_role.id))
        db.delete(legacy_role)
        existing.pop(legacy_name, None)

    for role_name, description in STANDARD_ROLE_DESCRIPTIONS.items():
        role = existing.get(role_name)
        if role is None:
            db.add(Role(name=role_name, description=description))
        else:
            role.description = description

    db.commit()
