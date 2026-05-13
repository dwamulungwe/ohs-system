from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.job_run import JobRunStatus
from app.models.user import User
from app.schemas.job_run import JobRunListRead, JobRunRead
from app.services.rbac import Permission, ensure_permission
from app.services.scheduler_service import (
    JobRunNotFoundError,
    get_job_run,
    list_job_runs,
    run_all_scheduled_jobs,
)

router = APIRouter()


@router.get("", response_model=JobRunListRead)
def read_job_runs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    job_name: Optional[str] = None,
    job_status: Optional[JobRunStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.JOB_RUNS_VIEW)
    return list_job_runs(db, skip=skip, limit=limit, job_name=job_name, job_status=job_status)


@router.get("/{job_run_id}", response_model=JobRunRead)
def read_job_run(
    job_run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.JOB_RUNS_VIEW)
    try:
        return get_job_run(db, job_run_id)
    except JobRunNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found")


@router.post("/run-scheduled", response_model=list[JobRunRead], status_code=status.HTTP_201_CREATED)
def run_scheduled_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_permission(current_user, Permission.JOB_RUNS_MANAGE)
    return run_all_scheduled_jobs(db)
