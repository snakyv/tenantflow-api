from uuid import uuid4

import httpx
import pytest

from app.integrations.email import send_invitation_email
from app.integrations.storage import create_s3_client, presign_get, presign_put

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_presigned_minio_upload_and_download_round_trip() -> None:
    object_key = f"integration/{uuid4().hex}.txt"
    body = b"tenantflow-minio-integration"
    put_url = presign_put(object_key, "text/plain", expires_seconds=60)
    get_url = presign_get(object_key, expires_seconds=60)

    async with httpx.AsyncClient(timeout=10) as client:
        uploaded = await client.put(
            put_url,
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        assert uploaded.status_code in {200, 204}, uploaded.text

        downloaded = await client.get(get_url)
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content == body

    s3 = create_s3_client()
    from app.core.config import get_settings

    s3.delete_object(Bucket=get_settings().minio_bucket, Key=object_key)


def test_mailpit_accepts_invitation_email() -> None:
    suffix = uuid4().hex[:12]
    recipient = f"mailpit-{suffix}@example.com"
    organization_name = f"Mailpit Integration {suffix}"
    token = f"invite-{uuid4().hex}"

    send_invitation_email(recipient, organization_name, token)

    response = httpx.get("http://127.0.0.1:8025/api/v1/messages", timeout=10)
    assert response.status_code == 200, response.text
    mailbox = response.text
    assert recipient in mailbox
    assert organization_name in mailbox
