import time

from app.modules.webhooks.signing import create_signature, verify_signature


def test_webhook_signature_round_trip() -> None:
    secret = "whsec_test"
    body = b'{"event":"task.completed"}'
    now = int(time.time())
    signature = create_signature(secret, body, now)
    assert verify_signature(secret, body, signature, tolerance_seconds=5)


def test_webhook_signature_rejects_tampered_body() -> None:
    secret = "whsec_test"
    now = int(time.time())
    signature = create_signature(secret, b"original", now)
    assert not verify_signature(secret, b"tampered", signature, tolerance_seconds=5)


def test_webhook_signature_rejects_expired_timestamp() -> None:
    secret = "whsec_test"
    old = int(time.time()) - 600
    signature = create_signature(secret, b"payload", old)
    assert not verify_signature(secret, b"payload", signature, tolerance_seconds=60)
