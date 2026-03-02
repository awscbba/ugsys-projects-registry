"""Unit tests for ProjectService application service.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10,
           3.1, 3.2, 10.1, 10.2, 10.3, 10.4, 10.10, 12.1, 12.2, 17.1, 17.3, 17.4

Tests cover:
- create happy path: ULID generated, status=PENDING, current_participants=0, event published
- create with end_date < start_date raises ValidationError(INVALID_DATE_RANGE)
- create with max_participants < 1 raises ValidationError(INVALID_MAX_PARTICIPANTS)
- create with event publish failure does not raise (logged only)
- update by non-owner non-admin raises AuthorizationError(FORBIDDEN)
- update status→active publishes projects.project.published
- update status→cancelled cascades subscriptions
- delete by non-admin raises AuthorizationError(FORBIDDEN)
- Property 2: Project creation invariants (hypothesis)
- Property 3: Date range validation (hypothesis)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.project_commands import (
    CreateProjectCommand,
    DeleteProjectCommand,
    UpdateProjectCommand,
)
from src.application.services.project_service import ProjectService
from src.domain.entities.project import Project
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import AuthorizationError, ValidationError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_project(
    *,
    id: str = "01JPROJECT",
    name: str = "Test Project",
    description: str = "A test project",
    created_by: str = "owner-id",
    status: ProjectStatus = ProjectStatus.PENDING,
    max_participants: int = 10,
    current_participants: int = 0,
    start_date: str = "2026-01-01",
    end_date: str = "2026-12-31",
) -> Project:
    """Factory for a valid Project domain entity."""
    return Project(
        id=id,
        name=name,
        description=description,
        rich_text="",
        category="tech",
        status=status,
        is_enabled=False,
        max_participants=max_participants,
        current_participants=current_participants,
        start_date=start_date,
        end_date=end_date,
        created_by=created_by,
        notification_emails=["notify@example.com"],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_create_command(
    *,
    name: str = "Test Project",
    description: str = "A test project",
    category: str = "tech",
    start_date: str = "2026-01-01",
    end_date: str = "2026-12-31",
    max_participants: int = 10,
    notification_emails: list[str] | None = None,
    created_by: str = "user-123",
) -> CreateProjectCommand:
    """Factory for a valid CreateProjectCommand."""
    return CreateProjectCommand(
        name=name,
        description=description,
        category=category,
        start_date=start_date,
        end_date=end_date,
        max_participants=max_participants,
        notification_emails=notification_emails or ["notify@example.com"],
        created_by=created_by,
    )


def make_service(
    project_repo: ProjectRepository | None = None,
    subscription_repo: SubscriptionRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> ProjectService:
    """Factory for ProjectService with optional mock overrides."""
    return ProjectService(
        project_repo=project_repo or AsyncMock(spec=ProjectRepository),
        subscription_repo=subscription_repo or AsyncMock(spec=SubscriptionRepository),
        event_publisher=event_publisher or AsyncMock(spec=EventPublisher),
    )


# ── create() tests ────────────────────────────────────────────────────────────


class TestProjectServiceCreate:
    """Tests for ProjectService.create()."""

    @pytest.mark.asyncio
    async def test_create_happy_path(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        saved_project = make_project(id="01JNEWPROJECT", name="New Project", created_by="user-123")
        project_repo.save.return_value = saved_project
        event_publisher.publish.return_value = None

        service = make_service(project_repo=project_repo, event_publisher=event_publisher)
        cmd = make_create_command(name="New Project", created_by="user-123")

        # Act
        result = await service.create(cmd)

        # Assert — ULID generated (non-empty id)
        assert result.id != ""
        # Assert — status is PENDING
        assert result.status == str(ProjectStatus.PENDING)
        # Assert — current_participants is 0
        assert result.current_participants == 0
        # Assert — event published once with correct detail_type
        event_publisher.publish.assert_called_once()
        publish_call_args = event_publisher.publish.call_args
        assert publish_call_args[0][0] == "projects.project.created"

    @pytest.mark.asyncio
    async def test_create_end_date_before_start_date_raises_validation_error(self) -> None:
        # Arrange
        service = make_service()
        cmd = make_create_command(start_date="2026-12-01", end_date="2026-11-01")

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.create(cmd)

        assert exc_info.value.error_code == "INVALID_DATE_RANGE"

    @pytest.mark.asyncio
    async def test_create_end_date_equal_to_start_date_raises_validation_error(self) -> None:
        # Arrange
        service = make_service()
        cmd = make_create_command(start_date="2026-06-01", end_date="2026-06-01")

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.create(cmd)

        assert exc_info.value.error_code == "INVALID_DATE_RANGE"

    @pytest.mark.asyncio
    async def test_create_max_participants_zero_raises_validation_error(self) -> None:
        # Arrange
        service = make_service()
        cmd = make_create_command(max_participants=0)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.create(cmd)

        assert exc_info.value.error_code == "INVALID_MAX_PARTICIPANTS"

    @pytest.mark.asyncio
    async def test_create_max_participants_negative_raises_validation_error(self) -> None:
        # Arrange
        service = make_service()
        cmd = make_create_command(max_participants=-5)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.create(cmd)

        assert exc_info.value.error_code == "INVALID_MAX_PARTICIPANTS"

    @pytest.mark.asyncio
    async def test_create_event_publish_failure_does_not_raise(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project_repo.save.return_value = make_project()
        event_publisher.publish.side_effect = Exception("EventBridge down")

        service = make_service(project_repo=project_repo, event_publisher=event_publisher)
        cmd = make_create_command()

        # Act — must not raise despite event publish failure
        result = await service.create(cmd)

        # Assert — project still returned
        assert result is not None
        assert result.id != ""

    @pytest.mark.asyncio
    async def test_create_sets_status_pending(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.save.return_value = make_project(status=ProjectStatus.PENDING)
        service = make_service(project_repo=project_repo)
        cmd = make_create_command()

        # Act
        result = await service.create(cmd)

        # Assert
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_create_sets_current_participants_zero(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.save.return_value = make_project(current_participants=0)
        service = make_service(project_repo=project_repo)
        cmd = make_create_command()

        # Act
        result = await service.create(cmd)

        # Assert
        assert result.current_participants == 0


# ── update() tests ────────────────────────────────────────────────────────────


class TestProjectServiceUpdate:
    """Tests for ProjectService.update()."""

    @pytest.mark.asyncio
    async def test_update_by_non_owner_non_admin_raises_authorization_error(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project(created_by="owner-id")

        service = make_service(project_repo=project_repo)
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="other-user",
            is_admin=False,
            name="New Name",
        )

        # Act + Assert
        with pytest.raises(AuthorizationError) as exc_info:
            await service.update(cmd)

        assert exc_info.value.error_code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_update_by_owner_succeeds(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project = make_project(created_by="owner-id")
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project

        service = make_service(project_repo=project_repo)
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="owner-id",
            is_admin=False,
            name="Updated Name",
        )

        # Act — should not raise
        result = await service.update(cmd)

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_by_admin_non_owner_succeeds(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project = make_project(created_by="owner-id")
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project

        service = make_service(project_repo=project_repo)
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="admin-user",
            is_admin=True,
            name="Admin Updated Name",
        )

        # Act — should not raise
        result = await service.update(cmd)

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_status_to_active_publishes_project_published_event(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project = make_project(created_by="owner-id", status=ProjectStatus.PENDING)
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project
        event_publisher.publish.return_value = None

        service = make_service(project_repo=project_repo, event_publisher=event_publisher)
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="owner-id",
            is_admin=False,
            status="active",
        )

        # Act
        await service.update(cmd)

        # Assert — projects.project.published was published
        published_calls = [c[0][0] for c in event_publisher.publish.call_args_list]
        assert "projects.project.published" in published_calls

    @pytest.mark.asyncio
    async def test_update_status_to_cancelled_cascades_subscriptions(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project = make_project(created_by="owner-id", status=ProjectStatus.ACTIVE)
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project

        active_sub = Subscription(
            id="01JSUB1",
            project_id="01JPROJECT",
            person_id="01JPERSON1",
            status=SubscriptionStatus.ACTIVE,
        )
        pending_sub = Subscription(
            id="01JSUB2",
            project_id="01JPROJECT",
            person_id="01JPERSON2",
            status=SubscriptionStatus.PENDING,
        )
        subscription_repo.list_by_project.return_value = ([active_sub, pending_sub], 2)
        subscription_repo.update.return_value = active_sub
        event_publisher.publish.return_value = None

        service = make_service(
            project_repo=project_repo,
            subscription_repo=subscription_repo,
            event_publisher=event_publisher,
        )
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="owner-id",
            is_admin=False,
            status="cancelled",
        )

        # Act
        await service.update(cmd)

        # Assert — subscription_repo.update called twice (once per subscription)
        assert subscription_repo.update.call_count == 2

        # Assert — each subscription has status=CANCELLED
        updated_subs = [c[0][0] for c in subscription_repo.update.call_args_list]
        for sub in updated_subs:
            assert sub.status == SubscriptionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_update_status_to_completed_cascades_subscriptions(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project = make_project(created_by="owner-id", status=ProjectStatus.ACTIVE)
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project

        active_sub = Subscription(
            id="01JSUB1",
            project_id="01JPROJECT",
            person_id="01JPERSON1",
            status=SubscriptionStatus.ACTIVE,
        )
        subscription_repo.list_by_project.return_value = ([active_sub], 1)
        subscription_repo.update.return_value = active_sub
        event_publisher.publish.return_value = None

        service = make_service(
            project_repo=project_repo,
            subscription_repo=subscription_repo,
            event_publisher=event_publisher,
        )
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="owner-id",
            is_admin=False,
            status="completed",
        )

        # Act
        await service.update(cmd)

        # Assert — subscription updated to CANCELLED
        assert subscription_repo.update.call_count == 1
        updated_sub = subscription_repo.update.call_args[0][0]
        assert updated_sub.status == SubscriptionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_update_status_to_cancelled_skips_already_cancelled_subscriptions(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project = make_project(created_by="owner-id", status=ProjectStatus.ACTIVE)
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = project

        already_cancelled = Subscription(
            id="01JSUB1",
            project_id="01JPROJECT",
            person_id="01JPERSON1",
            status=SubscriptionStatus.CANCELLED,
        )
        already_rejected = Subscription(
            id="01JSUB2",
            project_id="01JPROJECT",
            person_id="01JPERSON2",
            status=SubscriptionStatus.REJECTED,
        )
        subscription_repo.list_by_project.return_value = (
            [already_cancelled, already_rejected],
            2,
        )
        event_publisher.publish.return_value = None

        service = make_service(
            project_repo=project_repo,
            subscription_repo=subscription_repo,
            event_publisher=event_publisher,
        )
        cmd = UpdateProjectCommand(
            project_id="01JPROJECT",
            requester_id="owner-id",
            is_admin=False,
            status="cancelled",
        )

        # Act
        await service.update(cmd)

        # Assert — no updates since all subs are already in terminal state
        subscription_repo.update.assert_not_called()


# ── delete() tests ────────────────────────────────────────────────────────────


class TestProjectServiceDelete:
    """Tests for ProjectService.delete()."""

    @pytest.mark.asyncio
    async def test_delete_by_non_admin_raises_authorization_error(self) -> None:
        # Arrange
        service = make_service()
        cmd = DeleteProjectCommand(
            project_id="01JPROJECT",
            requester_id="regular-user",
            is_admin=False,
        )

        # Act + Assert
        with pytest.raises(AuthorizationError) as exc_info:
            await service.delete(cmd)

        assert exc_info.value.error_code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_delete_by_admin_succeeds(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        project_repo.find_by_id.return_value = make_project()
        project_repo.delete.return_value = None
        event_publisher.publish.return_value = None

        service = make_service(project_repo=project_repo, event_publisher=event_publisher)
        cmd = DeleteProjectCommand(
            project_id="01JPROJECT",
            requester_id="admin-user",
            is_admin=True,
        )

        # Act — should not raise
        await service.delete(cmd)

        # Assert — delete called and event published
        project_repo.delete.assert_called_once_with("01JPROJECT")
        event_publisher.publish.assert_called_once()
        assert event_publisher.publish.call_args[0][0] == "projects.project.deleted"


# ── Property-based tests ──────────────────────────────────────────────────────


class TestProjectServiceProperties:
    """Property-based tests for ProjectService.

    Validates: Requirements 17.1, 17.3, 17.4
    """

    @given(
        name=st.text(min_size=1, max_size=200),
        max_participants=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=50)
    def test_property_2_create_invariants(
        self,
        name: str,
        max_participants: int,
    ) -> None:
        """**Validates: Requirements 2.1, 2.2, 2.3**

        Property 2: Project creation invariants.
        For any valid project creation command, the created project always has:
        - status = PENDING
        - current_participants = 0
        - non-empty id (ULID generated)
        """
        import asyncio

        project_repo = AsyncMock(spec=ProjectRepository)
        event_publisher = AsyncMock(spec=EventPublisher)

        # The saved project reflects what the service builds
        def capture_and_return(project: Project) -> Project:
            return project

        project_repo.save.side_effect = capture_and_return
        event_publisher.publish.return_value = None

        service = make_service(project_repo=project_repo, event_publisher=event_publisher)
        cmd = make_create_command(
            name=name,
            max_participants=max_participants,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.create(cmd))
        finally:
            loop.close()

        # Invariants
        assert result.status == str(ProjectStatus.PENDING)
        assert result.current_participants == 0
        assert result.id != ""

    @given(
        start_year=st.integers(min_value=2025, max_value=2030),
        start_month=st.integers(min_value=1, max_value=12),
        start_day=st.integers(min_value=1, max_value=28),
        delta_days=st.integers(min_value=1, max_value=365),
    )
    @settings(max_examples=50)
    def test_property_3_end_date_before_start_date_always_raises(
        self,
        start_year: int,
        start_month: int,
        start_day: int,
        delta_days: int,
    ) -> None:
        """**Validates: Requirements 2.2, 2.3**

        Property 3: Date range validation.
        For any end_date strictly before start_date, ValidationError(INVALID_DATE_RANGE) is raised.
        """
        import asyncio
        from datetime import date, timedelta

        start_date = f"{start_year}-{start_month:02d}-{start_day:02d}"
        start = date(start_year, start_month, start_day)
        end = start - timedelta(days=delta_days)
        end_date = end.isoformat()

        service = make_service()
        cmd = make_create_command(start_date=start_date, end_date=end_date)

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValidationError) as exc_info:
                loop.run_until_complete(service.create(cmd))
        finally:
            loop.close()

        assert exc_info.value.error_code == "INVALID_DATE_RANGE"
