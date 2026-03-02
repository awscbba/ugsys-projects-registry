"""RateLimitMiddleware — per-user (JWT sub) rate limiting with IP fallback."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# Token bucket entry: (tokens_remaining, last_refill_time)
_buckets: dict[str, tuple[float, float]] = defaultdict(lambda: (60.0, time.monotonic()))


def _get_client_key(request: Request) -> str:
    """Extract rate-limit key: JWT sub if present, else client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # Decode payload without verification just to extract sub for rate-limit key
        try:
            import base64
            import json

            parts = token.split(".")
            if len(parts) == 3:
                padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded))
                sub = payload.get("sub")
                if sub:
                    return f"sub:{sub}"
        except Exception:
            logger.debug("rate_limit.jwt_decode_failed", path=request.url.path)
    # Fallback to IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"  # nosemgrep: directly-returned-format-string
    client = request.client
    if client:
        return f"ip:{client.host}"
    return "ip:unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, requests_per_minute: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._rpm = requests_per_minute
        self._refill_rate = requests_per_minute / 60.0  # tokens per second

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        key = _get_client_key(request)
        now = time.monotonic()
        tokens, last_refill = _buckets[key]

        # Refill tokens based on elapsed time
        elapsed = now - last_refill
        tokens = min(self._rpm, tokens + elapsed * self._refill_rate)

        if tokens < 1.0:
            reset_in = math.ceil((1.0 - tokens) / self._refill_rate)
            logger.warning("rate_limit.exceeded", key=key)
            return JSONResponse(
                status_code=429,
                # nosemgrep: python.flask.security.audit.directly-returned-format-string
                content={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"},
                headers={
                    "Retry-After": str(reset_in),
                    "X-RateLimit-Limit": str(self._rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now) + reset_in),
                },
            )

        tokens -= 1.0
        _buckets[key] = (tokens, now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._rpm)
        response.headers["X-RateLimit-Remaining"] = str(int(tokens))
        response.headers["X-RateLimit-Reset"] = str(
            int(now + (self._rpm - tokens) / self._refill_rate)
        )
        return response
