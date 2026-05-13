from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.asset_register import AssetRegisterItem
from app.models.audit_management import AuditManagementRecord
from app.models.behaviour_observation import BehaviourObservation
from app.models.contractor import ContractorRecord
from app.models.corrective_action import CorrectiveAction
from app.models.document_control import DocumentControlRecord
from app.models.emergency_drill import EmergencyDrillRecord
from app.models.hazard import Hazard
from app.models.incident import Incident
from app.models.incident_investigation import IncidentInvestigation
from app.models.inspection import Inspection
from app.models.jsa import JobSafetyAnalysis
from app.models.legal_compliance import LegalComplianceItem
from app.models.medical_surveillance import MedicalSurveillanceRecord
from app.models.permit import PermitToWork
from app.models.safety_communication import SafetyCommunication
from app.models.training import ComplianceAcknowledgement, TrainingRecord
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.services.audit_service import write_audit_log
from app.services.rbac import (
    Permission,
    ROLE_ADMIN,
    ROLE_OHS_MANAGER,
    ensure_permission,
    ensure_site_access,
    has_any_role,
    has_permission,
)

UPLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_FILE_TYPES: dict[str, set[str]] = {
    "jpg": {"image/jpeg", "image/pjpeg"},
    "jpeg": {"image/jpeg", "image/pjpeg"},
    "png": {"image/png", "image/x-png"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
}
ENTITY_MODELS = {
    AttachmentEntityType.incident: Incident,
    AttachmentEntityType.hazard: Hazard,
    AttachmentEntityType.inspection: Inspection,
    AttachmentEntityType.corrective_action: CorrectiveAction,
    AttachmentEntityType.permit: PermitToWork,
    AttachmentEntityType.training: TrainingRecord,
    AttachmentEntityType.compliance_acknowledgement: ComplianceAcknowledgement,
    AttachmentEntityType.safety_communication: SafetyCommunication,
    AttachmentEntityType.behaviour_observation: BehaviourObservation,
    AttachmentEntityType.incident_investigation: IncidentInvestigation,
    AttachmentEntityType.legal_compliance: LegalComplianceItem,
    AttachmentEntityType.jsa: JobSafetyAnalysis,
    AttachmentEntityType.contractor: ContractorRecord,
    AttachmentEntityType.asset_register: AssetRegisterItem,
    AttachmentEntityType.medical_surveillance: MedicalSurveillanceRecord,
    AttachmentEntityType.emergency_drill: EmergencyDrillRecord,
    AttachmentEntityType.document_control: DocumentControlRecord,
    AttachmentEntityType.audit_management: AuditManagementRecord,
}


@dataclass
class AttachmentDownload:
    attachment: Attachment
    file_path: Path


def _not_authorized(detail: str = "Not authorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _attachment_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")


def _entity_not_found(entity_type: AttachmentEntityType) -> HTTPException:
    label = entity_type.value.replace("_", " ")
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label.title()} not found")


def _normalize_filename(filename: Optional[str]) -> str:
    candidate = Path(filename or "upload").name.strip().replace("\x00", "")
    return candidate[:255] or "upload"


def _resolve_destination(entity_type: AttachmentEntityType, entity_id: int, stored_filename: str) -> tuple[Path, str]:
    relative_storage_path = Path(entity_type.value) / str(entity_id) / stored_filename
    upload_root = settings.upload_root_path.resolve()
    destination = (upload_root / relative_storage_path).resolve()
    if not destination.is_relative_to(upload_root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination, relative_storage_path.as_posix()


def _validate_upload(upload_file: UploadFile) -> tuple[str, str, str]:
    original_filename = _normalize_filename(upload_file.filename)
    extension = Path(original_filename).suffix.lower().lstrip(".")
    allowed_content_types = ALLOWED_FILE_TYPES.get(extension)
    if not allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type",
        )

    content_type = (upload_file.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported content type",
        )

    return original_filename, extension, content_type


def _get_entity(db: Session, entity_type: AttachmentEntityType, entity_id: int):
    entity = db.get(ENTITY_MODELS[entity_type], entity_id)
    if entity is None:
        raise _entity_not_found(entity_type)
    return entity


def _ensure_training_access(user: User, record: TrainingRecord, *, write: bool) -> None:
    if write:
        if has_permission(user, Permission.TRAINING_MANAGE):
            ensure_site_access(user, record.site_id)
            return
        if has_permission(user, Permission.TRAINING_SELF_UPDATE) and record.assigned_to_user_id == user.id:
            return
        raise _not_authorized()

    if has_permission(user, Permission.TRAINING_VIEW_ALL):
        ensure_site_access(user, record.site_id)
        return
    if has_permission(user, Permission.TRAINING_SELF_VIEW) and record.assigned_to_user_id == user.id:
        return
    raise _not_authorized()


def _ensure_compliance_access(user: User, record: ComplianceAcknowledgement, *, write: bool) -> None:
    if write:
        if has_permission(user, Permission.COMPLIANCE_MANAGE):
            ensure_site_access(user, record.site_id)
            return
        if has_permission(user, Permission.COMPLIANCE_SELF_UPDATE) and record.assigned_to_user_id == user.id:
            return
        raise _not_authorized()

    if has_permission(user, Permission.COMPLIANCE_VIEW_ALL):
        ensure_site_access(user, record.site_id)
        return
    if has_permission(user, Permission.COMPLIANCE_SELF_VIEW) and record.assigned_to_user_id == user.id:
        return
    raise _not_authorized()


def _ensure_corrective_action_access(user: User, action: CorrectiveAction, *, write: bool) -> None:
    ensure_site_access(user, action.site_id)
    if write:
        if has_permission(user, Permission.CORRECTIVE_ACTIONS_VERIFY):
            return
        if has_permission(user, Permission.CORRECTIVE_ACTIONS_EDIT):
            return
        if has_permission(user, Permission.CORRECTIVE_ACTIONS_SELF_UPDATE) and action.assigned_to_user_id == user.id:
            return
        raise _not_authorized()

    ensure_permission(user, Permission.CORRECTIVE_ACTIONS_VIEW)


def _ensure_permit_access(user: User, permit: PermitToWork, *, write: bool) -> None:
    ensure_site_access(user, permit.site_id)
    if write:
        if has_permission(user, Permission.PERMITS_APPROVE):
            return
        if has_permission(user, Permission.PERMITS_MANAGE):
            return
        if has_permission(user, Permission.PERMITS_REQUEST) and permit.requested_by_user_id == user.id:
            return
        raise _not_authorized()

    ensure_permission(user, Permission.PERMITS_VIEW)


def _ensure_behaviour_observation_access(
    user: User,
    observation: BehaviourObservation,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, observation.site_id)
    if write:
        ensure_permission(user, Permission.BEHAVIOUR_OBSERVATIONS_EDIT)
        return
    ensure_permission(user, Permission.BEHAVIOUR_OBSERVATIONS_VIEW)


def _ensure_safety_communication_access(
    user: User,
    communication: SafetyCommunication,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, communication.site_id)
    if write:
        ensure_permission(user, Permission.SAFETY_COMMUNICATIONS_EDIT)
        return
    ensure_permission(user, Permission.SAFETY_COMMUNICATIONS_VIEW)


def _ensure_investigation_access(
    user: User,
    investigation: IncidentInvestigation,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, investigation.site_id)
    ensure_permission(
        user,
        Permission.INVESTIGATIONS_EDIT if write else Permission.INVESTIGATIONS_VIEW,
    )


def _ensure_legal_compliance_access(
    user: User,
    item: LegalComplianceItem,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, item.site_id)
    ensure_permission(
        user,
        Permission.LEGAL_COMPLIANCE_EDIT if write else Permission.LEGAL_COMPLIANCE_VIEW,
    )


def _ensure_jsa_access(
    user: User,
    jsa: JobSafetyAnalysis,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, jsa.site_id)
    ensure_permission(user, Permission.JSA_EDIT if write else Permission.JSA_VIEW)


def _ensure_contractor_access(
    user: User,
    contractor: ContractorRecord,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, contractor.site_id)
    ensure_permission(
        user,
        Permission.CONTRACTORS_EDIT if write else Permission.CONTRACTORS_VIEW,
    )


def _ensure_asset_access(
    user: User,
    asset: AssetRegisterItem,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, asset.site_id)
    ensure_permission(user, Permission.ASSETS_EDIT if write else Permission.ASSETS_VIEW)


def _ensure_medical_surveillance_access(
    user: User,
    record: MedicalSurveillanceRecord,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, record.site_id)
    ensure_permission(
        user,
        Permission.MEDICAL_SURVEILLANCE_EDIT if write else Permission.MEDICAL_SURVEILLANCE_VIEW,
    )


def _ensure_emergency_drill_access(
    user: User,
    drill: EmergencyDrillRecord,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, drill.site_id)
    ensure_permission(
        user,
        Permission.EMERGENCY_DRILLS_EDIT if write else Permission.EMERGENCY_DRILLS_VIEW,
    )


def _ensure_document_access(
    user: User,
    document: DocumentControlRecord,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, document.site_id)
    ensure_permission(user, Permission.DOCUMENTS_EDIT if write else Permission.DOCUMENTS_VIEW)


def _ensure_audit_management_access(
    user: User,
    audit: AuditManagementRecord,
    *,
    write: bool,
) -> None:
    ensure_site_access(user, audit.site_id)
    ensure_permission(user, Permission.AUDITS_EDIT if write else Permission.AUDITS_VIEW)


def ensure_entity_access(user: User, entity_type: AttachmentEntityType, entity, *, write: bool) -> None:
    if entity_type == AttachmentEntityType.incident:
        ensure_permission(user, Permission.INCIDENTS_EDIT if write else Permission.INCIDENTS_VIEW)
        ensure_site_access(user, entity.site_id)
        return
    if entity_type == AttachmentEntityType.hazard:
        ensure_permission(user, Permission.HAZARDS_EDIT if write else Permission.HAZARDS_VIEW)
        ensure_site_access(user, entity.site_id)
        return
    if entity_type == AttachmentEntityType.inspection:
        ensure_permission(user, Permission.INSPECTIONS_EDIT if write else Permission.INSPECTIONS_VIEW)
        ensure_site_access(user, entity.site_id)
        return
    if entity_type == AttachmentEntityType.corrective_action:
        _ensure_corrective_action_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.permit:
        _ensure_permit_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.training:
        _ensure_training_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.compliance_acknowledgement:
        _ensure_compliance_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.safety_communication:
        _ensure_safety_communication_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.behaviour_observation:
        _ensure_behaviour_observation_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.incident_investigation:
        _ensure_investigation_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.legal_compliance:
        _ensure_legal_compliance_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.jsa:
        _ensure_jsa_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.contractor:
        _ensure_contractor_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.asset_register:
        _ensure_asset_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.medical_surveillance:
        _ensure_medical_surveillance_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.emergency_drill:
        _ensure_emergency_drill_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.document_control:
        _ensure_document_access(user, entity, write=write)
        return
    if entity_type == AttachmentEntityType.audit_management:
        _ensure_audit_management_access(user, entity, write=write)
        return
    raise _not_authorized()


def _attachment_query(entity_type: AttachmentEntityType, entity_id: int):
    return (
        select(Attachment)
        .where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
        )
        .order_by(Attachment.created_at.desc(), Attachment.id.desc())
    )


def _serialize_attachment(attachment: Attachment) -> AttachmentRead:
    return AttachmentRead.model_validate(
        {
            "id": attachment.id,
            "entity_type": attachment.entity_type,
            "entity_id": attachment.entity_id,
            "uploaded_by_user_id": attachment.uploaded_by_user_id,
            "uploaded_by_name": attachment.uploaded_by.full_name if attachment.uploaded_by else None,
            "original_filename": attachment.original_filename,
            "content_type": attachment.content_type,
            "file_size": attachment.file_size,
            "description": attachment.description,
            "created_at": attachment.created_at,
            "download_url": f"{settings.API_V1_STR}/attachments/{attachment.id}/download",
        }
    )


def get_attachment_list_for_entity(
    db: Session,
    entity_type: AttachmentEntityType,
    entity_id: int,
) -> list[AttachmentRead]:
    attachments = db.scalars(_attachment_query(entity_type, entity_id)).all()
    return [_serialize_attachment(attachment) for attachment in attachments]


def hydrate_entity_attachments(db: Session, entity_type: AttachmentEntityType, entity):
    setattr(entity, "attachments", get_attachment_list_for_entity(db, entity_type, entity.id))
    return entity


async def create_attachment(
    db: Session,
    *,
    entity_type: AttachmentEntityType,
    entity_id: int,
    upload_file: UploadFile,
    description: Optional[str],
    current_user: User,
) -> AttachmentRead:
    entity = _get_entity(db, entity_type, entity_id)
    ensure_entity_access(current_user, entity_type, entity, write=True)

    original_filename, extension, content_type = _validate_upload(upload_file)
    stored_filename = f"{uuid4().hex}.{extension}"
    destination, storage_path = _resolve_destination(entity_type, entity_id, stored_filename)

    file_size = 0
    try:
        with destination.open("wb") as output_file:
            while True:
                chunk = await upload_file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > settings.ATTACHMENT_MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            "Attachment exceeds the maximum allowed size of "
                            f"{settings.ATTACHMENT_MAX_FILE_SIZE_BYTES} bytes"
                        ),
                    )
                output_file.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()

    attachment = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by_user_id=current_user.id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        file_size=file_size,
        storage_path=storage_path,
        description=description.strip() if description and description.strip() else None,
    )
    try:
        db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise

    db.refresh(attachment)
    write_audit_log(
        db,
        actor_id=current_user.id,
        action="attachment.upload",
        resource_type="attachment",
        resource_id=attachment.id,
        details={"entity_type": entity_type.value, "entity_id": entity_id},
    )
    return _serialize_attachment(attachment)


def list_attachments(
    db: Session,
    *,
    entity_type: AttachmentEntityType,
    entity_id: int,
    current_user: User,
) -> list[AttachmentRead]:
    entity = _get_entity(db, entity_type, entity_id)
    ensure_entity_access(current_user, entity_type, entity, write=False)
    return get_attachment_list_for_entity(db, entity_type, entity_id)


def get_attachment_download(
    db: Session,
    *,
    attachment_id: int,
    current_user: User,
) -> AttachmentDownload:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise _attachment_not_found()

    entity = _get_entity(db, attachment.entity_type, attachment.entity_id)
    ensure_entity_access(current_user, attachment.entity_type, entity, write=False)

    file_path = (settings.upload_root_path / attachment.storage_path).resolve()
    upload_root = settings.upload_root_path.resolve()
    if not file_path.is_relative_to(upload_root) or not file_path.exists():
        raise _attachment_not_found()

    return AttachmentDownload(attachment=attachment, file_path=file_path)


def delete_attachment(
    db: Session,
    *,
    attachment_id: int,
    current_user: User,
) -> None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise _attachment_not_found()

    entity = _get_entity(db, attachment.entity_type, attachment.entity_id)
    ensure_entity_access(current_user, attachment.entity_type, entity, write=False)
    if attachment.uploaded_by_user_id != current_user.id and not has_any_role(
        current_user,
        ROLE_ADMIN,
        ROLE_OHS_MANAGER,
    ):
        raise _not_authorized("Not authorized to delete this attachment")

    file_path = (settings.upload_root_path / attachment.storage_path).resolve()
    upload_root = settings.upload_root_path.resolve()
    if file_path.is_relative_to(upload_root):
        file_path.unlink(missing_ok=True)

    db.delete(attachment)
    db.commit()
    write_audit_log(
        db,
        actor_id=current_user.id,
        action="attachment.delete",
        resource_type="attachment",
        resource_id=attachment_id,
        details={"entity_type": attachment.entity_type.value, "entity_id": attachment.entity_id},
    )


def get_attachment_report_rows(
    db: Session,
    *,
    entity_type: AttachmentEntityType,
    entity_id: int,
) -> list[dict[str, object]]:
    attachments = db.scalars(_attachment_query(entity_type, entity_id)).all()
    return [
        {
            "file_name": attachment.original_filename,
            "content_type": attachment.content_type,
            "file_size": attachment.file_size,
            "description": attachment.description,
            "uploaded_by_user_id": attachment.uploaded_by_user_id,
            "created_at": attachment.created_at.isoformat(),
        }
        for attachment in attachments
    ]
