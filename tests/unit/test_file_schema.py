from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.files.schemas import PresignUploadRequest


def _base() -> dict[str, object]:
    return {
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1024,
    }


def test_upload_requires_exactly_one_parent() -> None:
    with pytest.raises(ValidationError):
        PresignUploadRequest(**_base())

    with pytest.raises(ValidationError):
        PresignUploadRequest(**_base(), project_id=uuid4(), task_id=uuid4())


def test_upload_accepts_project_parent() -> None:
    payload = PresignUploadRequest(**_base(), project_id=uuid4())
    assert payload.project_id is not None
    assert payload.task_id is None
