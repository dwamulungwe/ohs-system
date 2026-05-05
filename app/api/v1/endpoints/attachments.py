from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.attachment import AttachmentEntityType
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.services.attachment_service import (
    create_attachment,
    delete_attachment,
    get_attachment_download,
    list_attachments,
)

router = APIRouter()


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    download = get_attachment_download(
        db,
        attachment_id=attachment_id,
        current_user=current_user,
    )
    return FileResponse(
        path=download.file_path,
        media_type=download.attachment.content_type,
        filename=download.attachment.original_filename,
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    delete_attachment(db, attachment_id=attachment_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{entity_type}/{entity_id}", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    entity_type: AttachmentEntityType,
    entity_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentRead:
    return await create_attachment(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        upload_file=file,
        description=description,
        current_user=current_user,
    )


@router.get("/{entity_type}/{entity_id}", response_model=list[AttachmentRead])
def list_entity_attachments(
    entity_type: AttachmentEntityType,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AttachmentRead]:
    return list_attachments(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        current_user=current_user,
    )
