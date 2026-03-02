"""S3 client adapter — implements S3Client port."""

from __future__ import annotations

from typing import Any

import structlog
from botocore.exceptions import ClientError

from src.domain.exceptions import ExternalServiceError
from src.domain.repositories.s3_client import S3Client

logger = structlog.get_logger()


class S3ClientAdapter(S3Client):
    def __init__(self, bucket_name: str, client: Any) -> None:
        self._bucket = bucket_name
        self._client = client

    async def generate_presigned_upload_url(
        self, key: str, content_type: str, expires_in: int = 300
    ) -> str:
        try:
            url: str = await self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error("s3.presigned_url_failed", key=key, error=str(e))
            raise ExternalServiceError(
                message=f"S3 presigned URL generation failed: {e}",
                user_message="An unexpected error occurred",
                error_code="S3_ERROR",
            ) from e
