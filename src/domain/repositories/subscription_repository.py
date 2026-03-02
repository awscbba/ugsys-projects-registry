"""Abstract repository interface for Subscription aggregate root.

Defines the outbound port for subscription persistence operations.
Infrastructure layer provides the concrete DynamoDB implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.subscription import Subscription


class SubscriptionRepository(ABC):
    """Port interface for subscription persistence operations."""

    @abstractmethod
    async def save(self, subscription: Subscription) -> Subscription: ...

    @abstractmethod
    async def find_by_id(self, subscription_id: str) -> Subscription | None: ...

    @abstractmethod
    async def update(self, subscription: Subscription) -> Subscription: ...

    @abstractmethod
    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> Subscription | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: str, page: int, page_size: int
    ) -> tuple[list[Subscription], int]: ...

    @abstractmethod
    async def list_by_person(self, person_id: str) -> list[Subscription]: ...

    @abstractmethod
    async def cancel_all_for_person(self, person_id: str) -> int:
        """Cancel all active/pending subscriptions for a person.

        Returns the count of cancelled subscriptions.
        """
        ...
