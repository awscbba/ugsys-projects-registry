"""Response envelope helpers."""

from __future__ import annotations

from typing import Any

from src.presentation.middleware.correlation_id import correlation_id_var


def envelope(data: object) -> dict[str, Any]:
    """Wrap data in the standard response envelope."""
    return {
        "data": data,
        "meta": {"request_id": correlation_id_var.get("")},
    }
