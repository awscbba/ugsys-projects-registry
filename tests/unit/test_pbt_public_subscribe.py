"""Property 13: Public subscription always pending.

Validates: Requirements 7.7
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.public_commands import PublicSubscribeCommand
from src.application.services.public_service import PublicService
from src.domain.entities.project import Project
from src.domain.repositories.event_publisher import EventPublisher
from src.domain.repositories.identity_client import IdentityClient
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus


@given(
    person_id=st.text(min_size=1, max_size=50),
    project_id=st.text(
        min_size=26,
        max_size=26,
        alphabet="0123456789ABCDEFGHJKMNPQRSTVWXYZ",
    ),
    email=st.emails(),
    first_name=st.text(min_size=1, max_size=50),
    last_name=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100)
def test_public_subscribe_always_pending(
    person_id: str,
    project_id: str,
    email: str,
    first_name: str,
    last_name: str,
) -> None:
    """Property 13: Public subscriptions always have status=pending."""
    project = Project(
        id=project_id,
        name="Test",
        description="Test",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        created_by="admin",
        current_participants=0,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )

    identity_client = AsyncMock(spec=IdentityClient)
    identity_client.check_email_exists.return_value = False
    identity_client.create_user.return_value = person_id

    saved_subs: list = []

    async def capture_save(sub):  # type: ignore[no-untyped-def]
        saved_subs.append(sub)
        return sub

    subscription_repo = AsyncMock(spec=SubscriptionRepository)
    subscription_repo.find_by_person_and_project.return_value = None
    subscription_repo.save.side_effect = capture_save

    project_repo = AsyncMock(spec=ProjectRepository)
    project_repo.find_by_id.return_value = project

    event_publisher = AsyncMock(spec=EventPublisher)

    service = PublicService(
        identity_client=identity_client,
        subscription_repo=subscription_repo,
        project_repo=project_repo,
        event_publisher=event_publisher,
    )

    cmd = PublicSubscribeCommand(
        project_id=project_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        notes=None,
    )

    asyncio.run(service.subscribe(cmd))

    assert len(saved_subs) == 1
    assert saved_subs[0].status == SubscriptionStatus.PENDING, (
        f"Expected PENDING, got {saved_subs[0].status}"
    )
