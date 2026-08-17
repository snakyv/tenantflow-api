from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TenantFlow API"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+asyncpg://tenantflow:tenantflow@localhost:55432/tenantflow"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "development-only-secret-change-me-32chars"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "tenantflow-api"
    jwt_audience: str = "tenantflow-api"
    webhook_encryption_key: str = ""
    webhook_allow_private_targets: bool = True
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    minio_endpoint: str = "http://localhost:9000"
    minio_public_endpoint: str | None = None
    minio_access_key: str = "tenantflow"
    minio_secret_key: str = "tenantflow-secret"
    minio_bucket: str = "tenantflow"
    minio_region: str = "us-east-1"

    mail_host: str = "localhost"
    mail_port: int = 1025
    mail_from: str = "no-reply@tenantflow.local"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_business: str = ""

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_runtime_secrets(self) -> None:
        if not self.is_production:
            return

        unsafe_jwt_values = {
            "development-only-secret-change-me-32chars",
            "replace-with-at-least-32-random-characters",
        }
        unsafe_webhook_values = {
            "",
            "replace-with-a-separate-32-character-secret",
        }
        if len(self.jwt_secret) < 32 or self.jwt_secret in unsafe_jwt_values:
            raise RuntimeError("JWT_SECRET must be a non-default secret of at least 32 characters in production")
        if len(self.webhook_encryption_key) < 32 or self.webhook_encryption_key in unsafe_webhook_values:
            raise RuntimeError(
                "WEBHOOK_ENCRYPTION_KEY must be a non-default secret of at least 32 characters in production"
            )
        if self.jwt_secret == self.webhook_encryption_key:
            raise RuntimeError("JWT_SECRET and WEBHOOK_ENCRYPTION_KEY must be different secrets")
        if self.webhook_allow_private_targets:
            raise RuntimeError("WEBHOOK_ALLOW_PRIVATE_TARGETS must be false in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_secrets()
    return settings
