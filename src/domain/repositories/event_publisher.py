"""Abstract interface for domain event publishing.

Defines the outbound port for publishing events to the event bus.
Infrastructure layer provides the concrete EventBridge implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EventPublisher(ABC):
    """Port interface for publishing domain events."""

    @abstractmethod
    async def publish(self, detail_type: str, payload: dict[str, Any]) -> None: ...
