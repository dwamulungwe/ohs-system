from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.inspection import Inspection, InspectionOverallResult, InspectionStatus
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionListRead, InspectionRead, InspectionUpdate
from app.services.attachment_service import hydrate_entity_attachments
from app.services.rbac import Permission, ensure_permission, ensure_site_access, resolve_site_scope
from app.services.inspection_service import (
    InspectionHazardNotFoundError,
    InspectionInspectorNotFoundError,
    InspectionNotFoundError,
    InspectionSiteNotFoundError,
    create_inspection as create_inspection_record,
    get_inspection as get_inspection_record,
    list_inspections as list_inspection_records,
    update_inspection as update_inspection_record,
)

router = APIRouter()


@router.get("", response_model=InspectionListRead)
def list_inspections(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    inspection_status: InspectionStatus | None = Query(default=None, alias="status"),
    overall_result: InspectionOverallResult | None = None,
    site_id: int | None = None,
    inspector_user_id: int | None = None,
    inspection_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_permission(current_user, Permission.INSPECTIONS_VIEW)
    site_id = resolve_site_scope(current_user, site_id)
    return list_inspection_records(
        db,
        skip=skip,
        limit=limit,
        status=inspection_status,
        overall_result=overall_result,
        site_id=site_id,
        inspector_user_id=inspector_user_id,
        inspection_type=inspection_type,
    )


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(
    inspection_in: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Inspection:
    ensure_permission(current_user, Permission.INSPECTIONS_CREATE)
    inspection_in = inspection_in.model_copy(
        update={"site_id": resolve_site_scope(current_user, inspection_in.site_id)}
    )
    try:
        return create_inspection_record(db, inspection_in, actor_id=current_user.id)
    except InspectionSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except InspectionInspectorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspector user not found")
    except InspectionHazardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked hazard not found")


@router.get("/{inspection_id}", response_model=InspectionRead)
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Inspection:
    ensure_permission(current_user, Permission.INSPECTIONS_VIEW)
    try:
        inspection = get_inspection_record(db, inspection_id)
        ensure_site_access(current_user, inspection.site_id)
        return hydrate_entity_attachments(db, AttachmentEntityType.inspection, inspection)
    except InspectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")


@router.patch("/{inspection_id}", response_model=InspectionRead)
def patch_inspection(
    inspection_id: int,
    inspection_in: InspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Inspection:
    ensure_permission(current_user, Permission.INSPECTIONS_EDIT)
    try:
        inspection = get_inspection_record(db, inspection_id)
        ensure_site_access(current_user, inspection.site_id)
        return update_inspection_record(db, inspection, inspection_in, actor_id=current_user.id)
    except InspectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")
    except InspectionSiteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    except InspectionInspectorNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspector user not found")
    except InspectionHazardNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked hazard not found")
