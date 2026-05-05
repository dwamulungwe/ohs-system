from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.role import RoleRead


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    phone_number: str | None = Field(default=None, min_length=7, max_length=40)
    is_active: bool = True
    assigned_site_id: int | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role_ids: list[int] = []


class UserBootstrap(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    assigned_site_id: int | None = None
    role_ids: list[int] | None = None


class UserRead(UserBase):
    id: int
    email: str
    roles: list[RoleRead] = []
    role_names: list[str] = []
    primary_role: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
