from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.reporting import (
    KPIDirection,
    KPISnapshotStatus,
    ReportingPeriodStatus,
    ReportingPeriodType,
)
from app.schemas.common import PaginatedResponse


class ReportingPeriodCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    period_type: ReportingPeriodType
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Period end must be on or after period start")
        return self


class ReportingPeriodRead(BaseModel):
    id: int
    organisation_id: int
    name: str
    period_type: ReportingPeriodType
    start_date: date
    end_date: date
    status: ReportingPeriodStatus
    prepared_by_user_id: Optional[int] = None
    reviewed_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    prepared_by_name: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    reopened_by_user_id: Optional[int] = None
    reopen_reason: Optional[str] = None
    report_version: int
    report_reference: Optional[str] = None
    supersedes_period_id: Optional[int] = None
    restatement_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportingPeriodListRead(PaginatedResponse[ReportingPeriodRead]):
    pass


class ReportingReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=4000)


class ReportingPeriodHistoryRead(BaseModel):
    id: int
    reporting_period_id: int
    actor_user_id: Optional[int] = None
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    reason: Optional[str] = None
    event_metadata: dict = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KPIDefinitionCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=2)
    category: str = Field(min_length=2, max_length=80)
    unit: str = Field(min_length=1, max_length=40)
    calculation_method: str = Field(min_length=2, max_length=120)
    numerator_definition: Optional[str] = None
    denominator_definition: Optional[str] = None
    multiplier: Optional[float] = Field(default=None, gt=0)
    direction: KPIDirection = KPIDirection.informational
    is_active: bool = True
    effective_from: date


class KPIDefinitionRead(BaseModel):
    id: int
    organisation_id: Optional[int] = None
    key: str
    name: str
    description: str
    category: str
    unit: str
    calculation_method: str
    numerator_definition: Optional[str] = None
    denominator_definition: Optional[str] = None
    multiplier: Optional[float] = None
    direction: KPIDirection
    is_active: bool
    version: int
    effective_from: date
    effective_to: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KPIEnablementUpdate(BaseModel):
    is_enabled: bool


class KPITargetCreate(BaseModel):
    kpi_definition_id: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    target_value: float
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    effective_from: date
    effective_to: Optional[date] = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Target effective_to must be on or after effective_from")
        if self.site_id is not None and self.department_id is not None:
            raise ValueError("Choose either a site target or department target, not both")
        return self


class KPITargetRead(BaseModel):
    id: int
    organisation_id: int
    kpi_definition_id: int
    kpi_key: str
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    target_value: float
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    effective_from: date
    effective_to: Optional[date] = None
    version: int
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkforceExposureCreate(BaseModel):
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    period_start: date
    period_end: date
    employee_headcount: Optional[int] = Field(default=None, ge=0)
    contractor_headcount: Optional[int] = Field(default=None, ge=0)
    employee_hours_worked: Optional[float] = Field(default=None, ge=0)
    contractor_hours_worked: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_exposure(self):
        if self.period_end < self.period_start:
            raise ValueError("Exposure period end must be on or after period start")
        if self.site_id is not None and self.department_id is not None:
            raise ValueError("Choose either a site exposure or department exposure, not both")
        if all(
            value is None
            for value in (
                self.employee_headcount,
                self.contractor_headcount,
                self.employee_hours_worked,
                self.contractor_hours_worked,
            )
        ):
            raise ValueError("At least one workforce statistic is required")
        return self


class WorkforceExposureUpdate(BaseModel):
    employee_headcount: Optional[int] = Field(default=None, ge=0)
    contractor_headcount: Optional[int] = Field(default=None, ge=0)
    employee_hours_worked: Optional[float] = Field(default=None, ge=0)
    contractor_hours_worked: Optional[float] = Field(default=None, ge=0)


class WorkforceExposureRead(WorkforceExposureCreate):
    id: int
    organisation_id: int
    created_by_user_id: Optional[int] = None
    total_hours_worked: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkforceExposureListRead(PaginatedResponse[WorkforceExposureRead]):
    pass


class KPISnapshotRead(BaseModel):
    id: int
    reporting_period_id: int
    organisation_id: int
    kpi_definition_id: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    kpi_key: str
    kpi_name: str
    kpi_version: int
    unit: str
    value: Optional[float] = None
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    target_value: Optional[float] = None
    status: KPISnapshotStatus
    calculation_metadata: dict = {}
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportSectionUpdate(BaseModel):
    content: dict


class ReportSectionRead(BaseModel):
    id: int
    reporting_period_id: int
    section_key: str
    title: str
    display_order: int
    is_enabled: bool
    content: dict
    updated_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagementActionPlanCreate(BaseModel):
    linked_action_id: int
    priority: str = Field(min_length=2, max_length=30)
    issue_summary: str = Field(min_length=2, max_length=4000)
    management_comment: Optional[str] = Field(default=None, max_length=4000)


class ManagementActionPlanRead(BaseModel):
    id: int
    reporting_period_id: int
    linked_action_id: int
    priority: str
    issue_summary: str
    management_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScorecardRow(BaseModel):
    kpi_key: str
    kpi_name: str
    unit: str
    target: Optional[float] = None
    actual: Optional[float] = None
    previous_period: Optional[float] = None
    ytd: Optional[float] = None
    same_period_prior_year: Optional[float] = None
    status: KPISnapshotStatus
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    explanation: dict = {}


class ScorecardRead(BaseModel):
    reporting_period_id: int
    report_reference: Optional[str] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    rows: list[ScorecardRow]


class SnapshotGenerationRead(BaseModel):
    reporting_period_id: int
    generated_at: datetime
    snapshot_count: int
    scopes: int


class ExceptionRead(BaseModel):
    source_type: str
    source_id: int
    title: str
    severity: str
    age_days: int
    due_date: Optional[date] = None
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    reason: str
    route: Optional[str] = None


class ForwardViewItemRead(BaseModel):
    source_type: str
    source_id: int
    title: str
    obligation_date: date
    days_until_due: int
    window_days: int
    site_id: Optional[int] = None
    department_id: Optional[int] = None
    route: Optional[str] = None


class ComparisonRow(BaseModel):
    scope_id: int
    scope_name: str
    metrics: dict[str, Optional[float]]


class ComparisonRead(BaseModel):
    reporting_period_id: int
    scope: str
    rows: list[ComparisonRow]
