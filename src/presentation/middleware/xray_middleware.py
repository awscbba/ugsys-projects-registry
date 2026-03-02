"""X-Ray middleware — annotates segments with request context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

try:
    from aws_xray_sdk.core import xray_recorder

    _xray_available = True
except ImportError:
    xray_recorder = None
    _xray_available = False


class XRayMiddleware(BaseHTTPMiddleware):
    """Reads X-Ray trace header and annotates segment with service context."""

    def __init__(self, app: Any, service_name: str, version: str, environment: str) -> None:
        super().__init__(app)
        self._service_name = service_name
        self._version = version
        self._environment = environment

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not _xray_available or xray_recorder is None:
            return await call_next(request)

        try:
            segment = xray_recorder.current_segment()
            if segment is not None:
                segment.put_annotation("service", self._service_name)
                segment.put_annotation("version", self._version)
                segment.put_annotation("environment", self._environment)

                correlation_id = request.headers.get("X-Request-ID", "")
                if correlation_id:
                    segment.put_annotation("correlation_id", correlation_id)

                user = getattr(request.state, "user", None)
                if user is not None:
                    user_id = getattr(user, "sub", None) or (
                        user.get("sub") if isinstance(user, dict) else None
                    )
                    if user_id:
                        segment.put_annotation("user_id", str(user_id))
        except Exception as exc:
            logger.debug("xray_middleware.annotation_failed", error=str(exc))

        response = await call_next(request)

        try:
            if _xray_available and xray_recorder is not None:
                segment = xray_recorder.current_segment()
                if segment is not None and response.status_code >= 400:
                    segment.put_annotation("http_status", response.status_code)
                    if response.status_code >= 500:
                        segment.put_annotation("error", True)
                    else:
                        segment.put_annotation("fault", True)
        except Exception as exc:
            logger.debug("xray_middleware.status_annotation_failed", error=str(exc))

        return response
