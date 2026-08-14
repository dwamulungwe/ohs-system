from typing import Optional
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin
from app.models.role import user_roles


class User(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    assigned_site_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
    assigned_site: Mapped[Optional["Site"]] = relationship(
        foreign_keys=[assigned_site_id],
        lazy="selectin",
    )
    organisation: Mapped["Organisation"] = relationship(lazy="selectin")
    department: Mapped[Optional["Department"]] = relationship(
        foreign_keys=[department_id],
        lazy="selectin",
    )

    @property
    def role_names(self) -> list[str]:
        from app.services.rbac import get_normalized_role_names

        return sorted(get_normalized_role_names(self))

    @property
    def primary_role(self) -> Optional[str]:
        from app.services.rbac import get_primary_role_name

        return get_primary_role_name(self)

    @property
    def enabled_modules(self) -> list[str]:
        organisation = getattr(self, "organisation", None)
        features = getattr(organisation, "features", None) or []
        return sorted(feature.key for feature in features if feature.is_enabled)

    @property
    def effective_permissions(self) -> list[str]:
        from app.services.rbac import get_effective_permissions

        return get_effective_permissions(self)
