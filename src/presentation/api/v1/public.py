"""Public routes (no auth) — /api/v1/public."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr

from src.application.commands.public_commands import PublicRegisterCommand, PublicSubscribeCommand
from src.application.services.public_service import PublicService
from src.presentation.dependencies import get_public_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(prefix="/public", tags=["Public"])


class CheckEmailRequest(BaseModel):
    email: EmailStr


class PublicRegisterRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str


class PublicSubscribeRequest(BaseModel):
    project_id: str
    email: EmailStr
    first_name: str
    last_name: str
    notes: str | None = None


@router.post("/check-email")
async def check_email(
    body: CheckEmailRequest,
    service: PublicService = Depends(get_public_service),
) -> dict[str, Any]:
    exists = await service.check_email(str(body.email))
    return envelope({"email": str(body.email), "exists": exists})


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def public_register(
    body: PublicRegisterRequest,
    service: PublicService = Depends(get_public_service),
) -> dict[str, Any]:
    cmd = PublicRegisterCommand(
        email=str(body.email),
        first_name=body.first_name,
        last_name=body.last_name,
        password=body.password,
    )
    result = await service.register(cmd)
    return envelope(asdict(result))


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def public_subscribe(
    body: PublicSubscribeRequest,
    service: PublicService = Depends(get_public_service),
) -> dict[str, Any]:
    cmd = PublicSubscribeCommand(
        project_id=body.project_id,
        email=str(body.email),
        first_name=body.first_name,
        last_name=body.last_name,
        notes=body.notes,
    )
    result = await service.subscribe(cmd)
    return envelope(asdict(result))
