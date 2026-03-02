"""Integration tests for the full middleware stack.

Validates the complete middleware chain:
  CorrelationIdMiddleware → SecurityHeadersMiddleware → RateLimitMiddleware → CORSMiddleware

Tests cover:
- OPTIONS preflight from allowed origin: 200, ACAO present, CORP absent
- GET from allowed origin: ACAO present, all security headers present
- GET from disallowed origin: no ACAO, security headers still present

Requirements: 2.1, 3.1, 3.2, 3.3
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from httpx import ASGITransport, AsyncClient

from src.presentation.middleware.correlation_id import CorrelationIdMiddleware
from src.presentation.middleware.rate_limiting import RateLimitMiddleware, _buckets
from src.presentation.middleware.security_headers import SecurityHeadersMiddleware

_ALLOWED_ORIGIN = "https://registry.apps.cloud.org.bo"
_DISALLOWED_ORIGIN = "https://evil.example.com"

_SECURITY_HEADERS_REQUIRED = [
    "x-content-type-options",
    "x-frame-options",
    "x-xss-protection",
    "strict-transport-security",
    "content-security-policy",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
]


def _make_full_stack_app() -> FastAPI:
    """Build a FastAPI app with the full middleware stack matching main.py order."""
    app = FastAPI()

    @app.get("/api/v1/projects")
    async def list_projects() -> PlainTextResponse:
        return PlainTextResponse("[]")

    # add_middleware order is reversed at execution time:
    # last added = first executed on the way in.
    # Desired execution order (in → out): CORS → RateLimit → SecurityHeaders → CorrelationId
    # So add_middleware order: CorrelationId, SecurityHeaders, RateLimit, CORS
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


@pytest.fixture
def app() -> FastAPI:
    return _make_full_stack_app()


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets() -> None:
    """Reset token buckets between tests."""
    _buckets.clear()


class TestFullMiddlewareStackCORSPreflight:
    """Integration tests for CORS preflight through the full middleware stack."""

    async def test_options_preflight_from_allowed_origin_succeeds(
        self, app: FastAPI
    ) -> None:
        """OPTIONS from allowed origin: 200, ACAO present, CORP absent.

        Validates: Requirement 2.1 — the core bug fix.
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/v1/projects",
                headers={
                    "Origin": _ALLOWED_ORIGIN,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
        assert "cross-origin-resource-policy" not in response.headers

    async def test_get_from_allowed_origin_has_acao_and_security_headers(
        self, app: FastAPI
    ) -> None:
        """GET from allowed origin: ACAO present, all security headers present.

        Validates: Requirements 3.1, 3.3 — preservation of security headers.
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects",
                headers={"Origin": _ALLOWED_ORIGIN},
            )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == _ALLOWED_ORIGIN
        assert "cross-origin-resource-policy" not in response.headers
        for header in _SECURITY_HEADERS_REQUIRED:
            assert header in response.headers, f"Missing security header: {header}"

    async def test_get_from_disallowed_origin_has_no_acao_but_keeps_security_headers(
        self, app: FastAPI
    ) -> None:
        """GET from disallowed origin: no ACAO, security headers still present.

        Validates: Requirements 3.1, 3.2 — CORS blocking preserved, security headers preserved.
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects",
                headers={"Origin": _DISALLOWED_ORIGIN},
            )

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers
        for header in _SECURITY_HEADERS_REQUIRED:
            assert header in response.headers, f"Missing security header: {header}"
