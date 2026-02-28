"""Unit tests for S2STokenProvider — TTL-based caching and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.domain.exceptions import ExternalServiceError
from src.infrastructure.adapters.s2s_token_provider import S2STokenProvider


@pytest.fixture
def provider() -> S2STokenProvider:
    return S2STokenProvider(
        token_url="https://cognito.example.com/oauth2/token",
        client_id="test-client-id",
        client_secret="test-client-secret",
    )


class TestGetToken:
    """Tests for get_token — caching and refresh logic."""

    @pytest.mark.asyncio
    async def test_fetches_token_on_first_call(self, provider: S2STokenProvider) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"access_token": "tok-abc", "expires_in": 3600},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act
            token = await provider.get_token()

        # Assert
        assert token == "tok-abc"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_cached_token_when_not_expired(self, provider: S2STokenProvider) -> None:
        # Arrange — seed the cache
        mock_response = httpx.Response(
            200,
            json={"access_token": "tok-cached", "expires_in": 3600},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await provider.get_token()

            # Act — second call should use cache
            token = await provider.get_token()

        # Assert — post called only once (first call)
        assert token == "tok-cached"
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_refreshes_token_when_within_60s_of_expiry(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange — seed cache with token expiring in 30s
        import time

        mock_response_1 = httpx.Response(
            200,
            json={"access_token": "tok-old", "expires_in": 3600},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        mock_response_2 = httpx.Response(
            200,
            json={"access_token": "tok-new", "expires_in": 3600},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )

        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [mock_response_1, mock_response_2]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await provider.get_token()

            # Simulate token about to expire (within 60s window)
            provider._expires_at = time.time() + 30

            # Act
            token = await provider.get_token()

        # Assert — should have refreshed
        assert token == "tok-new"
        assert mock_client.post.call_count == 2


class TestRefreshTokenErrors:
    """Tests for _refresh_token error handling."""

    @pytest.mark.asyncio
    async def test_raises_external_service_error_on_http_error(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            401,
            json={"error": "invalid_client"},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await provider.get_token()

            assert exc_info.value.error_code == "S2S_TOKEN_ERROR"
            assert "temporarily unavailable" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_raises_external_service_error_on_connection_error(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await provider.get_token()

            assert exc_info.value.error_code == "S2S_TOKEN_ERROR"

    @pytest.mark.asyncio
    async def test_raises_external_service_error_on_missing_access_token(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange — response missing access_token key
        mock_response = httpx.Response(
            200,
            json={"token_type": "Bearer"},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await provider.get_token()

            assert exc_info.value.error_code == "S2S_TOKEN_ERROR"

    @pytest.mark.asyncio
    async def test_sends_correct_client_credentials_payload(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"access_token": "tok-123", "expires_in": 3600},
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act
            await provider.get_token()

        # Assert — verify the POST payload
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://cognito.example.com/oauth2/token"
        assert call_kwargs[1]["data"] == {
            "grant_type": "client_credentials",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
        }
        assert call_kwargs[1]["timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_user_message_never_exposes_internal_details(
        self, provider: S2STokenProvider
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://cognito.example.com/oauth2/token"),
        )
        with patch("src.infrastructure.adapters.s2s_token_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await provider.get_token()

            # user_message must not contain HTTP status, URL, or internal details
            assert "500" not in exc_info.value.user_message
            assert "cognito" not in exc_info.value.user_message.lower()
            assert exc_info.value.user_message != exc_info.value.message
