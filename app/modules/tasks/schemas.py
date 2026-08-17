from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|urgent)$")
    assignee_id: UUID | None = None
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern=r"^(todo|in_progress|done|cancelled)$")
    priority: str | None = Field(default=None, pattern=r"^(low|medium|high|urgent)$")
    assignee_id: UUID | None = None
    due_at: datetime | None = None


class TaskResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    assignee_id: UUID | None
    created_by: UUID
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[TaskResponse]
    next_cursor: str | None = None
