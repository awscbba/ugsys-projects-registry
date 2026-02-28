"""Abstract interface for the Circuit Breaker pattern.

Defines the outbound port for circuit breaker state management.
Infrastructure layer provides the concrete in-memory implementation.

Circuit breaker methods are synchronous — they manage in-memory state only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum


class CircuitState(StrEnum):
    """Circuit breaker state machine states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker(ABC):
    """Port interface for circuit breaker state management."""

    @abstractmethod
    def state(self) -> CircuitState: ...

    @abstractmethod
    def record_success(self) -> None: ...

    @abstractmethod
    def record_failure(self) -> None: ...

    @abstractmethod
    def allow_request(self) -> bool: ...
