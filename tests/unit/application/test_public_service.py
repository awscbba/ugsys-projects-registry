"""Unit tests for PublicService application service.

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 17.1, 17.3

Tests cover:
- register with existing email raises ConflictError(EMAIL_ALREADY_EXISTS)
- register happy path returns PublicRegisterResult with correct user_id and email
- subscribe with missing project raises NotFoundError(PROJECT_NOT_FOUND)
- subscribe duplicate raises ConflictError(SUBSCRIPTION_ALREADY_EXISTS)
- subscribe always creates subscription with status=pending
- subscribe with existing email uses email as person_id
- subscribe with event publish failure does not raise
- Property 13: Public subscription always pending (hypothesis)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.public_commands import (
    PublicRegisterCommand,
    PublicSubscribeCommand,
)
from src.application.dtos.public_dtos import PublicRegisterResult
from src.application.services.public_service import PublicService
from src.domain.entities.project import Project
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.identity_client import IdentityClient
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_project(
    *,
    id: str = "01JPROJECT",
    name: str = "Test Project",
    description: str = "A test project",
    notification_emails: list[str] | None = None,
) -> Project:
    """Factory for a valid Project domain entity."""
    return Project(
        id=id,
        name=name,
        description=description,
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        max_participants=10,
        current_participants=0,
        start_date="2026-01-01",
        end_date="2026-12-31",
        created_by="owner-id",
        notification_emails=notification_emails or ["notify@example.com"],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_subscription(
    *,
    id: str = "01JSUB",
    project_id: str = "01JPROJECT",
    person_id: str = "user-456",
    status: SubscriptionStatus = SubscriptionStatus.PENDING,
) -> Subscription:
    """Factory for a valid Subscription domain entity."""
    return Subscription(
        id=id,
        project_id=project_id,
        person_id=person_id,
        status=status,
        notes="",
        is_active=False,
        subscription_date="2026-01-01T00:00:00+00:00",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_service(
    identity_client: IdentityClient | None = None,
    subscription_repo: SubscriptionRepository | None = None,
    project_repo: ProjectRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> PublicService:
    """Factory for PublicService with optional mock overrides."""
    return PublicService(
        identity_client=identity_client or AsyncMock(spec=IdentityClient),
        subscription_repo=subscription_repo or AsyncMock(spec=SubscriptionRepository),
        project_repo=project_repo or AsyncMock(spec=ProjectRepository),
        event_publisher=event_publisher or AsyncMock(spec=EventPublisher),
    )


# ── register() tests ──────────────────────────────────────────────────────────


class TestPublicServiceRegister:
    """Tests for PublicService.register()."""

    @pytest.mark.asyncio
    async def test_register_with_existing_email_raises_conflict(self) -> None:
        # Arrange
        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = True
        service = make_service(identity_client=identity_client)
        cmd = PublicRegisterCommand(
            email="existing@example.com",
            first_name="Jane",
            last_name="Doe",
            password="Str0ng!Pass",
        )

        # Act + Assert
        with pytest.raises(ConflictError) as exc_info:
            await service.register(cmd)

        assert exc_info.value.error_code == "EMAIL_ALREADY_EXISTS"
        assert "existing@example.com" not in exc_info.value.user_message
        identity_client.create_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_happy_path(self) -> None:
        # Arrange
        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = False
        identity_client.create_user.return_value = "user-123"
        service = make_service(identity_client=identity_client)
        cmd = PublicRegisterCommand(
            email="new@example.com",
            first_name="John",
            last_name="Smith",
            password="Str0ng!Pass",
        )

        # Act
        result = await service.register(cmd)

        # Assert
        assert isinstance(result, PublicRegisterResult)
        assert result.user_id == "user-123"
        assert result.email == "new@example.com"
        identity_client.create_user.assert_called_once_with(
            email="new@example.com",
            full_name="John Smith",
            password="Str0ng!Pass",
        )


# ── subscribe() tests ─────────────────────────────────────────────────────────


class TestPublicServiceSubscribe:
    """Tests for PublicService.subscribe()."""

    @pytest.mark.asyncio
    async def test_subscribe_project_not_found_raises_not_found(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = None
        service = make_service(project_repo=project_repo)
        cmd = PublicSubscribeCommand(
            project_id="missing-project",
            email="user@example.com",
            first_name="Alice",
            last_name="Wonder",
        )

        # Act + Assert
        with pytest.raises(NotFoundError) as exc_info:
            await service.subscribe(cmd)

        assert exc_info.value.error_code == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_raises_conflict(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project()

        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = True  # email exists

        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        subscription_repo.find_by_person_and_project.return_value = make_subscription()

        service = make_service(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
        )
        cmd = PublicSubscribeCommand(
            project_id="01JPROJECT",
            email="user@example.com",
            first_name="Alice",
            last_name="Wonder",
        )

        # Act + Assert
        with pytest.raises(ConflictError) as exc_info:
            await service.subscribe(cmd)

        assert exc_info.value.error_code == "SUBSCRIPTION_ALREADY_EXISTS"
        subscription_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_subscribe_always_creates_pending_status(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project()

        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = False
        identity_client.create_user.return_value = "user-456"

        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        subscription_repo.find_by_person_and_project.return_value = None
        subscription_repo.save.side_effect = lambda sub: sub

        service = make_service(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
        )
        cmd = PublicSubscribeCommand(
            project_id="01JPROJECT",
            email="new@example.com",
            first_name="Bob",
            last_name="Builder",
        )

        # Act
        result = await service.subscribe(cmd)

        # Assert — status is always pending regardless of any input
        assert result.status == "pending"
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_subscribe_existing_email_uses_email_as_person_id(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project()

        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = True  # email already exists

        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        subscription_repo.find_by_person_and_project.return_value = None
        subscription_repo.save.side_effect = lambda sub: sub

        service = make_service(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
        )
        cmd = PublicSubscribeCommand(
            project_id="01JPROJECT",
            email="existing@example.com",
            first_name="Carol",
            last_name="King",
        )

        # Act
        result = await service.subscribe(cmd)

        # Assert — email used as person_id placeholder, create_user NOT called
        identity_client.create_user.assert_not_called()
        subscription_repo.find_by_person_and_project.assert_called_once_with(
            "existing@example.com", "01JPROJECT"
        )
        assert result.person_id == "existing@example.com"

    @pytest.mark.asyncio
    async def test_subscribe_event_publish_failure_does_not_raise(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project()

        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = False
        identity_client.create_user.return_value = "user-789"

        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        subscription_repo.find_by_person_and_project.return_value = None
        subscription_repo.save.side_effect = lambda sub: sub

        event_publisher = AsyncMock(spec=EventPublisher)
        event_publisher.publish.side_effect = Exception("EventBridge unavailable")

        service = make_service(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
            event_publisher=event_publisher,
        )
        cmd = PublicSubscribeCommand(
            project_id="01JPROJECT",
            email="user@example.com",
            first_name="Dave",
            last_name="Grohl",
        )

        # Act — must not raise even though publish fails
        result = await service.subscribe(cmd)

        # Assert — subscription was still saved
        subscription_repo.save.assert_called_once()
        assert result.status == "pending"


# ── Property 13: Public subscription always pending ───────────────────────────


class TestPublicServiceProperties:
    """Property-based tests for PublicService."""

    @given(
        project_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
            ),
        ),
        email=st.emails(),
        person_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
            ),
        ),
    )
    @settings(max_examples=100)
    def test_property_13_public_subscription_always_pending(
        self,
        project_id: str,
        email: str,
        person_id: str,
    ) -> None:
        """Public subscribe always produces a PENDING subscription.

        Validates: Requirements 7.7
        """
        import asyncio

        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project(id=project_id)

        identity_client = AsyncMock(spec=IdentityClient)
        identity_client.check_email_exists.return_value = False
        identity_client.create_user.return_value = person_id

        subscription_repo = AsyncMock(spec=SubscriptionRepository)
        subscription_repo.find_by_person_and_project.return_value = None
        subscription_repo.save.side_effect = lambda sub: sub

        event_publisher = AsyncMock(spec=EventPublisher)

        service = make_service(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
            event_publisher=event_publisher,
        )
        cmd = PublicSubscribeCommand(
            project_id=project_id,
            email=email,
            first_name="Test",
            last_name="User",
        )

        # Act
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.subscribe(cmd))
        finally:
            loop.close()

        # Assert — status is ALWAYS pending regardless of inputs
        assert result.status == "pending"
        assert result.is_active is False
