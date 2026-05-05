from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.db.session import SessionLocal
from app.demo_seed import DEMO_PASSWORD, seed_demo_data


def _looks_local_database(database_url: str) -> bool:
    normalized = database_url.lower()
    if normalized.startswith("sqlite"):
        return True

    parsed = urlparse(database_url)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "db"}


def _validate_local_target() -> None:
    environment = settings.ENVIRONMENT.lower()
    database_url = str(settings.DATABASE_URL)
    if environment == "local" and _looks_local_database(database_url):
        return
    raise RuntimeError(
        "Refusing to seed demo data outside a local database target. "
        "Set ENVIRONMENT=local and point DATABASE_URL to sqlite, localhost, 127.0.0.1, or the local docker db service."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the OHS Management System with realistic demo data.")
    parser.parse_args()

    _validate_local_target()
    with SessionLocal() as db:
        summary = seed_demo_data(db)

    print("Demo data refreshed successfully.")
    print(f"Demo login password: {DEMO_PASSWORD}")
    print(f"Sites: {summary.sites}")
    print(f"Users: {summary.users}")
    print(f"Incidents: {summary.incidents}")
    print(f"Hazards: {summary.hazards}")
    print(f"Inspections: {summary.inspections}")
    print(f"Corrective actions: {summary.corrective_actions}")
    print(f"Training records: {summary.training_records}")
    print(f"Compliance acknowledgements: {summary.compliance_acknowledgements}")
    print(f"Permits: {summary.permits}")
    print(f"Notifications: {summary.notifications}")


if __name__ == "__main__":
    main()
