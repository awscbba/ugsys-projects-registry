"""ProjectService — application service for project lifecycle management."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from ulid import ULID

from src.application.commands.project_commands import (
    CreateProjectCommand,
    DeleteProjectCommand,
    UpdateProjectCommand,
)
from src.application.dtos.project_dtos import ProjectResponse, PublicProjectResponse
from src.application.queries.project_queries import ProjectListQuery
from src.application.tracing import traced
from src.domain.entities.project import Project
from src.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

logger = structlog.get_logger()


class ProjectService:
    """Application service for project lifecycle management."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        subscription_repo: SubscriptionRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._project_repo = project_repo
        self._subscription_repo = subscription_repo
        self._event_publisher = event_publisher

    @traced
    async def create(self, cmd: CreateProjectCommand) -> ProjectResponse:
        """Create a new project."""
        logger.info("project_service.create.started", name=cmd.name, created_by=cmd.created_by)
        start = time.perf_counter()

        if len(cmd.name) > 200:
            raise ValidationError(
                message=f"Project name exceeds 200 chars: {len(cmd.name)}",
                user_message="Project name must not exceed 200 characters",
                error_code="VALIDATION_ERROR",
            )

        if len(cmd.description) > 5000:
            raise ValidationError(
                message=f"Project description exceeds 5000 chars: {len(cmd.description)}",
                user_message="Project description must not exceed 5000 characters",
                error_code="VALIDATION_ERROR",
            )

        if cmd.end_date and cmd.start_date and cmd.end_date <= cmd.start_date:
            raise ValidationError(
                message=f"end_date {cmd.end_date!r} must be after start_date {cmd.start_date!r}",
                user_message="End date must be after start date",
                error_code="INVALID_DATE_RANGE",
            )

        if cmd.max_participants < 1:
            raise ValidationError(
                message=f"max_participants={cmd.max_participants} must be >= 1",
                user_message="Max participants must be at least 1",
                error_code="INVALID_MAX_PARTICIPANTS",
            )

        now = datetime.now(tz=UTC).isoformat()
        project = Project(
            id=str(ULID()),
            name=cmd.name,
            description=cmd.description,
            rich_text=cmd.rich_text or "",
            category=cmd.category,
            status=ProjectStatus.PENDING,
            is_enabled=False,
            max_participants=cmd.max_participants,
            current_participants=0,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            created_by=cmd.created_by,
            notification_emails=list(cmd.notification_emails),
            images=[cmd.image] if cmd.image else [],
            created_at=now,
            updated_at=now,
        )

        project = await self._project_repo.save(project)

        await self._publish_event(
            "projects.project.created",
            {"project_id": project.id, "name": project.name, "created_by": project.created_by},
        )

        logger.info(
            "project_service.create.completed",
            project_id=project.id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return ProjectResponse.from_domain(project)

    @traced
    async def get(self, project_id: str) -> ProjectResponse:
        """Get a project by ID."""
        logger.info("project_service.get.started", project_id=project_id)
        start = time.perf_counter()

        project = await self._project_repo.find_by_id(project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        logger.info(
            "project_service.get.completed",
            project_id=project_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return ProjectResponse.from_domain(project)

    @traced
    async def list_all(self, query: ProjectListQuery) -> tuple[list[ProjectResponse], int]:
        """List all projects (admin only) with pagination and filters."""
        logger.info("project_service.list_all.started", page=query.page, page_size=query.page_size)
        start = time.perf_counter()

        projects, total = await self._project_repo.list_by_query(query)
        responses = [ProjectResponse.from_domain(p) for p in projects]

        logger.info(
            "project_service.list_all.completed",
            total=total,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return responses, total

    @traced
    async def list_public(self) -> list[PublicProjectResponse]:
        """List public (active + enabled) projects."""
        logger.info("project_service.list_public.started")
        start = time.perf_counter()

        projects = await self._project_repo.list_public(limit=100)
        responses = [PublicProjectResponse.from_domain(p) for p in projects]

        logger.info(
            "project_service.list_public.completed",
            count=len(responses),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return responses

    @traced
    async def update(self, cmd: UpdateProjectCommand) -> ProjectResponse:
        """Update an existing project."""
        logger.info(
            "project_service.update.started",
            project_id=cmd.project_id,
            requester_id=cmd.requester_id,
        )
        start = time.perf_counter()

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        if not cmd.is_admin and project.created_by != cmd.requester_id:
            raise AuthorizationError(
                message=(f"User {cmd.requester_id} attempted IDOR on project {cmd.project_id}"),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        # Apply non-None fields from command
        if cmd.name is not None:
            project.name = cmd.name
        if cmd.description is not None:
            project.description = cmd.description
        if cmd.rich_text is not None:
            project.rich_text = cmd.rich_text
        if cmd.category is not None:
            project.category = cmd.category
        if cmd.start_date is not None:
            project.start_date = cmd.start_date
        if cmd.end_date is not None:
            project.end_date = cmd.end_date
        if cmd.max_participants is not None:
            project.max_participants = cmd.max_participants
        if cmd.notification_emails is not None:
            project.notification_emails = list(cmd.notification_emails)
        if cmd.image is not None:
            project.images = [cmd.image]
        if cmd.is_enabled is not None:
            project.is_enabled = cmd.is_enabled

        project.updated_at = datetime.now(tz=UTC).isoformat()

        new_status: ProjectStatus | None = None
        if cmd.status is not None:
            new_status = ProjectStatus(cmd.status)
            project.status = new_status

        terminal_statuses = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}

        if new_status in terminal_statuses:
            # Cascade: disable project and cancel all active/pending subscriptions
            project.is_enabled = False
            await self._project_repo.update(project)

            subs, _ = await self._subscription_repo.list_by_project(
                cmd.project_id, page=1, page_size=10000
            )
            now = datetime.now(tz=UTC).isoformat()
            for sub in subs:
                if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING):
                    sub.status = SubscriptionStatus.CANCELLED
                    sub.is_active = False
                    sub.updated_at = now
                    await self._subscription_repo.update(sub)
        else:
            await self._project_repo.update(project)

        if new_status == ProjectStatus.ACTIVE:
            await self._publish_event(
                "projects.project.published",
                {"project_id": project.id, "name": project.name},
            )

        await self._publish_event(
            "projects.project.updated",
            {"project_id": project.id, "name": project.name, "status": str(project.status)},
        )

        logger.info(
            "project_service.update.completed",
            project_id=project.id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return ProjectResponse.from_domain(project)

    @traced
    async def delete(self, cmd: DeleteProjectCommand) -> None:
        """Delete a project (admin only)."""
        logger.info(
            "project_service.delete.started",
            project_id=cmd.project_id,
            requester_id=cmd.requester_id,
        )
        start = time.perf_counter()

        if not cmd.is_admin:
            raise AuthorizationError(
                message=(
                    f"User {cmd.requester_id} attempted to delete"
                    f" project {cmd.project_id} without admin role"
                ),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        await self._project_repo.delete(cmd.project_id)

        await self._publish_event(
            "projects.project.deleted",
            {"project_id": cmd.project_id},
        )

        logger.info(
            "project_service.delete.completed",
            project_id=cmd.project_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def _publish_event(self, detail_type: str, payload: dict[str, Any]) -> None:
        """Publish a domain event, catching and logging any failure without re-raising."""
        try:
            await self._event_publisher.publish(detail_type, payload)
        except Exception as exc:
            logger.warning(
                "project_service.event_publish_failed",
                detail_type=detail_type,
                error=str(exc),
            )
