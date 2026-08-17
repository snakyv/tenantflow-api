from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.permissions import Permission
from app.db.session import get_session
from app.infra.idempotency import canonical_request_hash
from app.infra.idempotency_db import acquire_idempotency, complete_idempotency
from app.integrations.stripe_client import StripeWebhookVerificationError, construct_webhook_event
from app.modules.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
)
from app.modules.billing.service import (
    create_billing_checkout,
    create_billing_portal,
    get_or_create_subscription,
    process_stripe_event,
)

router = APIRouter(tags=["Billing"])


@router.get(
    "/organizations/{organization_id}/billing/subscription",
    response_model=SubscriptionResponse,
)
async def subscription_status(
    organization_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.BILLING_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    subscription = await get_or_create_subscription(session, organization_id)
    return SubscriptionResponse(
        plan=subscription.plan,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
    )


@router.post(
    "/organizations/{organization_id}/billing/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def checkout(
    organization_id: UUID,
    payload: CheckoutRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    context: OrganizationContext = Depends(require_permission(Permission.BILLING_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> CheckoutResponse:
    request_hash = canonical_request_hash(payload.model_dump(mode="json"))
    state = await acquire_idempotency(
        session,
        user_id=context.user.id,
        organization_id=organization_id,
        scope=f"billing:checkout:{organization_id}:{context.user.id}",
        key=idempotency_key,
        request_hash=request_hash,
    )
    if state.is_replay:
        if state.replay_body is None:
            raise RuntimeError("Completed billing idempotency record is missing its response body")
        return CheckoutResponse.model_validate(state.replay_body)

    checkout_session = await create_billing_checkout(
        session,
        organization_id=organization_id,
        plan=payload.plan,
        success_url=str(payload.success_url),
        cancel_url=str(payload.cancel_url),
        idempotency_key=idempotency_key,
    )
    response = CheckoutResponse(
        session_id=checkout_session.id,
        checkout_url=checkout_session.url,
    )
    await complete_idempotency(
        session,
        state.record,
        status_code=201,
        response_body=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/organizations/{organization_id}/billing/portal",
    response_model=PortalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def portal(
    organization_id: UUID,
    payload: PortalRequest,
    _: OrganizationContext = Depends(require_permission(Permission.BILLING_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> PortalResponse:
    portal_session = await create_billing_portal(
        session,
        organization_id=organization_id,
        return_url=str(payload.return_url),
    )
    return PortalResponse(session_id=portal_session.id, portal_url=portal_session.url)


@router.post("/webhooks/stripe", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_session),
) -> None:
    payload = await request.body()
    try:
        event = construct_webhook_event(payload, stripe_signature)
    except StripeWebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
    await process_stripe_event(session, event)
