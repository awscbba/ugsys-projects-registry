"""Image upload URL routes — /api/v1/images."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.application.commands.project_commands import GenerateUploadUrlCommand
from src.application.services.image_service import ImageService
from src.presentation.auth import CurrentUser, get_current_user
from src.presentation.dependencies import get_image_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(prefix="/images", tags=["Images"])


class GenerateUploadUrlRequest(BaseModel):
    file_size: int
    content_type: str


@router.post("/upload-url", status_code=status.HTTP_201_CREATED)
async def generate_upload_url(
    body: GenerateUploadUrlRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ImageService = Depends(get_image_service),
) -> dict[str, Any]:
    cmd = GenerateUploadUrlCommand(
        file_size=body.file_size,
        content_type=body.content_type,
        requester_id=user.sub,
    )
    result = await service.generate_upload_url(cmd)
    return envelope(asdict(result))
