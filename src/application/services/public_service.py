"""Application service for public (unauthenticated) operations.

Handles public user registration and project subscription without requiring
an existing authenticated identity.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog
from ulid import ULID

from src.application.commands.public_commands import (
    PublicRegisterCommand,
    PublicSubscribeCommand,
)
from src.application.dtos.public_dtos import PublicRegisterResult
from src.application.dtos.subscription_dtos import SubscriptionResponse
from src.application.tracing import traced
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.identity_client import IdentityClient
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import SubscriptionStatus

logger = structlog.get_logger()


class PublicService:
    """Orchestrates public registration and subscription flows."""

    def __init__(
        self,
        identity_client: IdentityClient,
        subscription_repo: SubscriptionRepository,
        project_repo: ProjectRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._identity_client = identity_client
        self._subscription_repo = subscription_repo
        self._project_repo = project_repo
        self._event_publisher = event_publisher

    @traced
    async def check_email(self, email: str) -> bool:
        """Check whether an email address is already registered.

        Delegates to the Identity Manager service.
        """
        logger.info("public_service.check_email.started", email=email)
        start = time.perf_counter()
        result = await self._identity_client.check_email_exists(email)
        logger.info(
            "public_service.check_email.completed",
            email=email,
            exists=result,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return result

    @traced
    async def register(self, cmd: PublicRegisterCommand) -> PublicRegisterResult:
        """Register a new user via the public endpoint.

        Raises ConflictError(EMAIL_ALREADY_EXISTS) if the email is taken.
        """
        logger.info("public_service.register.started", email=cmd.email)
        start = time.perf_counter()

        email_exists = await self._identity_client.check_email_exists(cmd.email)
        if email_exists:
            raise ConflictError(
                message=f"Email {cmd.email} is already registered",
                user_message="An account with this email already exists",
                error_code="EMAIL_ALREADY_EXISTS",
            )

        full_name = f"{cmd.first_name} {cmd.last_name}"
        user_id = await self._identity_client.create_user(
            email=cmd.email,
            full_name=full_name,
            password=cmd.password,
        )

        logger.info(
            "public_service.register.completed",
            user_id=user_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return PublicRegisterResult(user_id=user_id, email=cmd.email)

    @traced
    async def subscribe(self, cmd: PublicSubscribeCommand) -> SubscriptionResponse:
        """Subscribe to a project via the public endpoint.

        Creates the user in Identity Manager if they don't exist yet.
        Subscription is always created with status=PENDING.

        Raises:
            NotFoundError(PROJECT_NOT_FOUND): if the project does not exist.
            ConflictError(SUBSCRIPTION_ALREADY_EXISTS): if already subscribed.
        """
        logger.info(
            "public_service.subscribe.started",
            project_id=cmd.project_id,
            email=cmd.email,
        )
        start = time.perf_counter()

        # Load project — raises NotFoundError if missing
        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        # Resolve person_id: create user if new, use email as placeholder if existing
        email_exists = await self._identity_client.check_email_exists(cmd.email)
        if email_exists:
            # We don't have a get_by_email method; use email as person_id placeholder.
            # The identity manager will resolve this on its side.
            person_id = cmd.email
        else:
            full_name = f"{cmd.first_name} {cmd.last_name}"
            person_id = await self._identity_client.create_user(
                email=cmd.email,
                full_name=full_name,
                password="",
            )

        # Duplicate subscription check
        existing = await self._subscription_repo.find_by_person_and_project(
            person_id, cmd.project_id
        )
        if existing is not None:
            raise ConflictError(
                message=f"Person {person_id} already subscribed to project {cmd.project_id}",
                user_message="You are already subscribed to this project",
                error_code="SUBSCRIPTION_ALREADY_EXISTS",
            )

        # Build subscription entity — status is always PENDING for public subscribe
        now = datetime.now(UTC).isoformat()
        subscription = Subscription(
            id=str(ULID()),
            project_id=cmd.project_id,
            person_id=person_id,
            status=SubscriptionStatus.PENDING,
            notes=cmd.notes or "",
            is_active=False,
            subscription_date=now,
            created_at=now,
            updated_at=now,
        )

        await self._subscription_repo.save(subscription)

        # Publish event — failure is non-fatal
        try:
            await self._event_publisher.publish(
                "projects.subscription.created",
                {
                    "subscription_id": subscription.id,
                    "project_id": subscription.project_id,
                    "person_id": subscription.person_id,
                    "status": str(subscription.status),
                    "notification_emails": project.notification_emails,
                },
            )
        except Exception:
            logger.warning(
                "public_service.subscribe.event_publish_failed",
                subscription_id=subscription.id,
                project_id=cmd.project_id,
            )

        logger.info(
            "public_service.subscribe.completed",
            subscription_id=subscription.id,
            project_id=cmd.project_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return SubscriptionResponse.from_domain(subscription)
