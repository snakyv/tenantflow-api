from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.modules.webhooks.schemas import WebhookCreate
from app.modules.webhooks.service import create_webhook_endpoint, decrypt_signing_secret


async def test_webhook_secret_is_not_stored_in_plaintext() -> None:
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    endpoint, secret = await create_webhook_endpoint(
        session,
        organization_id=uuid4(),
        user_id=uuid4(),
        payload=WebhookCreate(url="https://example.com/hook", events=["project.created"]),
    )
    assert secret.startswith("whsec_")
    assert endpoint.signing_secret_encrypted != secret
    assert endpoint.signing_secret_hash != secret
    assert decrypt_signing_secret(endpoint.signing_secret_encrypted) == secret


async def test_unknown_webhook_event_is_rejected() -> None:
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    try:
        await create_webhook_endpoint(
            session,
            organization_id=uuid4(),
            user_id=uuid4(),
            payload=WebhookCreate(url="https://example.com/hook", events=["unknown.event"]),
        )
    except ValueError as exc:
        assert "Unsupported events" in str(exc)
    else:
        raise AssertionError("unknown event was accepted")
