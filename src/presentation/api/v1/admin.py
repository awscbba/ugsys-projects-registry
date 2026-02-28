"""Admin routes — /api/v1/admin."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.application.commands.project_commands import BulkActionCommand
from src.application.queries.project_queries import PaginatedUsersQuery
from src.application.services.admin_service import AdminService
from src.domain.exceptions import AuthorizationError
from src.presentation.auth import CurrentUser, get_current_user
from src.presentation.dependencies import get_admin_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["Admin"])


class BulkActionRequest(BaseModel):
    action: str
    user_ids: list[str]


def _require_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise AuthorizationError(
            message=f"User {user.sub} lacks admin role",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )


@router.get("/dashboard")
async def dashboard(
    user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict[str, Any]:
    _require_admin(user)
    result = await service.dashboard()
    return envelope(asdict(result))


@router.get("/dashboard/enhanced")
async def enhanced_dashboard(
    user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict[str, Any]:
    _require_admin(user)
    result = await service.enhanced_dashboard()
    return envelope(asdict(result))


@router.get("/analytics")
async def analytics(
    user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict[str, Any]:
    _require_admin(user)
    result = await service.analytics()
    return envelope(asdict(result))


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict[str, Any]:
    _require_admin(user)
    query = PaginatedUsersQuery(page=page, page_size=page_size)
    users, total = await service.paginated_users(query)
    return envelope({"items": users, "total": total, "page": page, "page_size": page_size})


@router.post("/users/bulk-action")
async def bulk_action(
    body: BulkActionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
) -> dict[str, Any]:
    _require_admin(user)
    cmd = BulkActionCommand(
        action=body.action,
        user_ids=body.user_ids,
        requester_id=user.sub,
    )
    result = await service.bulk_action(cmd)
    return envelope(asdict(result))
