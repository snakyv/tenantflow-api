from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from app.core.config import get_settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/csv",
}
MAX_FILE_SIZE = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    object_key: str
    url: str


def validate_upload(content_type: str, size_bytes: int) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported content type")
    if size_bytes <= 0 or size_bytes > MAX_FILE_SIZE:
        raise ValueError("File size is outside the allowed range")


def build_object_key(organization_id: UUID, filename: str) -> str:
    safe_suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if not safe_suffix.isalnum() or len(safe_suffix) > 10:
        safe_suffix = "bin"
    return f"organizations/{organization_id}/{uuid4()}.{safe_suffix}"


def create_s3_client(*, endpoint_url: str | None = None) -> Any:
    import boto3

    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name=settings.minio_region,
    )


def presign_put(object_key: str, content_type: str, expires_seconds: int = 900) -> str:
    settings = get_settings()
    client = create_s3_client(endpoint_url=settings.minio_public_endpoint or settings.minio_endpoint)
    return cast(
        str,
        client.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.minio_bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=expires_seconds,
        ),
    )


def presign_get(object_key: str, expires_seconds: int = 900) -> str:
    settings = get_settings()
    client = create_s3_client(endpoint_url=settings.minio_public_endpoint or settings.minio_endpoint)
    return cast(
        str,
        client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.minio_bucket, "Key": object_key},
            ExpiresIn=expires_seconds,
        ),
    )
