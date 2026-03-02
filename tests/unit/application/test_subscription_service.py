"""Unit tests for SubscriptionService application service.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10, 4.11,
           10.5, 10.6, 10.7, 10.8, 12.2, 12.6, 17.1, 17.3, 17.4

Tests cover:
- subscribe happy path: ULID generated, status=PENDING, event published with notification_emails
- subscribe super_admin: status=ACTIVE, current_participants incremented
- subscribe duplicate raises ConflictError(SUBSCRIPTION_ALREADY_EXISTS)
- approve increments current_participants and publishes event
- cancel by non-owner non-admin raises AuthorizationError(FORBIDDEN)
- cancel of active subscription decrements current_participants
- list_by_person by different user raises AuthorizationError(FORBIDDEN)
- Property 5: Participant count invariant (hypothesis)
- Property 6: Subscription uniqueness invariant (hypothesis)
- Property 7: Subscription status transition invariant (hypothesis)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.subscription_commands import (
    ApproveSubscriptionCommand,
    CancelSubscriptionCommand,
    CreateSubscriptionCommand,
    RejectSubscriptionCommand,
)
from src.application.services.subscription_service import SubscriptionService
from src.domain.entities.project import Project
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import AuthorizationError, ConflictError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_subscription(
    *,
    id: str = "01JSUB",
    project_id: str = "01JPROJ",
    person_id: str = "01JPERSON",
    status: SubscriptionStatus = SubscriptionStatus.PENDING,
    is_active: bool = False,
) -> Subscription:
    """Factory for a Subscription domain entity."""
    return Subscription(
        id=id,
        project_id=project_id,
        person_id=person_id,
        status=status,
        notes="",
        subscription_date="2026-01-01T00:00:00+00:00",
        is_active=is_active,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_project(
    *,
    id: str = "01JPROJ",
    current_participants: int = 0,
    notification_emails: list[str] | None = None,
) -> Project:
    """Factory for a Project domain entity."""
    return Project(
        id=id,
        name="Test Project",
        description="A test project",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        max_participants=10,
        current_participants=current_participants,
        start_date="2026-01-01",
        end_date="2026-12-31",
        created_by="owner-id",
        notification_emails=notification_emails
        if notification_emails is not None
        else ["notify@example.com"],
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_service(
    *,
    subscription_repo: SubscriptionRepository | None = None,
    project_repo: ProjectRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> tuple[SubscriptionService, AsyncMock, AsyncMock, AsyncMock]:
    """Create a SubscriptionService with mocked dependencies."""
    sub_repo = subscription_repo or AsyncMock(spec=SubscriptionRepository)
    proj_repo = project_repo or AsyncMock(spec=ProjectRepository)
    publisher = event_publisher or AsyncMock(spec=EventPublisher)
    service = SubscriptionService(
        subscription_repo=sub_repo,
        project_repo=proj_repo,
        event_publisher=publisher,
    )
    return service, sub_repo, proj_repo, publisher


# ── Unit tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_happy_path() -> None:
    """subscribe creates a PENDING subscription and publishes event with notification_emails."""
    # Arrange
    project = make_project(notification_emails=["admin@example.com"])
    saved_sub = make_subscription(status=SubscriptionStatus.PENDING)

    service, sub_repo, proj_repo, publisher = make_service()
    proj_repo.find_by_id.return_value = project
    sub_repo.find_by_person_and_project.return_value = None
    sub_repo.save.return_value = saved_sub

    cmd = CreateSubscriptionCommand(
        project_id="01JPROJ",
        person_id="01JPERSON",
        notes="Interested",
        is_super_admin=False,
    )

    # Act
    result = await service.subscribe(cmd)

    # Assert
    sub_repo.save.assert_called_once()
    saved_arg: Subscription = sub_repo.save.call_args[0][0]
    assert saved_arg.status == SubscriptionStatus.PENDING
    assert saved_arg.id  # ULID generated — non-empty
    assert len(saved_arg.id) > 0

    publisher.publish.assert_called_once()
    event_type, payload = publisher.publish.call_args[0]
    assert event_type == "projects.subscription.created"
    assert payload["notification_emails"] == ["admin@example.com"]
    assert payload["project_id"] == "01JPROJ"
    assert payload["person_id"] == "01JPERSON"

    assert result.status == "pending"


@pytest.mark.asyncio
async def test_subscribe_super_admin_creates_active_subscription() -> None:
    """subscribe with is_super_admin=True creates ACTIVE subscription and increments participants."""
    # Arrange
    project = make_project(current_participants=2)
    saved_sub = make_subscription(status=SubscriptionStatus.ACTIVE, is_active=True)

    service, sub_repo, proj_repo, _publisher = make_service()
    proj_repo.find_by_id.return_value = project
    sub_repo.find_by_person_and_project.return_value = None
    sub_repo.save.return_value = saved_sub

    cmd = CreateSubscriptionCommand(
        project_id="01JPROJ",
        person_id="01JPERSON",
        is_super_admin=True,
    )

    # Act
    result = await service.subscribe(cmd)

    # Assert — subscription saved with ACTIVE status
    saved_arg: Subscription = sub_repo.save.call_args[0][0]
    assert saved_arg.status == SubscriptionStatus.ACTIVE
    assert saved_arg.is_active is True

    # project.update called with incremented count
    proj_repo.update.assert_called_once()
    updated_project: Project = proj_repo.update.call_args[0][0]
    assert updated_project.current_participants == 3

    assert result.status == "active"


@pytest.mark.asyncio
async def test_subscribe_duplicate_raises_conflict_error() -> None:
    """subscribe raises ConflictError(SUBSCRIPTION_ALREADY_EXISTS) when already subscribed."""
    # Arrange
    project = make_project()
    existing_sub = make_subscription()

    service, sub_repo, proj_repo, publisher = make_service()
    proj_repo.find_by_id.return_value = project
    sub_repo.find_by_person_and_project.return_value = existing_sub

    cmd = CreateSubscriptionCommand(project_id="01JPROJ", person_id="01JPERSON")

    # Act + Assert
    with pytest.raises(ConflictError) as exc_info:
        await service.subscribe(cmd)

    assert exc_info.value.error_code == "SUBSCRIPTION_ALREADY_EXISTS"
    sub_repo.save.assert_not_called()
    publisher.publish.assert_not_called()


@pytest.mark.asyncio
async def test_approve_increments_current_participants_and_publishes_event() -> None:
    """approve sets status=ACTIVE, increments current_participants, publishes approved event."""
    # Arrange
    pending_sub = make_subscription(status=SubscriptionStatus.PENDING)
    project = make_project(current_participants=2)
    approved_sub = make_subscription(status=SubscriptionStatus.ACTIVE, is_active=True)

    service, sub_repo, proj_repo, publisher = make_service()
    sub_repo.find_by_id.return_value = pending_sub
    proj_repo.find_by_id.return_value = project
    sub_repo.update.return_value = approved_sub

    cmd = ApproveSubscriptionCommand(
        subscription_id="01JSUB",
        project_id="01JPROJ",
        admin_id="admin-id",
    )

    # Act
    result = await service.approve(cmd)

    # Assert — project updated with incremented count
    proj_repo.update.assert_called_once()
    updated_project: Project = proj_repo.update.call_args[0][0]
    assert updated_project.current_participants == 3

    # event published
    publisher.publish.assert_called_once()
    event_type, payload = publisher.publish.call_args[0]
    assert event_type == "projects.subscription.approved"
    assert payload["subscription_id"] == approved_sub.id

    assert result.status == "active"


@pytest.mark.asyncio
async def test_cancel_by_non_owner_non_admin_raises_authorization_error() -> None:
    """cancel raises AuthorizationError(FORBIDDEN) when requester is not owner or admin."""
    # Arrange
    sub = make_subscription(person_id="owner-id")

    service, sub_repo, _proj_repo, publisher = make_service()
    sub_repo.find_by_id.return_value = sub

    cmd = CancelSubscriptionCommand(
        subscription_id="01JSUB",
        project_id="01JPROJ",
        requester_id="other-user",
        is_admin=False,
    )

    # Act + Assert
    with pytest.raises(AuthorizationError) as exc_info:
        await service.cancel(cmd)

    assert exc_info.value.error_code == "FORBIDDEN"
    sub_repo.update.assert_not_called()
    publisher.publish.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_active_subscription_decrements_current_participants() -> None:
    """cancel of ACTIVE subscription decrements project.current_participants."""
    # Arrange
    active_sub = make_subscription(
        person_id="owner-id",
        status=SubscriptionStatus.ACTIVE,
        is_active=True,
    )
    project = make_project(current_participants=3)
    cancelled_sub = make_subscription(
        person_id="owner-id",
        status=SubscriptionStatus.CANCELLED,
        is_active=False,
    )

    service, sub_repo, proj_repo, _publisher = make_service()
    sub_repo.find_by_id.return_value = active_sub
    proj_repo.find_by_id.return_value = project
    sub_repo.update.return_value = cancelled_sub

    cmd = CancelSubscriptionCommand(
        subscription_id="01JSUB",
        project_id="01JPROJ",
        requester_id="owner-id",
        is_admin=False,
    )

    # Act
    result = await service.cancel(cmd)

    # Assert — project updated with decremented count
    proj_repo.update.assert_called_once()
    updated_project: Project = proj_repo.update.call_args[0][0]
    assert updated_project.current_participants == 2

    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_list_by_person_by_different_user_raises_authorization_error() -> None:
    """list_by_person raises AuthorizationError(FORBIDDEN) when requester != person_id."""
    # Arrange
    service, sub_repo, _proj_repo, _publisher = make_service()

    # Act + Assert
    with pytest.raises(AuthorizationError) as exc_info:
        await service.list_by_person(
            person_id="user-1",
            requester_id="user-2",
            is_admin=False,
        )

    assert exc_info.value.error_code == "FORBIDDEN"
    sub_repo.list_by_person.assert_not_called()


# ── Property-based tests ──────────────────────────────────────────────────────


class InMemorySubscriptionRepository:
    """Minimal in-memory SubscriptionRepository for property tests."""

    def __init__(self) -> None:
        self._store: dict[str, Subscription] = {}

    async def save(self, subscription: Subscription) -> Subscription:
        self._store[subscription.id] = subscription
        return subscription

    async def find_by_id(self, subscription_id: str) -> Subscription | None:
        return self._store.get(subscription_id)

    async def update(self, subscription: Subscription) -> Subscription:
        self._store[subscription.id] = subscription
        return subscription

    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> Subscription | None:
        for sub in self._store.values():
            if sub.person_id == person_id and sub.project_id == project_id:
                return sub
        return None

    async def list_by_project(
        self, project_id: str, page: int, page_size: int
    ) -> tuple[list[Subscription], int]:
        items = [s for s in self._store.values() if s.project_id == project_id]
        return items, len(items)

    async def list_by_person(self, person_id: str) -> list[Subscription]:
        return [s for s in self._store.values() if s.person_id == person_id]

    async def cancel_all_for_person(self, person_id: str) -> int:
        count = 0
        for sub in self._store.values():
            if sub.person_id == person_id and sub.status in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.PENDING,
            ):
                sub.status = SubscriptionStatus.CANCELLED
                sub.is_active = False
                count += 1
        return count


class InMemoryProjectRepository:
    """Minimal in-memory ProjectRepository for property tests."""

    def __init__(self, project: Project) -> None:
        self._project = project

    async def save(self, project: Project) -> Project:
        self._project = project
        return project

    async def find_by_id(self, project_id: str) -> Project | None:
        if self._project.id == project_id:
            return self._project
        return None

    async def update(self, project: Project) -> Project:
        self._project = project
        return project

    async def delete(self, project_id: str) -> None:
        pass

    async def list_paginated(
        self, page: int, page_size: int, **kwargs: object
    ) -> tuple[list[Project], int]:
        return [self._project], 1

    async def list_public(self, limit: int) -> list[Project]:
        return [self._project]

    async def list_by_query(self, query: object) -> tuple[list[Project], int]:
        return [self._project], 1


@pytest.mark.asyncio
@given(
    n_approvals=st.integers(min_value=0, max_value=10),
    n_cancellations_raw=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=50)
async def test_property_5_participant_count_invariant(
    n_approvals: int, n_cancellations_raw: int
) -> None:
    """Property 5: Participant count invariant.

    Validates: Requirements 4.2, 4.4, 4.6, 2.10

    After n_approvals approvals and n_cancellations cancellations,
    project.current_participants == n_approvals - n_cancellations.
    """
    n_cancellations = min(n_cancellations_raw, n_approvals)

    project = make_project(id="01JPROJ", current_participants=0)
    sub_repo = InMemorySubscriptionRepository()
    proj_repo = InMemoryProjectRepository(project)
    publisher = AsyncMock(spec=EventPublisher)

    service = SubscriptionService(
        subscription_repo=sub_repo,
        project_repo=proj_repo,
        event_publisher=publisher,
    )

    # Create and approve n_approvals subscriptions
    approved_sub_ids: list[str] = []
    for i in range(n_approvals):
        person_id = f"person-{i:04d}"

        # Subscribe (pending)
        create_cmd = CreateSubscriptionCommand(
            project_id="01JPROJ",
            person_id=person_id,
        )
        await service.subscribe(create_cmd)

        # Find the saved subscription id
        saved = await sub_repo.find_by_person_and_project(person_id, "01JPROJ")
        assert saved is not None
        real_sub_id = saved.id

        # Approve
        approve_cmd = ApproveSubscriptionCommand(
            subscription_id=real_sub_id,
            project_id="01JPROJ",
            admin_id="admin",
        )
        await service.approve(approve_cmd)
        approved_sub_ids.append(real_sub_id)

    # Cancel n_cancellations of the approved subscriptions
    for i in range(n_cancellations):
        sub_id = approved_sub_ids[i]
        sub = await sub_repo.find_by_id(sub_id)
        assert sub is not None
        person_id = sub.person_id

        cancel_cmd = CancelSubscriptionCommand(
            subscription_id=sub_id,
            project_id="01JPROJ",
            requester_id=person_id,
            is_admin=False,
        )
        await service.cancel(cancel_cmd)

    # Assert
    final_project = await proj_repo.find_by_id("01JPROJ")
    assert final_project is not None
    assert final_project.current_participants == n_approvals - n_cancellations


@pytest.mark.asyncio
@given(
    person_id=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=4,
        max_size=20,
    ),
    project_id=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=4,
        max_size=20,
    ),
)
@settings(max_examples=50)
async def test_property_6_subscription_uniqueness_invariant(
    person_id: str, project_id: str
) -> None:
    """Property 6: Subscription uniqueness invariant.

    Validates: Requirements 4.3, 17.6

    First subscribe succeeds; second subscribe raises ConflictError(SUBSCRIPTION_ALREADY_EXISTS).
    """
    project = make_project(id=project_id)
    sub_repo = InMemorySubscriptionRepository()
    proj_repo = InMemoryProjectRepository(project)
    publisher = AsyncMock(spec=EventPublisher)

    service = SubscriptionService(
        subscription_repo=sub_repo,
        project_repo=proj_repo,
        event_publisher=publisher,
    )

    cmd = CreateSubscriptionCommand(project_id=project_id, person_id=person_id)

    # First subscribe — must succeed
    result = await service.subscribe(cmd)
    assert result is not None

    # Second subscribe — must raise ConflictError
    with pytest.raises(ConflictError) as exc_info:
        await service.subscribe(cmd)

    assert exc_info.value.error_code == "SUBSCRIPTION_ALREADY_EXISTS"


@pytest.mark.asyncio
@given(
    transition=st.sampled_from(["approve", "reject", "cancel"]),
)
@settings(max_examples=30)
async def test_property_7_status_transition_invariant(transition: str) -> None:
    """Property 7: Subscription status transition invariant.

    Validates: Requirements 4.1, 4.4, 4.5, 4.6, 17.1

    After subscribe (pending):
    - approve → status=ACTIVE
    - reject  → status=REJECTED
    - cancel  → status=CANCELLED
    """
    project = make_project(id="01JPROJ", current_participants=0)
    sub_repo = InMemorySubscriptionRepository()
    proj_repo = InMemoryProjectRepository(project)
    publisher = AsyncMock(spec=EventPublisher)

    service = SubscriptionService(
        subscription_repo=sub_repo,
        project_repo=proj_repo,
        event_publisher=publisher,
    )

    # Subscribe — creates PENDING subscription
    create_cmd = CreateSubscriptionCommand(
        project_id="01JPROJ",
        person_id="person-001",
    )
    await service.subscribe(create_cmd)

    saved = await sub_repo.find_by_person_and_project("person-001", "01JPROJ")
    assert saved is not None
    assert saved.status == SubscriptionStatus.PENDING
    sub_id = saved.id

    if transition == "approve":
        cmd = ApproveSubscriptionCommand(
            subscription_id=sub_id,
            project_id="01JPROJ",
            admin_id="admin",
        )
        await service.approve(cmd)
        final = await sub_repo.find_by_id(sub_id)
        assert final is not None
        assert final.status == SubscriptionStatus.ACTIVE

    elif transition == "reject":
        cmd = RejectSubscriptionCommand(
            subscription_id=sub_id,
            project_id="01JPROJ",
            admin_id="admin",
        )
        await service.reject(cmd)
        final = await sub_repo.find_by_id(sub_id)
        assert final is not None
        assert final.status == SubscriptionStatus.REJECTED

    elif transition == "cancel":
        cmd = CancelSubscriptionCommand(
            subscription_id=sub_id,
            project_id="01JPROJ",
            requester_id="person-001",
            is_admin=False,
        )
        await service.cancel(cmd)
        final = await sub_repo.find_by_id(sub_id)
        assert final is not None
        assert final.status == SubscriptionStatus.CANCELLED
