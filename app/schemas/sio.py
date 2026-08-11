from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.sio import SIOObservationNature, SIOStatus, SIOUrgency
from app.schemas.common import PaginatedResponse


class SIOBase(BaseModel):
    external_reference_id: Optional[str] = Field(default=None, max_length=160)
    source_system: Optional[str] = Field(default=None, max_length=120)
    observation_date: Optional[date] = None
    department: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=2)
    incident_classification: Optional[str] = Field(default=None, max_length=200)
    status: SIOStatus = SIOStatus.unassigned
    observation_nature: SIOObservationNature
    responsible_department: Optional[str] = Field(default=None, max_length=200)
    site_id: int
    responsible_hs_officer_user_id: Optional[int] = None
    responsible_hs_officer_name: Optional[str] = Field(default=None, max_length=255)
    urgency: Optional[SIOUrgency] = None
    category: Optional[str] = Field(default=None, max_length=255)
    responsible_person_user_id: Optional[int] = None
    responsible_person_name: Optional[str] = Field(default=None, max_length=255)
    property_damage: Optional[str] = Field(default=None, max_length=255)
    source_created_at: Optional[datetime] = None
    source_created_by: Optional[str] = Field(default=None, max_length=255)
    source_modified_by: Optional[str] = Field(default=None, max_length=255)
    source_path: Optional[str] = None
    legacy_metadata: Optional[dict] = None


class SIOCreate(SIOBase):
    pass


class SIOUpdate(BaseModel):
    observation_date: Optional[date] = None
    department: Optional[str] = Field(default=None, min_length=1, max_length=200)
    source_type: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=2)
    incident_classification: Optional[str] = Field(default=None, max_length=200)
    status: Optional[SIOStatus] = None
    observation_nature: Optional[SIOObservationNature] = None
    responsible_department: Optional[str] = Field(default=None, max_length=200)
    site_id: Optional[int] = None
    responsible_hs_officer_user_id: Optional[int] = None
    responsible_hs_officer_name: Optional[str] = Field(default=None, max_length=255)
    urgency: Optional[SIOUrgency] = None
    category: Optional[str] = Field(default=None, max_length=255)
    responsible_person_user_id: Optional[int] = None
    responsible_person_name: Optional[str] = Field(default=None, max_length=255)
    property_damage: Optional[str] = Field(default=None, max_length=255)


class SIORead(SIOBase):
    id: int
    created_by_user_id: Optional[int] = None
    linked_hazard_id: Optional[int] = None
    linked_incident_id: Optional[int] = None
    linked_corrective_action_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SIOListRead(PaginatedResponse[SIORead]):
    pass


class SIOEscalationOptions(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    due_date: Optional[date] = None


class SIOAnalyticsRead(BaseModel):
    total_observations: int
    positive_observations: int
    negative_observations: int
    open_unassigned_observations: int
    urgent_high_priority_observations: int
    observations_by_site: dict[str, int]
    observations_by_category: dict[str, int]
    observations_by_source: dict[str, int]
    observations_by_department: dict[str, int]
    observation_trend_by_month: dict[str, int]
