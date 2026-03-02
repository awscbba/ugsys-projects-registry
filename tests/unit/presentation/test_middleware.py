"""Unit tests for presentation middleware.

Validates: Requirements 1.2, 15.5, 15.6, 15.7, 17.1

Tests cover:
- CorrelationIdMiddleware: sets X-Request-ID on response, propagates provided header
- SecurityHeadersMiddleware: sets all required headers, removes Server header
- RateLimitMiddleware: returns 429 with Retry-After after limit exceeded
- Property 17: Security headers invariant
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from httpx import ASGITransport, AsyncClient

from src.presentation.middleware.correlation_id import (
    CorrelationIdMiddleware,
    correlation_id_var,
)
from src.presentation.middleware.rate_limiting import RateLimitMiddleware, _buckets
from src.presentation.middleware.security_headers import SecurityHeadersMiddleware


def _make_app(*middleware_classes: object, **kwargs: object) -> FastAPI:
    """Build a minimal FastAPI app with the given middleware applied."""
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    @app.get("/api/v1/ping")
    async def api_ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    for cls in reversed(middleware_classes):  # type: ignore[arg-type]
        app.add_middleware(cls, **kwargs)  # type: ignore[arg-type]

    return app


# ── CorrelationIdMiddleware ───────────────────────────────────────────────────


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    @pytest.fixture
    def app(self) -> FastAPI:
        return _make_app(CorrelationIdMiddleware)

    async def test_sets_x_request_id_on_response(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) > 0

    async def test_propagates_provided_x_request_id(self, app: FastAPI) -> None:
        provided_id = "my-trace-id-123"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping", headers={"X-Request-ID": provided_id})

        assert response.headers["x-request-id"] == provided_id

    async def test_generates_uuid_when_header_absent(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.get("/ping")
            r2 = await client.get("/ping")

        # Each request without a header gets a unique generated ID
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    async def test_binds_correlation_id_to_context(self, app: FastAPI) -> None:
        """Verify the ContextVar is set during request processing."""
        captured: list[str] = []

        inner_app = FastAPI()

        @inner_app.get("/capture")
        async def capture() -> PlainTextResponse:
            captured.append(correlation_id_var.get())
            return PlainTextResponse("ok")

        inner_app.add_middleware(CorrelationIdMiddleware)

        async with AsyncClient(
            transport=ASGITransport(app=inner_app), base_url="http://test"
        ) as client:
            await client.get("/capture", headers={"X-Request-ID": "ctx-test-id"})

        assert captured == ["ctx-test-id"]


# ── SecurityHeadersMiddleware ─────────────────────────────────────────────────

_REQUIRED_HEADERS = [
    "x-content-type-options",
    "x-frame-options",
    "x-xss-protection",
    "strict-transport-security",
    "content-security-policy",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    # cross-origin-resource-policy intentionally excluded: would block cross-origin
    # fetch from the frontend SPA. CORS headers are the correct mechanism for APIs.
]


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware — Property 17: Security headers invariant."""

    @pytest.fixture
    def app(self) -> FastAPI:
        return _make_app(SecurityHeadersMiddleware)

    async def test_sets_all_required_security_headers(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        for header in _REQUIRED_HEADERS:
            assert header in response.headers, f"Missing security header: {header}"

    async def test_removes_server_header(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert "server" not in response.headers

    async def test_x_content_type_options_is_nosniff(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_x_frame_options_is_deny(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert response.headers["x-frame-options"] == "DENY"

    async def test_hsts_includes_preload(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        hsts = response.headers["strict-transport-security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    async def test_cache_control_set_on_api_routes(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/ping")

        assert "cache-control" in response.headers
        assert "no-store" in response.headers["cache-control"]

    async def test_cache_control_not_set_on_non_api_routes(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert "cache-control" not in response.headers

    async def test_security_headers_present_on_every_response(self, app: FastAPI) -> None:
        """Property 17: security headers invariant — every response has all headers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(3):
                response = await client.get("/ping")
                for header in _REQUIRED_HEADERS:
                    assert header in response.headers

    async def test_cross_origin_resource_policy_not_set(self, app: FastAPI) -> None:
        """CORP must not be set on API responses — it would block cross-origin SPA fetches."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert "cross-origin-resource-policy" not in response.headers

    async def test_options_preflight_passes_through_without_security_headers(
        self, app: FastAPI
    ) -> None:
        """OPTIONS requests must not have security headers injected — CORSMiddleware owns them."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options("/ping")

        # Security headers must NOT be present on preflight responses
        for header in _REQUIRED_HEADERS:
            assert header not in response.headers, (
                f"Security header '{header}' must not be set on OPTIONS preflight"
            )


# ── RateLimitMiddleware ───────────────────────────────────────────────────────


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.fixture(autouse=True)
    def clear_buckets(self) -> None:
        """Reset the shared token bucket state between tests."""
        _buckets.clear()

    @pytest.fixture
    def app(self) -> FastAPI:
        # Use a very low limit so tests don't need hundreds of requests
        return _make_app(RateLimitMiddleware, requests_per_minute=2)

    async def test_allows_requests_within_limit(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.get("/ping")
            r2 = await client.get("/ping")

        assert r1.status_code == 200
        assert r2.status_code == 200

    async def test_returns_429_after_limit_exceeded(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/ping")  # 1st — ok
            await client.get("/ping")  # 2nd — ok (limit=2)
            response = await client.get("/ping")  # 3rd — should be 429

        assert response.status_code == 429

    async def test_429_includes_retry_after_header(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/ping")
            await client.get("/ping")
            response = await client.get("/ping")

        assert response.status_code == 429
        assert "retry-after" in response.headers
        assert int(response.headers["retry-after"]) > 0

    async def test_429_includes_rate_limit_headers(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/ping")
            await client.get("/ping")
            response = await client.get("/ping")

        assert response.status_code == 429
        assert response.headers["x-ratelimit-limit"] == "2"
        assert response.headers["x-ratelimit-remaining"] == "0"

    async def test_successful_response_includes_rate_limit_headers(self, app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ping")

        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers

    async def test_different_ips_have_independent_limits(self, app: FastAPI) -> None:
        """Clients from different IPs should not share rate limit buckets."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Exhaust limit for IP 1.1.1.1
            await client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            await client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            r_ip1_third = await client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})

            # IP 2.2.2.2 should still be allowed
            r_ip2 = await client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"})

        assert r_ip1_third.status_code == 429
        assert r_ip2.status_code == 200


# ── Bug Condition Exploration Tests (CORS Preflight Fix) ──────────────────────


class TestSecurityHeadersMiddlewareCORSFix:
    """Bug condition exploration tests — Property 1: Fault Condition.

    These tests encode the EXPECTED (fixed) behavior.
    They FAIL on unfixed code (confirming the bug) and PASS on fixed code.

    Validates: Requirements 1.1, 1.2, 1.3
    """

    @pytest.fixture
    def app(self) -> FastAPI:
        return _make_app(SecurityHeadersMiddleware)

    async def test_options_preflight_does_not_inject_corp_header(self, app: FastAPI) -> None:
        """Bug condition: OPTIONS from allowed origin must NOT get Cross-Origin-Resource-Policy.

        FAILS on unfixed code: CORP is present → browser blocks preflight.
        PASSES on fixed code: OPTIONS short-circuit, CORP absent.
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/ping",
                headers={
                    "Origin": "https://registry.apps.cloud.org.bo",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert "cross-origin-resource-policy" not in response.headers

    async def test_options_preflight_does_not_inject_any_security_headers(
        self, app: FastAPI
    ) -> None:
        """OPTIONS short-circuit: no security headers stamped on preflight responses."""
        from src.presentation.middleware.security_headers import _SECURITY_HEADERS

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/v1/ping",
                headers={
                    "Origin": "https://registry.apps.cloud.org.bo",
                    "Access-Control-Request-Method": "POST",
                },
            )
        for header_key in _SECURITY_HEADERS:
            assert header_key.lower() not in response.headers, (
                f"Security header '{header_key}' must not be injected on OPTIONS preflight"
            )


# ── Preservation Property Tests (CORS Preflight Fix) ─────────────────────────


class TestSecurityHeadersMiddlewarePreservation:
    """Property 2: Preservation — non-OPTIONS requests retain all security headers.

    These tests PASS on both unfixed and fixed code, confirming baseline behavior
    is preserved by the fix.

    Validates: Requirements 3.1, 3.4
    """

    @pytest.fixture
    def app(self) -> FastAPI:
        return _make_app(SecurityHeadersMiddleware)

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_non_options_requests_always_get_security_headers(
        self, method: str, app: FastAPI
    ) -> None:
        """Property 2a: for any non-OPTIONS method, all _REQUIRED_HEADERS must be present."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(method, "/ping")
        for header in _REQUIRED_HEADERS:
            assert header in response.headers, f"Missing '{header}' on {method} response"

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_api_routes_always_get_cache_control(self, method: str, app: FastAPI) -> None:
        """Property 2b: Cache-Control must be set on /api/* routes for non-OPTIONS."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(method, "/api/v1/ping")
        assert "cache-control" in response.headers
        assert "no-store" in response.headers["cache-control"]

    @pytest.mark.parametrize("method", ["GET", "POST", "OPTIONS", "PUT", "DELETE"])
    async def test_server_header_always_absent(self, method: str, app: FastAPI) -> None:
        """Property 2c: Server header must never appear in any response."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(method, "/ping")
        assert "server" not in response.headers


def test_allowed_origins_json_array_parses_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """allowed_origins_list supports both comma-separated and JSON array formats.

    Lambda env vars use comma-separated strings; both formats must work.

    Validates: Requirements 1.3, 2.3
    """

    import src.config as config_module

    # Comma-separated format — what Lambda env vars use
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://registry.apps.cloud.org.bo,https://admin.cloud.org.bo",
    )
    s = config_module.Settings(_env_file=None)  # type: ignore[call-arg]
    origins = s.allowed_origins_list
    assert len(origins) == 2
    assert "https://registry.apps.cloud.org.bo" in origins
    assert "https://admin.cloud.org.bo" in origins

    # JSON array format also works
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        '["https://registry.apps.cloud.org.bo", "https://admin.cloud.org.bo"]',
    )
    s2 = config_module.Settings(_env_file=None)  # type: ignore[call-arg]
    origins2 = s2.allowed_origins_list
    assert len(origins2) == 2
    assert "https://registry.apps.cloud.org.bo" in origins2
    assert "https://admin.cloud.org.bo" in origins2
