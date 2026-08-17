from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import Project, User
from app.modules.audit.service import record_audit
from app.modules.webhooks.events import emit_event
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate


async def get_project(session: AsyncSession, organization_id: UUID, project_id: UUID) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
    )
    if project is None:
        raise NotFoundError("PROJECT_NOT_FOUND", "Project was not found")
    return project


async def create_project(
    session: AsyncSession, organization_id: UUID, user: User, payload: ProjectCreate
) -> Project:
    project = Project(
        organization_id=organization_id,
        name=payload.name.strip(),
        description=payload.description,
        status="active",
        created_by=user.id,
    )
    session.add(project)
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
    )
    await emit_event(
        session, organization_id=organization_id, event_type="project.created",
        payload={"project_id": str(project.id), "name": project.name},
    )
    return project


async def update_project(
    session: AsyncSession, organization_id: UUID, project_id: UUID, user: User, payload: ProjectUpdate
) -> Project:
    project = await get_project(session, organization_id, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="project.updated",
        entity_type="project",
        entity_id=project.id,
    )
    await emit_event(
        session, organization_id=organization_id, event_type="project.updated",
        payload={"project_id": str(project.id), "status": project.status},
    )
    return project


async def delete_project(
    session: AsyncSession, organization_id: UUID, project_id: UUID, user: User
) -> None:
    project = await get_project(session, organization_id, project_id)
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=user.id,
        action="project.deleted",
        entity_type="project",
        entity_id=project.id,
        metadata={"name": project.name},
    )
    await emit_event(
        session,
        organization_id=organization_id,
        event_type="project.deleted",
        payload={"project_id": str(project.id), "name": project.name},
    )
    await session.delete(project)
