from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin


class Organisation(TimestampMixin, Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    primary_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_contact_phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Lusaka", nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    settings: Mapped["OrganisationSettings"] = relationship(
        back_populates="organisation", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    features: Mapped[list["OrganisationFeature"]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan", lazy="selectin"
    )


class OrganisationSettings(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "organisation_settings"
    __table_args__ = (
        UniqueConstraint("organisation_id", name="uq_organisation_settings_organisation_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    branding: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    date_time_preferences: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    terminology: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    permit_expiry_warning_days: Mapped[int] = mapped_column(default=30, nullable=False)
    dashboard_preferences: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    notification_preferences: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    risk_matrix_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    numbering_prefixes: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    sio_workflow_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    action_workflow_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    reporting_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    ppe_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )
    incident_configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    organisation: Mapped[Organisation] = relationship(back_populates="settings")


class OrganisationFeature(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "organisation_features"
    __table_args__ = (
        UniqueConstraint("organisation_id", "key", name="uq_organisation_features_org_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict, nullable=False
    )

    organisation: Mapped[Organisation] = relationship(back_populates="features")
