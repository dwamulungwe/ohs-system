from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganisationBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=50)
    slug: str = Field(min_length=2, max_length=100)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(default=None, max_length=512)
    primary_contact_name: Optional[str] = Field(default=None, max_length=255)
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = Field(default=None, max_length=80)
    timezone: str = Field(default="Africa/Lusaka", max_length=80)
    country: Optional[str] = Field(default=None, max_length=120)
    is_active: bool = True


class OrganisationCreate(OrganisationBase):
    enabled_modules: Optional[list[str]] = None


class OrganisationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, min_length=2, max_length=50)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=100)
    legal_name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(default=None, max_length=512)
    primary_contact_name: Optional[str] = Field(default=None, max_length=255)
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = Field(default=None, max_length=80)
    timezone: Optional[str] = Field(default=None, max_length=80)
    country: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None


class OrganisationSettingsRead(BaseModel):
    organisation_id: int
    branding: dict = {}
    date_time_preferences: dict = {}
    terminology: dict = {}
    permit_expiry_warning_days: int = 30
    dashboard_preferences: dict = {}
    notification_preferences: dict = {}
    risk_matrix_configuration: dict = {}
    numbering_prefixes: dict = {}
    sio_workflow_configuration: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganisationSettingsUpdate(BaseModel):
    branding: Optional[dict] = None
    date_time_preferences: Optional[dict] = None
    terminology: Optional[dict] = None
    permit_expiry_warning_days: Optional[int] = Field(default=None, ge=1, le=365)
    dashboard_preferences: Optional[dict] = None
    notification_preferences: Optional[dict] = None
    risk_matrix_configuration: Optional[dict] = None
    numbering_prefixes: Optional[dict] = None
    sio_workflow_configuration: Optional[dict] = None


class OrganisationFeatureRead(BaseModel):
    key: str
    is_enabled: bool
    configuration: dict = {}

    model_config = ConfigDict(from_attributes=True)


class OrganisationFeatureUpdate(BaseModel):
    key: str
    is_enabled: bool
    configuration: Optional[dict] = None


class OrganisationFeaturesUpdate(BaseModel):
    features: list[OrganisationFeatureUpdate]


class OrganisationRead(OrganisationBase):
    id: int
    settings: Optional[OrganisationSettingsRead] = None
    features: list[OrganisationFeatureRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganisationContext(BaseModel):
    id: int
    name: str
    code: str
    slug: str
    logo_url: Optional[str] = None
    timezone: str
    country: Optional[str] = None
    settings: Optional[OrganisationSettingsRead] = None

    model_config = ConfigDict(from_attributes=True)
