from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class OrganisationOwnedMixin:
    """Marks records that must always be isolated by organisation."""

    @declared_attr
    def organisation_id(cls) -> Mapped[int]:
        return mapped_column(
            ForeignKey("organisations.id", ondelete="RESTRICT"),
            index=True,
            nullable=False,
        )
