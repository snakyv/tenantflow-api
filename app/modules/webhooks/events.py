from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WebhookDelivery, WebhookEndpoint


async def emit_event(
    session: AsyncSession,
    *,
    organization_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> UUID:
    event_id = uuid4()
    endpoints = (
        await session.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == organization_id,
                WebhookEndpoint.is_active.is_(True),
            )
        )
    ).all()
    delivery_ids: list[UUID] = []
    for endpoint in endpoints:
        if event_type not in endpoint.events:
            continue
        delivery = WebhookDelivery(
            event_id=event_id,
            endpoint_id=endpoint.id,
            event_type=event_type,
            payload={"id": str(event_id), "type": event_type, "data": payload},
            state="pending",
            attempt_count=0,
        )
        session.add(delivery)
        await session.flush()
        delivery_ids.append(delivery.id)

    if delivery_ids:
        # Publishing inside the request transaction intentionally fails the use case if the broker
        # cannot accept jobs. Workers retry the brief race where rows are not committed yet.
        from app.workers.tasks import deliver_webhook_task

        for delivery_id in delivery_ids:
            deliver_webhook_task.delay(str(delivery_id))
    return event_id
