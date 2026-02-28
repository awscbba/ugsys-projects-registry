"""X-Ray tracing decorator for application service methods.

Graceful fallback when X-Ray SDK is unavailable (local dev, unit tests).

This module lives in the application layer so that application services can
import it without violating the architecture rule that prohibits application
layer imports from infrastructure.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Coroutine
from contextlib import contextmanager
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger()

_xray_available = False
try:
    from aws_xray_sdk.core import xray_recorder

    _xray_available = True
except ImportError:
    xray_recorder = None  # type: ignore[assignment]

# TypeVar for the decorator — keeps the wrapped function's signature intact.
# ANN401 is suppressed via per-file-ignores for this cross-cutting utility.
_F = TypeVar("_F", bound=Callable[..., Coroutine[Any, Any, Any]])


@contextmanager
def traced_subsegment(name: str) -> Any:
    """Context manager that creates an X-Ray subsegment, or is a no-op if unavailable."""
    if not _xray_available or xray_recorder is None:
        yield None
        return
    try:
        with xray_recorder.in_subsegment(name) as subsegment:
            yield subsegment
    except Exception:
        # Never let tracing failures affect business logic
        yield None


def traced(func: _F) -> _F:
    """Decorator that wraps an async method in an X-Ray subsegment."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        name = func.__qualname__
        if not _xray_available or xray_recorder is None:
            return await func(*args, **kwargs)
        try:
            with xray_recorder.in_subsegment(name) as subsegment:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as exc:
                    if subsegment is not None:
                        subsegment.add_exception(exc, fatal=False)
                    raise
        except Exception:
            # If subsegment creation itself fails, run without tracing
            return await func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


__all__ = ["traced", "traced_subsegment"]
