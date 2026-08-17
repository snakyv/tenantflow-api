from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.pagination import decode_cursor, encode_cursor
from app.core.permissions import Permission
from app.db.models import Task
from app.db.session import get_session
from app.modules.tasks.schemas import TaskCreate, TaskPage, TaskResponse, TaskUpdate
from app.modules.tasks.service import create_task, delete_task, get_task, update_task

router = APIRouter(prefix="/organizations/{organization_id}/tasks", tags=["Tasks"])


def to_response(task: Task) -> TaskResponse:
    return TaskResponse.model_validate(task, from_attributes=True)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create(
    organization_id: UUID,
    payload: TaskCreate,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    task = await create_task(session, organization_id, context.user, payload)
    return to_response(task)


@router.get("", response_model=TaskPage)
async def list_tasks(
    organization_id: UUID,
    project_id: UUID | None = None,
    status_filter: Literal["todo", "in_progress", "done", "cancelled"] | None = Query(
        default=None,
        alias="status",
    ),
    assignee_id: UUID | None = None,
    priority: Literal["low", "medium", "high", "urgent"] | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    _: OrganizationContext = Depends(require_permission(Permission.PROJECT_READ)),
    session: AsyncSession = Depends(get_session),
) -> TaskPage:
    statement = select(Task).where(Task.organization_id == organization_id)
    if project_id:
        statement = statement.where(Task.project_id == project_id)
    if status_filter:
        statement = statement.where(Task.status == status_filter)
    if assignee_id:
        statement = statement.where(Task.assignee_id == assignee_id)
    if priority:
        statement = statement.where(Task.priority == priority)
    if cursor:
        try:
            position = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        statement = statement.where(
            or_(
                Task.created_at < position.created_at,
                and_(Task.created_at == position.created_at, Task.id < position.entity_id),
            )
        )
    rows = (
        await session.scalars(
            statement.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return TaskPage(items=[to_response(task) for task in page_rows], next_cursor=next_cursor)


@router.get("/{task_id}", response_model=TaskResponse)
async def retrieve(
    organization_id: UUID,
    task_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.PROJECT_READ)),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    return to_response(await get_task(session, organization_id, task_id))


@router.patch("/{task_id}", response_model=TaskResponse)
async def update(
    organization_id: UUID,
    task_id: UUID,
    payload: TaskUpdate,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    task = await update_task(session, organization_id, task_id, context.user, payload)
    return to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    organization_id: UUID,
    task_id: UUID,
    context: OrganizationContext = Depends(require_permission(Permission.PROJECT_WRITE)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await delete_task(session, organization_id, task_id, context.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
