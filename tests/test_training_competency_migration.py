from __future__ import annotations

import ast
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings


def test_0023_ddl_is_frozen_and_self_contained() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260820_0023_enterprise_training_competency.py"
    )
    source = migration_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    application_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app"):
            application_imports.append(node.module)
        if isinstance(node, ast.Import):
            application_imports.extend(
                alias.name for alias in node.names if alias.name.startswith("app")
            )
    assert application_imports == []
    assert "__table__" not in source

    created_tables = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
        and node.func.attr == "create_table"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert created_tables == {
        "training_courses",
        "competencies",
        "contractor_workers",
        "course_competency_mappings",
        "training_requirements",
        "training_assignments",
        "training_sessions",
        "training_attendance",
        "training_assessments",
        "training_certificates",
        "competency_awards",
        "competency_status_events",
        "work_authorizations",
        "training_requests",
        "training_reminder_deliveries",
        "training_deficiency_links",
    }


def test_0023_preserves_and_backfills_historical_training_rows(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "phase2d-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    config = Config("alembic.ini")

    command.upgrade(config, "20260820_0022")
    engine = create_engine(database_url)
    original = {
        "title": "Legacy Crane Operator",
        "training_type": "equipment_training",
        "due_date": "2026-02-01",
        "completed_at": "2026-02-05 10:30:00",
        "expiry_date": "2027-02-05",
        "status": "completed",
        "certificate_metadata": [{"number": "CRANE-LEGACY-001", "provider": "Legacy Provider"}],
        "notes": "Imported before Phase 2D and must remain unchanged.",
    }
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO organisations
                (id, name, code, slug, timezone, is_active, created_at, updated_at)
            VALUES
                (77, 'Migration Test Org', 'MIG77', 'migration-test-org', 'Africa/Lusaka', 1,
                 '2026-01-01 00:00:00', '2026-01-01 00:00:00')
        """))
        connection.execute(text("""
            INSERT INTO users
                (id, email, full_name, hashed_password, is_active, created_at, updated_at,
                 assigned_site_id, organisation_id, is_platform_admin)
            VALUES
                (770, 'legacy@example.com', 'Legacy Worker', 'not-used', 1,
                 '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, 77, 0)
        """))
        connection.execute(text("""
            INSERT INTO training_records
                (id, title, training_type, site_id, assigned_to_user_id, assigned_by_user_id,
                 due_date, completed_at, expiry_date, status, certificate_metadata, notes,
                 created_at, updated_at, organisation_id)
            VALUES
                (7700, :title, :training_type, NULL, 770, 770, :due_date, :completed_at,
                 :expiry_date, :status, :certificate_metadata, :notes,
                 '2026-02-01 09:00:00', '2026-02-05 10:30:00', 77)
        """), {**original, "certificate_metadata": json.dumps(original["certificate_metadata"])})

    command.upgrade(config, "20260820_0023")
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT title, training_type, due_date, completed_at, expiry_date, status,
                   certificate_metadata, notes, course_id
            FROM training_records WHERE id = 7700
        """)).mappings().one()
        course = connection.execute(text("""
            SELECT name, category, is_system
            FROM training_courses WHERE id = :course_id
        """), {"course_id": row["course_id"]}).mappings().one()
        assignment = connection.execute(text("""
            SELECT assigned_user_id, assigned_by_user_id, due_date, status, source,
                   training_record_id
            FROM training_assignments WHERE training_record_id = 7700
        """)).mappings().one()

    assert row["title"] == original["title"]
    assert row["training_type"] == original["training_type"]
    assert str(row["due_date"]) == original["due_date"]
    assert str(row["completed_at"]).startswith(original["completed_at"])
    assert str(row["expiry_date"]) == original["expiry_date"]
    assert row["status"] == original["status"]
    assert json.loads(row["certificate_metadata"]) == original["certificate_metadata"]
    assert row["notes"] == original["notes"]
    assert course == {"name": original["title"], "category": "historical", "is_system": 0}
    assert assignment == {
        "assigned_user_id": 770,
        "assigned_by_user_id": 770,
        "due_date": original["due_date"],
        "status": "completed",
        "source": "historical_backfill",
        "training_record_id": 7700,
    }

    command.downgrade(config, "20260820_0022")
    command.upgrade(config, "20260820_0023")
    with engine.connect() as connection:
        preserved = connection.execute(text("""
            SELECT title, certificate_metadata, notes, course_id
            FROM training_records WHERE id = 7700
        """)).mappings().one()
        assignment_count = connection.scalar(text("""
            SELECT COUNT(*) FROM training_assignments WHERE training_record_id = 7700
        """))
    assert preserved["title"] == original["title"]
    assert json.loads(preserved["certificate_metadata"]) == original["certificate_metadata"]
    assert preserved["notes"] == original["notes"]
    assert preserved["course_id"] is not None
    assert assignment_count == 1
