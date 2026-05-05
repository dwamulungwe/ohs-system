from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.attachment import AttachmentEntityType


class AttachmentRead(BaseModel):
    id: int
    entity_type: AttachmentEntityType
    entity_id: int
    uploaded_by_user_id: int | None = None
    uploaded_by_name: str | None = None
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    file_size: int = Field(ge=0)
    description: str | None = None
    created_at: datetime
    download_url: str = Field(min_length=1, max_length=2048)

    model_config = ConfigDict(from_attributes=True)
