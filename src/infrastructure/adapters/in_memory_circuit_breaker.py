"""In-memory circuit breaker implementation.

Implements the CircuitBreaker ABC with a simple state machine:
CLOSED → OPEN after N consecutive failures;
OPEN → HALF_OPEN after cooldown expires;
HALF_OPEN → CLOSED on success;
HALF_OPEN → OPEN on failure.

Uses time.monotonic() for cooldown tracking (immune to wall-clock changes).
Lambda cold starts reset state — acceptable for serverless.
"""

from __future__ import annotations

import time

import structlog

from src.domain.repositories.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger()


class InMemoryCircuitBreaker(CircuitBreaker):
    """In-memory circuit breaker with configurable threshold and cooldown."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        cooldown_seconds: int = 30,
    ) -> None:
        self._service_name = service_name
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self._cooldown_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info(
                "circuit_breaker.half_open",
                service=self._service_name,
            )
        return self._state

    def allow_request(self) -> bool:
        current = self.state()
        return current in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                "circuit_breaker.closed",
                service=self._service_name,
            )
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker.opened",
                service=self._service_name,
                failure_count=self._failure_count,
                cooldown_seconds=self._cooldown_seconds,
            )
