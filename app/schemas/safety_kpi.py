from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import PaginatedResponse


class SafetyKPIBase(BaseModel):
    site_id: int
    period_start: date
    period_end: date
    hours_worked: float = Field(ge=0)
    reporting_label: Optional[str] = Field(default=None, min_length=2, max_length=120)
    employees_count: Optional[int] = Field(default=None, ge=0)
    contractors_count: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("Period end must be on or after the period start")
        return self


class SafetyKPICreate(SafetyKPIBase):
    pass


class SafetyKPIUpdate(BaseModel):
    site_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    hours_worked: Optional[float] = Field(default=None, ge=0)
    reporting_label: Optional[str] = Field(default=None, min_length=2, max_length=120)
    employees_count: Optional[int] = Field(default=None, ge=0)
    contractors_count: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class SafetyKPIRead(SafetyKPIBase):
    id: int
    created_by_user_id: Optional[int] = None
    recordable_incidents: int
    lost_time_incidents: int
    trifr: float
    ltifr: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafetyKPIListRead(PaginatedResponse[SafetyKPIRead]):
    pass
