import pytest

from app.core.config import Settings


def test_production_requires_independent_long_secrets() -> None:
    settings = Settings(app_env="production", jwt_secret="short", webhook_encryption_key="short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_runtime_secrets()


def test_production_accepts_valid_secrets() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret="j" * 48,
        webhook_encryption_key="w" * 48,
        webhook_allow_private_targets=False,
    )
    settings.validate_runtime_secrets()


def test_production_rejects_default_development_jwt_secret() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret="development-only-secret-change-me-32chars",
        webhook_encryption_key="w" * 48,
        webhook_allow_private_targets=False,
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_runtime_secrets()


def test_production_requires_separate_secrets() -> None:
    shared = "s" * 48
    settings = Settings(
        app_env="production",
        jwt_secret=shared,
        webhook_encryption_key=shared,
    )
    with pytest.raises(RuntimeError, match="must be different"):
        settings.validate_runtime_secrets()


def test_production_rejects_private_webhook_targets() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret="j" * 48,
        webhook_encryption_key="w" * 48,
        webhook_allow_private_targets=True,
    )
    with pytest.raises(RuntimeError, match="WEBHOOK_ALLOW_PRIVATE_TARGETS"):
        settings.validate_runtime_secrets()
