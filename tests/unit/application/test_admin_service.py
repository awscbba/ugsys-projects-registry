"""Unit tests for AdminService application service.

Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 17.1

Tests cover:
- bulk_action with empty user_ids raises ValidationError(VALIDATION_ERROR)
- bulk_action with invalid action raises ValidationError(VALIDATION_ERROR)
- bulk_action delete for user with active subscriptions returns BUSINESS_RULE_VIOLATION
  and continues processing other users in the batch
- bulk_action delete for user with only cancelled subscriptions succeeds
- bulk_action deactivate calls identity_client.deactivate_user for each user
- dashboard returns correct aggregate counts from mocked repos
- bulk_action continues after per-user exception from identity_client
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from ulid import ULID

from src.application.commands.project_commands import BulkActionCommand
from src.application.services.admin_service import AdminService
from src.domain.entities.project import Project
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import ValidationError
from src.domain.repositories.form_submission_repository import FormSubmissionRepository
from src.domain.repositories.identity_client import IdentityClient
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_subscription(
    person_id: str = "user1",
    project_id: str = "proj1",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    now = "2026-01-01T00:00:00+00:00"
    return Subscription(
        id=str(ULID()),
        project_id=project_id,
        person_id=person_id,
        status=status,
        notes="",
        subscription_date=now,
        is_active=(status == SubscriptionStatus.ACTIVE),
        created_at=now,
        updated_at=now,
    )


def make_project(
    project_id: str = "proj1",
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    now = "2026-01-01T00:00:00+00:00"
    return Project(
        id=project_id,
        name="Test Project",
        description="desc",
        rich_text="",
        category="tech",
        status=status,
        is_enabled=True,
        max_participants=10,
        current_participants=0,
        start_date=now,
        end_date=now,
        created_by="admin1",
        notification_emails=[],
        images=[],
        created_at=now,
        updated_at=now,
    )


def make_service(
    *,
    project_repo: ProjectRepository | None = None,
    subscription_repo: SubscriptionRepository | None = None,
    form_submission_repo: FormSubmissionRepository | None = None,
    identity_client: IdentityClient | None = None,
) -> tuple[AdminService, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    proj_repo = project_repo or AsyncMock(spec=ProjectRepository)
    sub_repo = subscription_repo or AsyncMock(spec=SubscriptionRepository)
    form_repo = form_submission_repo or AsyncMock(spec=FormSubmissionRepository)
    id_client = identity_client or AsyncMock(spec=IdentityClient)
    service = AdminService(
        project_repo=proj_repo,
        subscription_repo=sub_repo,
        form_submission_repo=form_repo,
        identity_client=id_client,
    )
    return service, proj_repo, sub_repo, form_repo, id_client


# ── bulk_action validation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_action_empty_user_ids_raises_validation_error() -> None:
    """bulk_action with user_ids=[] raises ValidationError(VALIDATION_ERROR)."""
    # Arrange
    service, *_ = make_service()
    cmd = BulkActionCommand(action="delete", user_ids=[], requester_id="admin1")

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.bulk_action(cmd)

    assert exc_info.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_bulk_action_invalid_action_raises_validation_error() -> None:
    """bulk_action with action='suspend' raises ValidationError(VALIDATION_ERROR)."""
    # Arrange
    service, *_ = make_service()
    cmd = BulkActionCommand(action="suspend", user_ids=["user1"], requester_id="admin1")

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.bulk_action(cmd)

    assert exc_info.value.error_code == "VALIDATION_ERROR"


# ── bulk_action delete ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_action_delete_user_with_active_subscriptions_returns_business_rule_violation() -> (
    None
):
    """delete user with ACTIVE subscription returns BUSINESS_RULE_VIOLATION for that user;
    other users in the batch are still processed successfully."""
    # Arrange
    active_sub = make_subscription(person_id="user1", status=SubscriptionStatus.ACTIVE)
    service, _proj_repo, sub_repo, _form_repo, id_client = make_service()

    # user1 has an active subscription → blocked
    # user2 has no subscriptions → succeeds
    sub_repo.list_by_person.side_effect = lambda uid: [active_sub] if uid == "user1" else []
    id_client.delete_user.return_value = None

    cmd = BulkActionCommand(
        action="delete",
        user_ids=["user1", "user2"],
        requester_id="admin1",
    )

    # Act
    result = await service.bulk_action(cmd)

    # Assert — user1 blocked, user2 succeeded
    assert result.total == 2
    assert result.failed == 1
    assert result.succeeded == 1

    user1_result = next(r for r in result.results if r.user_id == "user1")
    assert user1_result.success is False
    assert user1_result.error_code == "BUSINESS_RULE_VIOLATION"

    user2_result = next(r for r in result.results if r.user_id == "user2")
    assert user2_result.success is True

    # delete_user called only for user2
    id_client.delete_user.assert_called_once_with("user2")


@pytest.mark.asyncio
async def test_bulk_action_delete_user_with_no_blocking_subscriptions_succeeds() -> None:
    """delete user with only CANCELLED subscriptions calls identity_client.delete_user
    and returns success=True."""
    # Arrange
    cancelled_sub = make_subscription(person_id="user1", status=SubscriptionStatus.CANCELLED)
    service, _proj_repo, sub_repo, _form_repo, id_client = make_service()
    sub_repo.list_by_person.return_value = [cancelled_sub]
    id_client.delete_user.return_value = None

    cmd = BulkActionCommand(action="delete", user_ids=["user1"], requester_id="admin1")

    # Act
    result = await service.bulk_action(cmd)

    # Assert
    assert result.succeeded == 1
    assert result.failed == 0
    id_client.delete_user.assert_called_once_with("user1")

    user1_result = result.results[0]
    assert user1_result.success is True


# ── bulk_action deactivate ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_action_deactivate_calls_identity_client() -> None:
    """bulk_action deactivate calls identity_client.deactivate_user for each user_id."""
    # Arrange
    service, _proj_repo, _sub_repo, _form_repo, id_client = make_service()
    id_client.deactivate_user.return_value = None

    cmd = BulkActionCommand(
        action="deactivate",
        user_ids=["user1", "user2", "user3"],
        requester_id="admin1",
    )

    # Act
    result = await service.bulk_action(cmd)

    # Assert
    assert result.succeeded == 3
    assert result.failed == 0
    assert id_client.deactivate_user.call_count == 3
    id_client.deactivate_user.assert_any_call("user1")
    id_client.deactivate_user.assert_any_call("user2")
    id_client.deactivate_user.assert_any_call("user3")


# ── dashboard ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_returns_aggregate_counts() -> None:
    """dashboard aggregates counts from all repos and returns correct DashboardData."""
    # Arrange
    active_project = make_project(project_id="proj1", status=ProjectStatus.ACTIVE)
    pending_project = make_project(project_id="proj2", status=ProjectStatus.PENDING)

    active_sub = make_subscription(
        person_id="user1", project_id="proj1", status=SubscriptionStatus.ACTIVE
    )
    pending_sub = make_subscription(
        person_id="user2", project_id="proj1", status=SubscriptionStatus.PENDING
    )

    service, proj_repo, sub_repo, form_repo, _id_client = make_service()

    proj_repo.list_by_query.return_value = ([active_project, pending_project], 2)

    # proj1 has 2 subscriptions (1 active, 1 pending); proj2 has 0
    sub_repo.list_by_project.side_effect = lambda pid, page, page_size: (
        ([active_sub, pending_sub], 2) if pid == "proj1" else ([], 0)
    )

    # proj1 has 3 form submissions; proj2 has 0
    form_repo.list_by_project.side_effect = lambda pid: (
        ["sub1", "sub2", "sub3"] if pid == "proj1" else []
    )

    # Act
    result = await service.dashboard()

    # Assert
    assert result.total_projects == 2
    assert result.active_projects == 1
    assert result.total_subscriptions == 2
    assert result.pending_subscriptions == 1
    assert result.total_form_submissions == 3


# ── bulk_action error resilience ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_action_continues_after_per_user_exception() -> None:
    """bulk_action continues processing remaining users when one raises an exception."""
    # Arrange
    service, _proj_repo, sub_repo, _form_repo, id_client = make_service()
    sub_repo.list_by_person.return_value = []  # no blocking subscriptions

    # user1 raises, user2 succeeds
    id_client.delete_user.side_effect = [
        RuntimeError("Identity service unavailable"),
        None,
    ]

    cmd = BulkActionCommand(
        action="delete",
        user_ids=["user1", "user2"],
        requester_id="admin1",
    )

    # Act
    result = await service.bulk_action(cmd)

    # Assert — user1 failed, user2 succeeded
    assert result.total == 2
    assert result.failed == 1
    assert result.succeeded == 1

    user1_result = next(r for r in result.results if r.user_id == "user1")
    assert user1_result.success is False

    user2_result = next(r for r in result.results if r.user_id == "user2")
    assert user2_result.success is True
