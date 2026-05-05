from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")


class AttachmentMetadata(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    size_bytes: int = Field(ge=0)
    checksum: str | None = Field(default=None, max_length=128)


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    skip: int
    limit: int
