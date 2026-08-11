from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    parent_department_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    parent_department_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    is_active: Optional[bool] = None


class DepartmentRead(DepartmentBase):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
