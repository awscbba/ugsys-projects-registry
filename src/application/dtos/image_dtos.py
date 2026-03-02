"""Response DTOs for image upload operations.

UploadUrlResult: Presigned S3 upload URL with CloudFront delivery URL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UploadUrlResult:
    """Result of a presigned upload URL generation request."""

    upload_url: str
    cloudfront_url: str
    image_id: str
    expires_in: int = 300
