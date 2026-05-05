from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.approval import ApprovalActionType, ApprovalEntityType, ApprovalStatus
from app.schemas.common import PaginatedResponse


class ApprovalRequestCreate(BaseModel):
    action_type: ApprovalActionType
    assigned_approver_user_id: int | None = None
    request_notes: str | None = Field(default=None, max_length=4000)


class ApprovalDecisionUpdate(BaseModel):
    status: ApprovalStatus
    decision_notes: str | None = Field(default=None, max_length=4000)


class ApprovalRead(BaseModel):
    id: int
    entity_type: ApprovalEntityType
    entity_id: int
    requested_by_user_id: int | None = None
    assigned_approver_user_id: int | None = None
    action_type: ApprovalActionType
    status: ApprovalStatus
    request_notes: str | None = None
    decision_notes: str | None = None
    decided_by_user_id: int | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalListRead(PaginatedResponse[ApprovalRead]):
    pass
