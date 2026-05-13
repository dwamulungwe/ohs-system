from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor_id: Optional[int] = None
    action: str = Field(min_length=2, max_length=120)
    resource_type: str = Field(min_length=2, max_length=120)
    resource_id: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = Field(default=None, max_length=64)


class AuditLogRead(AuditLogCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
