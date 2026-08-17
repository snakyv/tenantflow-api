from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import OrganizationMembership, Project, Task, User
from app.modules.audit.service import record_audit
from app.modules.webhooks.events import emit_event
from app.modules.tasks.schemas import TaskCreate, TaskUpdate


async def _validate_project(session: AsyncSession, organization_id: UUID, project_id: UUID) -> None:
    exists = await session.scalar(
        select(Project.id).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if exists is None:
        raise NotFoundError("PROJECT_NOT_FOUND", "Project was not found")


async def _validate_assignee(session: AsyncSession, organization_id: UUID, user_id: UUID | None) -> None:
    if user_id is None:
        return
    exists = await session.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if exists is None:
        raise ConflictError("INVALID_ASSIGNEE", "Assignee must belong to this organization")


async def get_task(session: AsyncSession, organization_id: UUID, task_id: UUID) -> Task:
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.organization_id == organization_id))
    if task is None:
        raise NotFoundError("TASK_NOT_FOUND", "Task was not found")
    return task


async def create_task(session: AsyncSession, organization_id: UUID, user: User, payload: TaskCreate) -> Task:
    await _validate_project(session, organization_id, payload.project_id)
    await _validate_assignee(session, organization_id, payload.assignee_id)
    task = Task(
        organization_id=organization_id,
        project_id=payload.project_id,
        title=payload.title.strip(),
        description=payload.description,
        priority=payload.priority,
        status="todo",
        assignee_id=payload.assignee_id,
        due_at=payload.due_at,
        created_by=user.id,
    )
    session.add(task)
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="task.created",
        entity_type="task",
        entity_id=task.id,
    )
    await emit_event(
        session, organization_id=organization_id, event_type="task.created",
        payload={"task_id": str(task.id), "project_id": str(task.project_id), "title": task.title},
    )
    return task


async def update_task(
    session: AsyncSession, organization_id: UUID, task_id: UUID, user: User, payload: TaskUpdate
) -> Task:
    task = await get_task(session, organization_id, task_id)
    values = payload.model_dump(exclude_unset=True)
    if "assignee_id" in values:
        await _validate_assignee(session, organization_id, values["assignee_id"])
    for field, value in values.items():
        setattr(task, field, value)
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="task.updated",
        entity_type="task",
        entity_id=task.id,
    )
    event_type = "task.completed" if task.status == "done" else "task.updated"
    await emit_event(
        session, organization_id=organization_id, event_type=event_type,
        payload={"task_id": str(task.id), "project_id": str(task.project_id), "status": task.status},
    )
    return task


async def delete_task(
    session: AsyncSession, organization_id: UUID, task_id: UUID, user: User
) -> None:
    task = await get_task(session, organization_id, task_id)
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="task.deleted",
        entity_type="task",
        entity_id=task.id,
        metadata={"title": task.title, "project_id": str(task.project_id)},
    )
    await emit_event(
        session,
        organization_id=organization_id,
        event_type="task.deleted",
        payload={"task_id": str(task.id), "project_id": str(task.project_id)},
    )
    await session.delete(task)
