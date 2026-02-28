"""Abstract interface for S3 image storage operations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class S3Client(ABC):
    """Port interface for S3 presigned URL generation."""

    @abstractmethod
    async def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 300,
    ) -> str:
        """Generate a presigned PUT URL for uploading an object.

        Returns the presigned URL string.
        """
        ...
