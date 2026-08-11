from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin


class Department(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name", name="uq_departments_org_name"),
        UniqueConstraint("organisation_id", "code", name="uq_departments_org_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    manager_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_departments_manager_user_id_users",
        ),
        index=True,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent_department: Mapped[Optional["Department"]] = relationship(
        remote_side="Department.id", foreign_keys=[parent_department_id], lazy="selectin"
    )
    manager: Mapped[Optional["User"]] = relationship(
        foreign_keys=[manager_user_id], lazy="selectin"
    )
