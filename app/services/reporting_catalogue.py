from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.reporting import KPIDefinition, KPIDirection, OrganisationKPISetting
from app.services.tenancy import current_organisation_id, enabled_feature_keys


CATEGORY_FEATURES = {
    "SIO": "sios",
    "Actions": "corrective_actions",
    "Incidents": "incidents",
    "Risk & Hazards": "hazards",
    "Inspections": "inspections",
    "Audits": "audits",
    "Training": "training",
    "Permits & Compliance": "compliance",
}


def _entry(
    key: str,
    category: str,
    *,
    unit: str = "count",
    direction: KPIDirection = KPIDirection.informational,
    multiplier: float | None = None,
    numerator: str | None = None,
    denominator: str | None = None,
    description: str | None = None,
) -> dict:
    return {
        "key": key,
        "name": key.replace("_", " ").title().replace("Sio", "SIO").replace("Lti", "LTI").replace("Trir", "TRIR").replace("Ltifr", "LTIFR"),
        "description": description or f"Period KPI for {key.replace('_', ' ')}.",
        "category": category,
        "unit": unit,
        "calculation_method": key,
        "numerator_definition": numerator,
        "denominator_definition": denominator,
        "multiplier": multiplier,
        "direction": direction,
    }


KPI_CATALOGUE = [
    # SIO
    *[_entry(key, "SIO", direction=KPIDirection.lower_is_better if key in {"sio_negative", "sio_open", "sio_overdue", "sio_high_urgent"} else KPIDirection.informational) for key in (
        "sio_raised", "sio_positive", "sio_negative", "sio_open", "sio_overdue", "sio_high_urgent",
    )],
    _entry("sio_closure_rate", "SIO", unit="percent", direction=KPIDirection.higher_is_better, numerator="SIOs closed in the period", denominator="SIOs raised in the period"),
    _entry("sio_on_time_closure_rate", "SIO", unit="percent", direction=KPIDirection.higher_is_better, numerator="SIOs closed on or before due date", denominator="SIOs closed with a due date"),
    _entry("sio_average_closure_days", "SIO", unit="days", direction=KPIDirection.lower_is_better),
    # Actions
    *[_entry(key, "Actions", direction=KPIDirection.lower_is_better) for key in (
        "action_open", "action_overdue", "action_due_7_days", "action_due_30_days",
        "action_high_critical_overdue", "action_awaiting_verification", "action_reopened",
        "action_extension_requests",
    )],
    _entry("action_overdue_rate", "Actions", unit="percent", direction=KPIDirection.lower_is_better, numerator="Open actions overdue at period end", denominator="Open actions at period end"),
    _entry("action_original_due_on_time_closure_rate", "Actions", unit="percent", direction=KPIDirection.higher_is_better, numerator="Actions closed on or before their original due date", denominator="Closed actions with an original due date"),
    _entry("action_current_due_on_time_closure_rate", "Actions", unit="percent", direction=KPIDirection.higher_is_better, numerator="Actions closed on or before the approved current due date", denominator="Closed actions with a current due date"),
    _entry("action_average_closure_days", "Actions", unit="days", direction=KPIDirection.lower_is_better),
    _entry("action_median_closure_days", "Actions", unit="days", direction=KPIDirection.lower_is_better),
    _entry("action_verification_rejection_rate", "Actions", unit="percent", direction=KPIDirection.lower_is_better, numerator="Rejected completion verifications", denominator="All completion verification decisions"),
    # Incidents
    *[_entry(key, "Incidents", direction=KPIDirection.lower_is_better) for key in (
        "total_incidents", "near_miss_count", "first_aid_count", "medical_treatment_count",
        "restricted_work_count", "lost_time_injury_count", "occupational_illness_count",
        "fatality_count", "property_damage_count", "environmental_incident_count",
        "high_critical_incidents", "open_investigations", "overdue_investigations",
    )],
    _entry("average_investigation_closure_days", "Incidents", unit="days", direction=KPIDirection.lower_is_better),
    _entry("days_since_last_lti", "Incidents", unit="days", direction=KPIDirection.higher_is_better),
    _entry("trir", "Incidents", unit="rate", direction=KPIDirection.lower_is_better, multiplier=200_000, numerator="Recordable incidents", denominator="Actual employee plus contractor hours worked"),
    _entry("ltifr", "Incidents", unit="rate", direction=KPIDirection.lower_is_better, multiplier=1_000_000, numerator="Lost-time injuries", denominator="Actual employee plus contractor hours worked"),
    # Risk and hazards
    *[_entry(key, "Risk & Hazards", direction=KPIDirection.lower_is_better) for key in (
        "open_hazards", "critical_hazards", "high_risk_hazards", "uncontrolled_hazards",
        "overdue_controls", "hazards_due_review", "new_hazards", "residual_high_risk_hazards",
    )],
    _entry("hazards_closed", "Risk & Hazards", direction=KPIDirection.informational),
    # Inspections
    *[_entry(key, "Inspections", direction=KPIDirection.lower_is_better if key in {"inspections_missed", "critical_inspection_findings", "repeat_inspection_findings"} else KPIDirection.informational) for key in (
        "inspections_planned", "inspections_completed", "inspections_missed", "inspection_findings",
        "critical_inspection_findings", "repeat_inspection_findings",
    )],
    _entry("inspection_completion_rate", "Inspections", unit="percent", direction=KPIDirection.higher_is_better, numerator="Completed inspections", denominator="Planned inspections"),
    # Audits
    *[_entry(key, "Audits", direction=KPIDirection.lower_is_better if key in {"major_findings", "minor_findings", "open_audit_findings", "overdue_audit_findings", "repeat_audit_findings"} else KPIDirection.informational) for key in (
        "audits_planned", "audits_completed", "major_findings", "minor_findings", "open_audit_findings",
        "overdue_audit_findings", "repeat_audit_findings",
    )],
    _entry("audit_completion_rate", "Audits", unit="percent", direction=KPIDirection.higher_is_better, numerator="Completed audits", denominator="Planned audits"),
    # Training
    *[_entry(key, "Training", direction=KPIDirection.lower_is_better if key in {"training_overdue", "training_expiring_30", "training_expiring_60", "training_expiring_90", "competency_gaps"} else KPIDirection.informational) for key in (
        "training_required", "training_completed", "training_overdue", "training_expiring_30",
        "training_expiring_60", "training_expiring_90", "competency_gaps",
    )],
    _entry("training_compliance_rate", "Training", unit="percent", direction=KPIDirection.higher_is_better, numerator="Completed current training assignments", denominator="Required training assignments"),
    # Permits and compliance
    *[_entry(key, "Permits & Compliance", direction=KPIDirection.lower_is_better if key in {"permits_renewal_30", "permits_renewal_60", "permits_renewal_90", "expired_permits", "compliance_due_soon", "compliance_overdue"} else KPIDirection.informational) for key in (
        "active_permits", "permits_renewal_30", "permits_renewal_60", "permits_renewal_90",
        "expired_permits", "permit_renewal_started", "compliance_total", "compliance_compliant",
        "compliance_due_soon", "compliance_overdue",
    )],
    _entry("compliance_rate", "Permits & Compliance", unit="percent", direction=KPIDirection.higher_is_better, numerator="Compliant obligations", denominator="Applicable compliance obligations"),
]


def ensure_platform_kpi_catalogue(db: Session) -> None:
    existing = {
        item.key
        for item in db.scalars(
            select(KPIDefinition).where(
                KPIDefinition.organisation_id.is_(None), KPIDefinition.version == 1
            )
        ).all()
    }
    if len(existing) == len(KPI_CATALOGUE):
        return
    for entry in KPI_CATALOGUE:
        if entry["key"] in existing:
            continue
        db.add(
            KPIDefinition(
                organisation_id=None,
                version=1,
                effective_from=date(2026, 1, 1),
                effective_to=None,
                is_active=True,
                **entry,
            )
        )
    db.commit()


def applicable_kpi_definitions(db: Session, *, as_of: date) -> list[KPIDefinition]:
    organisation_id = current_organisation_id(db)
    ensure_platform_kpi_catalogue(db)
    candidates = list(
        db.scalars(
            select(KPIDefinition)
            .where(
                or_(
                    KPIDefinition.organisation_id.is_(None),
                    KPIDefinition.organisation_id == organisation_id,
                ),
                KPIDefinition.is_active.is_(True),
                KPIDefinition.effective_from <= as_of,
                or_(KPIDefinition.effective_to.is_(None), KPIDefinition.effective_to >= as_of),
            )
            .order_by(KPIDefinition.key, KPIDefinition.version.desc())
        ).all()
    )
    # Tenant definitions override platform definitions, then the latest version wins.
    selected: dict[str, KPIDefinition] = {}
    for definition in candidates:
        current = selected.get(definition.key)
        if current is None:
            selected[definition.key] = definition
            continue
        current_is_tenant = current.organisation_id == organisation_id
        definition_is_tenant = definition.organisation_id == organisation_id
        if definition_is_tenant and not current_is_tenant:
            selected[definition.key] = definition
        elif definition_is_tenant == current_is_tenant and definition.version > current.version:
            selected[definition.key] = definition

    feature_keys = set(enabled_feature_keys(db, organisation_id))
    settings = {
        setting.kpi_key: setting.is_enabled
        for setting in db.scalars(select(OrganisationKPISetting)).all()
    }
    return sorted(
        (
            definition
            for definition in selected.values()
            if settings.get(definition.key, True)
            and (
                CATEGORY_FEATURES.get(definition.category) is None
                or CATEGORY_FEATURES[definition.category] in feature_keys
                or (
                    definition.category == "Permits & Compliance"
                    and bool({"permits", "compliance"}.intersection(feature_keys))
                )
            )
        ),
        key=lambda item: (item.category, item.name),
    )
