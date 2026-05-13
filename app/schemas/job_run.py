from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job_run import JobRunStatus
from app.schemas.common import PaginatedResponse


class JobRunRead(BaseModel):
    id: int
    job_name: str
    status: JobRunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int
    details: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobRunListRead(PaginatedResponse[JobRunRead]):
    pass
