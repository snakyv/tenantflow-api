from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


SUPPORTED_EVENTS = {
    "project.created",
    "project.updated",
    "project.deleted",
    "task.created",
    "task.updated",
    "task.completed",
    "task.deleted",
    "member.invited",
}


class WebhookCreate(BaseModel):
    url: AnyHttpUrl
    events: list[str] = Field(min_length=1, max_length=20)


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: list[str]
    is_active: bool
    signing_secret: str | None = None


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    event_id: UUID
    endpoint_id: UUID
    event_type: str
    state: str
    attempt_count: int
    response_status: int | None
    last_error: str | None
    next_retry_at: datetime | None
    created_at: datetime
    updated_at: datetime
