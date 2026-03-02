"""SecurityHeadersMiddleware — sets all required security headers and removes Server header."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none';",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # cross-origin allows the frontend SPA (different origin) to fetch API responses.
    # same-origin would block all cross-origin reads, breaking the SPA.
    "Cross-Origin-Resource-Policy": "cross-origin",
}

_CACHE_CONTROL = "no-store, no-cache, must-revalidate"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Pass OPTIONS preflight requests straight through — CORSMiddleware handles them.
        # Adding security headers to a preflight response can cause browsers to reject it.
        if request.method == "OPTIONS":
            return await call_next(request)

        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = _CACHE_CONTROL
        # Remove Server header to prevent technology fingerprinting
        if "server" in response.headers:
            del response.headers["server"]
        if "Server" in response.headers:
            del response.headers["Server"]
        return response
