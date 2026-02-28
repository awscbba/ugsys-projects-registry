"""Health check routes — no authentication required."""

from __future__ import annotations

from fastapi import APIRouter

from src.config import settings

router = APIRouter(tags=["Health"])


@router.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok"}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"service": settings.service_name, "status": "ok", "version": settings.version}
