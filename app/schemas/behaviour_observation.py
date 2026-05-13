from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.behaviour_observation import (
    BehaviourObservationSeverity,
    BehaviourObservationStatus,
    BehaviourObservationType,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentMetadata, PaginatedResponse


class BehaviourObservationBase(BaseModel):
    site_id: int
    title: str = Field(min_length=2, max_length=200)
    observation_type: BehaviourObservationType
    status: BehaviourObservationStatus = BehaviourObservationStatus.open
    severity: BehaviourObservationSeverity = BehaviourObservationSeverity.medium
    description: str = Field(min_length=2)
    immediate_action_taken: Optional[str] = None
    follow_up_notes: Optional[str] = None
    person_involved_name: Optional[str] = Field(default=None, max_length=160)
    action_required: bool = False
    observed_at: datetime
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class BehaviourObservationCreate(BehaviourObservationBase):
    pass


class BehaviourObservationUpdate(BaseModel):
    site_id: Optional[int] = None
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    observation_type: Optional[BehaviourObservationType] = None
    status: Optional[BehaviourObservationStatus] = None
    severity: Optional[BehaviourObservationSeverity] = None
    description: Optional[str] = Field(default=None, min_length=2)
    immediate_action_taken: Optional[str] = None
    follow_up_notes: Optional[str] = None
    person_involved_name: Optional[str] = Field(default=None, max_length=160)
    action_required: Optional[bool] = None
    observed_at: Optional[datetime] = None
    attachments_metadata: Optional[list[AttachmentMetadata]] = None


class BehaviourObservationRead(BehaviourObservationBase):
    id: int
    observed_by_user_id: Optional[int] = None
    closed_at: Optional[datetime] = None
    closed_by_user_id: Optional[int] = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BehaviourObservationListRead(PaginatedResponse[BehaviourObservationRead]):
    pass
