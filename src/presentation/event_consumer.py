"""EventBridge Lambda handler — routes incoming events to application services.

This is a separate Lambda entry point (not the HTTP API handler).
It receives EventBridge events and routes them to the appropriate service.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger()

# Lazy import to avoid circular deps — services are injected at runtime
_event_consumer_service: Any = None


def set_event_consumer_service(service: Any) -> None:
    """Inject the EventConsumerService at startup (called from main.py lifespan)."""
    global _event_consumer_service
    _event_consumer_service = service


async def handle_event(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Route an EventBridge event to the appropriate handler.

    Re-raises on transient errors so Lambda retries the event.
    """
    detail_type = event.get("detail-type", "")
    source = event.get("source", "")
    detail = event.get("detail", {})

    # detail may be a JSON string (EventBridge wraps it)
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except (json.JSONDecodeError, ValueError):
            detail = {}

    correlation_id = detail.get("correlation_id", "")

    import structlog.contextvars

    with structlog.contextvars.bound_contextvars(
        correlation_id=correlation_id,
        detail_type=detail_type,
        source=source,
    ):
        logger.info(
            "event_consumer.received",
            detail_type=detail_type,
            source=source,
            correlation_id=correlation_id,
        )

        if detail_type == "identity.user.deactivated":
            payload = detail.get("payload", detail)
            user_id = payload.get("user_id") or payload.get("sub", "")
            if not user_id:
                logger.warning("event_consumer.missing_user_id", detail_type=detail_type)
                return {"statusCode": 200, "body": "skipped: missing user_id"}

            if _event_consumer_service is None:
                logger.error("event_consumer.service_not_initialized")
                raise RuntimeError("EventConsumerService not initialized")

            await _event_consumer_service.handle_user_deactivated(user_id)
            logger.info("event_consumer.handled", detail_type=detail_type, user_id=user_id)
        else:
            logger.info("event_consumer.unhandled_event_type", detail_type=detail_type)

    return {"statusCode": 200, "body": "ok"}
