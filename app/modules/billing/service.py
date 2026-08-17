from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.models import StripeEvent, Subscription
from app.integrations.stripe_client import (
    CheckoutSession,
    PortalSession,
    create_checkout_session,
    create_portal_session,
)
from app.modules.audit.service import record_audit
from app.observability.metrics import STRIPE_WEBHOOK_EVENTS


ALLOWED_STRIPE_SUBSCRIPTION_STATES = {
    "trialing": "trialing",
    "active": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "paused": "inactive",
    "incomplete": "inactive",
    "incomplete_expired": "inactive",
    "canceled": "cancelled",
}


async def get_or_create_subscription(session: AsyncSession, organization_id: UUID) -> Subscription:
    subscription = await session.scalar(
        select(Subscription).where(Subscription.organization_id == organization_id)
    )
    if subscription is None:
        subscription = Subscription(
            organization_id=organization_id,
            plan="free",
            status="inactive",
        )
        session.add(subscription)
        await session.flush()
    return subscription


async def create_billing_checkout(
    session: AsyncSession,
    *,
    organization_id: UUID,
    plan: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str,
) -> CheckoutSession:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ConflictError("STRIPE_NOT_CONFIGURED", "Stripe test mode is not configured")
    price_id = settings.stripe_price_pro if plan == "pro" else settings.stripe_price_business
    if not price_id:
        raise ConflictError("STRIPE_PRICE_NOT_CONFIGURED", f"Stripe price for plan '{plan}' is not configured")
    subscription = await get_or_create_subscription(session, organization_id)
    return await create_checkout_session(
        organization_id=organization_id,
        customer_id=subscription.stripe_customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=idempotency_key,
    )


def _extract_customer_id(obj: dict[str, Any]) -> str | None:
    raw = obj.get("customer")
    return str(raw) if raw else None


async def _resolve_organization_id(
    session: AsyncSession,
    obj: dict[str, Any],
) -> UUID | None:
    metadata = obj.get("metadata") or {}
    org_id_raw = metadata.get("organization_id") or obj.get("client_reference_id")
    if org_id_raw:
        return UUID(str(org_id_raw))
    customer_id = _extract_customer_id(obj)
    if customer_id:
        organization_id = await session.scalar(
            select(Subscription.organization_id).where(
                Subscription.stripe_customer_id == customer_id
            )
        )
        return UUID(str(organization_id)) if organization_id is not None else None
    return None


async def process_stripe_event(session: AsyncSession, event: dict[str, Any]) -> bool:
    """Process a verified Stripe event once, safely under concurrent retries.

    The event marker is inserted first with PostgreSQL ON CONFLICT DO NOTHING. Because the marker
    and business changes share the same request transaction, any processing failure rolls both
    back, allowing Stripe to retry safely.
    """
    event_id = str(event["id"])
    event_type = str(event["type"])
    inserted = await session.scalar(
        insert(StripeEvent)
        .values(
            stripe_event_id=event_id,
            event_type=event_type,
            processed_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["stripe_event_id"])
        .returning(StripeEvent.id)
    )
    if inserted is None:
        STRIPE_WEBHOOK_EVENTS.labels(outcome="duplicate").inc()
        return False

    obj = dict(event["data"]["object"])
    organization_id = await _resolve_organization_id(session, obj)

    if organization_id is not None:
        subscription = await get_or_create_subscription(session, organization_id)
        if event_type == "checkout.session.completed":
            subscription.stripe_customer_id = _extract_customer_id(obj)
            subscription.status = "active"
        elif event_type.startswith("customer.subscription."):
            subscription.stripe_subscription_id = str(obj.get("id")) if obj.get("id") else None
            subscription.stripe_customer_id = _extract_customer_id(obj)
            if event_type == "customer.subscription.deleted":
                subscription.status = "cancelled"
            else:
                raw_status = str(obj.get("status", "inactive"))
                subscription.status = ALLOWED_STRIPE_SUBSCRIPTION_STATES.get(raw_status, "inactive")

            items = ((obj.get("items") or {}).get("data") or [])
            price_id = None
            if items:
                price_id = (items[0].get("price") or {}).get("id")
            settings = get_settings()
            if price_id == settings.stripe_price_pro:
                subscription.plan = "pro"
            elif price_id == settings.stripe_price_business:
                subscription.plan = "business"

            period_end = obj.get("current_period_end")
            if isinstance(period_end, (int, float)):
                subscription.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
        elif event_type == "invoice.payment_failed":
            subscription.status = "past_due"

        await record_audit(
            session,
            organization_id=organization_id,
            actor_id=None,
            action="billing.stripe_event_processed",
            entity_type="stripe_event",
            entity_id=inserted,
            metadata={"stripe_event_id": event_id, "event_type": event_type},
        )

    await session.flush()
    STRIPE_WEBHOOK_EVENTS.labels(outcome="processed").inc()
    return True


async def create_billing_portal(
    session: AsyncSession,
    *,
    organization_id: UUID,
    return_url: str,
) -> PortalSession:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ConflictError("STRIPE_NOT_CONFIGURED", "Stripe test mode is not configured")
    subscription = await get_or_create_subscription(session, organization_id)
    if not subscription.stripe_customer_id:
        raise ConflictError(
            "STRIPE_CUSTOMER_UNAVAILABLE",
            "Complete a Stripe Checkout session before opening the customer portal",
        )
    return await create_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=return_url,
    )
