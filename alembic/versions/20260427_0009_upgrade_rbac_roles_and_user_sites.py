"""upgrade rbac roles and user sites

Revision ID: 20260427_0009
Revises: 20260423_0008
Create Date: 2026-04-27

"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0009"
down_revision = "20260423_0008"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_foreign_key(table_name: str, foreign_key_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(foreign_key["name"] == foreign_key_name for foreign_key in inspector.get_foreign_keys(table_name))


def _execute(statement: str, **params: object) -> None:
    op.get_bind().execute(sa.text(statement), params)


def upgrade() -> None:
    assigned_site_index = op.f("ix_users_assigned_site_id")
    assigned_site_fk = "fk_users_assigned_site_id_sites"
    needs_column = not _has_column("users", "assigned_site_id")
    needs_index = not _has_index("users", assigned_site_index)
    needs_foreign_key = not _has_foreign_key("users", assigned_site_fk)

    if needs_column or needs_index or needs_foreign_key:
        with op.batch_alter_table("users") as batch_op:
            if needs_column:
                batch_op.add_column(sa.Column("assigned_site_id", sa.Integer(), nullable=True))
            if needs_index:
                batch_op.create_index(assigned_site_index, ["assigned_site_id"], unique=False)
            if needs_foreign_key:
                batch_op.create_foreign_key(
                    assigned_site_fk,
                    "sites",
                    ["assigned_site_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    role_updates = [
        ("ohs_manager", "Enterprise OHS manager with operational oversight.", "safety_manager"),
        ("safety_officer", "Operational safety officer.", "auditor"),
        ("employee", "Employee self-service safety role.", "worker"),
    ]

    for target_name, target_description, legacy_name in role_updates:
        _execute(
            """
            UPDATE roles
            SET name = :target_name, description = :target_description
            WHERE name = :legacy_name
              AND NOT EXISTS (SELECT 1 FROM roles WHERE name = :target_name)
            """,
            target_name=target_name,
            target_description=target_description,
            legacy_name=legacy_name,
        )

        _execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT ur.user_id, target.id
            FROM user_roles ur
            JOIN roles legacy ON legacy.id = ur.role_id
            JOIN roles target ON target.name = :target_name
            WHERE legacy.name = :legacy_name
              AND NOT EXISTS (
                SELECT 1
                FROM user_roles existing
                WHERE existing.user_id = ur.user_id
                  AND existing.role_id = target.id
              )
            """,
            target_name=target_name,
            legacy_name=legacy_name,
        )

        _execute(
            """
            DELETE FROM user_roles
            WHERE role_id IN (
                SELECT id FROM roles WHERE name = :legacy_name
            )
            """,
            legacy_name=legacy_name,
        )
        _execute("DELETE FROM roles WHERE name = :legacy_name", legacy_name=legacy_name)

    _execute(
        """
        INSERT INTO roles (name, description, created_at, updated_at)
        VALUES (:name, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (name) DO NOTHING
        """,
        name="safety_officer",
        description="Operational safety officer.",
    )
    _execute(
        """
        UPDATE roles
        SET description = :description
        WHERE name = :name
        """,
        name="admin",
        description="Enterprise administrator with full system access.",
    )
    _execute(
        """
        UPDATE roles
        SET description = :description
        WHERE name = :name
        """,
        name="supervisor",
        description="Site supervisor with assigned-site operational access.",
    )
    _execute(
        """
        UPDATE roles
        SET description = :description
        WHERE name = :name
        """,
        name="ohs_manager",
        description="Enterprise OHS manager with operational oversight.",
    )
    _execute(
        """
        UPDATE roles
        SET description = :description
        WHERE name = :name
        """,
        name="employee",
        description="Employee self-service safety role.",
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE roles SET name = 'safety_manager', description = 'Default safety manager role' WHERE name = 'ohs_manager'")
    )
    op.execute(
        sa.text("UPDATE roles SET name = 'auditor', description = 'Default auditor role' WHERE name = 'safety_officer'")
    )
    op.execute(
        sa.text("UPDATE roles SET name = 'worker', description = 'Default worker role' WHERE name = 'employee'")
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_assigned_site_id_sites", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_users_assigned_site_id"))
        batch_op.drop_column("assigned_site_id")
