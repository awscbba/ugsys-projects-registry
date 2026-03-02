"""Identity Manager HTTP client with circuit breaker protection.

Implements the IdentityClient port using httpx for HTTP calls to
ugsys-identity-manager. Every call is wrapped with circuit breaker
logic and authenticated via S2S bearer token.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast

import httpx
import structlog

from src.domain.exceptions import ExternalServiceError
from src.domain.repositories.circuit_breaker import CircuitBreaker
from src.domain.repositories.identity_client import IdentityClient
from src.infrastructure.adapters.s2s_token_provider import S2STokenProvider

logger = structlog.get_logger()

T = TypeVar("T")


class IdentityManagerClient(IdentityClient):
    """Concrete HTTP client for Identity Manager with circuit breaker."""

    def __init__(
        self,
        base_url: str,
        s2s_token_provider: S2STokenProvider,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self._base_url = base_url
        self._token_provider = s2s_token_provider
        self._cb = circuit_breaker

    def _get_trace_header(self) -> dict[str, str]:
        """Get X-Ray trace header for outbound propagation."""
        try:
            from aws_xray_sdk.core import xray_recorder

            segment = xray_recorder.current_segment()
            if segment is not None:
                return {"X-Amzn-Trace-Id": f"Root={segment.trace_id};Sampled=1"}
        except Exception as exc:
            logger.debug("identity_client.trace_header_unavailable", error=str(exc))
        return {}

    async def _call_with_circuit_breaker(
        self,
        operation: str,
        coro_factory: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Wrap an HTTP call with circuit breaker logic.

        Checks allow_request() before the call, records success/failure after.
        Raises ExternalServiceError(SERVICE_UNAVAILABLE) when circuit is open.
        """
        if not self._cb.allow_request():
            logger.warning("identity_client.circuit_open", operation=operation)
            raise ExternalServiceError(
                message=f"Identity Manager circuit breaker is open for {operation}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="SERVICE_UNAVAILABLE",
            )
        start = time.perf_counter()
        try:
            result = await coro_factory()
            self._cb.record_success()
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                f"identity_client.{operation}.completed",
                duration_ms=duration_ms,
            )
            return result
        except ExternalServiceError:
            self._cb.record_failure()
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                f"identity_client.{operation}.failed",
                duration_ms=duration_ms,
            )
            raise
        except Exception as e:
            self._cb.record_failure()
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                f"identity_client.{operation}.failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            raise ExternalServiceError(
                message=f"Identity Manager {operation} failed: {e}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="EXTERNAL_SERVICE_ERROR",
            ) from e

    async def check_email_exists(self, email: str) -> bool:
        """Check if an email is registered in Identity Manager."""

        async def _call() -> bool:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/auth/check-email",
                    json={"email": email},
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=5.0,
                )
            if resp.status_code == 200:
                return cast(bool, resp.json().get("exists", False))
            raise ExternalServiceError(
                message=f"Identity Manager check-email returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        return await self._call_with_circuit_breaker("check_email_exists", _call)

    async def create_user(self, email: str, full_name: str, password: str) -> str:
        """Create a user in Identity Manager. Returns the new user_id."""

        async def _call() -> str:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/users",
                    json={
                        "email": email,
                        "full_name": full_name,
                        "password": password,
                    },
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=5.0,
                )
            if resp.status_code == 201:
                return cast(str, resp.json()["data"]["id"])
            raise ExternalServiceError(
                message=f"Identity Manager create-user returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        return await self._call_with_circuit_breaker("create_user", _call)

    async def register_service(
        self,
        service_id: str,
        display_name: str,
        version: str,
        nav_icon: str,
        health_url: str,
        config_schema: dict[str, Any],
        roles: list[dict[str, str]],
    ) -> None:
        """Register this service with Identity Manager."""

        async def _call() -> None:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/services/register",
                    json={
                        "service_id": service_id,
                        "display_name": display_name,
                        "version": version,
                        "nav_icon": nav_icon,
                        "health_url": health_url,
                        "roles": roles,
                        "config_schema": config_schema,
                    },
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=10.0,
                )
            if resp.status_code == 200:
                return
            raise ExternalServiceError(
                message=f"Identity Manager register-service returned {resp.status_code}",
                user_message="Service registration failed",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        await self._call_with_circuit_breaker("register_service", _call)

    async def get_service_config(self, service_id: str) -> dict[str, Any]:
        """Fetch operator config for this service from Identity Manager."""

        async def _call() -> dict[str, Any]:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/services/{service_id}/config",
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=5.0,
                )
            if resp.status_code == 200:
                return cast(dict[str, Any], resp.json().get("config", {}))
            raise ExternalServiceError(
                message=f"Identity Manager get-service-config returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        return await self._call_with_circuit_breaker("get_service_config", _call)

    async def list_users(self, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        """List users with pagination. Returns (users, total)."""

        async def _call() -> tuple[list[dict[str, Any]], int]:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/users",
                    params={"page": page, "page_size": page_size},
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=10.0,
                )
            if resp.status_code == 200:
                body = resp.json()
                users: list[dict[str, Any]] = cast(list[dict[str, Any]], body.get("data", []))
                total: int = cast(int, body.get("meta", {}).get("total", len(users)))
                return users, total
            raise ExternalServiceError(
                message=f"Identity Manager list-users returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        return await self._call_with_circuit_breaker("list_users", _call)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user in Identity Manager."""

        async def _call() -> None:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self._base_url}/api/v1/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=5.0,
                )
            if resp.status_code in (200, 204):
                return
            raise ExternalServiceError(
                message=f"Identity Manager delete-user returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        await self._call_with_circuit_breaker("delete_user", _call)

    async def deactivate_user(self, user_id: str) -> None:
        """Deactivate a user in Identity Manager."""

        async def _call() -> None:
            token = await self._token_provider.get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"{self._base_url}/api/v1/users/{user_id}",
                    json={"is_active": False},
                    headers={"Authorization": f"Bearer {token}", **self._get_trace_header()},
                    timeout=5.0,
                )
            if resp.status_code in (200, 204):
                return
            raise ExternalServiceError(
                message=f"Identity Manager deactivate-user returned {resp.status_code}",
                user_message="An unexpected error occurred",
                error_code="IDENTITY_SERVICE_ERROR",
            )

        await self._call_with_circuit_breaker("deactivate_user", _call)
