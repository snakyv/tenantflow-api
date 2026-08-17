from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PresignUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    project_id: UUID | None = None
    task_id: UUID | None = None

    @model_validator(mode="after")
    def require_exactly_one_parent(self) -> Self:
        if (self.project_id is None) == (self.task_id is None):
            raise ValueError("Exactly one of project_id or task_id must be provided")
        return self


class PresignUploadResponse(BaseModel):
    attachment_id: UUID
    object_key: str
    upload_url: str
    expires_in: int = 900


class DownloadResponse(BaseModel):
    download_url: str
    expires_in: int = 900
