from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.role import RoleRead


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    phone_number: Optional[str] = Field(default=None, min_length=7, max_length=40)
    is_active: bool = True
    assigned_site_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role_ids: list[int] = []


class UserBootstrap(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_active: Optional[bool] = None
    assigned_site_id: Optional[int] = None
    role_ids: Optional[list[int]] = None


class UserRead(UserBase):
    id: int
    email: str
    roles: list[RoleRead] = []
    role_names: list[str] = []
    primary_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
