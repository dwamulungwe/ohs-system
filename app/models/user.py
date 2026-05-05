from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import TimestampMixin
from app.models.role import user_roles


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
    assigned_site: Mapped["Site | None"] = relationship(
        foreign_keys=[assigned_site_id],
        lazy="selectin",
    )

    @property
    def role_names(self) -> list[str]:
        from app.services.rbac import get_normalized_role_names

        return sorted(get_normalized_role_names(self))

    @property
    def primary_role(self) -> str | None:
        from app.services.rbac import get_primary_role_name

        return get_primary_role_name(self)
