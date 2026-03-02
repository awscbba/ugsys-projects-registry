"""EventConsumerService — handles inbound domain events from EventBridge."""

from __future__ import annotations

import time

import structlog

from src.application.tracing import traced
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.subscription_repository import SubscriptionRepository

logger = structlog.get_logger()


class EventConsumerService:
    """Processes inbound domain events and applies side effects."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._event_publisher = event_publisher

    @traced
    async def handle_user_deactivated(self, person_id: str) -> None:
        """Cancel all active/pending subscriptions for a deactivated user.

        Publishes ``projects.subscription.cancelled`` for each cancelled
        subscription.  Completes successfully when the user has no
        subscriptions.
        """
        logger.info("event_consumer.handle_user_deactivated.started", person_id=person_id)
        start = time.perf_counter()

        # Fetch subscriptions before cancellation so we can publish per-item events
        subscriptions = await self._subscription_repo.list_by_person(person_id)
        active_or_pending = [s for s in subscriptions if s.status in {"active", "pending"}]

        cancelled_count = await self._subscription_repo.cancel_all_for_person(person_id)

        for subscription in active_or_pending:
            await self._event_publisher.publish(
                "projects.subscription.cancelled",
                {
                    "subscription_id": subscription.id,
                    "project_id": subscription.project_id,
                    "person_id": subscription.person_id,
                    "reason": "user_deactivated",
                },
            )

        logger.info(
            "event_consumer.handle_user_deactivated.completed",
            person_id=person_id,
            cancelled_count=cancelled_count,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
