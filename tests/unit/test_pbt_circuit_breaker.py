"""Property 21: Circuit Breaker state transitions.

Validates: Requirements 20.1, 20.2, 20.5, 17.1
"""

from __future__ import annotations

import time
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.repositories.circuit_breaker import CircuitState
from src.infrastructure.adapters.in_memory_circuit_breaker import InMemoryCircuitBreaker

_CB_TIME_PATCH = "src.infrastructure.adapters.in_memory_circuit_breaker.time.monotonic"


@given(
    n_failures=st.integers(min_value=5, max_value=20),
    n_successes_before=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_circuit_opens_after_threshold_failures(n_failures: int, n_successes_before: int) -> None:
    """After failure_threshold consecutive failures, circuit must be OPEN."""
    cb = InMemoryCircuitBreaker(service_name="test", failure_threshold=5, cooldown_seconds=30)

    # Some successes first (resets failure count)
    for _ in range(n_successes_before):
        cb.record_success()

    # Now consecutive failures — enough to exceed threshold
    for _ in range(n_failures):
        cb.record_failure()

    assert cb.state() == CircuitState.OPEN
    assert cb.allow_request() is False


@given(n_successes=st.integers(min_value=1, max_value=10))
@settings(max_examples=50)
def test_success_resets_failure_count(n_successes: int) -> None:
    """Recording success resets failure count and closes circuit."""
    cb = InMemoryCircuitBreaker(service_name="test", failure_threshold=5, cooldown_seconds=30)

    # Get close to threshold but not over
    for _ in range(4):
        cb.record_failure()

    # Success resets
    for _ in range(n_successes):
        cb.record_success()

    assert cb.state() == CircuitState.CLOSED
    assert cb._failure_count == 0


@given(extra_failures=st.integers(min_value=0, max_value=5))
@settings(max_examples=50)
def test_half_open_to_closed_on_success(extra_failures: int) -> None:
    """HALF_OPEN → CLOSED on success."""
    cb = InMemoryCircuitBreaker(service_name="test", failure_threshold=5, cooldown_seconds=30)

    # Open the circuit
    for _ in range(5):
        cb.record_failure()
    assert cb._state == CircuitState.OPEN

    # Simulate cooldown expiry by patching time.monotonic
    future_time = time.monotonic() + 31
    with patch(_CB_TIME_PATCH, return_value=future_time):
        assert cb.state() == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state() == CircuitState.CLOSED


@given(extra_failures=st.integers(min_value=1, max_value=5))
@settings(max_examples=50)
def test_half_open_to_open_on_failure(extra_failures: int) -> None:
    """HALF_OPEN → OPEN on failure."""
    cb = InMemoryCircuitBreaker(service_name="test", failure_threshold=5, cooldown_seconds=30)

    for _ in range(5):
        cb.record_failure()

    future_time = time.monotonic() + 31
    with patch(_CB_TIME_PATCH, return_value=future_time):
        assert cb.state() == CircuitState.HALF_OPEN
        for _ in range(extra_failures):
            cb.record_failure()
        assert cb.state() == CircuitState.OPEN
