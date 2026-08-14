from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.corrective_action import CorrectiveAction
from app.models.department import Department
from app.models.organisation import OrganisationSettings
from app.models.reporting import (
    KPIDefinition,
    KPIDirection,
    KPISnapshot,
    KPISnapshotStatus,
    KPITarget,
    ManagementActionPlanItem,
    OrganisationKPISetting,
    ReportSection,
    ReportingPeriod,
    ReportingPeriodHistory,
    ReportingPeriodStatus,
    WorkforceExposure,
)
from app.models.site import Site
from app.models.user import User
from app.models.ppe import PPEInventory, PPEIssue, PPERequest, PPERequestStatus, PPEStockLocation
from app.schemas.reporting import (
    KPIDefinitionCreate,
    KPITargetCreate,
    ManagementActionPlanCreate,
    ReportingPeriodCreate,
    WorkforceExposureCreate,
    WorkforceExposureUpdate,
)
from app.services.audit_service import write_audit_log
from app.services.query_utils import paginate
from app.services.reporting_calculations import CalculationContext, calculate_kpi
from app.services.reporting_catalogue import applicable_kpi_definitions, ensure_platform_kpi_catalogue
from app.services.tenancy import current_organisation_id, enabled_feature_keys


class ReportingServiceError(Exception):
    pass


class ReportingNotFoundError(ReportingServiceError):
    pass


class ReportingConflictError(ReportingServiceError):
    pass


class ReportingTransitionError(ReportingServiceError):
    pass


class ReportingLockedError(ReportingServiceError):
    pass


SECTION_DEFINITIONS = (
    ("executive_summary", "Executive Summary", None),
    ("kpi_scorecard", "KPI Scorecard", None),
    ("sio", "SIO Performance", "sios"),
    ("incidents", "Incident Performance", "incidents"),
    ("actions", "Action Performance", "corrective_actions"),
    ("risk_hazards", "Risk & Hazards", "hazards"),
    ("inspections_audits", "Inspections & Audits", ("inspections", "audits")),
    ("training", "Training & Competency", "training"),
    ("compliance_permits", "Compliance & Permits", ("compliance", "permits")),
    ("ppe", "PPE Management", "ppe"),
    ("occupational_health", "Occupational Health", "medical_surveillance"),
    ("environmental", "Environmental", None),
    ("forward_view", "90-Day Forward View", None),
    ("management_action_plan", "Management Action Plan", None),
    ("approvals", "Approvals", None),
    ("exports", "Exports", None),
)

EXECUTIVE_SUMMARY_FIELDS = (
    "overall_performance",
    "major_events",
    "key_improvements",
    "critical_concerns",
    "management_attention",
    "priorities_next_period",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    *,
    actor_id: Optional[int],
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    details: Optional[dict] = None,
) -> None:
    write_audit_log(
        db,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )


def _history(
    db: Session,
    period: ReportingPeriod,
    *,
    actor_id: Optional[int],
    event_type: str,
    from_status: Optional[ReportingPeriodStatus] = None,
    to_status: Optional[ReportingPeriodStatus] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ReportingPeriodHistory:
    history = ReportingPeriodHistory(
        reporting_period_id=period.id,
        actor_user_id=actor_id,
        event_type=event_type,
        from_status=from_status.value if from_status else None,
        to_status=to_status.value if to_status else None,
        reason=reason,
        event_metadata=metadata or {},
    )
    db.add(history)
    return history


def get_reporting_period(db: Session, period_id: int) -> ReportingPeriod:
    period = db.get(ReportingPeriod, period_id)
    if period is None:
        raise ReportingNotFoundError("Reporting period was not found")
    return period


def list_reporting_periods(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[ReportingPeriodStatus] = None,
) -> dict:
    statement = select(ReportingPeriod)
    if status is not None:
        statement = statement.where(ReportingPeriod.status == status)
    statement = statement.order_by(ReportingPeriod.end_date.desc(), ReportingPeriod.report_version.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def _section_is_enabled(feature_keys: set[str], required) -> bool:
    if required is None:
        return True
    if isinstance(required, tuple):
        return bool(feature_keys.intersection(required))
    return required in feature_keys


def _create_default_sections(db: Session, period: ReportingPeriod) -> None:
    features = set(enabled_feature_keys(db, period.organisation_id))
    for order, (key, title, required_feature) in enumerate(SECTION_DEFINITIONS, start=1):
        content = {field: "" for field in EXECUTIVE_SUMMARY_FIELDS} if key == "executive_summary" else {}
        db.add(
            ReportSection(
                reporting_period_id=period.id,
                section_key=key,
                title=title,
                display_order=order,
                is_enabled=_section_is_enabled(features, required_feature),
                content=content,
            )
        )


def create_reporting_period(
    db: Session,
    period_in: ReportingPeriodCreate,
    *,
    actor_id: int,
) -> ReportingPeriod:
    duplicate = db.scalar(
        select(ReportingPeriod).where(
            ReportingPeriod.name == period_in.name,
            ReportingPeriod.period_type == period_in.period_type,
            ReportingPeriod.start_date == period_in.start_date,
            ReportingPeriod.end_date == period_in.end_date,
            ReportingPeriod.report_version == 1,
        )
    )
    if duplicate is not None:
        raise ReportingConflictError("A reporting period with the same name, type, and dates already exists")
    period = ReportingPeriod(
        **period_in.model_dump(),
        status=ReportingPeriodStatus.draft,
        prepared_by_user_id=actor_id,
        report_version=1,
    )
    db.add(period)
    db.flush()
    _create_default_sections(db, period)
    _history(
        db,
        period,
        actor_id=actor_id,
        event_type="created",
        to_status=ReportingPeriodStatus.draft,
    )
    db.commit()
    db.refresh(period)
    _audit(
        db,
        actor_id=actor_id,
        action="reporting_period.create",
        resource_type="reporting_period",
        resource_id=period.id,
        details={"name": period.name, "period_type": period.period_type.value},
    )
    return period


def _ensure_editable(period: ReportingPeriod) -> None:
    if period.status not in {ReportingPeriodStatus.draft, ReportingPeriodStatus.reopened}:
        raise ReportingLockedError("Report content can only be edited while draft or reopened")


def list_report_sections(db: Session, period: ReportingPeriod) -> list[ReportSection]:
    return list(
        db.scalars(
            select(ReportSection)
            .where(ReportSection.reporting_period_id == period.id)
            .order_by(ReportSection.display_order)
        ).all()
    )


def update_report_section(
    db: Session,
    period: ReportingPeriod,
    section_key: str,
    *,
    content: dict,
    actor_id: int,
) -> ReportSection:
    _ensure_editable(period)
    section = db.scalar(
        select(ReportSection).where(
            ReportSection.reporting_period_id == period.id,
            ReportSection.section_key == section_key,
        )
    )
    if section is None:
        raise ReportingNotFoundError("Report section was not found")
    if section_key == "executive_summary":
        unknown = set(content).difference(EXECUTIVE_SUMMARY_FIELDS)
        if unknown:
            raise ReportingConflictError(f"Unknown executive summary fields: {', '.join(sorted(unknown))}")
        section.content = {field: str(content.get(field, "")) for field in EXECUTIVE_SUMMARY_FIELDS}
    else:
        section.content = content
    section.updated_by_user_id = actor_id
    _history(db, period, actor_id=actor_id, event_type="commentary_edited", metadata={"section_key": section_key})
    db.commit()
    db.refresh(section)
    _audit(
        db,
        actor_id=actor_id,
        action="report.section.update",
        resource_type="report_section",
        resource_id=section.id,
        details={"reporting_period_id": period.id, "section_key": section_key},
    )
    return section


def add_management_action(
    db: Session,
    period: ReportingPeriod,
    item_in: ManagementActionPlanCreate,
    *,
    actor_id: int,
) -> ManagementActionPlanItem:
    _ensure_editable(period)
    action = db.get(CorrectiveAction, item_in.linked_action_id)
    if action is None:
        raise ReportingNotFoundError("Linked action was not found")
    existing = db.scalar(
        select(ManagementActionPlanItem).where(
            ManagementActionPlanItem.reporting_period_id == period.id,
            ManagementActionPlanItem.linked_action_id == action.id,
        )
    )
    if existing:
        raise ReportingConflictError("The action is already in this management action plan")
    item = ManagementActionPlanItem(reporting_period_id=period.id, **item_in.model_dump())
    db.add(item)
    _history(db, period, actor_id=actor_id, event_type="management_action_added", metadata={"linked_action_id": action.id})
    db.commit()
    db.refresh(item)
    return item


def list_kpi_definitions(
    db: Session,
    *,
    include_inactive: bool = False,
    key: Optional[str] = None,
) -> list[KPIDefinition]:
    ensure_platform_kpi_catalogue(db)
    organisation_id = current_organisation_id(db)
    statement = select(KPIDefinition).where(
        or_(KPIDefinition.organisation_id.is_(None), KPIDefinition.organisation_id == organisation_id)
    )
    if not include_inactive:
        statement = statement.where(KPIDefinition.is_active.is_(True))
    if key:
        statement = statement.where(KPIDefinition.key == key)
    return list(db.scalars(statement.order_by(KPIDefinition.category, KPIDefinition.key, KPIDefinition.version.desc())).all())


def get_kpi_definition(db: Session, definition_id: int) -> KPIDefinition:
    definition = db.get(KPIDefinition, definition_id)
    organisation_id = current_organisation_id(db)
    if definition is None or definition.organisation_id not in {None, organisation_id}:
        raise ReportingNotFoundError("KPI definition was not found")
    return definition


def create_kpi_definition_version(
    db: Session,
    definition_in: KPIDefinitionCreate,
    *,
    actor_id: int,
) -> KPIDefinition:
    organisation_id = current_organisation_id(db)
    previous = db.scalar(
        select(KPIDefinition)
        .where(
            KPIDefinition.organisation_id == organisation_id,
            KPIDefinition.key == definition_in.key,
        )
        .order_by(KPIDefinition.version.desc())
    )
    version = 1 if previous is None else previous.version + 1
    if previous is not None and definition_in.effective_from <= previous.effective_from:
        raise ReportingConflictError("A new KPI version must take effect after the previous version")
    if previous is not None and previous.effective_to is None:
        previous.effective_to = definition_in.effective_from - timedelta(days=1)
    definition = KPIDefinition(
        organisation_id=organisation_id,
        version=version,
        effective_to=None,
        **definition_in.model_dump(),
    )
    db.add(definition)
    db.commit()
    db.refresh(definition)
    _audit(
        db,
        actor_id=actor_id,
        action="kpi_definition.version.create",
        resource_type="kpi_definition",
        resource_id=definition.id,
        details={"key": definition.key, "version": definition.version},
    )
    return definition


def set_kpi_enablement(db: Session, *, kpi_key: str, is_enabled: bool, actor_id: int) -> OrganisationKPISetting:
    if not list_kpi_definitions(db, include_inactive=True, key=kpi_key):
        raise ReportingNotFoundError("KPI definition was not found")
    setting = db.scalar(select(OrganisationKPISetting).where(OrganisationKPISetting.kpi_key == kpi_key))
    if setting is None:
        setting = OrganisationKPISetting(kpi_key=kpi_key, is_enabled=is_enabled)
        db.add(setting)
    else:
        setting.is_enabled = is_enabled
    db.commit()
    db.refresh(setting)
    _audit(db, actor_id=actor_id, action="kpi.enablement.update", resource_type="kpi_setting", resource_id=setting.id, details={"kpi_key": kpi_key, "is_enabled": is_enabled})
    return setting


def _scope_clause(model, *, site_id: Optional[int], department_id: Optional[int]):
    return and_(
        model.site_id.is_(None) if site_id is None else model.site_id == site_id,
        model.department_id.is_(None) if department_id is None else model.department_id == department_id,
    )


def create_kpi_target(
    db: Session,
    target_in: KPITargetCreate,
    *,
    actor_id: int,
) -> KPITarget:
    definition = get_kpi_definition(db, target_in.kpi_definition_id)
    if target_in.site_id is not None and db.get(Site, target_in.site_id) is None:
        raise ReportingNotFoundError("Site was not found")
    if target_in.department_id is not None and db.get(Department, target_in.department_id) is None:
        raise ReportingNotFoundError("Department was not found")
    previous = db.scalar(
        select(KPITarget)
        .where(
            KPITarget.kpi_key == definition.key,
            _scope_clause(KPITarget, site_id=target_in.site_id, department_id=target_in.department_id),
        )
        .order_by(KPITarget.version.desc())
    )
    version = 1 if previous is None else previous.version + 1
    if previous and target_in.effective_from <= previous.effective_from:
        raise ReportingConflictError("A new target version must take effect after the previous version")
    if previous and previous.effective_to is None:
        previous.effective_to = target_in.effective_from - timedelta(days=1)
    target = KPITarget(
        kpi_definition_id=definition.id,
        kpi_key=definition.key,
        version=version,
        created_by_user_id=actor_id,
        **target_in.model_dump(exclude={"kpi_definition_id"}),
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    _audit(
        db,
        actor_id=actor_id,
        action="kpi_target.version.create",
        resource_type="kpi_target",
        resource_id=target.id,
        details={"kpi_key": target.kpi_key, "version": target.version},
    )
    return target


def list_kpi_targets(
    db: Session,
    *,
    kpi_key: Optional[str] = None,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> list[KPITarget]:
    statement = select(KPITarget)
    if kpi_key:
        statement = statement.where(KPITarget.kpi_key == kpi_key)
    if site_id is not None:
        statement = statement.where(KPITarget.site_id == site_id)
    if department_id is not None:
        statement = statement.where(KPITarget.department_id == department_id)
    return list(db.scalars(statement.order_by(KPITarget.kpi_key, KPITarget.effective_from.desc())).all())


def _effective_target(
    db: Session,
    definition: KPIDefinition,
    *,
    as_of: date,
    site_id: Optional[int],
    department_id: Optional[int],
) -> Optional[KPITarget]:
    candidates = list(
        db.scalars(
            select(KPITarget).where(
                KPITarget.kpi_key == definition.key,
                KPITarget.effective_from <= as_of,
                or_(KPITarget.effective_to.is_(None), KPITarget.effective_to >= as_of),
            )
        ).all()
    )
    def precedence(item: KPITarget) -> tuple[int, date, int]:
        if department_id is not None and item.department_id == department_id and item.site_id is None:
            scope_rank = 3
        elif site_id is not None and item.site_id == site_id and item.department_id is None:
            scope_rank = 2
        elif item.site_id is None and item.department_id is None:
            scope_rank = 1
        else:
            scope_rank = 0
        return scope_rank, item.effective_from, item.version
    applicable = [item for item in candidates if precedence(item)[0] > 0]
    return max(applicable, key=precedence) if applicable else None


def create_workforce_exposure(
    db: Session,
    exposure_in: WorkforceExposureCreate,
    *,
    actor_id: int,
) -> WorkforceExposure:
    if exposure_in.site_id is not None and db.get(Site, exposure_in.site_id) is None:
        raise ReportingNotFoundError("Site was not found")
    if exposure_in.department_id is not None and db.get(Department, exposure_in.department_id) is None:
        raise ReportingNotFoundError("Department was not found")
    duplicate = db.scalar(
        select(WorkforceExposure).where(
            _scope_clause(WorkforceExposure, site_id=exposure_in.site_id, department_id=exposure_in.department_id),
            WorkforceExposure.period_start == exposure_in.period_start,
            WorkforceExposure.period_end == exposure_in.period_end,
        )
    )
    if duplicate:
        raise ReportingConflictError("Workforce exposure already exists for this scope and period")
    exposure = WorkforceExposure(**exposure_in.model_dump(), created_by_user_id=actor_id)
    db.add(exposure)
    db.commit()
    db.refresh(exposure)
    _audit(db, actor_id=actor_id, action="workforce_exposure.create", resource_type="workforce_exposure", resource_id=exposure.id)
    return exposure


def list_workforce_exposures(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> dict:
    statement = select(WorkforceExposure)
    if site_id is not None:
        statement = statement.where(WorkforceExposure.site_id == site_id)
    if department_id is not None:
        statement = statement.where(WorkforceExposure.department_id == department_id)
    statement = statement.order_by(WorkforceExposure.period_end.desc(), WorkforceExposure.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def update_workforce_exposure(
    db: Session,
    exposure_id: int,
    exposure_in: WorkforceExposureUpdate,
    *,
    actor_id: int,
) -> WorkforceExposure:
    exposure = db.get(WorkforceExposure, exposure_id)
    if exposure is None:
        raise ReportingNotFoundError("Workforce exposure was not found")
    for field, value in exposure_in.model_dump(exclude_unset=True).items():
        setattr(exposure, field, value)
    db.commit()
    db.refresh(exposure)
    _audit(db, actor_id=actor_id, action="workforce_exposure.update", resource_type="workforce_exposure", resource_id=exposure.id)
    return exposure


def _snapshot_status(
    definition: KPIDefinition,
    value: Optional[float],
    target: Optional[KPITarget],
) -> KPISnapshotStatus:
    if value is None:
        return KPISnapshotStatus.insufficient_data
    if definition.direction == KPIDirection.informational or target is None:
        return KPISnapshotStatus.informational
    if definition.direction == KPIDirection.higher_is_better:
        if value >= target.target_value:
            return KPISnapshotStatus.good
        if target.critical_threshold is not None and value < target.critical_threshold:
            return KPISnapshotStatus.critical
        return KPISnapshotStatus.warning
    if definition.direction == KPIDirection.lower_is_better:
        if value <= target.target_value:
            return KPISnapshotStatus.good
        if target.critical_threshold is not None and value > target.critical_threshold:
            return KPISnapshotStatus.critical
        return KPISnapshotStatus.warning
    lower = target.warning_threshold
    upper = target.critical_threshold
    if lower is not None and upper is not None and lower <= value <= upper:
        return KPISnapshotStatus.good
    return KPISnapshotStatus.warning


def _previous_period(db: Session, period: ReportingPeriod) -> Optional[ReportingPeriod]:
    return db.scalar(
        select(ReportingPeriod)
        .where(
            ReportingPeriod.id != period.id,
            ReportingPeriod.period_type == period.period_type,
            ReportingPeriod.end_date < period.start_date,
            ReportingPeriod.status.in_([ReportingPeriodStatus.approved, ReportingPeriodStatus.locked]),
        )
        .order_by(ReportingPeriod.end_date.desc(), ReportingPeriod.report_version.desc())
    )


def _prior_year_period(db: Session, period: ReportingPeriod) -> Optional[ReportingPeriod]:
    try:
        prior_start = period.start_date.replace(year=period.start_date.year - 1)
        prior_end = period.end_date.replace(year=period.end_date.year - 1)
    except ValueError:
        prior_start = period.start_date - timedelta(days=365)
        prior_end = period.end_date - timedelta(days=365)
    return db.scalar(
        select(ReportingPeriod)
        .where(
            ReportingPeriod.start_date == prior_start,
            ReportingPeriod.end_date == prior_end,
            ReportingPeriod.status.in_([ReportingPeriodStatus.approved, ReportingPeriodStatus.locked]),
        )
        .order_by(ReportingPeriod.report_version.desc())
    )


def _snapshot_value(
    db: Session,
    period_id: Optional[int],
    *,
    key: str,
    site_id: Optional[int],
    department_id: Optional[int],
) -> Optional[float]:
    if period_id is None:
        return None
    snapshot = db.scalar(
        select(KPISnapshot).where(
            KPISnapshot.reporting_period_id == period_id,
            KPISnapshot.kpi_key == key,
            _scope_clause(KPISnapshot, site_id=site_id, department_id=department_id),
        )
    )
    return snapshot.value if snapshot else None


def _reporting_scopes(db: Session) -> list[tuple[Optional[int], Optional[int]]]:
    scopes: list[tuple[Optional[int], Optional[int]]] = [(None, None)]
    scopes.extend((site_id, None) for site_id in db.scalars(select(Site.id)).all())
    scopes.extend((None, department_id) for department_id in db.scalars(select(Department.id).where(Department.is_active.is_(True))).all())
    return scopes


def generate_kpi_snapshots(
    db: Session,
    period: ReportingPeriod,
    *,
    actor_id: int,
) -> dict:
    if period.status == ReportingPeriodStatus.locked:
        raise ReportingLockedError("Locked reporting period snapshots cannot be regenerated")
    definitions = applicable_kpi_definitions(db, as_of=period.end_date)
    if not definitions:
        raise ReportingConflictError("No active KPI definitions are enabled for this organisation")
    db.query(KPISnapshot).filter(KPISnapshot.reporting_period_id == period.id).delete(synchronize_session=False)
    scopes = _reporting_scopes(db)
    generated_at = _now()
    previous = _previous_period(db, period)
    prior_year = _prior_year_period(db, period)
    for site_id, department_id in scopes:
        context = CalculationContext(db, period, site_id=site_id, department_id=department_id)
        ytd_period = SimpleNamespace(
            start_date=date(period.end_date.year, 1, 1),
            end_date=period.end_date,
        )
        ytd_context = CalculationContext(db, ytd_period, site_id=site_id, department_id=department_id)
        for definition in definitions:
            result = calculate_kpi(context, definition)
            ytd_result = calculate_kpi(ytd_context, definition)
            target = _effective_target(
                db,
                definition,
                as_of=period.end_date,
                site_id=site_id,
                department_id=department_id,
            )
            metadata = dict(result.metadata or {})
            scope_query = []
            if site_id is not None:
                scope_query.append(f"site_id={site_id}")
            if department_id is not None:
                scope_query.append(f"department_id={department_id}")
            query_string = f"?{'&'.join(scope_query)}" if scope_query else ""
            metadata["drilldown_path"] = f"/reporting/periods/{period.id}/kpis/{definition.key}/drilldown{query_string}"
            metadata["comparison"] = {
                "previous_period_id": previous.id if previous else None,
                "previous_period_value": _snapshot_value(
                    db,
                    previous.id if previous else None,
                    key=definition.key,
                    site_id=site_id,
                    department_id=department_id,
                ),
                "same_period_prior_year_id": prior_year.id if prior_year else None,
                "same_period_prior_year_value": _snapshot_value(
                    db,
                    prior_year.id if prior_year else None,
                    key=definition.key,
                    site_id=site_id,
                    department_id=department_id,
                ),
                "ytd_value": ytd_result.value,
            }
            if target:
                metadata["target"] = {
                    "target_id": target.id,
                    "target_version": target.version,
                    "warning_threshold": target.warning_threshold,
                    "critical_threshold": target.critical_threshold,
                    "effective_from": target.effective_from.isoformat(),
                    "effective_to": target.effective_to.isoformat() if target.effective_to else None,
                }
            db.add(
                KPISnapshot(
                    reporting_period_id=period.id,
                    kpi_definition_id=definition.id,
                    site_id=site_id,
                    department_id=department_id,
                    kpi_key=definition.key,
                    kpi_name=definition.name,
                    kpi_version=definition.version,
                    unit=definition.unit,
                    value=result.value,
                    numerator=result.numerator,
                    denominator=result.denominator,
                    target_value=target.target_value if target else None,
                    status=_snapshot_status(definition, result.value, target),
                    calculation_metadata=metadata,
                    generated_at=generated_at,
                )
            )
    _history(
        db,
        period,
        actor_id=actor_id,
        event_type="snapshots_generated",
        metadata={"kpi_count": len(definitions), "scope_count": len(scopes)},
    )
    db.commit()
    snapshot_count = len(definitions) * len(scopes)
    _audit(
        db,
        actor_id=actor_id,
        action="report.snapshots.generate",
        resource_type="reporting_period",
        resource_id=period.id,
        details={"snapshot_count": snapshot_count, "scope_count": len(scopes)},
    )
    return {
        "reporting_period_id": period.id,
        "generated_at": generated_at,
        "snapshot_count": snapshot_count,
        "scopes": len(scopes),
    }


def list_snapshots(
    db: Session,
    period: ReportingPeriod,
    *,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> list[KPISnapshot]:
    return list(
        db.scalars(
            select(KPISnapshot)
            .where(
                KPISnapshot.reporting_period_id == period.id,
                _scope_clause(KPISnapshot, site_id=site_id, department_id=department_id),
            )
            .order_by(KPISnapshot.kpi_name)
        ).all()
    )


def _ensure_snapshots(db: Session, period: ReportingPeriod, actor_id: int) -> None:
    if db.scalar(select(func.count(KPISnapshot.id)).where(KPISnapshot.reporting_period_id == period.id)) == 0:
        generate_kpi_snapshots(db, period, actor_id=actor_id)


def submit_reporting_period(db: Session, period: ReportingPeriod, *, actor_id: int) -> ReportingPeriod:
    if period.status not in {ReportingPeriodStatus.draft, ReportingPeriodStatus.reopened}:
        raise ReportingTransitionError("Only a draft or reopened report can be submitted")
    _ensure_snapshots(db, period, actor_id)
    previous = period.status
    period.status = ReportingPeriodStatus.under_review
    period.submitted_at = _now()
    _history(db, period, actor_id=actor_id, event_type="submitted", from_status=previous, to_status=period.status)
    db.commit()
    db.refresh(period)
    _audit(db, actor_id=actor_id, action="report.submit", resource_type="reporting_period", resource_id=period.id)
    return period


def review_reporting_period(db: Session, period: ReportingPeriod, *, actor_id: int) -> ReportingPeriod:
    if period.status != ReportingPeriodStatus.under_review:
        raise ReportingTransitionError("Only a report under review can be reviewed")
    period.reviewed_by_user_id = actor_id
    period.reviewed_at = _now()
    _history(db, period, actor_id=actor_id, event_type="reviewed", from_status=period.status, to_status=period.status)
    db.commit()
    db.refresh(period)
    _audit(db, actor_id=actor_id, action="report.review", resource_type="reporting_period", resource_id=period.id)
    return period


def approve_reporting_period(db: Session, period: ReportingPeriod, *, actor_id: int) -> ReportingPeriod:
    if period.status != ReportingPeriodStatus.under_review:
        raise ReportingTransitionError("Only a report under review can be approved")
    previous = period.status
    period.status = ReportingPeriodStatus.approved
    period.approved_by_user_id = actor_id
    period.approved_at = _now()
    _history(db, period, actor_id=actor_id, event_type="approved", from_status=previous, to_status=period.status)
    db.commit()
    db.refresh(period)
    _audit(db, actor_id=actor_id, action="report.approve", resource_type="reporting_period", resource_id=period.id)
    return period


def _report_reference(db: Session, period: ReportingPeriod) -> str:
    settings = db.scalar(select(OrganisationSettings))
    prefix = "HSE-MR"
    if settings:
        prefix = str(
            (settings.reporting_configuration or {}).get("report_prefix")
            or (settings.numbering_prefixes or {}).get("management_report")
            or prefix
        )
    prefix = "".join(character for character in prefix.upper() if character.isalnum() or character == "-").strip("-") or "HSE-MR"
    label = period.end_date.strftime("%Y-%m") if period.period_type.value == "monthly" else period.end_date.isoformat()
    return f"{prefix}-{label}-V{period.report_version}"


def lock_reporting_period(db: Session, period: ReportingPeriod, *, actor_id: int) -> ReportingPeriod:
    if period.status != ReportingPeriodStatus.approved:
        raise ReportingTransitionError("Only an approved report can be locked")
    _ensure_snapshots(db, period, actor_id)
    previous = period.status
    period.status = ReportingPeriodStatus.locked
    period.locked_at = _now()
    period.report_reference = period.report_reference or _report_reference(db, period)
    _history(
        db,
        period,
        actor_id=actor_id,
        event_type="locked",
        from_status=previous,
        to_status=period.status,
        metadata={"report_reference": period.report_reference, "report_version": period.report_version},
    )
    db.commit()
    db.refresh(period)
    _audit(db, actor_id=actor_id, action="report.lock", resource_type="reporting_period", resource_id=period.id, details={"report_reference": period.report_reference})
    return period


def reopen_reporting_period(
    db: Session,
    period: ReportingPeriod,
    *,
    actor_id: int,
    reason: str,
) -> ReportingPeriod:
    reason = reason.strip()
    if not reason:
        raise ReportingTransitionError("A reopening reason is required")
    if period.status not in {ReportingPeriodStatus.approved, ReportingPeriodStatus.locked}:
        raise ReportingTransitionError("Only an approved or locked report can be reopened")
    if period.status == ReportingPeriodStatus.approved:
        previous = period.status
        period.status = ReportingPeriodStatus.reopened
        period.reopened_at = _now()
        period.reopened_by_user_id = actor_id
        period.reopen_reason = reason
        _history(db, period, actor_id=actor_id, event_type="reopened", from_status=previous, to_status=period.status, reason=reason)
        db.commit()
        db.refresh(period)
        _audit(db, actor_id=actor_id, action="report.reopen", resource_type="reporting_period", resource_id=period.id, details={"reason": reason})
        return period

    latest_version = db.scalar(
        select(func.max(ReportingPeriod.report_version)).where(
            ReportingPeriod.name == period.name,
            ReportingPeriod.period_type == period.period_type,
        )
    ) or period.report_version
    restatement = ReportingPeriod(
        name=period.name,
        period_type=period.period_type,
        start_date=period.start_date,
        end_date=period.end_date,
        status=ReportingPeriodStatus.reopened,
        prepared_by_user_id=actor_id,
        reopened_at=_now(),
        reopened_by_user_id=actor_id,
        reopen_reason=reason,
        restatement_reason=reason,
        report_version=latest_version + 1,
        supersedes_period_id=period.id,
    )
    db.add(restatement)
    db.flush()
    for section in list_report_sections(db, period):
        db.add(
            ReportSection(
                reporting_period_id=restatement.id,
                section_key=section.section_key,
                title=section.title,
                display_order=section.display_order,
                is_enabled=section.is_enabled,
                content=dict(section.content or {}),
                updated_by_user_id=actor_id,
            )
        )
    for item in period.management_actions:
        db.add(
            ManagementActionPlanItem(
                reporting_period_id=restatement.id,
                linked_action_id=item.linked_action_id,
                priority=item.priority,
                issue_summary=item.issue_summary,
                management_comment=item.management_comment,
            )
        )
    _history(db, period, actor_id=actor_id, event_type="restatement_created", from_status=period.status, to_status=period.status, reason=reason, metadata={"new_period_id": restatement.id, "new_version": restatement.report_version})
    _history(db, restatement, actor_id=actor_id, event_type="reopened", from_status=ReportingPeriodStatus.locked, to_status=ReportingPeriodStatus.reopened, reason=reason, metadata={"supersedes_period_id": period.id})
    db.commit()
    db.refresh(restatement)
    _audit(db, actor_id=actor_id, action="report.restatement.create", resource_type="reporting_period", resource_id=restatement.id, details={"supersedes_period_id": period.id, "reason": reason, "report_version": restatement.report_version})
    return restatement


def get_scorecard(
    db: Session,
    period: ReportingPeriod,
    *,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> dict:
    snapshots = list_snapshots(db, period, site_id=site_id, department_id=department_id)
    rows = []
    for snapshot in snapshots:
        comparison = (snapshot.calculation_metadata or {}).get("comparison", {})
        rows.append(
            {
                "kpi_key": snapshot.kpi_key,
                "kpi_name": snapshot.kpi_name,
                "unit": snapshot.unit,
                "target": snapshot.target_value,
                "actual": snapshot.value,
                "previous_period": comparison.get("previous_period_value"),
                "ytd": comparison.get("ytd_value"),
                "same_period_prior_year": comparison.get("same_period_prior_year_value"),
                "status": snapshot.status,
                "numerator": snapshot.numerator,
                "denominator": snapshot.denominator,
                "explanation": snapshot.calculation_metadata,
            }
        )
    return {
        "reporting_period_id": period.id,
        "report_reference": period.report_reference,
        "site_id": site_id,
        "department_id": department_id,
        "rows": rows,
    }


def get_comparison(db: Session, period: ReportingPeriod, *, scope: str) -> dict:
    if scope == "site":
        records = [(item.id, item.name) for item in db.scalars(select(Site).order_by(Site.name)).all()]
        scope_kwargs = lambda item_id: {"site_id": item_id, "department_id": None}
    elif scope == "department":
        records = [(item.id, item.name) for item in db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.name)).all()]
        scope_kwargs = lambda item_id: {"site_id": None, "department_id": item_id}
    else:
        raise ReportingConflictError("Comparison scope must be site or department")
    rows = []
    for scope_id, name in records:
        snapshots = list_snapshots(db, period, **scope_kwargs(scope_id))
        rows.append({"scope_id": scope_id, "scope_name": name, "metrics": {item.kpi_key: item.value for item in snapshots}})
    return {"reporting_period_id": period.id, "scope": scope, "rows": rows}


def get_kpi_drilldown(
    db: Session,
    period: ReportingPeriod,
    *,
    kpi_key: str,
    site_id: Optional[int] = None,
    department_id: Optional[int] = None,
) -> dict:
    snapshot = db.scalar(
        select(KPISnapshot).where(
            KPISnapshot.reporting_period_id == period.id,
            KPISnapshot.kpi_key == kpi_key,
            _scope_clause(KPISnapshot, site_id=site_id, department_id=department_id),
        )
    )
    if snapshot is None:
        raise ReportingNotFoundError("KPI snapshot was not found for this period and scope")
    context = CalculationContext(db, period, site_id=site_id, department_id=department_id)
    items: list[dict] = []
    if kpi_key.startswith("action_"):
        open_states = {
            "open", "assigned", "accepted", "in_progress", "completion_requested",
            "pending_verification", "declined", "on_hold", "reopened", "overdue",
        }
        candidates = list(context.actions)
        if kpi_key in {"action_open", "action_overdue", "action_overdue_rate", "action_high_critical_overdue", "action_awaiting_verification", "action_due_7_days", "action_due_30_days"}:
            candidates = [item for item in candidates if context.action_status_at_end(item) in open_states]
        if kpi_key in {"action_overdue", "action_overdue_rate", "action_high_critical_overdue"}:
            candidates = [item for item in candidates if context.action_due_date_at(item, period.end_date) and context.action_due_date_at(item, period.end_date) < period.end_date]
        if kpi_key == "action_high_critical_overdue":
            candidates = [item for item in candidates if item.priority.value in {"high", "critical"}]
        if kpi_key == "action_awaiting_verification":
            candidates = [item for item in candidates if context.action_status_at_end(item) in {"completion_requested", "pending_verification"}]
        if kpi_key == "action_reopened":
            candidates = [item for item in candidates if any(activity.event_type == "reopened" and context._in_period(activity.created_at) for activity in item.activities)]
        for item in candidates:
            items.append({
                "id": item.id,
                "reference": item.action_reference,
                "title": item.title,
                "status": context.action_status_at_end(item),
                "priority": item.priority.value,
                "due_date": context.action_due_date_at(item, period.end_date),
                "site_id": item.site_id,
                "department_id": item.responsible_department_id or item.department_id,
                "route": f"/corrective-actions/{item.id}",
            })
    elif kpi_key.startswith("sio_"):
        for item in context.sios:
            items.append({
                "id": item.id,
                "reference": item.reference_number,
                "title": item.description,
                "status": context.sio_status_at_end(item),
                "priority": item.urgency.value if item.urgency else None,
                "due_date": item.due_date,
                "site_id": item.site_id,
                "department_id": item.responsible_department_id or item.department_id,
                "route": f"/sios/{item.id}",
            })
    elif snapshot.kpi_definition.category == "Incidents":
        for item in context.incidents:
            items.append({"id": item.id, "title": item.title, "status": item.status.value, "priority": item.severity.value, "occurred_at": item.occurred_at, "site_id": item.site_id, "route": f"/incidents/{item.id}"})
    elif snapshot.kpi_definition.category == "Risk & Hazards":
        for item in context.hazards:
            items.append({"id": item.id, "title": item.title, "status": item.status.value, "priority": item.risk_level.value, "due_date": item.due_date, "site_id": item.site_id, "route": f"/hazards/{item.id}"})
    elif snapshot.kpi_definition.category == "Training":
        for item in context.training:
            items.append({"id": item.id, "title": item.title, "status": item.status.value, "due_date": item.due_date, "site_id": item.site_id, "route": f"/training/{item.id}"})
    elif snapshot.kpi_definition.category == "Inspections":
        for item in context.inspections:
            items.append({"id": item.id, "title": item.title, "status": item.status.value, "occurred_at": item.inspection_date, "site_id": item.site_id, "route": f"/inspections/{item.id}"})
    elif snapshot.kpi_definition.category == "Audits":
        for item in context.audits:
            items.append({"id": item.id, "title": f"{item.audit_type.value.title()} audit", "status": item.status.value, "occurred_at": item.audit_date, "site_id": item.site_id, "route": f"/audits/{item.id}"})
    elif snapshot.kpi_definition.category == "Permits & Compliance":
        for item in context.permits:
            items.append({"id": item.id, "title": item.title, "status": item.status.value, "due_date": item.end_datetime, "site_id": item.site_id, "route": f"/permits/{item.id}"})
        for item in context.compliance:
            items.append({"id": item.id, "title": item.title, "status": item.compliance_status.value, "due_date": item.next_review_date, "site_id": item.site_id, "route": f"/legal-compliance/{item.id}"})
    elif snapshot.kpi_definition.category == "PPE":
        if kpi_key == "ppe_low_stock_items":
            statement = select(PPEInventory).where(PPEInventory.quantity_available <= PPEInventory.reorder_level)
            if site_id is not None:
                statement = statement.join(PPEStockLocation).where(PPEStockLocation.site_id == site_id)
            for item in db.scalars(statement).all():
                items.append({"id": item.id, "title": item.item_name, "status": "low_stock", "site_id": item.location.site_id, "route": "/ppe"})
        elif kpi_key == "ppe_requests_outstanding":
            statement = select(PPERequest).where(PPERequest.status == PPERequestStatus.requested)
            for item in db.scalars(statement).all():
                recipient = db.get(User, item.recipient_user_id)
                if site_id is not None and (recipient is None or recipient.assigned_site_id != site_id):
                    continue
                if department_id is not None and (recipient is None or recipient.department_id != department_id):
                    continue
                items.append({"id": item.id, "title": f"PPE request #{item.id}", "status": item.status.value, "site_id": recipient.assigned_site_id if recipient else None, "route": "/ppe"})
        else:
            statement = select(PPEIssue).where(PPEIssue.issue_date <= period.end_date)
            if site_id is not None:
                statement = statement.where(PPEIssue.site_id_snapshot == site_id)
            if department_id is not None:
                statement = statement.where(PPEIssue.department_id_snapshot == department_id)
            for item in db.scalars(statement).all():
                items.append({"id": item.id, "title": item.item_name_snapshot, "status": item.status.value, "due_date": item.expected_replacement_date, "site_id": item.site_id_snapshot, "department_id": item.department_id_snapshot, "route": "/ppe"})
    return {
        "reporting_period_id": period.id,
        "kpi_key": kpi_key,
        "site_id": site_id,
        "department_id": department_id,
        "total": len(items),
        "items": items,
    }
