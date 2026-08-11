from typing import Optional
from sqlalchemy import String, Table, Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name", name="uq_roles_org_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
