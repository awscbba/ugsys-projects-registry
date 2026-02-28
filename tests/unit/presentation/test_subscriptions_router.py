"""Unit tests for the subscriptions router.

Validates: Requirements 4.7, 12.6, 17.1

Tests cover:
- POST /api/v1/projects/{id}/subscriptions returns 201 with envelope
- GET /api/v1/subscriptions/person/{person_id} by different user returns 403
- DELETE /api/v1/projects/{id}/subscribers/{sub_id} by non-owner returns 403
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.application.services.subscription_service import SubscriptionService
from src.domain.entities.subscription import Subscription
from src.domain.exceptions import AuthorizationError
from src.domain.value_objects.project_status import SubscriptionStatus
from src.presentation.api.v1.subscriptions import router
from src.presentation.auth import CurrentUser
from src.presentation.middleware.exception_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_subscription(
    *,
    id: str = "01JSUB",
    project_id: str = "01JPROJECT",
    person_id: str = "user-id",
    status: SubscriptionStatus = SubscriptionStatus.PENDING,
) -> Subscription:
    return Subscription(
        id=id,
        project_id=project_id,
        person_id=person_id,
        status=status,
        notes="",
        subscription_date="2025-01-01T00:00:00Z",
        is_active=True,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
    )


def _make_app(service: SubscriptionService, user: CurrentUser) -> FastAPI:
    app = FastAPI()
    app.state.subscription_service = service

    from src.presentation.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    from src.domain.exceptions import DomainError

    app.add_exception_handler(DomainError, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def sub_service() -> AsyncMock:
    return AsyncMock(spec=SubscriptionService)


@pytest.fixture
def regular_user() -> CurrentUser:
    return CurrentUser(sub="user-id", email="user@example.com", roles=["user"])


@pytest.fixture
def other_user() -> CurrentUser:
    return CurrentUser(sub="other-id", email="other@example.com", roles=["user"])


@pytest.fixture
def admin_user() -> CurrentUser:
    return CurrentUser(sub="admin-id", email="admin@example.com", roles=["admin"])


# ── POST /api/v1/projects/{id}/subscriptions ──────────────────────────────────


class TestSubscribe:
    async def test_returns_201_with_envelope(
        self, sub_service: AsyncMock, regular_user: CurrentUser
    ) -> None:
        sub_service.subscribe.return_value = make_subscription(person_id=regular_user.sub)

        app = _make_app(sub_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/01JPROJECT/subscriptions",
                json={},
            )

        assert response.status_code == 201
        body = response.json()
        assert "data" in body
        assert "meta" in body
        assert body["data"]["project_id"] == "01JPROJECT"

    async def test_person_id_taken_from_jwt_sub(
        self, sub_service: AsyncMock, regular_user: CurrentUser
    ) -> None:
        sub_service.subscribe.return_value = make_subscription(person_id=regular_user.sub)

        app = _make_app(sub_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/projects/01JPROJECT/subscriptions", json={})

        call_args = sub_service.subscribe.call_args[0][0]
        assert call_args.person_id == regular_user.sub


# ── GET /api/v1/subscriptions/person/{person_id} ─────────────────────────────


class TestListPersonSubscriptions:
    async def test_different_user_returns_403(
        self, sub_service: AsyncMock, other_user: CurrentUser
    ) -> None:
        sub_service.list_by_person.side_effect = AuthorizationError(
            message="User other-id attempted IDOR on user-id subscriptions",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )

        app = _make_app(sub_service, other_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subscriptions/person/user-id")

        assert response.status_code == 403
        assert response.json()["error"] == "FORBIDDEN"

    async def test_own_subscriptions_returns_200(
        self, sub_service: AsyncMock, regular_user: CurrentUser
    ) -> None:
        sub_service.list_by_person.return_value = [make_subscription()]

        app = _make_app(sub_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/subscriptions/person/{regular_user.sub}")

        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    async def test_admin_can_view_any_person_subscriptions(
        self, sub_service: AsyncMock, admin_user: CurrentUser
    ) -> None:
        sub_service.list_by_person.return_value = [make_subscription()]

        app = _make_app(sub_service, admin_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/subscriptions/person/user-id")

        assert response.status_code == 200


# ── DELETE /api/v1/projects/{id}/subscribers/{sub_id} ────────────────────────


class TestCancelSubscription:
    async def test_non_owner_returns_403(
        self, sub_service: AsyncMock, other_user: CurrentUser
    ) -> None:
        sub_service.cancel.side_effect = AuthorizationError(
            message="User other-id is not owner of subscription 01JSUB",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )

        app = _make_app(sub_service, other_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/projects/01JPROJECT/subscribers/01JSUB")

        assert response.status_code == 403
        assert response.json()["error"] == "FORBIDDEN"

    async def test_owner_returns_204(
        self, sub_service: AsyncMock, regular_user: CurrentUser
    ) -> None:
        sub_service.cancel.return_value = None

        app = _make_app(sub_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/projects/01JPROJECT/subscribers/01JSUB")

        assert response.status_code == 204

    async def test_admin_can_cancel_any_subscription(
        self, sub_service: AsyncMock, admin_user: CurrentUser
    ) -> None:
        sub_service.cancel.return_value = None

        app = _make_app(sub_service, admin_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/projects/01JPROJECT/subscribers/01JSUB")

        assert response.status_code == 204


# ── GET /api/v1/projects/{id}/subscriptions (moderator) ──────────────────────


class TestListProjectSubscriptions:
    async def test_non_moderator_returns_403(
        self, sub_service: AsyncMock, regular_user: CurrentUser
    ) -> None:
        app = _make_app(sub_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/01JPROJECT/subscriptions")

        assert response.status_code == 403

    async def test_admin_returns_200(self, sub_service: AsyncMock, admin_user: CurrentUser) -> None:
        sub_service.list_by_project.return_value = ([], 0)

        app = _make_app(sub_service, admin_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/01JPROJECT/subscriptions")

        assert response.status_code == 200
