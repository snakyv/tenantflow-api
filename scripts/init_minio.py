import time

from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import get_settings
from app.integrations.storage import create_s3_client


def main() -> None:
    settings = get_settings()
    client = create_s3_client()
    for attempt in range(1, 31):
        try:
            client.head_bucket(Bucket=settings.minio_bucket)
            print(f"Bucket '{settings.minio_bucket}' already exists")
            return
        except EndpointConnectionError:
            if attempt == 30:
                raise
            time.sleep(1)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchBucket", "NotFound"}:
                client.create_bucket(Bucket=settings.minio_bucket)
                print(f"Created bucket '{settings.minio_bucket}'")
                return
            raise


if __name__ == "__main__":
    main()
