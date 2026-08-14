from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.core.config import settings

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


class TenantSession(Session):
    def get(self, entity, ident, **kwargs):
        record = super().get(entity, ident, **kwargs)
        if record is None or self.info.get("bypass_tenant_filter"):
            return record
        from app.models.common import OrganisationOwnedMixin

        if isinstance(record, OrganisationOwnedMixin):
            organisation_id = self.info.get("organisation_id")
            if not organisation_id or record.organisation_id != organisation_id:
                return None
        return record


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=TenantSession)


@event.listens_for(Session, "do_orm_execute")
def enforce_tenant_reads(execute_state) -> None:
    if execute_state.session.info.get("bypass_tenant_filter"):
        return

    from app.models.common import OrganisationOwnedMixin

    organisation_id = execute_state.session.info.get("organisation_id", -1)
    if execute_state.is_update or execute_state.is_delete:
        mapper = execute_state.bind_mapper
        if mapper is not None and issubclass(mapper.class_, OrganisationOwnedMixin):
            execute_state.statement = execute_state.statement.where(
                mapper.class_.organisation_id == organisation_id
            )
        return
    if not execute_state.is_select:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            OrganisationOwnedMixin,
            lambda model: model.organisation_id == organisation_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def enforce_tenant_writes(session: Session, _flush_context, _instances) -> None:
    from app.models.common import OrganisationOwnedMixin
    from app.models.reporting import (
        KPISnapshot,
        ManagementActionPlanItem,
        ReportSection,
        ReportingPeriod,
        ReportingPeriodStatus,
    )

    organisation_id = session.info.get("organisation_id")
    allow_cross_tenant = session.info.get("allow_cross_tenant_writes", False)

    for record in set(session.new).union(session.dirty).union(session.deleted):
        if not isinstance(record, OrganisationOwnedMixin):
            continue
        record_organisation_id = getattr(record, "organisation_id", None)
        if record in session.new and record_organisation_id is None and organisation_id:
            record.organisation_id = organisation_id
            record_organisation_id = organisation_id
        if allow_cross_tenant:
            continue
        if not organisation_id:
            raise RuntimeError("Tenant-owned writes require an organisation context")
        if record_organisation_id != organisation_id:
            raise RuntimeError("Cross-organisation write blocked")

        if isinstance(record, (KPISnapshot, ReportSection, ManagementActionPlanItem)):
            period = getattr(record, "reporting_period", None)
            if period is None and getattr(record, "reporting_period_id", None):
                period = session.get(ReportingPeriod, record.reporting_period_id)
            if period is not None and period.status == ReportingPeriodStatus.locked:
                raise RuntimeError("Locked report data is immutable")
