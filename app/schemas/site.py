from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SiteBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=50)
    address: str | None = None


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    code: str | None = Field(default=None, min_length=2, max_length=50)
    address: str | None = None


class SiteRead(SiteBase):
    id: int
    created_by_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
