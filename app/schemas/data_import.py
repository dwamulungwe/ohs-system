from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.data_import import ImportJobStatus, ImportRowStatus
from app.schemas.common import PaginatedResponse


class ImportMessage(BaseModel):
    row_number: Optional[int] = None
    field: Optional[str] = None
    level: str = "error"
    message: str


class ImportReport(BaseModel):
    rows_detected: int
    rows_valid: int
    rows_imported: int
    duplicates_skipped: int
    rows_failed: int
    unresolved_sites: list[str] = Field(default_factory=list)
    site_mappings: dict[str, int] = Field(default_factory=dict)
    failure_reasons: list[ImportMessage] = Field(default_factory=list)


class DataImportRowRead(BaseModel):
    id: int
    row_number: int
    external_reference_id: Optional[str] = None
    source_site_name: Optional[str] = None
    resolved_site_id: Optional[int] = None
    status: ImportRowStatus
    messages: list[dict] = Field(default_factory=list)
    imported_sio_id: Optional[int] = None
    failure_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DataImportJobSummaryRead(BaseModel):
    id: int
    importer_type: str
    source_system: str
    original_filename: str
    status: ImportJobStatus
    is_dry_run: bool
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_rows: int
    successful_rows: int
    skipped_rows: int
    failed_rows: int
    validation_messages: list[dict] = Field(default_factory=list)
    report: dict = Field(default_factory=dict)
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DataImportJobRead(DataImportJobSummaryRead):
    rows: list[DataImportRowRead] = Field(default_factory=list)


class DataImportJobListRead(PaginatedResponse[DataImportJobSummaryRead]):
    pass


class ImportConfirmRequest(BaseModel):
    site_mappings: dict[str, int] = Field(default_factory=dict)
    create_sites: list[str] = Field(default_factory=list)
