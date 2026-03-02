"""S2S token provider — caches service-to-service JWT with TTL-based refresh.

Fetches tokens via OAuth2 client_credentials grant from the Cognito token
endpoint. The token is cached in memory and refreshed 60 seconds before expiry.
"""

from __future__ import annotations

import time

import httpx
import structlog

from src.domain.exceptions import ExternalServiceError

logger = structlog.get_logger()


class S2STokenProvider:
    """Provides cached service-to-service bearer tokens."""

    def __init__(self, token_url: str, client_id: str, client_secret: str) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._cached_token: str | None = None
        self._expires_at: float = 0.0

    async def get_token(self) -> str:
        """Return a valid S2S token, refreshing if within 60s of expiry."""
        if self._cached_token and time.time() < self._expires_at - 60:
            return self._cached_token
        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        """Fetch a new token via client_credentials grant."""
        logger.info("s2s_token.refresh_started", token_url=self._token_url)
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    timeout=5.0,
                )
            resp.raise_for_status()
            data = resp.json()
            self._cached_token = data["access_token"]
            self._expires_at = time.time() + data["expires_in"]
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "s2s_token.refresh_completed",
                expires_in=data["expires_in"],
                duration_ms=duration_ms,
            )
            return self._cached_token
        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "s2s_token.refresh_failed",
                status_code=e.response.status_code,
                duration_ms=duration_ms,
            )
            raise ExternalServiceError(
                message=f"S2S token refresh failed: HTTP {e.response.status_code}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="S2S_TOKEN_ERROR",
            ) from e
        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "s2s_token.refresh_failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            raise ExternalServiceError(
                message=f"S2S token refresh request failed: {e}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="S2S_TOKEN_ERROR",
            ) from e
        except (KeyError, ValueError) as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "s2s_token.invalid_response",
                error=str(e),
                duration_ms=duration_ms,
            )
            raise ExternalServiceError(
                message=f"S2S token response missing required fields: {e}",
                user_message="Service temporarily unavailable, please try again later",
                error_code="S2S_TOKEN_ERROR",
            ) from e
