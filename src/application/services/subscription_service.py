"""SubscriptionService — application service for subscription lifecycle management."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from ulid import ULID

from src.application.commands.subscription_commands import (
    ApproveSubscriptionCommand,
    CancelSubscriptionCommand,
    CreateSubscriptionCommand,
    RejectSubscriptionCommand,
)
from src.application.dtos.subscription_dtos import (
    EnrichedSubscriptionResponse,
    SubscriptionResponse,
)
from src.application.tracing import traced
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import AuthorizationError, ConflictError, NotFoundError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import SubscriptionStatus

logger = structlog.get_logger()


class SubscriptionService:
    """Application service for subscription lifecycle management."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        project_repo: ProjectRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._project_repo = project_repo
        self._event_publisher = event_publisher

    @traced
    async def subscribe(self, cmd: CreateSubscriptionCommand) -> SubscriptionResponse:
        """Create a new subscription for a person on a project."""
        logger.info(
            "subscription_service.subscribe.started",
            project_id=cmd.project_id,
            person_id=cmd.person_id,
        )
        start = time.perf_counter()

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        existing = await self._subscription_repo.find_by_person_and_project(
            cmd.person_id, cmd.project_id
        )
        if existing is not None:
            raise ConflictError(
                message=(f"Person {cmd.person_id} already subscribed to project {cmd.project_id}"),
                user_message="You are already subscribed to this project",
                error_code="SUBSCRIPTION_ALREADY_EXISTS",
            )

        status = SubscriptionStatus.ACTIVE if cmd.is_super_admin else SubscriptionStatus.PENDING
        now = datetime.now(tz=UTC).isoformat()

        subscription = Subscription(
            id=str(ULID()),
            project_id=cmd.project_id,
            person_id=cmd.person_id,
            status=status,
            notes=cmd.notes or "",
            subscription_date=now,
            is_active=(status == SubscriptionStatus.ACTIVE),
            created_at=now,
            updated_at=now,
        )

        if status == SubscriptionStatus.ACTIVE:
            project.current_participants += 1
            await self._project_repo.update(project)

        subscription = await self._subscription_repo.save(subscription)

        await self._publish_event(
            "projects.subscription.created",
            {
                "subscription_id": subscription.id,
                "project_id": subscription.project_id,
                "person_id": subscription.person_id,
                "status": str(subscription.status),
                "notification_emails": project.notification_emails,
            },
        )

        logger.info(
            "subscription_service.subscribe.completed",
            subscription_id=subscription.id,
            status=str(status),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return SubscriptionResponse.from_domain(subscription)

    @traced
    async def approve(self, cmd: ApproveSubscriptionCommand) -> SubscriptionResponse:
        """Approve a pending subscription."""
        logger.info(
            "subscription_service.approve.started",
            subscription_id=cmd.subscription_id,
            admin_id=cmd.admin_id,
        )
        start = time.perf_counter()

        subscription = await self._subscription_repo.find_by_id(cmd.subscription_id)
        if subscription is None:
            raise NotFoundError(
                message=f"Subscription {cmd.subscription_id} not found",
                user_message="Subscription not found",
                error_code="SUBSCRIPTION_NOT_FOUND",
            )

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        subscription.status = SubscriptionStatus.ACTIVE
        subscription.is_active = True
        subscription.updated_at = datetime.now(tz=UTC).isoformat()

        project.current_participants += 1
        await self._project_repo.update(project)

        subscription = await self._subscription_repo.update(subscription)

        await self._publish_event(
            "projects.subscription.approved",
            {
                "subscription_id": subscription.id,
                "project_id": subscription.project_id,
                "person_id": subscription.person_id,
            },
        )

        logger.info(
            "subscription_service.approve.completed",
            subscription_id=subscription.id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return SubscriptionResponse.from_domain(subscription)

    @traced
    async def reject(self, cmd: RejectSubscriptionCommand) -> SubscriptionResponse:
        """Reject a pending subscription."""
        logger.info(
            "subscription_service.reject.started",
            subscription_id=cmd.subscription_id,
            admin_id=cmd.admin_id,
        )
        start = time.perf_counter()

        subscription = await self._subscription_repo.find_by_id(cmd.subscription_id)
        if subscription is None:
            raise NotFoundError(
                message=f"Subscription {cmd.subscription_id} not found",
                user_message="Subscription not found",
                error_code="SUBSCRIPTION_NOT_FOUND",
            )

        subscription.status = SubscriptionStatus.REJECTED
        subscription.is_active = False
        subscription.updated_at = datetime.now(tz=UTC).isoformat()

        subscription = await self._subscription_repo.update(subscription)

        await self._publish_event(
            "projects.subscription.rejected",
            {
                "subscription_id": subscription.id,
                "project_id": subscription.project_id,
                "person_id": subscription.person_id,
            },
        )

        logger.info(
            "subscription_service.reject.completed",
            subscription_id=subscription.id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return SubscriptionResponse.from_domain(subscription)

    @traced
    async def cancel(self, cmd: CancelSubscriptionCommand) -> SubscriptionResponse:
        """Cancel an existing subscription."""
        logger.info(
            "subscription_service.cancel.started",
            subscription_id=cmd.subscription_id,
            requester_id=cmd.requester_id,
        )
        start = time.perf_counter()

        subscription = await self._subscription_repo.find_by_id(cmd.subscription_id)
        if subscription is None:
            raise NotFoundError(
                message=f"Subscription {cmd.subscription_id} not found",
                user_message="Subscription not found",
                error_code="SUBSCRIPTION_NOT_FOUND",
            )

        if not cmd.is_admin and subscription.person_id != cmd.requester_id:
            raise AuthorizationError(
                message=(
                    f"User {cmd.requester_id} attempted IDOR on subscription {cmd.subscription_id}"
                ),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        was_active = subscription.status == SubscriptionStatus.ACTIVE

        if was_active:
            project = await self._project_repo.find_by_id(cmd.project_id)
            if project is not None:
                project.current_participants = max(0, project.current_participants - 1)
                await self._project_repo.update(project)

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.is_active = False
        subscription.updated_at = datetime.now(tz=UTC).isoformat()

        subscription = await self._subscription_repo.update(subscription)

        await self._publish_event(
            "projects.subscription.cancelled",
            {
                "subscription_id": subscription.id,
                "project_id": subscription.project_id,
                "person_id": subscription.person_id,
            },
        )

        logger.info(
            "subscription_service.cancel.completed",
            subscription_id=subscription.id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return SubscriptionResponse.from_domain(subscription)

    @traced
    async def list_by_project(
        self, project_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[SubscriptionResponse], int]:
        """List subscriptions for a project with pagination."""
        logger.info(
            "subscription_service.list_by_project.started",
            project_id=project_id,
            page=page,
            page_size=page_size,
        )
        start = time.perf_counter()

        subs, total = await self._subscription_repo.list_by_project(project_id, page, page_size)
        responses = [SubscriptionResponse.from_domain(s) for s in subs]

        logger.info(
            "subscription_service.list_by_project.completed",
            project_id=project_id,
            total=total,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return responses, total

    @traced
    async def list_by_person(
        self, person_id: str, requester_id: str, is_admin: bool
    ) -> list[EnrichedSubscriptionResponse]:
        """List all subscriptions for a person (IDOR-protected)."""
        logger.info(
            "subscription_service.list_by_person.started",
            person_id=person_id,
            requester_id=requester_id,
        )
        start = time.perf_counter()

        if not is_admin and person_id != requester_id:
            raise AuthorizationError(
                message=(f"User {requester_id} attempted IDOR on person {person_id} subscriptions"),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        subs = await self._subscription_repo.list_by_person(person_id)
        responses = [EnrichedSubscriptionResponse.from_domain(s) for s in subs]

        logger.info(
            "subscription_service.list_by_person.completed",
            person_id=person_id,
            count=len(responses),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return responses

    async def _publish_event(self, detail_type: str, payload: dict[str, Any]) -> None:
        """Publish a domain event, catching and logging any failure without re-raising."""
        try:
            await self._event_publisher.publish(detail_type, payload)
        except Exception as exc:
            logger.warning(
                "subscription_service.event_publish_failed",
                detail_type=detail_type,
                error=str(exc),
            )
