from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.approval import ApprovalActionType, ApprovalEntityType, ApprovalStatus
from app.schemas.common import PaginatedResponse


class ApprovalRequestCreate(BaseModel):
    action_type: ApprovalActionType
    assigned_approver_user_id: Optional[int] = None
    request_notes: Optional[str] = Field(default=None, max_length=4000)


class ApprovalDecisionUpdate(BaseModel):
    status: ApprovalStatus
    decision_notes: Optional[str] = Field(default=None, max_length=4000)


class ApprovalRead(BaseModel):
    id: int
    entity_type: ApprovalEntityType
    entity_id: int
    requested_by_user_id: Optional[int] = None
    assigned_approver_user_id: Optional[int] = None
    action_type: ApprovalActionType
    status: ApprovalStatus
    request_notes: Optional[str] = None
    decision_notes: Optional[str] = None
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalListRead(PaginatedResponse[ApprovalRead]):
    pass
