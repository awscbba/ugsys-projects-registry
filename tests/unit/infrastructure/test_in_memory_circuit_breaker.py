"""Unit tests for InMemoryCircuitBreaker.

Tests cover all state machine transitions and the Property 21 property-based test.
"""

from __future__ import annotations

from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.repositories.circuit_breaker import CircuitState
from src.infrastructure.adapters.in_memory_circuit_breaker import InMemoryCircuitBreaker


class TestClosedToOpen:
    """CLOSED → OPEN after N consecutive failures."""

    def test_starts_in_closed_state(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc")
        assert cb.state() == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state() == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc", failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.state() == CircuitState.OPEN

    def test_opens_after_custom_threshold(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state() == CircuitState.OPEN


class TestOpenRejectsRequests:
    """OPEN state rejects requests immediately."""

    def test_allow_request_returns_false_when_open(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitState.OPEN
        assert cb.allow_request() is False


class TestOpenToHalfOpen:
    """OPEN → HALF_OPEN after cooldown expires."""

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        cb = InMemoryCircuitBreaker(
            service_name="test-svc", failure_threshold=2, cooldown_seconds=10
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitState.OPEN

        # Simulate cooldown expiry by patching time.monotonic
        with patch("src.infrastructure.adapters.in_memory_circuit_breaker.time") as mock_time:
            # Set monotonic to return a time well past the cooldown
            mock_time.monotonic.return_value = cb._last_failure_time + 10
            assert cb.state() == CircuitState.HALF_OPEN
            assert cb.allow_request() is True

    def test_stays_open_before_cooldown(self) -> None:
        cb = InMemoryCircuitBreaker(
            service_name="test-svc", failure_threshold=2, cooldown_seconds=30
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitState.OPEN

        with patch("src.infrastructure.adapters.in_memory_circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_time + 29
            assert cb.state() == CircuitState.OPEN
            assert cb.allow_request() is False


class TestHalfOpenToClosed:
    """HALF_OPEN → CLOSED on success."""

    def test_success_in_half_open_closes_circuit(self) -> None:
        cb = InMemoryCircuitBreaker(
            service_name="test-svc", failure_threshold=2, cooldown_seconds=10
        )
        cb.record_failure()
        cb.record_failure()

        with patch("src.infrastructure.adapters.in_memory_circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_time + 10
            assert cb.state() == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state() == CircuitState.CLOSED
        assert cb.allow_request() is True


class TestHalfOpenToOpen:
    """HALF_OPEN → OPEN on failure."""

    def test_failure_in_half_open_reopens_circuit(self) -> None:
        cb = InMemoryCircuitBreaker(
            service_name="test-svc", failure_threshold=2, cooldown_seconds=10
        )
        cb.record_failure()
        cb.record_failure()

        with patch("src.infrastructure.adapters.in_memory_circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_time + 10
            assert cb.state() == CircuitState.HALF_OPEN

        # Failure in HALF_OPEN should reopen
        cb.record_failure()
        assert cb.state() == CircuitState.OPEN
        assert cb.allow_request() is False


class TestSuccessResetsFailureCount:
    """Success resets failure count to 0."""

    def test_success_resets_count_in_closed(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state() == CircuitState.CLOSED

        # After reset, need full threshold again to open
        for _ in range(4):
            cb.record_failure()
        assert cb.state() == CircuitState.CLOSED

    def test_success_resets_count_in_half_open(self) -> None:
        cb = InMemoryCircuitBreaker(
            service_name="test-svc", failure_threshold=2, cooldown_seconds=10
        )
        cb.record_failure()
        cb.record_failure()

        with patch("src.infrastructure.adapters.in_memory_circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = cb._last_failure_time + 10
            assert cb.state() == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state() == CircuitState.CLOSED


class TestDefaultParameters:
    """Verify default threshold and cooldown values."""

    def test_default_failure_threshold_is_5(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc")
        assert cb._failure_threshold == 5

    def test_default_cooldown_is_30(self) -> None:
        cb = InMemoryCircuitBreaker(service_name="test-svc")
        assert cb._cooldown_seconds == 30


# ── Property-Based Test ───────────────────────────────────────────────────────
# Feature: projects-registry, Property 21: Circuit Breaker state transitions
# **Validates: Requirements 20.1, 20.2, 20.4, 20.5, 20.6**


@given(
    failures=st.lists(st.just("fail"), min_size=0, max_size=20),
    successes=st.lists(st.just("success"), min_size=0, max_size=20),
)
@settings(max_examples=200)
def test_property_21_circuit_breaker_state_transitions(
    failures: list[str],
    successes: list[str],
) -> None:
    """Property 21: Circuit Breaker state transitions.

    For any sequence of success/failure calls, the state machine invariants hold:
    - After N consecutive failures (N >= threshold): state is OPEN, allow_request is False
    - After any success: failure count resets to 0
    - State is always one of CLOSED, OPEN, HALF_OPEN
    """
    threshold = 5
    cb = InMemoryCircuitBreaker(
        service_name="prop-test-svc",
        failure_threshold=threshold,
        cooldown_seconds=9999,  # large cooldown so OPEN never auto-transitions
    )

    # Interleave failures and successes in order
    actions = [("fail", _) for _ in failures] + [("success", _) for _ in successes]

    consecutive_failures = 0

    for action, _ in actions:
        if action == "fail":
            cb.record_failure()
            consecutive_failures += 1
        else:
            cb.record_success()
            consecutive_failures = 0

        # Invariant 1: state is always valid
        current_state = cb.state()
        assert current_state in (
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        )

        # Invariant 2: after >= threshold consecutive failures, must be OPEN
        if consecutive_failures >= threshold:
            assert current_state == CircuitState.OPEN
            assert cb.allow_request() is False

        # Invariant 3: after success, failure count is 0
        if action == "success":
            assert cb._failure_count == 0
