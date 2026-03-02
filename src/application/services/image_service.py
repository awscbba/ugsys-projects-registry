"""Application service for image upload URL generation."""

from __future__ import annotations

import time
from typing import ClassVar

import structlog
from ulid import ULID

from src.application.commands.project_commands import GenerateUploadUrlCommand
from src.application.dtos.image_dtos import UploadUrlResult
from src.application.tracing import traced
from src.domain.exceptions import ValidationError
from src.domain.repositories.s3_client import S3Client

logger = structlog.get_logger()


class ImageService:
    """Handles presigned S3 upload URL generation for project images."""

    MAX_FILE_SIZE: ClassVar[int] = 10 * 1024 * 1024  # 10 MB
    ALLOWED_CONTENT_TYPES: ClassVar[set[str]] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    def __init__(self, s3_client: S3Client, cloudfront_base_url: str) -> None:
        self._s3_client = s3_client
        self._cloudfront_base_url = cloudfront_base_url.rstrip("/")

    @traced
    async def generate_upload_url(self, cmd: GenerateUploadUrlCommand) -> UploadUrlResult:
        """Validate the request and return a presigned upload URL with CloudFront URL."""
        logger.info("image_service.generate_upload_url.started", requester_id=cmd.requester_id)
        start = time.perf_counter()

        if cmd.file_size > self.MAX_FILE_SIZE:
            raise ValidationError(
                message=f"File size {cmd.file_size} exceeds maximum {self.MAX_FILE_SIZE} bytes",
                user_message="File size exceeds the 10 MB limit",
                error_code="IMAGE_TOO_LARGE",
            )

        if cmd.content_type not in self.ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(self.ALLOWED_CONTENT_TYPES))
            raise ValidationError(
                message=f"Content type '{cmd.content_type}' is not allowed",
                user_message=f"Content type must be one of: {allowed}",
                error_code="IMAGE_INVALID_CONTENT_TYPE",
            )

        image_id = str(ULID())
        key = f"projects/images/{image_id}"

        upload_url = await self._s3_client.generate_presigned_upload_url(
            key=key,
            content_type=cmd.content_type,
            expires_in=300,
        )
        cloudfront_url = f"{self._cloudfront_base_url}/{key}"

        logger.info(
            "image_service.generate_upload_url.completed",
            requester_id=cmd.requester_id,
            image_id=image_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )

        return UploadUrlResult(
            upload_url=upload_url,
            cloudfront_url=cloudfront_url,
            image_id=image_id,
            expires_in=300,
        )
