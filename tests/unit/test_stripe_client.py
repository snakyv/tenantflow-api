from typing import Any

import pytest
import stripe

from app.integrations.stripe_client import construct_webhook_event


class _FakeStripeEvent:
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": "evt_test_v15",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "organization_id": "00000000-0000-0000-0000-000000000001"
                    },
                    "customer": "cus_test",
                }
            },
        }


class _FakeStripeClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def construct_event(
        self, _payload: bytes, _signature: str, _secret: str
    ) -> _FakeStripeEvent:
        return _FakeStripeEvent()


def test_construct_webhook_event_normalizes_stripe_v15_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stripe, "StripeClient", _FakeStripeClient)

    event = construct_webhook_event(b"{}", "test-signature")

    assert isinstance(event, dict)
    assert event["id"] == "evt_test_v15"
    assert event["data"]["object"]["customer"] == "cus_test"
