from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.data_import import DataImportJob
from app.models.user import User
from app.schemas.data_import import (
    DataImportJobListRead,
    DataImportJobRead,
    ImportConfirmRequest,
)
from app.services.data_import_service import (
    YALELO_SIO_IMPORTER,
    ImportJobNotFoundError,
    ImportStateError,
    ImportValidationError,
    confirm_yalelo_sio_import,
    get_import_job,
    list_import_jobs,
    preview_yalelo_sio_import,
)
from app.services.rbac import Permission, ensure_permission

router = APIRouter()


@router.get("", response_model=DataImportJobListRead)
def read_import_jobs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.DATA_IMPORTS_MANAGE)
    return list_import_jobs(db, skip=skip, limit=limit)


@router.post("/preview", response_model=DataImportJobRead, status_code=status.HTTP_201_CREATED)
async def preview_import(
    file: UploadFile = File(...),
    importer_type: str = Form(default=YALELO_SIO_IMPORTER),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataImportJob:
    ensure_permission(current_user, Permission.DATA_IMPORTS_MANAGE)
    if importer_type != YALELO_SIO_IMPORTER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported importer type: {importer_type}",
        )
    content = await file.read(settings.ATTACHMENT_MAX_FILE_SIZE_BYTES + 1)
    if len(content) > settings.ATTACHMENT_MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Workbook is too large")
    try:
        return preview_yalelo_sio_import(
            db,
            content=content,
            filename=file.filename or "upload.xlsx",
            actor_id=current_user.id,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{job_id}", response_model=DataImportJobRead)
def read_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataImportJob:
    ensure_permission(current_user, Permission.DATA_IMPORTS_MANAGE)
    try:
        return get_import_job(db, job_id)
    except ImportJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")


@router.post("/{job_id}/confirm", response_model=DataImportJobRead)
def confirm_import(
    job_id: int,
    request: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataImportJob:
    ensure_permission(current_user, Permission.DATA_IMPORTS_MANAGE)
    try:
        job = get_import_job(db, job_id)
        return confirm_yalelo_sio_import(db, job, request, actor_id=current_user.id)
    except ImportJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    except ImportStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
