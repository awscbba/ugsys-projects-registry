"""Integration test — RS256 enforcement: HS256 and 'none' tokens must be rejected.

Validates: Requirement 1.3, 12.5 (security.md RS256-only enforcement)
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import jwt
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from ugsys_auth_client import TokenValidator
from ugsys_auth_client.auth_middleware import AuthMiddleware

from src.application.services.form_service import FormService
from src.application.services.project_service import ProjectService
from src.domain.exceptions import DomainError
from src.presentation.api.v1.projects import router
from src.presentation.middleware.exception_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)

_HS256_SECRET = "test-secret-key"


def _make_hs256_token(sub: str = "user-123", roles: list[str] | None = None) -> str:
    """Create an HS256-signed token (should be rejected by RS256 validator)."""
    payload = {
        "sub": sub,
        "email": "test@example.com",
        "roles": roles or [],
        "iat": 9999999999,
        "exp": 9999999999,
        "type": "access",
    }
    return jwt.encode(payload, _HS256_SECRET, algorithm="HS256")


def _make_app_with_rs256_validator() -> FastAPI:
    """Build a minimal app with RS256 TokenValidator wired as AuthMiddleware."""
    validator = TokenValidator(jwt_algorithm="RS256")  # no jwks_url → RS256 mode, rejects HS256

    app = FastAPI(redirect_slashes=False)
    app.state.token_validator = validator

    app.add_middleware(AuthMiddleware, validator=validator)

    project_service = AsyncMock(spec=ProjectService)
    form_service = AsyncMock(spec=FormService)
    app.state.project_service = project_service
    app.state.form_service = form_service

    app.add_exception_handler(DomainError, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(router, prefix="/api/v1")
    return app


class TestRS256AlgorithmEnforcement:
    """RS256 is the only accepted algorithm — HS256 and 'none' must be rejected."""

    async def test_hs256_token_rejected_with_401(self) -> None:
        """HS256-signed token must result in 401 on a protected endpoint."""
        app = _make_app_with_rs256_validator()
        hs256_token = _make_hs256_token(roles=["admin"])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects/",
                headers={"Authorization": f"Bearer {hs256_token}"},
            )

        assert response.status_code == 401

    async def test_no_token_rejected_with_401(self) -> None:
        """Missing Authorization header must result in 401 on a protected endpoint."""
        app = _make_app_with_rs256_validator()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/")

        assert response.status_code == 401

    async def test_public_endpoint_accessible_without_token(self) -> None:
        """Public endpoint must remain accessible without any token."""
        app = _make_app_with_rs256_validator()
        app.state.project_service.list_public = AsyncMock(return_value=[])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/public")

        assert response.status_code == 200

    async def test_token_validator_rejects_hs256_directly(self) -> None:
        """TokenValidator.validate() returns None for HS256 token in RS256 mode."""
        validator = TokenValidator(jwt_algorithm="RS256")
        hs256_token = _make_hs256_token()
        result = validator.validate(hs256_token)
        assert result is None

    async def test_token_validator_rejects_none_algorithm(self) -> None:
        """TokenValidator.validate() returns None for 'none' algorithm token."""
        validator = TokenValidator(jwt_algorithm="RS256")
        # Craft a token with alg=none manually (PyJWT refuses to sign with none)
        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            .rstrip(b"=")
            .decode()
        )
        payload_b64 = (
            base64.urlsafe_b64encode(json.dumps({"sub": "x", "exp": 9999999999, "iat": 1}).encode())
            .rstrip(b"=")
            .decode()
        )
        none_token = f"{header}.{payload_b64}."
        result = validator.validate(none_token)
        assert result is None
