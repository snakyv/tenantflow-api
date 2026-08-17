from uuid import uuid4

import pytest

from app.integrations.storage import MAX_FILE_SIZE, build_object_key, validate_upload


def test_storage_object_key_is_tenant_scoped_and_does_not_use_raw_filename() -> None:
    organization_id = uuid4()
    key = build_object_key(organization_id, "../../invoice.PDF")
    assert key.startswith(f"organizations/{organization_id}/")
    assert "invoice" not in key
    assert key.endswith(".pdf")


def test_rejects_unsupported_content_type() -> None:
    with pytest.raises(ValueError):
        validate_upload("application/x-msdownload", 100)


def test_rejects_oversized_upload() -> None:
    with pytest.raises(ValueError):
        validate_upload("application/pdf", MAX_FILE_SIZE + 1)
