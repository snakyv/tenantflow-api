from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.config import get_settings

if TYPE_CHECKING:
    from stripe.params.checkout import SessionCreateParams


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    id: str
    url: str


@dataclass(frozen=True, slots=True)
class PortalSession:
    id: str
    url: str


async def create_checkout_session(
    *,
    organization_id: UUID,
    customer_id: str | None,
    price_id: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str,
) -> CheckoutSession:
    import stripe

    settings = get_settings()
    client = stripe.StripeClient(
        settings.stripe_secret_key,
        http_client=stripe.HTTPXClient(),
        max_network_retries=2,
    )
    params: SessionCreateParams = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(organization_id),
        "metadata": {"organization_id": str(organization_id)},
        "subscription_data": {"metadata": {"organization_id": str(organization_id)}},
    }
    if customer_id:
        params["customer"] = customer_id
    session = await client.v1.checkout.sessions.create_async(
        params,
        options={"idempotency_key": idempotency_key},
    )
    if not session.url:
        raise RuntimeError("Stripe Checkout Session did not return a hosted URL")
    return CheckoutSession(id=session.id, url=session.url)


async def create_portal_session(*, customer_id: str, return_url: str) -> PortalSession:
    import stripe

    settings = get_settings()
    client = stripe.StripeClient(
        settings.stripe_secret_key,
        http_client=stripe.HTTPXClient(),
        max_network_retries=2,
    )
    session = await client.v1.billing_portal.sessions.create_async(
        {"customer": customer_id, "return_url": return_url}
    )
    return PortalSession(id=session.id, url=session.url)


class StripeWebhookVerificationError(ValueError):
    """Raised when Stripe's signature verification rejects the raw webhook payload."""


def construct_webhook_event(payload: bytes, signature: str) -> Any:
    import stripe

    settings = get_settings()
    client = stripe.StripeClient(settings.stripe_secret_key or "sk_test_unconfigured")
    try:
        return client.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise StripeWebhookVerificationError("Invalid Stripe webhook") from exc
