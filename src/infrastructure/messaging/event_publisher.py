"""EventBridge publisher — concrete implementation of the EventPublisher port.

Publishes domain events to the ugsys-platform-bus with a standard envelope
containing event_id (ULID), event_version, timestamp, correlation_id, and payload.

All boto3 calls are wrapped in try/except ClientError and raise
ExternalServiceError with a safe user_message on failure.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import structlog
from botocore.exceptions import ClientError
from ulid import ULID

from src.domain.exceptions import ExternalServiceError
from src.domain.repositories.event_publisher import EventPublisher

logger = structlog.get_logger()

# Shared ContextVar for correlation ID — set by CorrelationIdMiddleware
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class EventBridgePublisher(EventPublisher):
    """Publishes domain events to EventBridge with a standard envelope."""

    def __init__(self, event_bus_name: str, client: Any) -> None:  # noqa: ANN401
        self._bus = event_bus_name
        self._client = client

    async def publish(self, detail_type: str, payload: dict[str, Any]) -> None:
        """Publish a domain event to EventBridge.

        Args:
            detail_type: Event type (e.g. "projects.project.created").
            payload: Event payload dict.

        Raises:
            ExternalServiceError: If the EventBridge put_events call fails.
        """
        event_id = str(ULID())
        envelope = {
            "event_id": event_id,
            "event_version": "1.0",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "correlation_id": correlation_id_var.get(""),
            "payload": payload,
        }

        try:
            await self._client.put_events(
                Entries=[
                    {
                        "Source": "ugsys.projects-registry",
                        "DetailType": detail_type,
                        "Detail": json.dumps(envelope),
                        "EventBusName": self._bus,
                    }
                ],
            )
            logger.info(
                "eventbridge.published",
                detail_type=detail_type,
                event_id=event_id,
                event_bus=self._bus,
            )
        except ClientError as e:
            logger.error(
                "eventbridge.publish_failed",
                detail_type=detail_type,
                event_id=event_id,
                event_bus=self._bus,
                error_code=e.response["Error"]["Code"],
                error=str(e),
            )
            raise ExternalServiceError(
                message=f"EventBridge publish failed for {detail_type}: {e}",
                user_message="An unexpected error occurred",
                error_code="EVENT_PUBLISH_FAILED",
            ) from e
