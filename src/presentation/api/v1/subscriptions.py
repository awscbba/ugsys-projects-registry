"""Subscription routes — /api/v1/projects/{id}/subscriptions and /api/v1/subscriptions."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from src.application.commands.subscription_commands import (
    ApproveSubscriptionCommand,
    CancelSubscriptionCommand,
    CreateSubscriptionCommand,
    RejectSubscriptionCommand,
)
from src.application.services.subscription_service import SubscriptionService
from src.domain.exceptions import AuthorizationError, ValidationError
from src.presentation.auth import CurrentUser, get_current_user
from src.presentation.dependencies import get_subscription_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(tags=["Subscriptions"])


class CreateSubscriptionRequest(BaseModel):
    notes: str | None = None


class UpdateSubscriptionRequest(BaseModel):
    action: str  # "approve" or "reject"
    reason: str | None = None


class CheckSubscriptionRequest(BaseModel):
    person_id: str
    project_id: str


@router.post("/projects/{project_id}/subscriptions", status_code=status.HTTP_201_CREATED)
async def subscribe(
    project_id: str,
    body: CreateSubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, Any]:
    cmd = CreateSubscriptionCommand(
        project_id=project_id,
        person_id=user.sub,
        notes=body.notes,
        is_super_admin=user.is_super_admin,
    )
    result = await service.subscribe(cmd)
    return envelope(asdict(result))


@router.get("/projects/{project_id}/subscriptions")
async def list_project_subscriptions(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, Any]:
    if not user.is_moderator:
        raise AuthorizationError(
            message=f"User {user.sub} lacks moderator role for subscription listing",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )
    subs, total = await service.list_by_project(project_id, page, page_size)
    return envelope(
        {"items": [asdict(s) for s in subs], "total": total, "page": page, "page_size": page_size}
    )


@router.put("/projects/{project_id}/subscribers/{subscription_id}")
async def update_subscription(
    project_id: str,
    subscription_id: str,
    body: UpdateSubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, Any]:
    if not user.is_admin:
        raise AuthorizationError(
            message=f"User {user.sub} lacks admin role for subscription update",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )
    if body.action == "approve":
        cmd = ApproveSubscriptionCommand(
            subscription_id=subscription_id,
            project_id=project_id,
            admin_id=user.sub,
        )
        result = await service.approve(cmd)
    elif body.action == "reject":
        cmd = RejectSubscriptionCommand(
            subscription_id=subscription_id,
            project_id=project_id,
            admin_id=user.sub,
            reason=body.reason,
        )
        result = await service.reject(cmd)
    else:
        raise ValidationError(
            message=f"Invalid subscription action: {body.action!r}",
            user_message="Action must be 'approve' or 'reject'",
            error_code="VALIDATION_ERROR",
        )
    return envelope(asdict(result))


@router.delete(
    "/projects/{project_id}/subscribers/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_subscription(
    project_id: str,
    subscription_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> None:
    cmd = CancelSubscriptionCommand(
        subscription_id=subscription_id,
        project_id=project_id,
        requester_id=user.sub,
        is_admin=user.is_admin,
    )
    await service.cancel(cmd)


@router.get("/subscriptions/person/{person_id}")
async def list_person_subscriptions(
    person_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, Any]:
    subs = await service.list_by_person(
        person_id=person_id,
        requester_id=user.sub,
        is_admin=user.is_admin,
    )
    return envelope([asdict(s) for s in subs])


@router.post("/subscriptions/check")
async def check_subscription(
    body: CheckSubscriptionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
) -> dict[str, Any]:
    subs, _ = await service.list_by_project(body.project_id, page=1, page_size=10000)
    is_subscribed = any(s.person_id == body.person_id for s in subs)
    return envelope(
        {
            "is_subscribed": is_subscribed,
            "person_id": body.person_id,
            "project_id": body.project_id,
        }
    )
