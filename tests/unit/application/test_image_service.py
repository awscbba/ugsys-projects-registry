"""Unit tests for ImageService application service.

Validates: Requirements 8.1, 8.2, 8.3, 17.1

Tests cover:
- file_size > 10 MB raises ValidationError(IMAGE_TOO_LARGE)
- invalid content_type raises ValidationError(IMAGE_INVALID_CONTENT_TYPE)
- valid request returns presigned URL and CloudFront URL with correct format
- exact max file size (10 MB) is allowed without raising
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.commands.project_commands import GenerateUploadUrlCommand
from src.application.services.image_service import ImageService
from src.domain.exceptions import ValidationError
from src.domain.repositories.s3_client import S3Client

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_service(
    presigned_url: str = "https://s3.example.com/presigned",
) -> tuple[ImageService, AsyncMock]:
    mock_s3: AsyncMock = AsyncMock(spec=S3Client)
    mock_s3.generate_presigned_upload_url.return_value = presigned_url
    service = ImageService(s3_client=mock_s3, cloudfront_base_url="https://cdn.example.com")
    return service, mock_s3


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_size_over_limit_raises_image_too_large() -> None:
    # Arrange
    service, _ = make_service()
    cmd = GenerateUploadUrlCommand(
        file_size=10 * 1024 * 1024 + 1,
        content_type="image/jpeg",
        requester_id="user-1",
    )

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.generate_upload_url(cmd)

    assert exc_info.value.error_code == "IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_invalid_content_type_raises_image_invalid_content_type() -> None:
    # Arrange
    service, _ = make_service()
    cmd = GenerateUploadUrlCommand(
        file_size=1024,
        content_type="application/pdf",
        requester_id="user-1",
    )

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.generate_upload_url(cmd)

    assert exc_info.value.error_code == "IMAGE_INVALID_CONTENT_TYPE"


@pytest.mark.asyncio
async def test_valid_request_returns_presigned_and_cloudfront_urls() -> None:
    # Arrange
    presigned = "https://s3.example.com/presigned"
    service, mock_s3 = make_service(presigned_url=presigned)
    cmd = GenerateUploadUrlCommand(
        file_size=1024,
        content_type="image/jpeg",
        requester_id="user-1",
    )

    # Act
    result = await service.generate_upload_url(cmd)

    # Assert
    assert result.upload_url == presigned
    assert result.cloudfront_url.startswith("https://cdn.example.com/projects/images/")
    assert result.image_id != ""
    assert result.expires_in == 300
    mock_s3.generate_presigned_upload_url.assert_awaited_once()


@pytest.mark.asyncio
async def test_exact_max_file_size_is_allowed() -> None:
    # Arrange
    service, _ = make_service()
    cmd = GenerateUploadUrlCommand(
        file_size=10 * 1024 * 1024,
        content_type="image/png",
        requester_id="user-1",
    )

    # Act + Assert — no exception raised
    result = await service.generate_upload_url(cmd)
    assert result.image_id != ""
