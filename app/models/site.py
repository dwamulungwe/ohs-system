from typing import Optional
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.common import OrganisationOwnedMixin, TimestampMixin


class Site(OrganisationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_sites_org_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_sites_created_by_id_users",
        ),
        nullable=True,
    )

    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
