from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Permission
from app.db.models import WebhookDelivery, WebhookEndpoint
from app.db.session import get_session
from app.modules.audit.service import record_audit
from app.modules.webhooks.schemas import WebhookCreate, WebhookDeliveryResponse, WebhookResponse
from app.modules.webhooks.service import create_webhook_endpoint

router = APIRouter(prefix="/organizations/{organization_id}/webhooks", tags=["Webhooks"])


def delivery_response(delivery: WebhookDelivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse.model_validate(delivery, from_attributes=True)


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    organization_id: UUID,
    payload: WebhookCreate,
    context: OrganizationContext = Depends(require_permission(Permission.WEBHOOK_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> WebhookResponse:
    try:
        endpoint, secret = await create_webhook_endpoint(
            session, organization_id, context.user.id, payload
        )
        await record_audit(
            session,
            organization_id=organization_id,
            actor_id=context.user.id,
            action="webhook.created",
            entity_type="webhook_endpoint",
            entity_id=endpoint.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return WebhookResponse(
        id=endpoint.id,
        url=endpoint.url,
        events=endpoint.events,
        is_active=endpoint.is_active,
        signing_secret=secret,
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    organization_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.WEBHOOK_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> list[WebhookResponse]:
    rows = (
        await session.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.organization_id == organization_id)
            .order_by(WebhookEndpoint.created_at.desc())
        )
    ).all()
    return [
        WebhookResponse(id=x.id, url=x.url, events=x.events, is_active=x.is_active)
        for x in rows
    ]


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_webhook(
    organization_id: UUID,
    endpoint_id: UUID,
    context: OrganizationContext = Depends(require_permission(Permission.WEBHOOK_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    endpoint = await session.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.organization_id == organization_id,
        )
    )
    if endpoint is None:
        raise NotFoundError("WEBHOOK_ENDPOINT_NOT_FOUND", "Webhook endpoint was not found")
    endpoint.is_active = False
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=context.user.id,
        action="webhook.deactivated",
        entity_type="webhook_endpoint",
        entity_id=endpoint.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_deliveries(
    organization_id: UUID,
    state: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: OrganizationContext = Depends(require_permission(Permission.WEBHOOK_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> list[WebhookDeliveryResponse]:
    statement = (
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookEndpoint.organization_id == organization_id)
    )
    if state is not None:
        if state not in {"pending", "delivered", "retrying", "dead"}:
            raise HTTPException(status_code=422, detail="Unsupported delivery state")
        statement = statement.where(WebhookDelivery.state == state)
    statement = statement.order_by(WebhookDelivery.created_at.desc()).limit(limit)
    rows = (await session.scalars(statement)).all()
    return [delivery_response(row) for row in rows]


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryResponse)
async def retry_delivery(
    organization_id: UUID,
    delivery_id: UUID,
    context: OrganizationContext = Depends(require_permission(Permission.WEBHOOK_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> WebhookDeliveryResponse:
    delivery = await session.scalar(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(
            WebhookDelivery.id == delivery_id,
            WebhookEndpoint.organization_id == organization_id,
        )
        .with_for_update()
    )
    if delivery is None:
        raise NotFoundError("WEBHOOK_DELIVERY_NOT_FOUND", "Webhook delivery was not found")
    endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None or not endpoint.is_active:
        raise ConflictError("WEBHOOK_ENDPOINT_INACTIVE", "Webhook endpoint is inactive")
    if delivery.state == "delivered":
        raise ConflictError("WEBHOOK_ALREADY_DELIVERED", "Delivered webhooks are not retried")

    delivery.state = "retrying"
    delivery.next_retry_at = None
    delivery.last_error = None
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=context.user.id,
        action="webhook.delivery_retried",
        entity_type="webhook_delivery",
        entity_id=delivery.id,
    )

    from app.workers.tasks import deliver_webhook_task

    deliver_webhook_task.delay(str(delivery.id))
    return delivery_response(delivery)
