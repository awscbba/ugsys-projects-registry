"""Unit tests for EventConsumerService application service.

Validates: Requirements 11.1, 11.2, 17.1

Tests cover:
- handle_user_deactivated cancels all active/pending subscriptions and publishes
  one projects.subscription.cancelled event per cancelled subscription
- handle_user_deactivated for a user with no subscriptions completes without error
  and publishes no events
"""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest
from ulid import ULID

from src.application.services.event_consumer_service import EventConsumerService
from src.domain.entities.subscription import Subscription
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import SubscriptionStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_subscription(
    person_id: str = "person-1",
    project_id: str = "project-1",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    now = "2026-01-01T00:00:00+00:00"
    return Subscription(
        id=str(ULID()),
        project_id=project_id,
        person_id=person_id,
        status=status,
        created_at=now,
        updated_at=now,
    )


def make_service(
    subscriptions: list[Subscription] | None = None,
    cancelled_count: int = 0,
) -> tuple[EventConsumerService, AsyncMock, AsyncMock]:
    mock_repo: AsyncMock = AsyncMock(spec=SubscriptionRepository)
    mock_repo.list_by_person.return_value = subscriptions or []
    mock_repo.cancel_all_for_person.return_value = cancelled_count

    mock_publisher: AsyncMock = AsyncMock(spec=EventPublisher)

    service = EventConsumerService(
        subscription_repo=mock_repo,
        event_publisher=mock_publisher,
    )
    return service, mock_repo, mock_publisher


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_user_deactivated_cancels_subscriptions_and_publishes_one_event_each() -> None:
    # Arrange — two active subscriptions for the same person
    person_id = "person-1"
    sub1 = make_subscription(
        person_id=person_id, project_id="proj-1", status=SubscriptionStatus.ACTIVE
    )
    sub2 = make_subscription(
        person_id=person_id, project_id="proj-2", status=SubscriptionStatus.PENDING
    )
    service, mock_repo, mock_publisher = make_service(
        subscriptions=[sub1, sub2],
        cancelled_count=2,
    )

    # Act
    await service.handle_user_deactivated(person_id)

    # Assert — repo was asked to cancel all
    mock_repo.cancel_all_for_person.assert_awaited_once_with(person_id)

    # Assert — one event published per cancelled subscription
    assert mock_publisher.publish.await_count == 2
    mock_publisher.publish.assert_has_awaits(
        [
            call(
                "projects.subscription.cancelled",
                {
                    "subscription_id": sub1.id,
                    "project_id": sub1.project_id,
                    "person_id": sub1.person_id,
                    "reason": "user_deactivated",
                },
            ),
            call(
                "projects.subscription.cancelled",
                {
                    "subscription_id": sub2.id,
                    "project_id": sub2.project_id,
                    "person_id": sub2.person_id,
                    "reason": "user_deactivated",
                },
            ),
        ],
        any_order=False,
    )


@pytest.mark.asyncio
async def test_handle_user_deactivated_no_subscriptions_completes_without_error() -> None:
    # Arrange — user has no subscriptions
    person_id = "person-with-no-subs"
    service, mock_repo, mock_publisher = make_service(subscriptions=[], cancelled_count=0)

    # Act — must not raise
    await service.handle_user_deactivated(person_id)

    # Assert — cancel was still called, but no events published
    mock_repo.cancel_all_for_person.assert_awaited_once_with(person_id)
    mock_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_user_deactivated_only_publishes_for_active_or_pending_subscriptions() -> None:
    # Arrange — mix of statuses; only active/pending should trigger events
    person_id = "person-mixed"
    active_sub = make_subscription(
        person_id=person_id, project_id="proj-a", status=SubscriptionStatus.ACTIVE
    )
    rejected_sub = make_subscription(
        person_id=person_id, project_id="proj-b", status=SubscriptionStatus.REJECTED
    )
    cancelled_sub = make_subscription(
        person_id=person_id, project_id="proj-c", status=SubscriptionStatus.CANCELLED
    )
    service, _mock_repo, mock_publisher = make_service(
        subscriptions=[active_sub, rejected_sub, cancelled_sub],
        cancelled_count=1,
    )

    # Act
    await service.handle_user_deactivated(person_id)

    # Assert — only the active subscription triggers an event
    assert mock_publisher.publish.await_count == 1
    mock_publisher.publish.assert_awaited_once_with(
        "projects.subscription.cancelled",
        {
            "subscription_id": active_sub.id,
            "project_id": active_sub.project_id,
            "person_id": active_sub.person_id,
            "reason": "user_deactivated",
        },
    )
