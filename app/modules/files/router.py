from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.db.models import Attachment, Project, Task
from app.db.session import get_session
from app.integrations.storage import build_object_key, presign_get, presign_put, validate_upload
from app.modules.files.schemas import DownloadResponse, PresignUploadRequest, PresignUploadResponse

router = APIRouter(prefix="/organizations/{organization_id}/files", tags=["Files"])


@router.post("/presign", response_model=PresignUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_upload(
    organization_id: UUID,
    payload: PresignUploadRequest,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> PresignUploadResponse:
    try:
        validate_upload(payload.content_type, payload.size_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.project_id and not await session.scalar(
        select(Project.id).where(Project.id == payload.project_id, Project.organization_id == organization_id)
    ):
        raise NotFoundError("PROJECT_NOT_FOUND", "Project was not found")
    if payload.task_id and not await session.scalar(
        select(Task.id).where(Task.id == payload.task_id, Task.organization_id == organization_id)
    ):
        raise NotFoundError("TASK_NOT_FOUND", "Task was not found")

    object_key = build_object_key(organization_id, payload.filename)
    attachment = Attachment(
        organization_id=organization_id,
        project_id=payload.project_id,
        task_id=payload.task_id,
        object_key=object_key,
        original_filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        created_by=context.user.id,
    )
    session.add(attachment)
    await session.flush()
    return PresignUploadResponse(
        attachment_id=attachment.id,
        object_key=object_key,
        upload_url=presign_put(object_key, payload.content_type),
    )


@router.get("/{attachment_id}/download", response_model=DownloadResponse)
async def get_download(
    organization_id: UUID,
    attachment_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.PROJECT_READ)),
    session: AsyncSession = Depends(get_session),
) -> DownloadResponse:
    attachment = await session.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.organization_id == organization_id,
        )
    )
    if attachment is None:
        raise NotFoundError("ATTACHMENT_NOT_FOUND", "Attachment was not found")
    return DownloadResponse(download_url=presign_get(attachment.object_key))
