"""Unit tests for EventBridgePublisher.

Tests cover:
- Happy path: successful event publishing with correct envelope format
- ClientError wrapping: raises ExternalServiceError on failure
- Envelope structure: event_id (ULID), event_version, timestamp, correlation_id, payload
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError

from src.domain.exceptions import ExternalServiceError
from src.infrastructure.messaging.event_publisher import (
    EventBridgePublisher,
    correlation_id_var,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock EventBridge client."""
    client = AsyncMock()
    client.put_events = AsyncMock(return_value={"FailedEntryCount": 0, "Entries": []})
    return client


@pytest.fixture
def publisher(mock_client: AsyncMock) -> EventBridgePublisher:
    """Create an EventBridgePublisher with a mock client."""
    return EventBridgePublisher(event_bus_name="ugsys-event-bus", client=mock_client)


@pytest.mark.asyncio
async def test_publish_calls_put_events_with_correct_entry(
    publisher: EventBridgePublisher,
    mock_client: AsyncMock,
) -> None:
    """Publish should call put_events with Source, DetailType, Detail, EventBusName."""
    payload = {"project_id": "01JTEST", "name": "Test Project"}

    await publisher.publish("projects.project.created", payload)

    mock_client.put_events.assert_called_once()
    call_kwargs = mock_client.put_events.call_args[1]
    entries = call_kwargs["Entries"]
    assert len(entries) == 1

    entry = entries[0]
    assert entry["Source"] == "ugsys.projects-registry"
    assert entry["DetailType"] == "projects.project.created"
    assert entry["EventBusName"] == "ugsys-event-bus"


@pytest.mark.asyncio
async def test_publish_envelope_contains_required_fields(
    publisher: EventBridgePublisher,
    mock_client: AsyncMock,
) -> None:
    """The Detail envelope must include event_id, event_version, timestamp, correlation_id, payload."""
    payload = {"subscription_id": "01JSUB"}

    await publisher.publish("projects.subscription.created", payload)

    call_kwargs = mock_client.put_events.call_args[1]
    detail_json = call_kwargs["Entries"][0]["Detail"]
    envelope = json.loads(detail_json)

    assert "event_id" in envelope
    assert len(envelope["event_id"]) == 26  # ULID length
    assert envelope["event_version"] == "1.0"
    assert "timestamp" in envelope
    assert "T" in envelope["timestamp"]  # ISO 8601 format
    assert "correlation_id" in envelope
    assert envelope["payload"] == payload


@pytest.mark.asyncio
async def test_publish_includes_correlation_id_from_contextvar(
    publisher: EventBridgePublisher,
    mock_client: AsyncMock,
) -> None:
    """Correlation ID should be read from the correlation_id_var ContextVar."""
    token = correlation_id_var.set("test-correlation-123")
    try:
        await publisher.publish("projects.project.updated", {"id": "01J"})

        call_kwargs = mock_client.put_events.call_args[1]
        envelope = json.loads(call_kwargs["Entries"][0]["Detail"])
        assert envelope["correlation_id"] == "test-correlation-123"
    finally:
        correlation_id_var.reset(token)


@pytest.mark.asyncio
async def test_publish_uses_empty_correlation_id_when_not_set(
    publisher: EventBridgePublisher,
    mock_client: AsyncMock,
) -> None:
    """When no correlation ID is set, the envelope should use empty string."""
    await publisher.publish("projects.project.deleted", {"id": "01J"})

    call_kwargs = mock_client.put_events.call_args[1]
    envelope = json.loads(call_kwargs["Entries"][0]["Detail"])
    assert envelope["correlation_id"] == ""


@pytest.mark.asyncio
async def test_publish_raises_external_service_error_on_client_error(
    publisher: EventBridgePublisher,
    mock_client: AsyncMock,
) -> None:
    """ClientError from put_events should be wrapped in ExternalServiceError."""
    mock_client.put_events.side_effect = ClientError(
        error_response={"Error": {"Code": "InternalFailure", "Message": "Service error"}},
        operation_name="PutEvents",
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await publisher.publish("projects.project.created", {"id": "01J"})

    assert exc_info.value.error_code == "EVENT_PUBLISH_FAILED"
    assert exc_info.value.user_message == "An unexpected error occurred"
    # Internal message should contain detail for logs
    assert "EventBridge publish failed" in exc_info.value.message


@pytest.mark.asyncio
async def test_publish_event_id_is_unique_per_call(
    mock_client: AsyncMock,
) -> None:
    """Each publish call should generate a unique ULID event_id."""
    publisher = EventBridgePublisher(event_bus_name="ugsys-event-bus", client=mock_client)

    await publisher.publish("projects.project.created", {"id": "01J1"})
    await publisher.publish("projects.project.created", {"id": "01J2"})

    calls = mock_client.put_events.call_args_list
    envelope_1 = json.loads(calls[0][1]["Entries"][0]["Detail"])
    envelope_2 = json.loads(calls[1][1]["Entries"][0]["Detail"])

    assert envelope_1["event_id"] != envelope_2["event_id"]
