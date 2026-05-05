from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor_id: int | None = None
    action: str = Field(min_length=2, max_length=120)
    resource_type: str = Field(min_length=2, max_length=120)
    resource_id: int | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = Field(default=None, max_length=64)


class AuditLogRead(AuditLogCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
