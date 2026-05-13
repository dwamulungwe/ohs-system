from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset_register import AssetConditionStatus, AssetType
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class AssetRegisterBase(BaseModel):
    asset_type: AssetType
    asset_name: str = Field(min_length=2, max_length=200)
    asset_tag: str = Field(min_length=2, max_length=120)
    site_id: int
    location: str = Field(min_length=2, max_length=255)
    assigned_to_user_id: Optional[int] = None
    inspection_frequency: str = Field(min_length=2, max_length=120)
    next_inspection_date: Optional[date] = None
    condition_status: AssetConditionStatus = AssetConditionStatus.good
    last_inspected_at: Optional[datetime] = None
    notes: Optional[str] = None
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class AssetRegisterCreate(AssetRegisterBase):
    pass


class AssetRegisterUpdate(BaseModel):
    asset_type: Optional[AssetType] = None
    asset_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    asset_tag: Optional[str] = Field(default=None, min_length=2, max_length=120)
    site_id: Optional[int] = None
    location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    assigned_to_user_id: Optional[int] = None
    inspection_frequency: Optional[str] = Field(default=None, min_length=2, max_length=120)
    next_inspection_date: Optional[date] = None
    condition_status: Optional[AssetConditionStatus] = None
    last_inspected_at: Optional[datetime] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class AssetRegisterRead(AssetRegisterBase):
    id: int
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetRegisterListRead(PaginatedResponse[AssetRegisterRead]):
    pass
