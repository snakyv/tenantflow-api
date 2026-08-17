import base64
import hashlib
import secrets
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import WebhookEndpoint
from app.modules.webhooks.schemas import SUPPORTED_EVENTS, WebhookCreate
from app.modules.webhooks.target_validation import validate_webhook_target


def _fernet() -> Fernet:
    # A dedicated encryption key should be supplied in production. The deterministic development
    # derivation keeps local setup friction low without storing a plaintext signing secret.
    settings = get_settings()
    secret = settings.webhook_encryption_key or settings.jwt_secret
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def decrypt_signing_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


async def create_webhook_endpoint(
    session: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    payload: WebhookCreate,
) -> tuple[WebhookEndpoint, str]:
    unknown = set(payload.events) - SUPPORTED_EVENTS
    if unknown:
        raise ValueError(f"Unsupported events: {', '.join(sorted(unknown))}")
    await validate_webhook_target(str(payload.url))
    secret = f"whsec_{secrets.token_urlsafe(32)}"
    endpoint = WebhookEndpoint(
        organization_id=organization_id,
        url=str(payload.url),
        signing_secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        signing_secret_encrypted=_fernet().encrypt(secret.encode()).decode(),
        events=sorted(set(payload.events)),
        is_active=True,
        created_by=user_id,
    )
    session.add(endpoint)
    await session.flush()
    return endpoint, secret
