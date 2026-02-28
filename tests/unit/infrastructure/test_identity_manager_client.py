"""Unit tests for IdentityManagerClient — circuit breaker, S2S auth, HTTP calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.domain.exceptions import ExternalServiceError
from src.domain.repositories.circuit_breaker import CircuitBreaker
from src.infrastructure.adapters.identity_manager_client import IdentityManagerClient
from src.infrastructure.adapters.s2s_token_provider import S2STokenProvider


@pytest.fixture
def mock_token_provider() -> AsyncMock:
    provider = AsyncMock(spec=S2STokenProvider)
    provider.get_token.return_value = "s2s-test-token"
    return provider


@pytest.fixture
def mock_circuit_breaker() -> AsyncMock:
    cb = AsyncMock(spec=CircuitBreaker)
    cb.allow_request.return_value = True
    return cb


@pytest.fixture
def client(
    mock_token_provider: AsyncMock,
    mock_circuit_breaker: AsyncMock,
) -> IdentityManagerClient:
    return IdentityManagerClient(
        base_url="https://identity.example.com",
        s2s_token_provider=mock_token_provider,
        circuit_breaker=mock_circuit_breaker,
    )


def _mock_httpx_client(mock_client: AsyncMock) -> AsyncMock:
    """Helper to set up httpx.AsyncClient context manager mock."""
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker wrapping on all methods."""

    @pytest.mark.asyncio
    async def test_raises_service_unavailable_when_circuit_open(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        mock_circuit_breaker.allow_request.return_value = False

        # Act + Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.check_email_exists("test@example.com")

        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"
        assert "temporarily unavailable" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_records_success_on_successful_call(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"exists": True},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            await client.check_email_exists("test@example.com")

        # Assert
        mock_circuit_breaker.record_success.assert_called_once()
        mock_circuit_breaker.record_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_failure_on_connection_error(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.side_effect = httpx.ConnectError("Connection refused")
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError):
                await client.check_email_exists("test@example.com")

        mock_circuit_breaker.record_failure.assert_called_once()
        mock_circuit_breaker.record_success.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_failure_on_external_service_error(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError):
                await client.check_email_exists("test@example.com")

        mock_circuit_breaker.record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_open_blocks_all_methods(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        mock_circuit_breaker.allow_request.return_value = False

        # Act + Assert — all methods should raise SERVICE_UNAVAILABLE
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.create_user("a@b.com", "Test", "Pass123!")
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.register_service("svc", "Svc", "1.0", "icon", "http://h", {}, [])
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get_service_config("svc")
        assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"


class TestCheckEmailExists:
    """Tests for check_email_exists method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_email_exists(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"exists": True},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            result = await client.check_email_exists("exists@example.com")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_email_not_found(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"exists": False},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            result = await client.check_email_exists("new@example.com")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_correct_request(
        self,
        client: IdentityManagerClient,
        mock_token_provider: AsyncMock,
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"exists": False},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            await client.check_email_exists("test@example.com")

        # Assert
        call_kwargs = mock_http.post.call_args
        assert call_kwargs[0][0] == "https://identity.example.com/api/v1/auth/check-email"
        assert call_kwargs[1]["json"] == {"email": "test@example.com"}
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer s2s-test-token"
        assert call_kwargs[1]["timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_raises_on_non_200_status(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            503,
            json={"error": "service unavailable"},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/auth/check-email"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.check_email_exists("test@example.com")

            assert exc_info.value.error_code == "IDENTITY_SERVICE_ERROR"


class TestCreateUser:
    """Tests for create_user method."""

    @pytest.mark.asyncio
    async def test_returns_user_id_on_success(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            201,
            json={"data": {"id": "usr-abc123"}},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/users"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            user_id = await client.create_user("new@example.com", "New User", "Str0ng!Pass")

        # Assert
        assert user_id == "usr-abc123"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            201,
            json={"data": {"id": "usr-xyz"}},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/users"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            await client.create_user("dev@example.com", "Dev User", "P@ss1234")

        # Assert
        call_kwargs = mock_http.post.call_args
        assert call_kwargs[0][0] == "https://identity.example.com/api/v1/users"
        assert call_kwargs[1]["json"] == {
            "email": "dev@example.com",
            "full_name": "Dev User",
            "password": "P@ss1234",
        }
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer s2s-test-token"

    @pytest.mark.asyncio
    async def test_raises_on_non_201_status(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            409,
            json={"error": "conflict"},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/users"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.create_user("dup@example.com", "Dup", "Pass123!")

            assert exc_info.value.error_code == "IDENTITY_SERVICE_ERROR"


class TestRegisterService:
    """Tests for register_service method."""

    @pytest.mark.asyncio
    async def test_completes_on_200(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"status": "registered"},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/services/register"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act — should not raise
            await client.register_service(
                service_id="projects-registry",
                display_name="Projects Registry",
                version="1.0.0",
                nav_icon="folder",
                health_url="https://api.example.com/health",
                config_schema={"max_projects": {"type": "integer"}},
                roles=[{"role": "project_admin", "description": "Admin"}],
            )

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/services/register"),
        )
        schema = {"max_subs": {"type": "integer", "default": 100}}
        roles = [{"role": "mod", "description": "Moderator"}]

        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            await client.register_service(
                service_id="svc-1",
                display_name="Svc One",
                version="2.0",
                nav_icon="star",
                health_url="https://h.example.com/health",
                config_schema=schema,
                roles=roles,
            )

        # Assert
        call_kwargs = mock_http.post.call_args
        assert call_kwargs[0][0] == "https://identity.example.com/api/v1/services/register"
        payload = call_kwargs[1]["json"]
        assert payload["service_id"] == "svc-1"
        assert payload["display_name"] == "Svc One"
        assert payload["version"] == "2.0"
        assert payload["nav_icon"] == "star"
        assert payload["health_url"] == "https://h.example.com/health"
        assert payload["config_schema"] == schema
        assert payload["roles"] == roles
        assert call_kwargs[1]["timeout"] == 10.0

    @pytest.mark.asyncio
    async def test_raises_on_non_200_status(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("POST", "https://identity.example.com/api/v1/services/register"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.register_service("s", "S", "1", "i", "h", {}, [])

            assert exc_info.value.error_code == "IDENTITY_SERVICE_ERROR"


class TestGetServiceConfig:
    """Tests for get_service_config method."""

    @pytest.mark.asyncio
    async def test_returns_config_on_success(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"config": {"max_projects": 50, "approval_required": True}},
            request=httpx.Request(
                "GET", "https://identity.example.com/api/v1/services/svc-1/config"
            ),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.get.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            config = await client.get_service_config("svc-1")

        # Assert
        assert config == {"max_projects": 50, "approval_required": True}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_config_key(
        self, client: IdentityManagerClient
    ) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"status": "ok"},
            request=httpx.Request(
                "GET", "https://identity.example.com/api/v1/services/svc-1/config"
            ),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.get.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            config = await client.get_service_config("svc-1")

        # Assert
        assert config == {}

    @pytest.mark.asyncio
    async def test_sends_correct_request(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            200,
            json={"config": {}},
            request=httpx.Request(
                "GET", "https://identity.example.com/api/v1/services/my-svc/config"
            ),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.get.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act
            await client.get_service_config("my-svc")

        # Assert
        call_kwargs = mock_http.get.call_args
        assert call_kwargs[0][0] == "https://identity.example.com/api/v1/services/my-svc/config"
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer s2s-test-token"
        assert call_kwargs[1]["timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_raises_on_non_200_status(self, client: IdentityManagerClient) -> None:
        # Arrange
        mock_response = httpx.Response(
            404,
            json={"error": "not found"},
            request=httpx.Request("GET", "https://identity.example.com/api/v1/services/bad/config"),
        )
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.get.return_value = mock_response
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.get_service_config("bad")

            assert exc_info.value.error_code == "IDENTITY_SERVICE_ERROR"


class TestUserMessageSafety:
    """Tests that user_message never exposes internal details."""

    @pytest.mark.asyncio
    async def test_circuit_open_message_is_safe(
        self,
        client: IdentityManagerClient,
        mock_circuit_breaker: AsyncMock,
    ) -> None:
        # Arrange
        mock_circuit_breaker.allow_request.return_value = False

        # Act + Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.check_email_exists("test@example.com")

        assert "identity" not in exc_info.value.user_message.lower()
        assert "circuit" not in exc_info.value.user_message.lower()
        assert exc_info.value.user_message != exc_info.value.message

    @pytest.mark.asyncio
    async def test_http_error_message_is_safe(self, client: IdentityManagerClient) -> None:
        # Arrange
        with patch(
            "src.infrastructure.adapters.identity_manager_client.httpx.AsyncClient"
        ) as mock_cls:
            mock_http = _mock_httpx_client(AsyncMock())
            mock_http.post.side_effect = httpx.ConnectError("Connection refused to 10.0.0.1:8080")
            mock_cls.return_value = mock_http

            # Act + Assert
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.create_user("a@b.com", "A", "P1!")

            assert "10.0.0.1" not in exc_info.value.user_message
            assert "Connection refused" not in exc_info.value.user_message
            assert exc_info.value.user_message != exc_info.value.message
