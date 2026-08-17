import asyncio
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from celery.app.task import Task
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import (
    IdempotencyRecord,
    Invitation,
    Organization,
    RefreshToken,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.db.session import get_session_factory
from app.integrations.email import send_invitation_email
from app.modules.webhooks.service import decrypt_signing_secret
from app.modules.webhooks.signing import canonical_payload, create_signature
from app.modules.webhooks.target_validation import validate_webhook_target
from app.observability.metrics import record_background_job, record_webhook_delivery
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tenantflow.email.send_invitation", bind=True, max_retries=5)
def send_invitation_task(self: Task, invitation_id: str, raw_token: str) -> None:
    async def run() -> str:
        async with get_session_factory()() as session:
            invitation = await session.get(Invitation, UUID(invitation_id))
            if invitation is None:
                raise RuntimeError("Invitation is not committed yet")
            if invitation.status != "pending":
                return "skipped"
            organization = await session.get(Organization, invitation.organization_id)
            if organization is None:
                return "skipped"
            await asyncio.to_thread(
                send_invitation_email,
                invitation.email,
                organization.name,
                raw_token,
            )
            return "success"

    try:
        outcome = asyncio.run(run())
        asyncio.run(record_background_job("invitation_email", outcome))
    except (OSError, RuntimeError, smtplib.SMTPException) as exc:
        asyncio.run(record_background_job("invitation_email", "retry"))
        raise self.retry(exc=exc, countdown=min(300, 2 ** self.request.retries * 5)) from exc


@celery_app.task(name="tenantflow.webhooks.deliver", bind=True, max_retries=5)
def deliver_webhook_task(self: Task, delivery_id: str) -> None:
    async def run() -> str:
        async with get_session_factory()() as session:
            async with session.begin():
                delivery = await session.scalar(
                    select(WebhookDelivery)
                    .where(WebhookDelivery.id == UUID(delivery_id))
                    .with_for_update()
                )
                if delivery is None:
                    raise RuntimeError("Webhook delivery is not committed yet")
                if delivery.state in {"delivered", "dead"}:
                    return "skipped"
                endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
                if endpoint is None or not endpoint.is_active:
                    delivery.state = "dead"
                    await record_webhook_delivery("dead")
                    await record_background_job("webhook_delivery", "dead")
                    return "dead"
                try:
                    await validate_webhook_target(endpoint.url)
                except ValueError as exc:
                    delivery.state = "dead"
                    delivery.last_error = str(exc)
                    await record_webhook_delivery("dead")
                    await record_background_job("webhook_delivery", "dead")
                    return "dead"
                secret = decrypt_signing_secret(endpoint.signing_secret_encrypted)
                body = canonical_payload(delivery.payload)
                headers = {
                    "Content-Type": "application/json",
                    "X-TenantFlow-Signature": create_signature(secret, body),
                    "X-TenantFlow-Event": delivery.event_type,
                    "X-TenantFlow-Event-ID": str(delivery.event_id),
                }
                delivery.attempt_count += 1

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(endpoint.url, content=body, headers=headers)
                    response.raise_for_status()
            except httpx.HTTPError as exc:
                async with session.begin():
                    current = await session.get(
                        WebhookDelivery,
                        UUID(delivery_id),
                        with_for_update=True,
                    )
                    if current is None:
                        return "skipped"
                    current.last_error = str(exc)[:2000]
                    if current.attempt_count >= 5:
                        current.state = "dead"
                        outcome = "dead"
                    else:
                        current.state = "retrying"
                        current.next_retry_at = datetime.now(UTC) + timedelta(
                            seconds=2 ** current.attempt_count * 5
                        )
                        outcome = "retry"
                await record_webhook_delivery(outcome)
                await record_background_job("webhook_delivery", outcome)
                if outcome == "dead":
                    return "dead"
                raise
            else:
                async with session.begin():
                    current = await session.get(
                        WebhookDelivery,
                        UUID(delivery_id),
                        with_for_update=True,
                    )
                    if current is not None:
                        current.state = "delivered"
                        current.response_status = response.status_code
                        current.last_error = None
                        current.next_retry_at = None
                await record_webhook_delivery("delivered")
                await record_background_job("webhook_delivery", "success")
                return "delivered"

    try:
        outcome = asyncio.run(run())
        if outcome == "skipped":
            asyncio.run(record_webhook_delivery("skipped"))
            asyncio.run(record_background_job("webhook_delivery", "skipped"))
    except (httpx.HTTPError, RuntimeError) as exc:
        # HTTP failures were already classified by run(). A not-yet-committed row is a broker race.
        if isinstance(exc, RuntimeError):
            asyncio.run(record_background_job("webhook_delivery", "retry"))
        raise self.retry(exc=exc, countdown=min(300, 2 ** self.request.retries * 5)) from exc


@celery_app.task(name="tenantflow.maintenance.cleanup_expired", bind=True, max_retries=3)
def cleanup_expired_state_task(self: Task) -> None:
    async def run() -> None:
        now = datetime.now(UTC)
        async with get_session_factory()() as session:
            async with session.begin():
                await session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < now))
                await session.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
                await session.execute(
                    update(Invitation)
                    .where(Invitation.status == "pending", Invitation.expires_at < now)
                    .values(status="expired")
                )

    try:
        asyncio.run(run())
        asyncio.run(record_background_job("cleanup", "success"))
    except (OSError, RuntimeError, SQLAlchemyError) as exc:
        asyncio.run(record_background_job("cleanup", "retry"))
        raise self.retry(exc=exc, countdown=60) from exc
