from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.pagination import decode_cursor, encode_cursor
from app.core.permissions import Permission
from app.db.models import Project
from app.db.session import get_session
from app.modules.projects.schemas import ProjectCreate, ProjectPage, ProjectResponse, ProjectUpdate
from app.modules.projects.service import create_project, delete_project, get_project, update_project

router = APIRouter(prefix="/organizations/{organization_id}/projects", tags=["Projects"])


def to_response(project: Project) -> ProjectResponse:
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create(
    organization_id: UUID,
    payload: ProjectCreate,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await create_project(session, organization_id, context.user, payload)
    return to_response(project)


@router.get("", response_model=ProjectPage)
async def list_projects(
    organization_id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    _: OrganizationContext = Depends(require_permission(Permission.PROJECT_READ)),
    session: AsyncSession = Depends(get_session),
) -> ProjectPage:
    statement = select(Project).where(Project.organization_id == organization_id)
    if cursor:
        try:
            position = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        statement = statement.where(
            or_(
                Project.created_at < position.created_at,
                and_(
                    Project.created_at == position.created_at,
                    Project.id < position.entity_id,
                ),
            )
        )
    rows = (
        await session.scalars(
            statement.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return ProjectPage(items=[to_response(project) for project in page_rows], next_cursor=next_cursor)


@router.get("/{project_id}", response_model=ProjectResponse)
async def retrieve(
    organization_id: UUID,
    project_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.PROJECT_READ)),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    return to_response(await get_project(session, organization_id, project_id))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update(
    organization_id: UUID,
    project_id: UUID,
    payload: ProjectUpdate,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await update_project(session, organization_id, project_id, context.user, payload)
    return to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    organization_id: UUID,
    project_id: UUID,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_DELETE)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await delete_project(session, organization_id, project_id, context.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
