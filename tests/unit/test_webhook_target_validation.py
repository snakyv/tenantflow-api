from app.modules.webhooks.target_validation import _address_is_public


def test_webhook_target_ip_classification_rejects_internal_networks() -> None:
    assert not _address_is_public("127.0.0.1")
    assert not _address_is_public("10.0.0.10")
    assert not _address_is_public("169.254.169.254")
    assert not _address_is_public("::1")


def test_webhook_target_ip_classification_accepts_public_address() -> None:
    assert _address_is_public("8.8.8.8")
