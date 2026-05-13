from typing import Optional
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.hazard import Hazard
from app.models.inspection import Inspection, InspectionOverallResult, InspectionStatus
from app.models.site import Site
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionUpdate
from app.services.audit_service import write_audit_log
from app.services.query_utils import paginate


class InspectionServiceError(Exception):
    pass


class InspectionNotFoundError(InspectionServiceError):
    pass


class InspectionSiteNotFoundError(InspectionServiceError):
    pass


class InspectionInspectorNotFoundError(InspectionServiceError):
    pass


class InspectionHazardNotFoundError(InspectionServiceError):
    pass


def calculate_checklist_counts(checklist_items: list[dict]) -> tuple[int, int]:
    non_conformities = sum(1 for item in checklist_items if item.get("result") == "non_compliant")
    observations = sum(1 for item in checklist_items if item.get("result") == "observation")
    return non_conformities, observations


def derive_overall_result(checklist_items: list[dict]) -> InspectionOverallResult:
    non_conformities, observations = calculate_checklist_counts(checklist_items)
    if non_conformities >= 3:
        return InspectionOverallResult.critical_non_conformance
    if non_conformities >= 1:
        return InspectionOverallResult.major_non_conformance
    if observations >= 1:
        return InspectionOverallResult.minor_non_conformance
    return InspectionOverallResult.compliant


def _ensure_site_exists(db: Session, site_id: int) -> None:
    if db.get(Site, site_id) is None:
        raise InspectionSiteNotFoundError(f"Site {site_id} was not found")


def _ensure_inspector_exists(db: Session, inspector_user_id: int) -> None:
    if db.get(User, inspector_user_id) is None:
        raise InspectionInspectorNotFoundError(f"User {inspector_user_id} was not found")


def _get_hazards(db: Session, hazard_ids: list[int]) -> list[Hazard]:
    if not hazard_ids:
        return []
    unique_hazard_ids = sorted(set(hazard_ids))
    hazards = list(db.scalars(select(Hazard).where(Hazard.id.in_(unique_hazard_ids))).all())
    if len(hazards) != len(unique_hazard_ids):
        raise InspectionHazardNotFoundError("One or more hazards were not found")
    return hazards


def _collect_linked_hazard_ids(data: dict) -> list[int]:
    linked_ids = list(data.get("linked_hazard_ids") or [])
    for item in data.get("checklist_items") or []:
        linked_hazard_id = item.get("linked_hazard_id")
        if linked_hazard_id is not None:
            linked_ids.append(linked_hazard_id)
    return linked_ids


def _dump_json_items(data: dict) -> None:
    if "checklist_items" in data and data["checklist_items"] is not None:
        data["checklist_items"] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data["checklist_items"]
        ]
    if "attachments_metadata" in data and data["attachments_metadata"] is not None:
        data["attachments_metadata"] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data["attachments_metadata"]
        ]


def list_inspections(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[InspectionStatus] = None,
    overall_result: Optional[InspectionOverallResult] = None,
    site_id: Optional[int] = None,
    inspector_user_id: Optional[int] = None,
    inspection_type: Optional[str] = None,
) -> dict:
    statement: Select[tuple[Inspection]] = select(Inspection)
    if status is not None:
        statement = statement.where(Inspection.status == status)
    if overall_result is not None:
        statement = statement.where(Inspection.overall_result == overall_result)
    if site_id is not None:
        statement = statement.where(Inspection.site_id == site_id)
    if inspector_user_id is not None:
        statement = statement.where(Inspection.inspector_user_id == inspector_user_id)
    if inspection_type is not None:
        statement = statement.where(Inspection.inspection_type == inspection_type)

    statement = statement.order_by(Inspection.inspection_date.desc(), Inspection.id.desc())
    items, total = paginate(db, statement, skip=skip, limit=limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


def get_inspection(db: Session, inspection_id: int) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise InspectionNotFoundError(f"Inspection {inspection_id} was not found")
    return inspection


def create_inspection(db: Session, inspection_in: InspectionCreate, *, actor_id: Optional[int] = None) -> Inspection:
    data = inspection_in.model_dump()
    linked_hazard_ids = data.pop("linked_hazard_ids", [])
    _dump_json_items(data)
    _ensure_site_exists(db, data["site_id"])
    _ensure_inspector_exists(db, data["inspector_user_id"])
    hazards = _get_hazards(db, linked_hazard_ids + _collect_linked_hazard_ids(data))

    non_conformities, observations = calculate_checklist_counts(data["checklist_items"])
    data["number_of_non_conformities"] = non_conformities
    data["number_of_observations"] = observations
    if data.get("overall_result") is None:
        data["overall_result"] = derive_overall_result(data["checklist_items"])

    inspection = Inspection(**data, linked_hazards=hazards)
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="inspection.create",
        resource_type="inspection",
        resource_id=inspection.id,
        details={"status": inspection.status.value, "overall_result": inspection.overall_result.value},
    )
    return inspection


def update_inspection(
    db: Session,
    inspection: Inspection,
    inspection_in: InspectionUpdate,
    *,
    actor_id: Optional[int] = None,
) -> Inspection:
    update_data = inspection_in.model_dump(exclude_unset=True)
    linked_hazard_ids = update_data.pop("linked_hazard_ids", None)
    _dump_json_items(update_data)

    if "site_id" in update_data:
        _ensure_site_exists(db, update_data["site_id"])
    if "inspector_user_id" in update_data:
        _ensure_inspector_exists(db, update_data["inspector_user_id"])

    hazard_ids_to_validate = []
    if linked_hazard_ids is not None:
        hazard_ids_to_validate.extend(linked_hazard_ids)
    hazard_ids_to_validate.extend(_collect_linked_hazard_ids(update_data))
    hazards = _get_hazards(db, hazard_ids_to_validate)

    previous_status = inspection.status
    for field, value in update_data.items():
        setattr(inspection, field, value)

    if linked_hazard_ids is not None:
        inspection.linked_hazards = _get_hazards(db, linked_hazard_ids)
    elif hazards:
        existing_by_id = {hazard.id: hazard for hazard in inspection.linked_hazards}
        for hazard in hazards:
            existing_by_id[hazard.id] = hazard
        inspection.linked_hazards = list(existing_by_id.values())

    if "checklist_items" in update_data:
        non_conformities, observations = calculate_checklist_counts(inspection.checklist_items)
        inspection.number_of_non_conformities = non_conformities
        inspection.number_of_observations = observations
        if "overall_result" not in update_data:
            inspection.overall_result = derive_overall_result(inspection.checklist_items)

    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="inspection.update",
        resource_type="inspection",
        resource_id=inspection.id,
        details={"updated_fields": sorted(update_data.keys()) + (["linked_hazard_ids"] if linked_hazard_ids is not None else [])},
    )
    if "status" in update_data and inspection.status != previous_status:
        write_audit_log(
            db,
            actor_id=actor_id,
            action="inspection.status_transition",
            resource_type="inspection",
            resource_id=inspection.id,
            details={"from": previous_status.value, "to": inspection.status.value},
        )
    return inspection
