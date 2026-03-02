"""Property 16: Input length validation.

Validates: Requirements 13.3, 13.4
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.project_commands import CreateProjectCommand
from src.application.services.project_service import ProjectService
from src.domain.exceptions import ValidationError
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository


def _make_service() -> ProjectService:
    return ProjectService(
        project_repo=AsyncMock(spec=ProjectRepository),
        subscription_repo=AsyncMock(spec=SubscriptionRepository),
        event_publisher=AsyncMock(spec=EventPublisher),
    )


@given(name=st.text(min_size=201, max_size=500))
@settings(max_examples=50)
def test_project_name_too_long_raises_validation_error(name: str) -> None:
    """Project names > 200 chars should raise ValidationError."""
    service = _make_service()
    cmd = CreateProjectCommand(
        name=name,
        description="Valid description",
        category="tech",
        start_date="2025-01-01",
        end_date="2025-12-31",
        max_participants=10,
        notification_emails=[],
        created_by="user1",
    )

    async def run() -> None:
        with pytest.raises(ValidationError):
            await service.create(cmd)

    asyncio.run(run())


@given(suffix=st.text(min_size=1, max_size=100))
@settings(max_examples=50)
def test_project_description_too_long_raises_validation_error(suffix: str) -> None:
    """Project descriptions > 5000 chars should raise ValidationError."""
    # Build a description that is always > 5000 chars by padding a fixed base
    description = "x" * 5000 + suffix
    assert len(description) > 5000  # sanity check
    service = _make_service()
    cmd = CreateProjectCommand(
        name="Valid Name",
        description=description,
        category="tech",
        start_date="2025-01-01",
        end_date="2025-12-31",
        max_participants=10,
        notification_emails=[],
        created_by="user1",
    )

    async def run() -> None:
        with pytest.raises(ValidationError):
            await service.create(cmd)

    asyncio.run(run())
