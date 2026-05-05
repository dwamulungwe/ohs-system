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
    immediate_action_taken: str | None = None
    follow_up_notes: str | None = None
    person_involved_name: str | None = Field(default=None, max_length=160)
    action_required: bool = False
    observed_at: datetime
    attachments_metadata: list[AttachmentMetadata] = Field(default_factory=list)


class BehaviourObservationCreate(BehaviourObservationBase):
    pass


class BehaviourObservationUpdate(BaseModel):
    site_id: int | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    observation_type: BehaviourObservationType | None = None
    status: BehaviourObservationStatus | None = None
    severity: BehaviourObservationSeverity | None = None
    description: str | None = Field(default=None, min_length=2)
    immediate_action_taken: str | None = None
    follow_up_notes: str | None = None
    person_involved_name: str | None = Field(default=None, max_length=160)
    action_required: bool | None = None
    observed_at: datetime | None = None
    attachments_metadata: list[AttachmentMetadata] | None = None


class BehaviourObservationRead(BehaviourObservationBase):
    id: int
    observed_by_user_id: int | None = None
    closed_at: datetime | None = None
    closed_by_user_id: int | None = None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BehaviourObservationListRead(PaginatedResponse[BehaviourObservationRead]):
    pass
