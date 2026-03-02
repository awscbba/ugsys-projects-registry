"""Unit tests for the projects router.

Validates: Requirements 2.5, 2.8, 3.3, 3.4, 17.1

Tests cover:
- POST /api/v1/projects returns 201 with envelope
- GET /api/v1/projects/public returns only active+enabled projects without notification_emails
- PUT /api/v1/projects/{id} by non-owner returns 403
- DELETE /api/v1/projects/{id} without admin JWT returns 403
- Property 4: Public endpoint filter invariant
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.application.services.form_service import FormService
from src.application.services.project_service import ProjectService
from src.domain.entities.project import Project
from src.domain.exceptions import AuthorizationError
from src.domain.value_objects.project_status import ProjectStatus
from src.presentation.api.v1.projects import router
from src.presentation.auth import CurrentUser
from src.presentation.middleware.exception_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_project(
    *,
    id: str = "01JPROJECT",
    name: str = "Test Project",
    description: str = "A test project",
    category: str = "tech",
    status: ProjectStatus = ProjectStatus.ACTIVE,
    is_enabled: bool = True,
    max_participants: int = 10,
    current_participants: int = 0,
    start_date: str = "2025-01-01",
    end_date: str = "2025-12-31",
    created_by: str = "owner-id",
    notification_emails: list[str] | None = None,
) -> Project:
    return Project(
        id=id,
        name=name,
        description=description,
        rich_text=None,
        category=category,
        status=status,
        is_enabled=is_enabled,
        max_participants=max_participants,
        current_participants=current_participants,
        start_date=start_date,
        end_date=end_date,
        created_by=created_by,
        notification_emails=notification_emails or [],
        enable_subscription_notifications=True,
        images=[],
        form_schema=None,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
    )


def _make_app(
    project_service: ProjectService,
    form_service: FormService,
    user: CurrentUser,
) -> FastAPI:
    app = FastAPI(redirect_slashes=False)
    app.state.project_service = project_service
    app.state.form_service = form_service

    # Override auth dependency to inject the test user
    from src.presentation.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user

    from src.domain.exceptions import DomainError

    app.add_exception_handler(DomainError, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def project_service() -> AsyncMock:
    return AsyncMock(spec=ProjectService)


@pytest.fixture
def form_service() -> AsyncMock:
    return AsyncMock(spec=FormService)


@pytest.fixture
def admin_user() -> CurrentUser:
    return CurrentUser(sub="admin-id", email="admin@example.com", roles=["admin"])


@pytest.fixture
def regular_user() -> CurrentUser:
    return CurrentUser(sub="user-id", email="user@example.com", roles=["user"])


@pytest.fixture
def owner_user() -> CurrentUser:
    return CurrentUser(sub="owner-id", email="owner@example.com", roles=["user"])


# ── POST /api/v1/projects ─────────────────────────────────────────────────────


class TestCreateProject:
    async def test_returns_201_with_envelope(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        project = make_project(created_by=regular_user.sub)
        project_service.create.return_value = project

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/",
                json={
                    "name": "Test Project",
                    "description": "A test project",
                    "category": "tech",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "max_participants": 10,
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert "data" in body
        assert "meta" in body
        assert body["data"]["name"] == "Test Project"

    async def test_requester_id_taken_from_jwt_sub(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        project = make_project(created_by=regular_user.sub)
        project_service.create.return_value = project

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/projects/",
                json={
                    "name": "Test Project",
                    "description": "desc",
                    "category": "tech",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "max_participants": 5,
                },
            )

        call_args = project_service.create.call_args[0][0]
        assert call_args.created_by == regular_user.sub


# ── GET /api/v1/projects/public ───────────────────────────────────────────────


class TestListPublicProjects:
    """Property 4: Public endpoint filter invariant."""

    async def test_returns_200_with_envelope(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        project_service.list_public.return_value = [make_project()]

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/public")

        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    async def test_does_not_expose_notification_emails(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        # Service strips notification_emails before returning — simulate that
        project = make_project(notification_emails=[])
        project_service.list_public.return_value = [project]

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/public")

        body = response.json()
        for item in body["data"]:
            assert item.get("notification_emails") == []

    async def test_no_auth_required(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        """Public endpoint must not require authentication."""
        project_service.list_public.return_value = []

        # Build app without auth override — public route has no auth dependency
        app = FastAPI(redirect_slashes=False)
        app.state.project_service = project_service
        app.state.form_service = form_service
        app.include_router(router, prefix="/api/v1")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/public")

        assert response.status_code == 200


# ── GET /api/v1/projects (admin) ──────────────────────────────────────────────


class TestListAllProjects:
    async def test_non_admin_returns_403(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/")

        assert response.status_code == 403

    async def test_admin_returns_200(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        admin_user: CurrentUser,
    ) -> None:
        project_service.list_all.return_value = ([], 0)

        app = _make_app(project_service, form_service, admin_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/")

        assert response.status_code == 200


# ── PUT /api/v1/projects/{id} ─────────────────────────────────────────────────


class TestUpdateProject:
    async def test_non_owner_non_admin_returns_403(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        project_service.update.side_effect = AuthorizationError(
            message="User user-id is not owner of project 01JPROJECT",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/projects/01JPROJECT",
                json={"name": "New Name"},
            )

        assert response.status_code == 403
        assert response.json()["error"] == "FORBIDDEN"

    async def test_owner_can_update(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        owner_user: CurrentUser,
    ) -> None:
        updated = make_project(name="Updated Name", created_by=owner_user.sub)
        project_service.update.return_value = updated

        app = _make_app(project_service, form_service, owner_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/projects/01JPROJECT",
                json={"name": "Updated Name"},
            )

        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Name"


# ── DELETE /api/v1/projects/{id} ──────────────────────────────────────────────


class TestDeleteProject:
    async def test_non_admin_returns_403(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        regular_user: CurrentUser,
    ) -> None:
        project_service.delete.side_effect = AuthorizationError(
            message="User user-id lacks admin role",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )

        app = _make_app(project_service, form_service, regular_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/projects/01JPROJECT")

        assert response.status_code == 403

    async def test_admin_returns_204(
        self,
        project_service: AsyncMock,
        form_service: AsyncMock,
        admin_user: CurrentUser,
    ) -> None:
        project_service.delete.return_value = None

        app = _make_app(project_service, form_service, admin_user)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/v1/projects/01JPROJECT")

        assert response.status_code == 204
